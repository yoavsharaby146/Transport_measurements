"""Self-check / benchmark for the ICE live-plot slowdown diagnosis.

Demonstrates the root cause: pymeasure's Results.data (called by
ResultsCurve.update_data on every 0.2 s plot refresh) costs O(total rows)
per poll, so per-poll time grows as the map accumulates points. The
incremental parser used by the patched update_data is O(new rows).

Run: python _speed_check.py
"""
import os
import tempfile
import time

import numpy as np
import pandas as pd

from pymeasure.experiment import Procedure
from pymeasure.experiment.results import Results


class _Dummy(Procedure):
    DATA_COLUMNS = [f'col_{i}(u)' for i in range(20)]


def incremental_parse(path, pos, x_idx, y_idx, ncols):
    """The parse used by the patched ResultsCurve.update_data."""
    with open(path, 'rb') as f:
        f.seek(pos)
        chunk = f.read()
    end = chunk.rfind(b'\n')
    if end < 0:
        return pos, None, None
    xs, ys = [], []
    for line in chunk[:end].decode('utf-8', errors='replace').splitlines():
        if not line or line.startswith('#'):
            continue
        parts = line.split(',')
        if len(parts) != ncols:
            continue
        xs.append(float(parts[x_idx]))
        ys.append(float(parts[y_idx]))
    return pos + end + 1, np.asarray(xs), np.asarray(ys)


def make_file(path, n_rows, start_row=0):
    with open(path, 'a', encoding='utf-8') as f:
        for i in range(start_row, start_row + n_rows):
            f.write(','.join(f'{i * 0.001:.6f}' for _ in range(20)) + '\n')


def main():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'data.csv')
    x_idx, y_idx = 0, 1

    print(f"{'rows':>8} | {'Results.data poll (ms)':>24} | {'patched parse (ms)':>20}")
    print('-' * 62)
    for n in (10_000, 50_000, 150_000, 300_000):
        if os.path.exists(path):
            os.remove(path)
        proc = _Dummy()
        results = Results(proc, path)   # writes header
        make_file(path, n)
        results.data                     # initial full load
        make_file(path, 5)               # 5 new rows arrive (a poll's worth)

        t0 = time.perf_counter()
        data = results.data              # one poll the OLD way
        t_old = (time.perf_counter() - t0) * 1e3

        # patched way: parse only the 5 new rows
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
        # find byte offset after row n (all rows same length)
        line_len = len(','.join(['0.000'] * 20)) + 1  # not exact; recompute below
        with open(path, 'rb') as f:
            head = f.read(1 << 20)
        # locate end of the n-th data row by counting newlines
        pos = 0
        count = 0
        header_newlines = sum(1 for _ in open(path, encoding='utf-8')) - n - 5
        with open(path, 'rb') as f:
            raw = f.read()
        idx = -1
        for _ in range(header_newlines + n):
            idx = raw.index(b'\n', idx + 1)
        pos = idx + 1

        t0 = time.perf_counter()
        _, xs, ys = incremental_parse(path, pos, x_idx, y_idx, 20)
        t_new = (time.perf_counter() - t0) * 1e3

        # correctness: patched parse matches pandas values for the new rows
        ref = data  # includes the 5 new rows
        np.testing.assert_allclose(xs, ref[_Dummy.DATA_COLUMNS[x_idx]].to_numpy()[n:], rtol=1e-9)
        np.testing.assert_allclose(ys, ref[_Dummy.DATA_COLUMNS[y_idx]].to_numpy()[n:], rtol=1e-9)

        print(f"{n:>8} | {t_old:>24.1f} | {t_new:>20.3f}")

    print("\nExpected: 'Results.data poll' grows linearly with rows (the bug),")
    print("'patched parse' stays flat regardless of accumulated rows.")
    print("OK — patched parser matches pandas values")


if __name__ == '__main__':
    main()
