# ==================== IMPORTS ====================
import os
import re
import sys
import json

import numpy as np

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# reuse the shared CSV loader from the Data analysis folder
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data analysis"))
from csv_utils import read_data_csv  # noqa: E402

POLAR_THETA_ZERO = ["N (top)", "E (0 deg, standard)", "W", "S"]
POLAR_THETA_ZERO_MAP = {"E (0 deg, standard)": "E", "N (top)": "N", "W": "W", "S": "S"}
POLAR_DIRECTION = ["Counter-clockwise", "Clockwise"]
POLAR_MARKERS = ["o", "s", "^", "D", "x", "+", "*", "None"]
ANGLE_DISPLAY = ["0 to 360", "-180 to 180", "-90 to 90"]


def format_angle_deg(deg, mode="0 to 360"):
    """Wrap a 0..360 angle into the chosen display convention."""
    deg = float(deg) % 360.0
    if mode == "-180 to 180":
        return ((deg + 180.0) % 360.0) - 180.0
    if mode == "-90 to 90":
        return ((deg + 90.0) % 180.0) - 90.0
    return deg
SLICE_MODES = ["Linear interpolation", "Nearest row"]

ANGLE_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:deg|°)", re.IGNORECASE)
ANY_NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


def detect_angle_from_name(name):
    """Guess the angle (degrees) from a filename; None if no guess."""
    stem = os.path.splitext(os.path.basename(name))[0]
    m = ANGLE_RE.search(stem)
    if m:
        return float(m.group(1))
    m = ANY_NUM_RE.search(stem)
    if m:
        return float(m.group(1))
    return None


def detect_angle(path):
    """Angle for a file: folder name first (folder-per-angle layout),
    fallback to the filename itself."""
    folder = os.path.basename(os.path.dirname(os.path.abspath(path)))
    a = detect_angle_from_name(folder) if folder else None
    return a if a is not None else detect_angle_from_name(path)



