"""Shared CSV loading for measurement data files.

Measurement CSVs start with metadata lines (general settings, sweep config, ...)
before the column-title row. The title row always starts with 'time(s)'.
These helpers skip the preamble so callers only see titled data columns.
"""

import polars as pl


def detect_header_row(filepath, max_lines=100):
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


def show_help(parent, title, text, modal=False):
    """Show a how-to-use instructions window (shared by the analysis GUIs).

    parent: the parent Tk window, or None to create a standalone window
    (used by dialog-flow scripts with no persistent main window; a
    standalone window is always modal so the flow resumes on close).
    modal=True blocks (wait_window) until the user closes it.
    """
    import tkinter as tk

    standalone = parent is None
    if standalone:
        parent = tk.Tk()
        parent.withdraw()
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("+%d+%d" % (parent.winfo_rootx() + 60, parent.winfo_rooty() + 60))
    win.lift()
    win.attributes('-topmost', True)
    win.after_idle(win.attributes, '-topmost', False)

    body = tk.Frame(win, bg="#FFFFFF")
    body.pack(fill="both", expand=True)
    tk.Label(body, text=text, font=("Consolas", 9), bg="#FFFFFF",
             justify="left", anchor="w", padx=16, pady=14).pack(
        fill="both", expand=True)
    tk.Button(win, text="Close", command=win.destroy,
              width=12).pack(pady=(0, 12))
    win.update_idletasks()
    w = max(560, win.winfo_reqwidth())
    h = min(win.winfo_reqheight() + 20, parent.winfo_screenheight() - 120)
    win.geometry(f"{w}x{h}")

    if modal or standalone:
        parent.wait_window(win)
        if standalone:
            try:
                parent.destroy()
            except tk.TclError:
                pass
    return win


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
