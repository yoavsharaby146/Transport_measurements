"""
CSV Fast-Axis Interpolator
--------------------------
Regrids measurement data from a non-uniformly sampled fast axis (e.g.
magnetic-field sweeps with varying step size) onto a uniform grid, per
sweep segment — ready for FFT, plotting, binning.

Handles:
- non-uniform and descending fast-axis steps
- map files: each slow-axis setpoint (gate / field) regridded separately
- hysteresis loops: each monotonic run regridded separately
- NaN cells: skipped per column (independent masks)
- common grid across all segments (intersection of X ranges) so every
  setpoint lands on the identical fast-axis grid, or per-segment grids

Requirements: Python 3.8+, tkinter (stdlib), polars, numpy
Run: python csv_interpolator.py
Self-check: python csv_interpolator.py --selfcheck
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
import sys

import numpy as np
import polars as pl

from csv_utils import read_data_csv
from csv_integrator import (auto_compute_tolerance, build_segments,
                            RESET_BOTH, RESET_DIRECTION)


# grid definitions
GRID_POINTS = "points"   # grid defined by number of points
GRID_STEP = "step"       # grid defined by step size

GRID_LABELS = {
    "Number of points": GRID_POINTS,
    "Step size": GRID_STEP,
}


# ═══════════════════════════════════════════════════════════════════════════
#  CORE MATH (module-level, testable without GUI)
# ═══════════════════════════════════════════════════════════════════════════

def build_grid(lo, hi, grid_mode, grid_value):
    """Uniform ascending grid from lo to hi."""
    if not hi > lo:
        raise ValueError(f"grid range empty: lo={lo:g}, hi={hi:g}")
    if grid_mode == GRID_POINTS:
        n = int(grid_value)
        if n < 2:
            raise ValueError("number of points must be >= 2")
        return np.linspace(lo, hi, n)
    step = float(grid_value)
    if step <= 0:
        raise ValueError("step size must be > 0")
    n = int(np.floor((hi - lo) / step)) + 1
    return lo + step * np.arange(n)


def interp_segment(xs, ys, grid):
    """Linear interpolation of ys over xs onto grid (ascending).
    Grid points outside the segment's own valid range -> NaN.
    NaN cells in either column are skipped (per-column mask)."""
    out = np.full(len(grid), np.nan)
    m = np.isfinite(xs) & np.isfinite(ys)
    if m.sum() < 2:
        return out
    order = np.argsort(xs[m])
    vx = xs[m][order]
    inside = (grid >= vx[0]) & (grid <= vx[-1])
    out[inside] = np.interp(grid[inside], vx, ys[m][order])
    return out


def interpolate_df(df, x_col, keep_cols, slow_col=None, tolerance=1e-6,
                   grid_mode=GRID_POINTS, grid_value=101, common_grid=True):
    """Regrid df onto a uniform fast-axis grid, per sweep segment.

    Segments = slow-axis setpoints (map aware) split further at sweep
    direction reversals, so x is monotonic within every segment.

    common_grid=True: one grid spanning the intersection of all segments'
    X ranges — every setpoint lands on the identical fast-axis grid
    (NaN where a segment does not cover a point). False: each segment
    spans its own min/max.

    Returns (new_df, info). new_df columns = [x_col, slow_col?, *keep_cols]
    (slow column = mean setpoint value per segment). info dict has
    'segments' (source index ranges used), 'dropped' (segments with <2
    valid X points), 'grid' (the common grid, or None).
    """
    x = df[x_col].to_numpy().astype(float)
    slow_vals = df[slow_col].to_numpy().astype(float) if slow_col else None
    ys = {c: df[c].to_numpy().astype(float) for c in keep_cols}

    mode = RESET_BOTH if slow_vals is not None else RESET_DIRECTION
    segments = build_segments(x, slow_vals, tolerance, mode)

    # per-segment valid X ranges; drop segments with < 2 valid X points
    segs = []
    for s, e in segments:
        m = np.isfinite(x[s:e])
        if m.sum() >= 2:
            segs.append((s, e, float(x[s:e][m].min()), float(x[s:e][m].max())))
    if not segs:
        raise ValueError("no segment has 2+ valid fast-axis points")
    dropped = len(segments) - len(segs)

    grid = None
    if common_grid:
        lo = max(g[2] for g in segs)
        hi = min(g[3] for g in segs)
        if not hi > lo:
            raise ValueError("segment fast-axis ranges do not overlap — "
                             "use a per-segment grid instead")
        grid = build_grid(lo, hi, grid_mode, grid_value)

    out_x, out_slow = [], []
    out_y = {c: [] for c in keep_cols}
    used = []
    for s, e, lo_i, hi_i in segs:
        g = grid if common_grid else build_grid(lo_i, hi_i,
                                                grid_mode, grid_value)
        out_x.append(g)
        out_slow.append(np.full(len(g), float(np.mean(slow_vals[s:e]))
                                if slow_vals is not None else np.nan))
        for c in keep_cols:
            out_y[c].append(interp_segment(x[s:e], ys[c][s:e], g))
        used.append((s, e))

    out = {x_col: np.concatenate(out_x)}
    if slow_col:
        out[slow_col] = np.concatenate(out_slow)
    out.update({c: np.concatenate(v) for c, v in out_y.items()})
    info = {"segments": used, "dropped": dropped, "grid": grid}
    return pl.DataFrame(out), info


# ═══════════════════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════════════════

NONE_SLOW = "None (single sweep)"

INSTRUCTIONS = (
    "HOW TO USE\n"
    "1. Click 'Select File & Run' and pick one or more measurement CSVs\n"
    "2. Fast axis (X): the swept column with non-uniform steps (e.g. field)\n"
    "3. Keep columns: tick every column to interpolate onto the new grid\n"
    "   (the X column and the slow axis are always kept)\n"
    "4. Slow axis: setpoint column for maps (gate voltage / field), or\n"
    "   'None' for a single sweep — each setpoint is regridded separately\n"
    "5. Grid: 'Number of points' or 'Step size'. For later FFT use Step\n"
    "   size, smaller than half the fastest feature you care about\n"
    "6. Common grid: same fast-axis grid for all segments (needs overlapping\n"
    "   X ranges); untick to give each segment its own full range\n"
    "7. Output = <name>_interpolated.csv: uniform ascending fast axis,\n"
    "   NaN where a segment does not cover a common-grid point\n"
    "\n"
    "Notes: hysteresis sweeps are split at every direction reversal and\n"
    "regridded separately; NaN cells are skipped per column; descending\n"
    "sweeps are handled (output is always ascending)."
)


class InterpolatorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CSV Interpolator — Uniform Fast-Axis Grid")
        self.root.geometry("560x480")
        self.root.resizable(False, False)

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, 'topmost', False)

        tk.Label(self.root, text="CSV Interpolator",
                 font=("Arial", 14, "bold")).pack(pady=(15, 2))
        tk.Label(self.root,
                 text="Regrid non-uniform fast-axis data (e.g. field sweeps)\n"
                      "onto a uniform grid, per slow-axis setpoint",
                 font=("Arial", 9), fg="gray").pack(pady=(0, 8))

        instr = tk.Label(self.root, text=INSTRUCTIONS, font=("Consolas", 8),
                         bg="#F4F4F2", bd=1, relief="solid",
                         justify="left", anchor="w", padx=10, pady=8)
        instr.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        tk.Button(self.root, text="Select File & Run",
                  command=self.run, height=2, width=22).pack(pady=8)

    def _ask_settings(self, df):
        """One dialog: X column, keep columns, slow axis, grid spec."""
        columns = df.columns
        win = tk.Toplevel(self.root)
        win.title("Interpolation Settings")
        win.resizable(False, False)
        win.lift()

        result = {}

        tk.Label(win, text="Fast axis X column (swept, non-uniform steps):",
                 font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        x_var = tk.StringVar()
        x_combo = ttk.Combobox(win, textvariable=x_var, values=columns,
                               state="readonly", width=45)
        x_combo.current(0)
        x_combo.pack(anchor="w")

        tk.Label(win, text="Slow axis (map setpoint, e.g. gate / field):",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        slow_var = tk.StringVar()
        ttk.Combobox(win, textvariable=slow_var,
                     values=[NONE_SLOW] + columns,
                     state="readonly", width=45).pack(anchor="w")
        slow_var.set(NONE_SLOW)

        tk.Label(win, text="Keep columns — tick all to interpolate:",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        keep_frame = tk.Frame(win, bg="#F4F4F2", bd=1, relief="solid")
        keep_frame.pack(anchor="w", fill="both", expand=True, padx=2)
        keep_vars = {}
        for i in range(0, len(columns), 2):
            row = tk.Frame(keep_frame, bg="#F4F4F2")
            row.pack(anchor="w", fill="x")
            for c in columns[i:i + 2]:
                v = tk.BooleanVar(value=True)
                keep_vars[c] = v
                tk.Checkbutton(row, text=c, variable=v, bg="#F4F4F2",
                               anchor="w").pack(side="left", fill="x",
                                                expand=True, padx=4, pady=1)

        tk.Label(win, text="Uniform grid:", font=("Arial", 10)).pack(
            anchor="w", pady=(8, 0))
        grid_row = tk.Frame(win)
        grid_row.pack(anchor="w")
        mode_var = tk.StringVar()
        mode_combo = ttk.Combobox(grid_row, textvariable=mode_var,
                                  values=list(GRID_LABELS.keys()),
                                  state="readonly", width=18)
        mode_combo.current(1)   # default: Step size
        mode_combo.pack(side="left")
        val_var = tk.StringVar(value="0.1")
        ttk.Entry(grid_row, textvariable=val_var, width=12).pack(
            side="left", padx=(6, 0))

        common_var = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text="Common grid for all segments "
                                 "(intersection of X ranges)",
                       variable=common_var, anchor="w").pack(
            anchor="w", pady=(6, 0))

        def confirm():
            try:
                gv = (int(val_var.get()) if GRID_LABELS[mode_var.get()]
                      == GRID_POINTS else float(val_var.get()))
            except ValueError:
                gv = None
            if gv is None or gv <= 0:
                result['error'] = True
            result['x'] = x_var.get()
            result['slow'] = None if slow_var.get() == NONE_SLOW \
                else slow_var.get()
            excl = {result['x']} | ({result['slow']} if result['slow']
                                    else set())
            result['keep'] = [c for c in columns
                              if c not in excl and keep_vars[c].get()]
            result['grid_mode'] = GRID_LABELS[mode_var.get()]
            result['grid_value'] = gv
            result['common'] = common_var.get()
            win.destroy()

        tk.Button(win, text="Confirm", command=confirm,
                  width=15).pack(pady=12)

        win_h = 360 + max(0, (len(columns) + 1) // 2) * 24
        win_w = max(500, 260 + 2 * max((len(c) for c in columns),
                                       default=10) * 7)
        win.geometry(f"{win_w}x{win_h}")
        self.root.wait_window(win)
        return result or None

    def run(self):
        # 1. Select file(s)
        file_paths = filedialog.askopenfilename(
            parent=self.root, title="Select Measurement CSV(s)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            multiple=True
        )
        if not file_paths:
            return

        try:
            dfs = {}
            for p in file_paths:
                df = read_data_csv(p)
                print(f"Loaded: {os.path.basename(p)} "
                      f"({len(df)} rows, {len(df.columns)} columns)")
                if df.height < 2:
                    messagebox.showerror(
                        "Error",
                        f"{os.path.basename(p)} has fewer than 2 rows.")
                    return
                dfs[p] = df

            # 2. Settings (from first file's columns)
            first = next(iter(dfs.values()))
            cfg = self._ask_settings(first)
            if not cfg:
                return
            if cfg.get('error'):
                messagebox.showerror(
                    "Error", "Grid value must be a positive number.")
                return
            x_col, keep_cols = cfg['x'], cfg['keep']
            slow_col, common = cfg['slow'], cfg['common']
            grid_mode, grid_value = cfg['grid_mode'], cfg['grid_value']
            if not keep_cols:
                messagebox.showerror(
                    "Error", "Tick at least one keep column to interpolate.")
                return

            # 3. Setpoint tolerance if needed (from first file)
            tolerance = 1e-6
            if slow_col is not None:
                vals = first[slow_col].to_numpy().astype(float)
                auto_tol = auto_compute_tolerance(vals)
                tolerance = simpledialog.askfloat(
                    "Setpoint Tolerance",
                    f"Slow axis: '{slow_col}'\n"
                    f"Range: {vals.min():.6g} → {vals.max():.6g}\n"
                    f"Unique values detected: {len(np.unique(vals))}\n\n"
                    f"Tolerance for grouping into setpoints:\n\n"
                    f"Auto-detected: {auto_tol:.6g}",
                    initialvalue=auto_tol, parent=self.root
                )
                if tolerance is None:
                    return

            def run_one(df):
                return interpolate_df(df, x_col, keep_cols, slow_col,
                                      tolerance, grid_mode, grid_value,
                                      common)

            if len(dfs) == 1:
                # single file: manual save location
                file_path = next(iter(dfs))
                out_df, info = run_one(dfs[file_path])
                print(f"\n{len(info['segments'])} segment(s) regridded"
                      + (f", {info['dropped']} dropped (too few points)"
                         if info['dropped'] else ""))
                for i, (s, e) in enumerate(info['segments']):
                    print(f"  segment {i}: source rows {s}..{e - 1} "
                          f"({e - s} rows)")

                name = os.path.splitext(os.path.basename(file_path))[0]
                out_path = filedialog.asksaveasfilename(
                    parent=self.root, defaultextension=".csv",
                    filetypes=[("CSV", "*.csv")],
                    initialfile=f"{name}_interpolated.csv"
                )
                if not out_path:
                    return
                out_df.write_csv(out_path)

                msg = (f"Interpolation complete!\n\n"
                       f"Source: {os.path.basename(file_path)}\n"
                       f"Segments regridded: {len(info['segments'])}"
                       + (f" (dropped {info['dropped']})" if info['dropped']
                          else "") + "\n"
                       f"Output rows: {out_df.height}\n"
                       f"Saved: {out_path}")
                print(f"\n{msg}")
                messagebox.showinfo("Success", msg)
                self.root.quit()
                return

            # multiple files: same settings for all, auto-save beside source
            lines = []
            ok = 0
            for p, df in dfs.items():
                name = os.path.basename(p)
                stem = os.path.splitext(name)[0]
                needed = [x_col] + keep_cols + ([slow_col] if slow_col else [])
                missing = [c for c in needed if c not in df.columns]
                if missing:
                    lines.append(f"✗ {name} — missing columns: "
                                 f"{', '.join(missing)}")
                    continue
                try:
                    out_df, info = run_one(df)
                    out_path = os.path.join(os.path.dirname(p),
                                            f"{stem}_interpolated.csv")
                    out_df.write_csv(out_path)
                    ok += 1
                    print(f"\n{name}: {len(info['segments'])} segment(s) → "
                          f"{os.path.basename(out_path)}")
                    lines.append(f"✓ {name} — {len(info['segments'])} "
                                 f"segment(s) → {os.path.basename(out_path)}")
                except Exception as e:
                    lines.append(f"✗ {name} — {e}")

            msg = (f"Batch interpolation complete!\n\n"
                   f"Files: {len(dfs)} ({ok} ok)\n"
                   f"Keep columns: {', '.join(keep_cols)}\n\n"
                   + "\n".join(lines))
            print(f"\n{msg}")
            messagebox.showinfo("Batch Result", msg)
            self.root.quit()

        except Exception as e:
            error_msg = f"An error occurred:\n{str(e)}"
            print(error_msg)
            messagebox.showerror("Error", error_msg)


# ═══════════════════════════════════════════════════════════════════════════
#  SELF-CHECK
# ═══════════════════════════════════════════════════════════════════════════

def self_check():
    # 1. non-uniform x, linear y=2x: step grid reproduces 2x exactly
    x = np.array([0.0, 0.3, 0.4, 1.0, 2.2, 2.5, 4.0])
    df = pl.DataFrame({"B": x, "V": 2 * x})
    out, info = interpolate_df(df, "B", ["V"], None, 1e-6,
                               GRID_STEP, 0.25, common_grid=False)
    g = out["B"].to_numpy()
    assert np.allclose(np.diff(g), 0.25), g            # uniform ascending
    assert np.allclose(out["V"].to_numpy(), 2 * g), out["V"].to_numpy()

    # 2. points mode: linspace grid
    out, _ = interpolate_df(df, "B", ["V"], None, 1e-6,
                            GRID_POINTS, 9, common_grid=False)
    assert len(out) == 9 and np.allclose(out["V"].to_numpy(),
                                         2 * out["B"].to_numpy())

    # 3. descending sweep: correct values on ascending grid
    xd = np.array([4.0, 3.0, 2.0, 1.0, 0.0])            # field swept down
    dfd = pl.DataFrame({"B": xd, "V": 3 * xd})
    outd, _ = interpolate_df(dfd, "B", ["V"], None, 1e-6,
                             GRID_STEP, 1.0, common_grid=False)
    assert np.allclose(outd["B"].to_numpy(), [0, 1, 2, 3, 4])
    assert np.allclose(outd["V"].to_numpy(), [0, 3, 6, 9, 12])

    # 4. map: two gates with different ranges; common grid = intersection,
    #    same grid for both, NaN where a segment does not reach
    xg1 = np.linspace(0.0, 2.0, 21)     # gate 1: 0..2
    xg2 = np.linspace(0.5, 2.5, 21)     # gate 2: 0.5..2.5
    xm = np.concatenate([xg1, xg2])
    vm = np.sin(xm)
    vg = np.repeat([1.0, 2.0], 21)
    dfm = pl.DataFrame({"B": xm, "V": vm, "Vg": vg})
    outm, infom = interpolate_df(dfm, "B", ["V"], "Vg", 0.1,
                                 GRID_STEP, 0.5, common_grid=True)
    # intersection = 0.5..2.0 -> grid [0.5, 1.0, 1.5, 2.0], 4 rows per gate
    assert len(outm) == 8, len(outm)
    expect_grid = np.array([0.5, 1.0, 1.5, 2.0])
    for k in (0, 1):
        blk = outm["B"].to_numpy()[4 * k:4 * (k + 1)]
        assert np.allclose(blk, expect_grid), blk       # identical grid
        vals = outm["V"].to_numpy()[4 * k:4 * (k + 1)]
        assert np.allclose(vals, np.sin(expect_grid), atol=1e-12), vals
    # slow column: cluster mean per segment
    assert np.allclose(outm["Vg"].to_numpy()[:4], 1.0)
    assert np.allclose(outm["Vg"].to_numpy()[4:], 2.0)

    # 4b. non-overlapping ranges + common grid -> clear error
    xg3 = np.linspace(3.0, 4.0, 5)
    dfbad = pl.DataFrame({"B": np.concatenate([xg1, xg3]),
                          "V": np.concatenate([xg1, xg3]),
                          "Vg": np.concatenate([np.full(21, 1.0),
                                                np.full(5, 2.0)])})
    try:
        interpolate_df(dfbad, "B", ["V"], "Vg", 0.1,
                       GRID_STEP, 0.5, common_grid=True)
        raise AssertionError("expected overlap error")
    except ValueError as e:
        assert "overlap" in str(e)

    # 5. hysteresis: up + down within one setpoint -> 2 segments,
    #    each regridded on its own range (no wrap-around interpolation)
    up = np.linspace(0.0, 1.0, 11)
    tri = np.concatenate([up, up[::-1]])
    dft = pl.DataFrame({"B": tri, "V": tri ** 2, "Vg": np.full(22, 1.0)})
    outt, infot = interpolate_df(dft, "B", ["V"], "Vg", 0.1,
                                 GRID_STEP, 0.25, common_grid=False)
    assert len(infot["segments"]) == 2, infot            # split at reversal
    seg1 = outt[:5]                                      # 0..1 ascending
    assert np.allclose(seg1["B"].to_numpy(), [0, .25, .5, .75, 1.0])
    # linear interp of a parabola: endpoints/known samples exact, quarter
    # points get the chord value (0.065 between 0.04@0.2 and 0.09@0.3)
    assert np.allclose(seg1["V"].to_numpy(), [0, .065, .25, .565, 1.0])

    # 6. NaN holes: skipped per column, rest still exact
    vn = 2 * x.copy()
    vn[2] = np.nan
    dfn = pl.DataFrame({"B": x, "V": vn})
    outn, _ = interpolate_df(dfn, "B", ["V"], None, 1e-6,
                             GRID_STEP, 0.25, common_grid=False)
    gv = outn["V"].to_numpy()
    gn = outn["B"].to_numpy()
    finite = np.isfinite(gv)
    assert finite.all(), gv    # holes between samples bridge fine
    assert np.allclose(gv[finite], 2 * gn[finite])

    print("csv_interpolator self-check OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv or "--test" in sys.argv:
        self_check()
    else:
        app = InterpolatorApp()
        app.root.mainloop()