def value_at_x(xs, ys, x_target, mode="Linear interpolation"):
    """Value of y at x_target. xs need not be sorted; mode picks interp/nearest."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    mask = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[mask], ys[mask]
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    if mode == "Nearest row":
        return float(ys[np.argmin(np.abs(xs - x_target))])
    return float(np.interp(x_target, xs, ys))


class AngularPolarPlotter:
    """Polar slice plotter: one CSV per angle, radius = value at chosen x."""

    def __init__(self, root):
        self.root = root
        self.root.title("Angular Polar Slicer")
        self.root.geometry("1150x750")
        self.root.minsize(950, 600)

        self.files = []  # list of dicts: path, df, widgets

        # --- settings variables ---
        self.v_x_col = tk.StringVar()
        self.v_y_col = tk.StringVar()
        self.v_x_val = tk.StringVar()
        self.v_slice_mode = tk.StringVar(value=SLICE_MODES[0])
        self.v_theta_zero = tk.StringVar(value=POLAR_THETA_ZERO[0])
        self.v_direction = tk.StringVar(value=POLAR_DIRECTION[0])
        self.v_marker = tk.StringVar(value=POLAR_MARKERS[0])
        self.v_angle_display = tk.StringVar(value=ANGLE_DISPLAY[0])
        self.v_connect = tk.BooleanVar(value=True)
        self.v_close = tk.BooleanVar(value=False)
        self.v_r_offset = tk.BooleanVar(value=False)
        self.v_angle_labels = tk.BooleanVar(value=True)
        self.v_title = tk.StringVar(value="Angular Dependence")

        self._build_ui()

    # ==================== UI ====================
    def _build_ui(self):
        right = ttk.Frame(self.root, padding=4)
        right.pack(side='right', fill='both', expand=True)

        # ---- left panel: fully scrollable (small laptops) ----
        left_area = ttk.Frame(self.root)
        left_area.pack(side='left', fill='y')
        self.panel_canvas = tk.Canvas(left_area, highlightthickness=0, width=410)
        panel_scroll = ttk.Scrollbar(left_area, orient='vertical', command=self.panel_canvas.yview)
        left = ttk.Frame(self.panel_canvas, padding=8)
        left.bind(
            "<Configure>",
            lambda e: self.panel_canvas.configure(scrollregion=self.panel_canvas.bbox("all")))
        self._panel_win = self.panel_canvas.create_window((0, 0), window=left, anchor='nw')
        self.panel_canvas.bind(
            "<Configure>",
            lambda e: self.panel_canvas.itemconfigure(self._panel_win, width=e.width))
        self.panel_canvas.configure(yscrollcommand=panel_scroll.set)
        self.panel_canvas.pack(side='left', fill='both', expand=True)
        panel_scroll.pack(side='right', fill='y')
        # one global wheel handler: scroll whichever area the pointer is over
        # (file list if over it, otherwise the settings panel)
        self.root.bind_all("<MouseWheel>", self._on_wheel)

        # ---- left panel content ----
        ttk.Button(left, text="Load CSV Files...", command=self.load_files).pack(fill='x', pady=2)
        ttk.Button(left, text="Add Angle Folder...", command=self.load_folder).pack(fill='x', pady=2)
        ttk.Button(left, text="Remove Unchecked", command=self.remove_unchecked).pack(fill='x', pady=2)
        sess = ttk.Frame(left)
        sess.pack(fill='x', pady=2)
        ttk.Button(sess, text="Save Session", command=self.save_session).pack(side='left', fill='x', expand=True, padx=1)
        ttk.Button(sess, text="Load Session", command=self.load_session).pack(side='left', fill='x', expand=True, padx=1)

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=6)
        ttk.Label(left, text="Files (uncheck to skip, angle editable)",
                  font=('Arial', 10, 'bold')).pack(anchor='w')

        file_area = ttk.Frame(left)
        file_area.pack(fill='both', expand=True)
        self.file_canvas = tk.Canvas(file_area, highlightthickness=0, height=180)
        file_scroll = ttk.Scrollbar(file_area, orient='vertical', command=self.file_canvas.yview)
        self.file_inner = ttk.Frame(self.file_canvas)
        self.file_inner.bind(
            "<Configure>",
            lambda e: self.file_canvas.configure(scrollregion=self.file_canvas.bbox("all")))
        self._file_win = self.file_canvas.create_window((0, 0), window=self.file_inner, anchor='nw')
        # keep inner frame the same width as the canvas so long rows don't
        # force the canvas (and the whole window) to grow instead of scrolling
        self.file_canvas.bind(
            "<Configure>",
            lambda e: self.file_canvas.itemconfigure(self._file_win, width=e.width))
        self.file_canvas.configure(yscrollcommand=file_scroll.set)
        self.file_canvas.pack(side='left', fill='both', expand=True)
        file_scroll.pack(side='right', fill='y')

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=6)
        f = ttk.Frame(left)
        f.pack(fill='x', pady=1)
        ttk.Label(f, text="X column:", width=12).pack(side='left')
        self.x_col_combo = ttk.Combobox(f, textvariable=self.v_x_col, state='readonly')
        self.x_col_combo.pack(side='left', fill='x', expand=True)
        self.x_col_combo.bind(
            "<<ComboboxSelected>>", lambda e: (self.update_x_range_label(), self.update_plot()))
        f = ttk.Frame(left)
        f.pack(fill='x', pady=1)
        ttk.Label(f, text="Y column:", width=12).pack(side='left')
        self.y_col_combo = ttk.Combobox(f, textvariable=self.v_y_col, state='readonly')
        self.y_col_combo.pack(side='left', fill='x', expand=True)
        ttk.Label(left, text="X value(s) to slice at\n(comma-separated for several):").pack(anchor='w')
        ttk.Entry(left, textvariable=self.v_x_val).pack(fill='x')
        self.x_range_label = ttk.Label(left, text="x range: (no files loaded)",
                                       foreground='gray', font=('Arial', 8))
        self.x_range_label.pack(anchor='w')
        for mode in SLICE_MODES:
            ttk.Radiobutton(left, text=mode, variable=self.v_slice_mode, value=mode).pack(anchor='w')

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=6)
        self._combo_row(left, "Theta zero:", self.v_theta_zero, POLAR_THETA_ZERO)
        self._combo_row(left, "Direction:", self.v_direction, POLAR_DIRECTION)
        self._combo_row(left, "Marker:", self.v_marker, POLAR_MARKERS)
        self._combo_row(left, "Angle display:", self.v_angle_display, ANGLE_DISPLAY)
        ttk.Checkbutton(left, text="Connect points (sorted by angle)", variable=self.v_connect).pack(anchor='w')
        ttk.Checkbutton(left, text="Close circle (append first point)", variable=self.v_close).pack(anchor='w')
        ttk.Checkbutton(left, text="Offset R (subtract min value)", variable=self.v_r_offset).pack(anchor='w')
        ttk.Checkbutton(left, text="Show angle labels", variable=self.v_angle_labels).pack(anchor='w')
        ttk.Label(left, text="Title:").pack(anchor='w')
        ttk.Entry(left, textvariable=self.v_title).pack(fill='x')

        ttk.Button(left, text="Update Plot", command=self.update_plot).pack(fill='x', pady=6)
        # Enter anywhere in the panel also refreshes the plot
        self.root.bind("<Return>", lambda e: self.update_plot())

        # ---- right panel: matplotlib ----
        self.fig = plt.Figure(figsize=(7, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.ax = self.fig.add_subplot(111, projection='polar')

    def _combo_row(self, parent, label, var, values):
        f = ttk.Frame(parent)
        f.pack(fill='x', pady=1)
        ttk.Label(f, text=label, width=12).pack(side='left')
        ttk.Combobox(f, textvariable=var, values=values, state='readonly').pack(
            side='left', fill='x', expand=True)

    def _on_wheel(self, event):
        """Scroll the file list if the pointer is over it, else the settings panel."""
        steps = -event.delta // 120
        w = event.widget
        while w is not None:
            if w is self.file_canvas:
                self.file_canvas.yview_scroll(steps, "units")
                return
            if w is self.panel_canvas:
                self.panel_canvas.yview_scroll(steps, "units")
                return
            w = getattr(w, 'master', None)

    # ==================== FILE HANDLING ====================
    def load_files(self):
        paths = filedialog.askopenfilenames(
            title="Select angle-scan CSV files",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        for p in paths:
            try:
                df = read_data_csv(p)
            except Exception as e:
                messagebox.showerror("Load Error", f"{os.path.basename(p)}:\n{e}")
                continue
            if df.height == 0 or df.width < 2:
                messagebox.showwarning("Skipped", f"{os.path.basename(p)}: no data columns")
                continue
            self.files.append({"path": p, "df": df, "widgets": {}})
        self.refresh_file_rows()
        self.refresh_x_columns()
        self.update_plot()

    def load_folder(self):
        """Pick a folder; every CSV directly inside gets the folder's angle."""
        folder = filedialog.askdirectory(title="Select an angle folder")
        if not folder:
            return
        paths = sorted(
            os.path.join(folder, n) for n in os.listdir(folder)
            if n.lower().endswith('.csv'))
        if not paths:
            messagebox.showwarning("No CSVs", f"No CSV files directly inside:\n{folder}")
            return
        for p in paths:
            try:
                df = read_data_csv(p)
            except Exception as e:
                messagebox.showerror("Load Error", f"{os.path.basename(p)}:\n{e}")
                continue
            if df.height == 0 or df.width < 2:
                continue
            self.files.append({"path": p, "df": df, "widgets": {}})
        self.refresh_file_rows()
        self.refresh_x_columns()
        self.update_plot()

    # ==================== SESSION ====================
    def _session_settings(self):
        return {
            "x_col": self.v_x_col.get(), "y_col": self.v_y_col.get(),
            "x_val": self.v_x_val.get(), "slice_mode": self.v_slice_mode.get(),
            "theta_zero": self.v_theta_zero.get(), "direction": self.v_direction.get(),
            "marker": self.v_marker.get(), "angle_display": self.v_angle_display.get(),
            "connect": self.v_connect.get(),
            "close": self.v_close.get(), "r_offset": self.v_r_offset.get(),
            "angle_labels": self.v_angle_labels.get(), "title": self.v_title.get(),
        }

    def save_session(self):
        path = filedialog.asksaveasfilename(
            title="Save Session", defaultextension=".json",
            filetypes=[("JSON session", "*.json")])
        if not path:
            return
        try:
            files = []
            for e in self.files:
                w = e["widgets"]
                files.append({
                    "path": e["path"],
                    "angle": w["angle_var"].get() if w.get("angle_var") else "",
                    "keep": bool(w["keep_var"].get()) if w.get("keep_var") else True,
                    "columns": list(e["df"].columns),
                    "rows": e["df"].rows(),
                })
            out = {"settings": self._session_settings(), "files": files}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f)
            messagebox.showinfo("Session Saved", f"Saved {len(files)} file(s) to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_session(self):
        path = filedialog.askopenfilename(
            title="Load Session", filetypes=[("JSON session", "*.json")])
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            import polars as pl
            self.files = []
            for rec in data.get("files", []):
                cols = rec["columns"]
                rows = rec["rows"]
                df = pl.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(cols)})
                self.files.append({"path": rec.get("path", "?"), "df": df,
                                   "widgets": {"session_angle": rec.get("angle", ""),
                                               "session_keep": rec.get("keep", True)}})
            s = data.get("settings", {})
            for key, var in [
                ("x_val", self.v_x_val), ("slice_mode", self.v_slice_mode),
                ("theta_zero", self.v_theta_zero), ("direction", self.v_direction),
                ("marker", self.v_marker), ("title", self.v_title),
                ("angle_display", self.v_angle_display),
                ("x_col", self.v_x_col), ("y_col", self.v_y_col),
            ]:
                if s.get(key):
                    var.set(s[key])
            for key, var in [
                ("connect", self.v_connect), ("close", self.v_close),
                ("r_offset", self.v_r_offset), ("angle_labels", self.v_angle_labels),
            ]:
                if key in s:
                    var.set(bool(s[key]))
            self.refresh_file_rows()  # rebuilds widgets from session_angle/_keep
            self.refresh_x_columns()
            self.update_plot()
            messagebox.showinfo("Session Loaded", f"Loaded {len(self.files)} file(s).")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def remove_unchecked(self):
        self.files = [e for e in self.files
                      if e["widgets"].get("keep_var") and e["widgets"]["keep_var"].get()]
        self.refresh_file_rows()
        self.refresh_x_columns()
        self.update_plot()

    def refresh_file_rows(self):
        for w in self.file_inner.winfo_children():
            w.destroy()
        for entry in self.files:
            row = ttk.Frame(self.file_inner)
            row.pack(fill='x', pady=1)
            sw = entry["widgets"]
            keep = tk.BooleanVar(value=bool(sw.get("session_keep", True)))
            angle = tk.StringVar(value=sw.get("session_angle", "") or "")
            if not angle.get():
                guessed = detect_angle(entry["path"])
                if guessed is not None:
                    angle.set(f"{guessed:g}")
            ttk.Checkbutton(row, variable=keep).pack(side='left')
            ttk.Label(row, text=os.path.basename(entry["path"]), width=30,
                      anchor='w', relief='groove').pack(side='left', padx=1, fill='x', expand=True)
            ttk.Label(row, text="angle:").pack(side='left')
            ttk.Entry(row, textvariable=angle, width=7).pack(side='left', padx=1)
            entry["widgets"] = {"row": row, "keep_var": keep, "angle_var": angle}

    def refresh_x_columns(self):
        cols = list(self.files[0]["df"].columns) if self.files else []
        self.x_col_combo['values'] = cols
        self.y_col_combo['values'] = cols
        if cols and self.v_x_col.get() not in cols:
            # first column is time(s); x is normally the second column
            self.v_x_col.set(cols[1] if len(cols) > 1 else cols[0])
        if cols and self.v_y_col.get() not in cols:
            self.v_y_col.set(cols[-1])
        self.update_x_range_label()

    def update_x_range_label(self):
        """Show the x range of the currently chosen X column across all files."""
        if not self.files:
            self.x_range_label.config(text="x range: (no files loaded)")
            return
        try:
            lo, hi = np.inf, -np.inf
            for e in self.files:
                xs = np.asarray(e["df"][self.v_x_col.get()].to_numpy(), dtype=float)
                xs = xs[np.isfinite(xs)]
                if xs.size:
                    lo, hi = min(lo, xs.min()), max(hi, xs.max())
            if np.isfinite(lo):
                self.x_range_label.config(text=f"x range in files: {lo:g} to {hi:g}")
        except Exception:
            pass
        if self.files and not self.v_x_val.get():
            try:
                xs = self.files[0]["df"][self.v_x_col.get()].to_numpy()
                self.v_x_val.set(f"{float(np.nanmax(xs)):g}")
            except Exception:
                pass

    # ==================== PLOTTING ====================
    def update_plot(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.ax.set_theta_zero_location(POLAR_THETA_ZERO_MAP.get(self.v_theta_zero.get(), "N"))
        direction = -1 if self.v_direction.get() == "Clockwise" else 1
        self.ax.set_theta_direction(direction)

        # theta tick labels in the chosen angle convention
        disp = self.v_angle_display.get()
        tick_degs = np.arange(0, 360, 30)
        self.ax.set_xticks(np.deg2rad(tick_degs))
        self.ax.set_xticklabels([f"{format_angle_deg(d, disp):g}\u00b0" for d in tick_degs])

        try:
            x_targets = [float(v.strip()) for v in self.v_x_val.get().split(',') if v.strip()]
        except ValueError:
            self.ax.set_title("enter valid X value(s), e.g. 5 or 5, 10, 15", fontsize=10)
            self.canvas.draw()
            return
        if not x_targets:
            self.ax.set_title("enter at least one X value", fontsize=10)
            self.canvas.draw()
            return

        x_col = self.v_x_col.get()
        y_col = self.v_y_col.get()
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        any_clamped = False
        plotted = 0

        for k, x_target in enumerate(x_targets):
            points = []  # (theta_deg, r)
            clamped = False
            for entry in self.files:
                w = entry["widgets"]
                if not (w and w.get("keep_var") and w["keep_var"].get()):
                    continue
                try:
                    theta = float(w["angle_var"].get())
                except (ValueError, TypeError):
                    continue  # no angle set -> skip
                df = entry["df"]
                if x_col not in df.columns or y_col not in df.columns:
                    continue
                xs = np.asarray(df[x_col].to_numpy(), dtype=float)
                xs = xs[np.isfinite(xs)]
                if xs.size and (x_target < xs.min() or x_target > xs.max()):
                    clamped = True
                try:
                    r = value_at_x(xs, df[y_col].to_numpy(), x_target, self.v_slice_mode.get())
                except Exception:
                    continue
                points.append((theta, r))
            any_clamped = any_clamped or clamped
            if not points:
                continue

            thetas = np.deg2rad([p[0] for p in points])
            rs = np.array([p[1] for p in points])
            if self.v_r_offset.get():
                rs = rs - rs.min()

            order = np.argsort(thetas)
            thetas, rs = thetas[order], rs[order]
            marker = None if self.v_marker.get() == "None" else self.v_marker.get()
            color = colors[k % len(colors)]
            label = f"x = {x_target:g} @ {x_col}"

            if self.v_connect.get():
                if self.v_close.get():
                    thetas = np.append(thetas, thetas[0] + 2 * np.pi)
                    rs = np.append(rs, rs[0])
                self.ax.plot(thetas, rs, marker=marker, markersize=6, linewidth=2,
                             color=color, label=label)
            else:
                self.ax.plot(thetas, rs, marker=marker or 'o', markersize=6,
                             linestyle='', color=color, label=label)

            if self.v_angle_labels.get():
                for t, r in zip(thetas, rs):
                    self.ax.annotate(f"{format_angle_deg(np.rad2deg(t), disp):g}\u00b0",
                                     xy=(t, r),
                                     fontsize=8, ha='center', va='bottom', color=color)
            plotted += 1

        if not plotted:
            self.ax.set_title("no points (check angle / x settings)", fontsize=10)
            self.canvas.draw()
            return

        if len(x_targets) > 1:
            self.ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1), fontsize=9)

        title = f"{self.v_title.get()}"
        if len(x_targets) == 1:
            title += f"   (x = {x_targets[0]:g} @ {x_col})"
        if any_clamped:
            title += "\nWARNING: x outside range for some file(s), clamped to end value"
        self.ax.set_title(title, fontsize=11, fontweight='bold', pad=20)
        self.canvas.draw()


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        # interpolation picks the right value, sorted or not
        assert value_at_x([0, 10, 20, 30], [1, 3, 5, 7], 15) == 4.0
        assert value_at_x([30, 0, 20, 10], [7, 1, 5, 3], 15) == 4.0
        assert value_at_x([0, 10, 20], [1, 3, 5], 19, "Nearest row") == 5
        # clamps outside range like np.interp
        assert value_at_x([0, 10], [1, 3], -5) == 1.0
        # angle detection from filenames
        assert detect_angle_from_name("sample_30deg.csv") == 30.0
        assert detect_angle_from_name("run 12.5 deg.csv") == 12.5
        assert detect_angle_from_name("phi-45.csv") == -45.0
        assert detect_angle_from_name("no numbers here.csv") is None
        # folder name wins over filename; filename wins when folder has no number
        assert detect_angle(r"C:\data\30 deg\run1.csv") == 30.0
        assert detect_angle(r"C:\data\30 deg\75deg.csv") == 30.0
        assert detect_angle(r"C:\data\runs\75deg.csv") == 75.0
        # angle display conventions
        assert format_angle_deg(270, "-180 to 180") == -90.0
        assert format_angle_deg(180, "-180 to 180") == -180.0
        assert format_angle_deg(135, "-90 to 90") == -45.0
        assert format_angle_deg(90, "-90 to 90") == -90.0
        assert format_angle_deg(45, "0 to 360") == 45.0
        print("angular polar self-check OK")
        sys.exit(0)

    root = tk.Tk()
    app = AngularPolarPlotter(root)
    root.mainloop()
