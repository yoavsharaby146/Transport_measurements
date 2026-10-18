"""
CSV Cumulative Trapezoid Integrator
-----------------------------------
Adds a cumulative trapezoid integral of a Y column over an X column
(e.g. voltage over bias current) to a measurement CSV.

Handles:
- sweeps that start anywhere (not necessarily 0) and run in either
  direction — the trapezoid uses the actual per-step dx, so the sign
  of the sweep comes out automatically
- map files: bias swept at many slow-axis setpoints (gate voltages,
  fields) — integration resets per setpoint so it never runs across
  setpoint jumps
- hysteresis loops: optionally reset at every sweep-direction reversal

Requirements: Python 3.8+, tkinter (stdlib), polars, numpy
Run: python csv_integrator.py
Self-check: python csv_integrator.py --selfcheck
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
import sys

import numpy as np
import polars as pl

from csv_utils import read_data_csv


# reset modes for cumulative integration
RESET_NEVER = "never"            # one running integral over the whole file
RESET_DIRECTION = "direction"    # reset at every sweep-direction reversal
RESET_SETPOINT = "setpoint"      # reset at every slow-axis setpoint change
RESET_BOTH = "both"              # reset at setpoints AND reversals
RESET_ZERO = "zero"              # reset at zero crossing of X (+/- sides apart)

RESET_LABELS = {
    "Never — one integral over whole file": RESET_NEVER,
    "At each slow-axis setpoint": RESET_SETPOINT,
    "At each direction reversal": RESET_DIRECTION,
    "At each setpoint and each reversal": RESET_BOTH,
    "At each zero crossing of X (separate +/- sides)": RESET_ZERO,
}


# ═══════════════════════════════════════════════════════════════════════════
#  CORE MATH (module-level, testable without GUI)
# ═══════════════════════════════════════════════════════════════════════════

def cumtrapz_segment(y, x):
    """Cumulative trapezoid integral of y over x within one sweep segment.

    Result[k] = integral from x[0] to x[k]. First element is 0.
    Works for ascending or descending x (dx carries the sign) and for
    non-uniform steps.
    """
    out = np.zeros(len(x))
    if len(x) > 1:
        out[1:] = np.cumsum((y[:-1] + y[1:]) / 2.0 * np.diff(x))
    return out


def cluster_setpoints(values, tolerance):
    """Cluster values into setpoints within tolerance (same logic as map_splitter).

    Returns dict: each unique value -> its cluster mean.
    """
    if len(values) == 0:
        return {}
    sorted_vals = sorted(values)
    clusters = []
    current = [sorted_vals[0]]
    for val in sorted_vals[1:]:
        if val - current[-1] <= tolerance:
            current.append(val)
        else:
            clusters.append(current)
            current = [val]
    clusters.append(current)
    means = [sum(c) / len(c) for c in clusters]
    return {v: min(means, key=lambda m: abs(m - v)) for v in values}


def auto_compute_tolerance(values):
    """Half the minimum non-zero gap between sorted unique values."""
    unique_vals = np.sort(np.unique(values))
    if len(unique_vals) <= 1:
        return float(np.ptp(values)) * 0.01 if len(values) > 1 else 1e-6
    gaps = np.diff(unique_vals)
    nonzero = gaps[gaps > 0]
    if len(nonzero) == 0:
        return float(np.ptp(values)) * 0.01
    return float(nonzero.min() * 0.5)


def _contiguous_runs(labels):
    """Split a label sequence into contiguous runs. Returns list of (start, stop)."""
    runs = []
    s = 0
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            runs.append((s, i))
            s = i
    runs.append((s, len(labels)))
    return runs


def direction_splits(x, start, stop, jitter_frac=0.1):
    """Split x[start:stop] into monotonic runs at direction reversals.

    Steps smaller than jitter_frac * median(|step|) (repeated boundary
    values, jitter) carry the previous direction instead of splitting.
    The turnaround point is shared by both runs so nothing is lost.
    Returns list of (start, stop).
    """
    d = np.diff(x[start:stop])
    if len(d) == 0:
        return [(start, stop)]
    med = np.median(np.abs(d))
    thr = jitter_frac * med if med > 0 else 0.0
    signs = np.sign(d)
    signs[np.abs(d) < thr] = 0
    for i in range(1, len(signs)):     # carry sign through jitter steps
        if signs[i] == 0:
            signs[i] = signs[i - 1]
    if signs[0] == 0:                  # leading jitter
        nz = signs[signs != 0]
        signs[:] = nz[0] if len(nz) else 1.0
    runs = []
    s = 0
    for i in range(1, len(signs)):
        if signs[i] != signs[i - 1]:
            runs.append((start + s, start + i + 1))  # keep turnaround point
            s = i
    runs.append((start + s, stop))
    return runs


def zero_splits(x, start, stop, zero_frac=0.5):
    """Split x[start:stop] at zero crossings — positive and negative sides
    integrated separately, each anchored at zero (0 → positive edge and
    0 → negative edge).

    The point closest to zero at each crossing is shared by both runs and
    serves as the anchor: Φ(I) = ∫₀^I y dx on both sides. A point within
    zero_frac * median(|step|) of zero counts as the zero point; consecutive
    zero points collapse onto one shared point.
    Returns list of (start, stop).
    """
    seg = x[start:stop]
    if len(seg) < 2:
        return [(start, stop)]
    med = float(np.median(np.abs(np.diff(seg))))
    thr = zero_frac * med if med > 0 else 0.0
    sgn = np.sign(seg)
    near_zero = np.abs(seg) < thr

    runs = []
    s = 0
    i = 1
    while i < len(seg):
        split_at = None
        if near_zero[i]:
            split_at = i
        elif sgn[i] != 0 and sgn[i - 1] != 0 and sgn[i] != sgn[i - 1]:
            # no exact zero on this grid: share the point closest to zero
            split_at = i if abs(seg[i]) < abs(seg[i - 1]) else i - 1
        if split_at is not None and split_at > s:
            runs.append((start + s, start + split_at + 1))
            k = split_at
            while k + 1 < len(seg) and near_zero[k + 1]:
                k += 1                     # collapse consecutive zero points
            s = k
            i = k + 1
            continue
        i += 1
    runs.append((start + s, stop))
    return runs


def build_segments(x, slow_vals, tolerance, reset_mode):
    """Determine integration segments (index ranges) for the whole file."""
    n = len(x)
    if slow_vals is not None and reset_mode in (RESET_SETPOINT, RESET_BOTH,
                                                RESET_ZERO):
        cluster_map = cluster_setpoints(list(np.unique(slow_vals)), tolerance)
        labels = [cluster_map[v] for v in slow_vals]
        groups = _contiguous_runs(labels)
    else:
        groups = [(0, n)]

    segments = []
    for s, e in groups:
        if reset_mode in (RESET_DIRECTION, RESET_BOTH):
            segments.extend(direction_splits(x, s, e))
        elif reset_mode == RESET_ZERO:
            segments.extend(zero_splits(x, s, e))
        else:
            segments.append((s, e))
    return segments


def integrate_df(df, x_col, y_col, slow_col=None, tolerance=1e-6,
                 reset_mode=RESET_NEVER, x_scale=1.0, y_div=1.0):
    """Add cumulative-trapezoid column 'integ_<y_col>' to df.

    x_scale: constant factor applied to the X column before integrating
    (e.g. 1/R when X is a voltage representing current = U/R).
    y_div: constant divisor applied to the Y column before integrating
    (e.g. the lock-in AC excitation current I_ac: Y/I_ac = dV/dI, so the
    integral reconstructs voltage). Both only scale the result —
    segmentation is invariant.

    Returns (new_df, segments).
    """
    x = df[x_col].to_numpy().astype(float) * x_scale
    y = df[y_col].to_numpy().astype(float) / y_div
    slow_vals = (df[slow_col].to_numpy().astype(float)
                 if slow_col else None)
    segments = build_segments(x, slow_vals, tolerance, reset_mode)
    out = np.full(len(x), np.nan)
    for s, e in segments:
        if reset_mode == RESET_ZERO:
            # anchor at the zero end: integral runs 0 → positive edge and
            # 0 → negative edge (Φ(I) = ∫₀^I y dx on both sides)
            anchor = s if abs(x[s]) <= abs(x[e - 1]) else e - 1
            idx = np.arange(s, e)
            if anchor != s:
                idx = idx[::-1]   # integrate from zero toward the edge
            out[idx] = cumtrapz_segment(y[idx], x[idx])
        else:
            out[s:e] = cumtrapz_segment(y[s:e], x[s:e])
    name = f"integ_{y_col}"
    return df.with_columns(pl.Series(name, out).alias(name)), segments

# ═══════════════════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════════════════

NONE_SLOW = "None (single sweep)"


class IntegratorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CSV Integrator — Cumulative Trapezoid")
        self.root.geometry("440x210")

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        tk.Label(self.root, text="CSV Integrator",
                 font=("Arial", 14, "bold")).pack(pady=(15, 2))
        tk.Label(self.root,
                 text="Cumulative trapezoid of Y over X (e.g. V over I),\n"
                      "reset per sweep segment / slow-axis setpoint",
                 font=("Arial", 9), fg="gray").pack(pady=(0, 10))
        tk.Button(self.root, text="Select File & Run",
                  command=self.run, height=2, width=22).pack(pady=10)

    def _ask_settings(self, df):
        """One dialog: X column, Y column, slow axis, reset mode."""
        columns = df.columns
        win = tk.Toplevel(self.root)
        win.title("Integration Settings")
        win.geometry("420x320")
        win.lift()

        result = {}

        tk.Label(win, text="X column (integrate over, e.g. bias current):",
                 font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        x_var = tk.StringVar()
        ttk.Combobox(win, textvariable=x_var, values=columns,
                     state="readonly", width=45).pack(anchor="w")

        tk.Label(win, text="Y column(s) (integrand, e.g. lock-in voltage —\n"
                           "ctrl/shift-click for multiple):",
                 font=("Arial", 10), justify="left").pack(anchor="w", pady=(8, 0))
        y_list = tk.Listbox(win, selectmode="extended", height=4,
                            exportselection=False, width=47)
        for c in columns:
            y_list.insert("end", c)
        y_list.pack(anchor="w")

        tk.Label(win, text="Slow axis column (setpoints, e.g. gate / field):",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        slow_var = tk.StringVar()
        ttk.Combobox(win, textvariable=slow_var,
                     values=[NONE_SLOW] + columns,
                     state="readonly", width=45).pack(anchor="w")
        slow_var.set(NONE_SLOW)

        tk.Label(win, text="Reset cumulative integral:",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        mode_var = tk.StringVar()
        ttk.Combobox(win, textvariable=mode_var,
                     values=list(RESET_LABELS.keys()),
                     state="readonly", width=45).pack(anchor="w")
        mode_var.set(list(RESET_LABELS.keys())[0])

        tk.Label(win, text="X scale factor (X·factor, e.g. 1/R for V→I):",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        scale_var = tk.StringVar(value="1.0")
        ttk.Entry(win, textvariable=scale_var, width=47).pack(anchor="w")

        tk.Label(win, text="Y divide by (Y/factor, e.g. excitation "
                           "current I_ac → V):",
                 font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        ydiv_var = tk.StringVar(value="1.0")
        ttk.Entry(win, textvariable=ydiv_var, width=47).pack(anchor="w")

        def confirm():
            try:
                result['scale'] = float(scale_var.get())
                result['ydiv'] = float(ydiv_var.get())
            except ValueError:
                result['scale'] = None   # trigger error message in run()
            result['x'] = x_var.get()
            result['ys'] = [columns[i] for i in y_list.curselection()]
            result['slow'] = None if slow_var.get() == NONE_SLOW else slow_var.get()
            result['mode'] = RESET_LABELS[mode_var.get()]
            win.destroy()

        tk.Button(win, text="Confirm", command=confirm,
                  width=15).pack(pady=15)
        self.root.wait_window(win)
        return result or None

    def run(self):
        # 1. Select file
        file_path = filedialog.askopenfilename(
            parent=self.root, title="Select Measurement CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            df = read_data_csv(file_path)
            print(f"Loaded: {os.path.basename(file_path)} "
                  f"({len(df)} rows, {len(df.columns)} columns)")
            if df.height < 2:
                messagebox.showerror("Error", "Need at least 2 rows.")
                return

            # 2. Settings
            cfg = self._ask_settings(df)
            if not cfg:
                return
            x_col, y_cols, slow_col, mode = (cfg['x'], cfg['ys'],
                                             cfg['slow'], cfg['mode'])
            x_scale = cfg['scale']
            y_div = cfg['ydiv']

            if not x_col or not y_cols:
                messagebox.showerror("Error",
                                     "Pick an X column and at least one "
                                     "Y column.")
                return
            if x_col in y_cols:
                messagebox.showerror("Error",
                                     "X column cannot also be a Y column.")
                return
            if x_scale is None or y_div is None or y_div == 0:
                messagebox.showerror("Error",
                                     "Scale/divisor must be nonzero numbers "
                                     "(use 1.0 for no conversion).")
                return

            # 3. Setpoint tolerance if needed
            tolerance = 1e-6
            if slow_col is not None and mode in (RESET_SETPOINT, RESET_BOTH,
                                                 RESET_ZERO):
                vals = df[slow_col].to_numpy().astype(float)
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

            # 4. Integrate each selected Y column
            out_df, segments = None, None
            for yc in y_cols:
                out_df, segments = integrate_df(df if out_df is None else out_df,
                                                x_col, yc, slow_col,
                                                tolerance, mode, x_scale, y_div)
            new_cols = [f"integ_{yc}" for yc in y_cols]
            print(f"\n{len(segments)} integration segment(s):")
            for i, (s, e) in enumerate(segments):
                print(f"  segment {i}: rows {s}..{e - 1} ({e - s} rows)")

            # 5. Save
            name = os.path.splitext(os.path.basename(file_path))[0]
            out_path = filedialog.asksaveasfilename(
                parent=self.root,
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"{name}_integrated.csv"
            )
            if not out_path:
                return
            out_df.write_csv(out_path)

            msg = (f"Integration complete!\n\n"
                   f"Source: {os.path.basename(file_path)}\n"
                   f"Y columns: {', '.join(y_cols)}\n"
                   f"Conversions: X·{x_scale:g}, Y/{y_div:g}\n"
                   f"New columns: {', '.join(new_cols)}\n"
                   f"Reset mode: {mode}\n"
                   f"Segments: {len(segments)}\n"
                   f"Saved: {out_path}")
            print(f"\n{msg}")
            messagebox.showinfo("Success", msg)
            self.root.quit()

        except Exception as e:
            error_msg = f"An error occurred:\n{str(e)}"
            print(error_msg)


# ═══════════════════════════════════════════════════════════════════════════
#  SELF-CHECK
# ═══════════════════════════════════════════════════════════════════════════

def self_check():
    # 1. exactness on linear data, sweep +30µA → −30µA @ 0.1µA steps:
    #    V = 2I  →  cumulative integral = I² − I₀²  (start value and
    #    direction handled by dx sign, no special-casing)
    I = np.linspace(30e-6, -30e-6, 601)
    out = cumtrapz_segment(2 * I, I)
    expect = I ** 2 - I[0] ** 2
    assert np.allclose(out, expect, rtol=1e-9, atol=1e-16), \
        f"linear check failed, max err {np.max(np.abs(out - expect)):.3g}"
    assert out[0] == 0.0

    # 2. setpoint reset, including a non-contiguous repeated setpoint
    I_up = np.linspace(-10, 10, 21)
    x = np.concatenate([I_up, I_up, I_up])
    slow = np.repeat([1.0, 2.0, 1.0], 21)
    segs = build_segments(x, slow, 0.1, RESET_SETPOINT)
    assert len(segs) == 3, segs
    res = np.full(len(x), np.nan)
    for s, e in segs:
        res[s:e] = cumtrapz_segment(2 * x[s:e], x[s:e])
    assert res[0] == 0 and res[21] == 0 and res[42] == 0, "no reset at setpoints"

    # 3. direction reset: triangle sweep shares turnaround point, no loss
    tri = np.concatenate([np.arange(0, 11),
                          np.arange(10, -1, -1)]).astype(float)
    segs = build_segments(tri, None, 0, RESET_DIRECTION)
    assert len(segs) == 2, segs
    assert segs[0][1] == segs[1][0] + 1, "turnaround point not shared"
    res_tri = np.concatenate([cumtrapz_segment(2 * tri[s:e], tri[s:e])
                              for s, e in segs])
    assert res_tri[10] == 100.0, res_tri[10]   # ∫2I dI from 0 to 10
    assert res_tri[12] == 0.0, res_tri[12]     # reset at reversal (point 11
                                               # shared: idx 11 = run-A peak)

    # 4. jitter guard: repeated boundary value must not create extra split
    xj = np.array([0, 1, 2, 2, 3, 2, 1, 0.0])
    segs = build_segments(xj, None, 0, RESET_DIRECTION)
    assert len(segs) == 2, segs

    # 5. integrate_df end-to-end: column added, values match per segment
    df = pl.DataFrame({"I": x, "V": 2 * x, "Vg": slow})
    out_df, segs = integrate_df(df, "I", "V", "Vg", 0.1, RESET_SETPOINT)
    assert "integ_V" in out_df.columns
    col = out_df["integ_V"].to_numpy()
    assert np.allclose(col, res)
    assert not np.isnan(col).any()

    # 6. x_scale / y_div: constant conversions scale result, segments unchanged
    out_s, segs_s = integrate_df(df, "I", "V", "Vg", 0.1, RESET_SETPOINT,
                                 x_scale=0.5, y_div=0.5)
    assert segs_s == segs
    assert np.allclose(out_s["integ_V"].to_numpy(), 1.0 * col)  # ×0.5 / ÷0.5

    # 7. zero-crossing reset: -10 → +10 sweep, exact zero on grid (step 0.1)
    z = np.linspace(-10, 10, 201)          # z[100] == 0.0 exactly
    segz = build_segments(z, None, 0, RESET_ZERO)
    assert len(segz) == 2 and segz[0][1] == 101 and segz[1][0] == 100, segz
    outz, _ = integrate_df(pl.DataFrame({"I": z, "V": 2 * z}), "I", "V",
                           None, 1e-6, RESET_ZERO)
    cz = outz["integ_V"].to_numpy()
    assert cz[100] == 0.0, cz[100]         # zero point anchors both sides
    assert np.isclose(cz[50], 25.0)        # ∫₀^I 2I dI = I² at I = −5
    assert np.isclose(cz[0], 100.0)        # 0 → negative edge: I² at I = −10
    assert np.isclose(cz[200], 100.0)      # 0 → positive edge: I² at I = +10

    # 7b. grid with no exact zero: share point closest to zero
    zn = np.array([-0.3, -0.1, 0.1, 0.3])
    segzn = build_segments(zn, None, 0, RESET_ZERO)
    assert len(segzn) == 2, segzn

    # 7c. consecutive zero points collapse onto one shared point
    zc = np.array([-1.0, 0.0, 0.0, 1.0])
    segzc = build_segments(zc, None, 0, RESET_ZERO)
    assert len(segzc) == 2, segzc

    # 7d. map-aware: two setpoints, each crossing zero → 4 segments
    xm = np.concatenate([z, z])
    dfz = pl.DataFrame({"I": xm, "V": 2 * xm, "Vg": np.repeat([1.0, 2.0], 201)})
    outm, segm = integrate_df(dfz, "I", "V", "Vg", 0.1, RESET_ZERO)
    assert len(segm) == 4, segm
    cm = outm["integ_V"].to_numpy()
    assert cm[100] == 0.0 and cm[301] == 0.0   # each side starts at zero

    # 8. multi-Y: integrate two Y columns -> two new columns, X-independent
    dfm = pl.DataFrame({"I": x, "V1": 2 * x, "V2": 4 * x})
    for yc in ("V1", "V2"):
        dfm, _ = integrate_df(dfm, "I", yc, None, 1e-6, RESET_NEVER)
    assert "integ_V1" in dfm.columns and "integ_V2" in dfm.columns
    assert np.allclose(dfm["integ_V2"].to_numpy(),
                       2 * dfm["integ_V1"].to_numpy())

    print("csv_integrator self-check OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv or "--test" in sys.argv:
        self_check()
    else:
        app = IntegratorApp()
        app.root.mainloop()
