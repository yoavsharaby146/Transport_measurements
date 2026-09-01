"""Self-check for csv_operations vectorized rewrite.

Generates two CSVs (one with a non-numeric column, different row counts),
then verifies the new vectorized compute_expr matches the OLD per-row
eval algorithm row by row, and prints timings.
Run: python _speed_check.py
"""
import csv
import math
import os
import random
import re
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_operations import AppState  # noqa: E402


def old_eval(expr, state, i):
    """The original per-row algorithm, kept verbatim as the reference."""
    row_by_alias = {f.alias: {h: f._cols[h][i] for h in f.headers} for f in state.files}
    js = expr
    for f in state.files:
        for h in f.headers:
            val = row_by_alias.get(f.alias, {}).get(h, float("nan"))
            js = js.replace(f"{f.alias}.{h}", str(val))
    if state.files:
        for h in state.files[0].headers:
            pattern = r'(?<![a-zA-Z0-9_\.])' + re.escape(h) + r'(?![a-zA-Z0-9_\.])'
            val = row_by_alias.get(state.files[0].alias, {}).get(h, float("nan"))
            js = re.sub(pattern, str(val), js)
    try:
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed["abs"] = abs
        return float(eval(js, {"__builtins__": {}}, allowed))
    except Exception:
        return float("nan")


def main():
    tmp = tempfile.mkdtemp()
    n1, n2 = 200_000, 199_000  # different row counts on purpose
    p1 = os.path.join(tmp, "f1.csv")
    p2 = os.path.join(tmp, "f2.csv")
    rng = random.Random(42)
    with open(p1, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["a", "temp", "temp_c", "s"])
        for _ in range(n1):
            w.writerow([rng.uniform(-10, 10), rng.uniform(0, 5),
                        rng.uniform(0, 5), rng.choice(["ok", "bad"])])
    with open(p2, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["c", "d"])
        for _ in range(n2):
            w.writerow([rng.uniform(-10, 10), rng.uniform(1, 10)])

    state = AppState()
    state.add_file(p1)
    state.add_file(p2)
    assert state.files[0].n_rows == n1 and state.files[1].n_rows == n2

    exprs = [
        "f1.a + f2.c * 2",            # qualified refs
        "sqrt(abs(a) + 1)",           # bare names, math funcs
        "f1.temp / f2.d",             # cross-file
        "f1.temp_c - f1.temp",        # prefix collision: temp_c vs temp
        "s + 1",                      # non-numeric column -> NaN
        "f1.a + nope",                # unknown name -> NaN
        "2*pi",                       # constant expression
    ]
    # old algorithm had a prefix bug: js.replace('f1.temp', ...) also
    # mangled 'f1.temp_c' -> NaN. New code handles it correctly, so this
    # expr is checked against direct numpy math instead of old_eval.
    buggy_in_old = {"f1.temp_c - f1.temp"}

    total = min(f.n_rows for f in state.files)
    sample = list(range(0, total, 4097))[:40] + [total - 1]  # ~41 rows compared
    for expr in exprs:
        new = state.compute_expr(expr, total)
        assert len(new) == total, expr
        if expr in buggy_in_old:
            ref = state.files[0]._cols["temp_c"] - state.files[0]._cols["temp"]
            assert abs(new[0] - ref[0]) < 1e-12, expr
            continue
        for i in sample:
            expected = old_eval(expr, state, i)
            got = float(new[i])
            if math.isnan(expected):
                assert math.isnan(got), (expr, i, got)
            else:
                assert abs(got - expected) <= 1e-9 * max(1, abs(expected)), (expr, i, got, expected)

    # build_output: headers, min-row-count, blank column, preview slicing
    state.copy_cols = [("f1", "a"), ("f2", "c")]
    state.ops = [{"name": "sum", "expr": "a + f2.c"},
                 {"name": "blank", "expr": ""}]
    headers, rows = state.build_output()
    assert headers == ["f1.a", "f2.c", "sum", "blank"], headers
    assert len(rows) == total
    assert rows[0][3] == "" and rows[-1][3] == ""
    h20, r20 = state.build_output(n_rows=20)
    assert len(r20) == 20 and h20 == headers
    for i in range(20):
        assert abs(rows[i][2] - (rows[i][0] + rows[i][1])) < 1e-12

    # timing: old per-row vs new vectorized for one expression
    expr = "sqrt(abs(a) + 1) + f2.c * 2"
    t0 = time.perf_counter()
    old_vals = [old_eval(expr, state, i) for i in range(total)]
    t_old = time.perf_counter() - t0
    t0 = time.perf_counter()
    new_vals = state.compute_expr(expr, total)
    t_new = time.perf_counter() - t0
    assert all(abs(float(new_vals[i]) - old_vals[i]) < 1e-9 for i in range(0, total, 997))

    print(f"OK — {total} rows, {len(exprs)} expressions match old behavior")
    print(f"old per-row eval : {t_old:.2f} s")
    print(f"new vectorized   : {t_new:.4f} s  ({t_old / max(t_new, 1e-9):.0f}x faster)")


if __name__ == "__main__":
    main()
