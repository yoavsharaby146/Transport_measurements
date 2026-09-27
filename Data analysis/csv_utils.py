"""Shared CSV loading for measurement data files.

Measurement CSVs start with metadata lines (general settings, sweep config, ...)
before the column-title row. The title row always starts with 'time(s)'.
These helpers skip the preamble so callers only see titled data columns.
"""

import polars as pl


def detect_header_row(filepath, max_lines=50):
    """Return index of the column-title row; 0 if the file has no preamble.

    Scans the first `max_lines` lines for one containing 'time(s)'
    (case-insensitive) — the convention used by all measurement procedures.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            if 'time(s)' in line.lower():
                return i
    return 0


def read_data_csv(filepath, **kwargs):
    """Read a measurement CSV, skipping any preamble before the column titles."""
    kwargs.setdefault('infer_schema_length', 10000)
    kwargs.setdefault('truncate_ragged_lines', True)
    kwargs.setdefault('ignore_errors', True)
    return pl.read_csv(filepath, skip_rows=detect_header_row(filepath), **kwargs)


if __name__ == "__main__":
    # self-check: preamble before titles must be skipped, data intact
    import tempfile, os
    content = (
        "General settings,SR830#1\n"
        "sweep,Aux\n"
        "time(s),Tsample(K),field(T)\n"
        "0,1.5,0.1\n"
        "1,1.6,0.2\n"
    )
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.csv")
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        assert detect_header_row(p) == 2
        df = read_data_csv(p)
        assert df.columns == ['time(s)', 'Tsample(K)', 'field(T)'], df.columns
        assert df.shape == (2, 3), df.shape
        # no-preamble file: fallback 0
        with open(p, 'w', encoding='utf-8') as f:
            f.write("time(s),x\n0,1\n")
        assert detect_header_row(p) == 0
    print("csv_utils self-check OK")
