"""Self-check for the 3D Line plot type (run: python "Plotter/test_3d_line.py")."""
import importlib.util
import os

import numpy as np
import polars as pl
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("plot_data", os.path.join(HERE, "Plot data.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# Never block on error popups during the test
mod.messagebox.showerror = lambda *a, **k: print("ERROR DIALOG:", a[-1] if a else k)
mod.messagebox.showinfo = lambda *a, **k: print("INFO DIALOG:", a[-1] if a else k)

root = tk.Tk()
root.withdraw()
app = mod.InteractivePlotter(root)

# Synthetic 2-SMU sweep: SMU1 swept at each SMU2 step, lockin = f(SMU1, SMU2)
xs, ys, zs = [], [], []
for y in np.linspace(-2.0, 2.0, 9):
    for x in np.linspace(-1.0, 1.0, 41):
        xs.append(x); ys.append(y); zs.append(np.sin(3 * x + y))
df = pl.DataFrame({"SMU1": xs, "SMU2": ys, "LockIn": zs})
app.datasets["sweep.csv"] = df
app.refresh_dataset_list(new_load=True)

app.plot_type.set("3D Line")
app.x_combo.set("SMU1")
app.y_listbox.selection_clear(0, tk.END)
app.y_listbox.selection_set(list(app.y_listbox.get(0, tk.END)).index("SMU2"))
app.z_combo.set("LockIn")
app.dataset_listbox.selection_clear(0, tk.END)
app.dataset_listbox.selection_set(0)
app.update_plot()
root.update_idletasks()

from mpl_toolkits.mplot3d import Axes3D
assert isinstance(app.ax, Axes3D), "axes are not 3D"
n3d = len(app.ax.lines)
assert n3d == 9, f"expected 9 sweep lines, got {n3d}"

# Perpendicular cross-sweeps at fixed X values
app.v_3d_cross_x.set("0, 0.5")
app.update_plot()
n3d = len(app.ax.lines)
assert n3d == 11, f"expected 9 X-sweeps + 2 Y-sweeps, got {n3d}"
# The 2 cross lines must run along Y (constant X)
for ln in app.ax.lines[9:]:
    xd, yd, zd = ln.get_data_3d()  # 3D data (get_xdata gives projected 2D)
    assert np.allclose(xd, xd[0]), "cross line X is not constant"
    assert not np.allclose(yd, yd[0]), "cross line Y is constant (should vary)"
app.v_3d_cross_x.set("all")
app.update_plot()
assert len(app.ax.lines) == 9 + 41, f"'all' cross mode wrong: {len(app.ax.lines)}"
app.v_3d_cross_x.set("")

# Visibility toggle (context menu / legend click path)
app.hidden_legend_items.add(("sweep.csv", "SMU2"))
app.update_plot()
vis = sum(1 for ln in app.ax.lines if ln.get_visible())
assert vis == 0, f"hidden series still visible: {vis}"
app.hidden_legend_items.clear()

# Legend + view control via Elev/Azim entries
app.show_legend.set(True)
app.v_3d_elev.set("30")
app.v_3d_azim.set("-60")
app.update_plot()
assert app.ax.get_legend() is not None, "legend missing"
assert (round(app.ax.elev), round(app.ax.azim)) == (30, -60), "view not applied"
# Live entry update (no replot): entry trace re-aims the current axes
app.v_3d_azim.set("45")
assert round(app.ax.azim) == 45, "live azim update failed"
app.v_3d_elev.set("10")
assert round(app.ax.elev) == 10, "live elev update failed"

out = os.path.join(HERE, "test_3d_line.png")
app.fig.savefig(out, dpi=100)
assert os.path.getsize(out) > 1000, "PNG looks empty"
print("OK: 9 sweeps plotted, hide/show toggle, legend, view control, PNG saved:", out)
root.destroy()
