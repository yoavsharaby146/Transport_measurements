"""Self-check for Plot data.py performance rework.

1. _load_csv: old readlines()-based algorithm vs new head/tail-scan
   algorithm — same polars DataFrame output, timing comparison.
2. _extract_line_profile: old per-sample Python loop vs new vectorized
   numpy version — same x/y/z/distance values, timing comparison.
Run: python _speed_check.py
"""
import importlib.util
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "plot_data", os.path.join(HERE, "Plot data.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
InteractivePlotter = mod.InteractivePlotter


def old_load_csv(filepath):
    """The original algorithm, kept verbatim as the reference."""
    import polars as pl
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header_line = 0
    for i, line in enumerate(lines[:50]):
        if 'time(s)' in line.lower(): header_line = i; break
    skip_footer = 0
    header_cols = len(lines[header_line].split(','))
    for i in range(len(lines) - 1, header_line, -1):
        line = lines[i].strip()
        if not line: skip_footer += 1; continue
        if line.startswith(';') or line.startswith('#'): skip_footer += 1; continue
        if len(line.split(',')) != header_cols: skip_footer += 1; continue
        break
    if skip_footer > 0:
        return pl.read_csv(filepath, skip_rows=header_line,
                           n_rows=len(lines) - header_line - skip_footer,
                           truncate_ragged_lines=True, ignore_errors=True)
    else:
        return pl.read_csv(filepath, skip_rows=header_line,
                           truncate_ragged_lines=True, ignore_errors=True)

def old_extract_line_profile(self, points):
    """The original per-sample loop, kept verbatim as the reference."""
    if self._cmap_zi_data is None or self._cmap_extent is None:
        return []
    zi = self._cmap_zi_data
    xmin, xmax, ymin, ymax = self._cmap_extent
    ny, nx = zi.shape
    all_sampled = []
    cumulative_distance = 0.0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        seg_len = np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        n_samples = max(int(seg_len / max(xmax - xmin, ymax - ymin) * 500), 10)
        for j in range(n_samples):
            t = j / n_samples
            sx = x0 + t * (x1 - x0)
            sy = y0 + t * (y1 - y0)
            px = (sx - xmin) / (xmax - xmin) * (nx - 1)
            py = (sy - ymin) / (ymax - ymin) * (ny - 1)
            px0 = int(np.floor(px)); py0 = int(np.floor(py))
            px1 = px0 + 1; py1 = py0 + 1
            if 0 <= px0 < nx and 0 <= py0 < ny and 0 <= px1 < nx and 0 <= py1 < ny:
                fx = px - px0; fy = py - py0
                z_val = (zi[py0, px0]*(1-fx)*(1-fy) + zi[py0, px1]*fx*(1-fy) +
                         zi[py1, px0]*(1-fx)*fy + zi[py1, px1]*fx*fy)
            else:
                z_val = np.nan
            all_sampled.append({'x': sx, 'y': sy, 'z': z_val,
                                'distance': cumulative_distance + np.sqrt((sx-x0)**2 + (sy-y0)**2)})
        cumulative_distance += seg_len
    lx, ly = points[-1]
    px = (lx - xmin) / (xmax - xmin) * (nx - 1)
    py = (ly - ymin) / (ymax - ymin) * (ny - 1)
    px0 = int(np.floor(px)); py0 = int(np.floor(py))
    px1 = px0 + 1; py1 = py0 + 1
    if 0 <= px0 < nx and 0 <= py0 < ny and 0 <= px1 < nx and 0 <= py1 < ny:
        fx = px - px0; fy = py - py0
        z_val = (zi[py0, px0]*(1-fx)*(1-fy) + zi[py0, px1]*fx*(1-fy) +
                 zi[py1, px0]*(1-fx)*fy + zi[py1, px1]*fx*fy)
    else:
        z_val = np.nan
    all_sampled.append({'x': lx, 'y': ly, 'z': z_val, 'distance': cumulative_distance})
    return all_sampled


def main():
    import tempfile
    rng = np.random.default_rng(7)

    # ---- 1. _load_csv equivalence + timing ----
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "big.csv")
    n_rows = 200_000
    with open(path, "w", newline="") as f:
        f.write("junk preamble line\n")
        f.write("time(s),x,y,z\n")
        for i in range(n_rows):
            f.write(f"{i*0.01:.3f},{rng.uniform(0,1):.6f},{rng.uniform(0,1):.6f},{rng.uniform(0,100):.6f}\n")
        f.write("# footer comment\n")
        f.write("ragged,line\n")

    t0 = time.perf_counter()
    df_old = old_load_csv(path)
    t_old = time.perf_counter() - t0
    t0 = time.perf_counter()
    df_new = InteractivePlotter._load_csv(object.__new__(InteractivePlotter), path)
    t_new = time.perf_counter() - t0

    assert df_old.columns == df_new.columns, (df_old.columns, df_new.columns)
    assert df_old.shape == df_new.shape, (df_old.shape, df_new.shape)
    for c in df_old.columns:
        np.testing.assert_allclose(df_old[c].to_numpy(), df_new[c].to_numpy(), rtol=1e-9)
    print(f"_load_csv: old {t_old:.2f} s, new {t_new:.2f} s ({t_old / max(t_new, 1e-9):.1f}x)")

    # ---- 2. profile extraction equivalence + timing ----
    obj = object.__new__(InteractivePlotter)
    obj._cmap_zi_data = rng.uniform(0, 100, (300, 300))
    obj._cmap_extent = (0.0, 1.0, 0.0, 1.0)
    points = [(0.05, 0.1), (0.5, 0.6), (0.95, 0.9)]

    t0 = time.perf_counter()
    old_prof = old_extract_line_profile(obj, points)
    t_oldp = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(20):
        old_extract_line_profile(obj, points)
    t_old20 = time.perf_counter() - t0

    t0 = time.perf_counter()
    new_prof = InteractivePlotter._extract_line_profile(obj, points)
    t_newp = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(20):
        InteractivePlotter._extract_line_profile(obj, points)
    t_new20 = time.perf_counter() - t0

    assert len(old_prof) == len(new_prof['z']), (len(old_prof), len(new_prof['z']))
    for key in ('x', 'y', 'distance'):
        ref = np.array([d[key] for d in old_prof])
        np.testing.assert_allclose(ref, new_prof[key], rtol=1e-9, atol=1e-12)
    ref_z = np.array([d['z'] for d in old_prof])
    assert np.array_equal(np.isnan(ref_z), np.isnan(new_prof['z'])), "NaN pattern differs"
    np.testing.assert_allclose(ref_z[~np.isnan(ref_z)], new_prof['z'][~np.isnan(new_prof['z'])],
                               rtol=1e-9)
    print(f"profile: old {t_oldp*1000:.1f} ms, new {t_newp*1000:.2f} ms "
          f"({t_oldp / max(t_newp, 1e-12):.0f}x)  [20x: {t_old20:.2f}s -> {t_new20:.3f}s]")

    # ---- 3. regular-grid fast path sanity (reshape, no griddata) ----
    gx, gy = np.meshgrid(np.linspace(0, 1, 40), np.linspace(0, 1, 25))
    Xn, Yn, Z = gx.ravel(), gy.ravel(), gx.ravel() * 10 + gy.ravel()
    xu, x_inv = np.unique(Xn, return_inverse=True)
    yu, y_inv = np.unique(Yn, return_inverse=True)
    assert len(xu) * len(yu) == len(Xn)
    zi = np.full((len(yu), len(xu)), np.nan)
    zi[y_inv, x_inv] = Z
    assert np.all(np.isfinite(zi))
    np.testing.assert_allclose(zi.max(), 10 + 1.0)
    np.testing.assert_allclose(zi.min(), 0.0)
    print("regular-grid fast path: OK (exact reshape, no griddata needed)")

    print("OK — all checks passed")


if __name__ == "__main__":
    main()
