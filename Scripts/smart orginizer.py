import polars as pl
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os


class ScanOrganizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Scan Organizer")
        self.root.geometry("400x250")

        # --- Force Window to Front ---
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        # --- UI Setup ---
        tk.Label(self.root, text="Select Scan Type:", font=("Arial", 11, "bold")).pack(pady=10)

        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(self.root, textvariable=self.mode_var, state="readonly", width=40)
        self.mode_combo['values'] = (
            "Smart Split (Fast & Slow Axis - Auto Detect)",
            "Hysteresis - Auto Detect (0 -> SP1 -> SP2 -> 0)",
            "Standard Loop - Auto Detect (0 -> Max -> 0)",
            "Snake - Auto Detect (Alternating)"
        )
        self.mode_combo.current(0)
        self.mode_combo.pack(pady=5)

        tk.Label(self.root, text="Note: All modes auto-detect sweeps from a chosen axis column.",
                 font=("Arial", 8), fg="gray").pack(pady=0)

        tk.Button(self.root, text="Select File & Run", command=self.process_selection, height=2, width=20).pack(pady=20)

    def process_selection(self):
        mode = self.mode_var.get()

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select your Data CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)

            # Route to correct logic
            if "Smart Split" in mode:
                self.process_smart_axis_split(df, file_path)
            elif "Hysteresis" in mode:
                self.process_hysteresis(df, file_path)
            elif "Standard Loop" in mode:
                self.process_standard_loop(df, file_path)
            elif "Snake" in mode:
                self.process_snake(df, file_path)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    # =========================================================
    # SHARED HELPERS
    # =========================================================
    def _ask_axis_and_threshold(self, df, title_prefix="Axis"):
        """Ask user to select an axis column and change threshold.
        Returns (col_name, threshold) or (None, None) if cancelled."""
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
            return None, None

        # --- Column selection dialog ---
        col_window = tk.Toplevel(self.root)
        col_window.title(f"Select {title_prefix} Column")
        col_window.geometry("320x180")
        col_window.lift()

        result = {'col': None}

        tk.Label(col_window, text=f"Which column is the {title_prefix}?",
                 font=("Arial", 10)).pack(pady=10)
        col_var = tk.StringVar()
        col_box = ttk.Combobox(col_window, textvariable=col_var, values=columns,
                               state="readonly", width=35)
        col_box.current(0)
        col_box.pack(pady=5)

        def on_confirm():
            result['col'] = col_var.get()
            col_window.destroy()

        tk.Button(col_window, text="Confirm", command=on_confirm, width=15).pack(pady=20)
        self.root.wait_window(col_window)

        if result['col'] is None:
            return None, None

        # --- Threshold dialog ---
        col = result['col']
        col_range = df[col].max() - df[col].min()
        default_thresh = col_range * 0.01

        threshold = simpledialog.askfloat(
            "Change Threshold",
            f"Enter change threshold for '{col}':\n"
            f"(If |change| < this value, the axis is considered constant)\n"
            f"Default (1% of range): {default_thresh:.6g}",
            initialvalue=default_thresh, parent=self.root)

        if threshold is None:
            return None, None

        return col, threshold

    def _auto_detect_sweeps(self, df, axis_col, threshold):
        """Detect sweep segments where the axis is changing (not constant).
        Returns a list of DataFrames, each being one sweep segment,
        plus the modified df (with helper columns) for reference."""
        df = df.with_columns([
            (pl.col(axis_col).diff().abs() < threshold).alias("axis_is_constant")
        ])
        df = df.with_columns([
            (pl.col("axis_is_constant") != pl.col("axis_is_constant").shift(1))
            .cum_sum().alias("segment_id")
        ])

        sweeps = []
        grouped = df.group_by('segment_id', maintain_order=True)
        for seg_id, segment in grouped:
            if len(segment) < 3:
                continue
            is_constant = segment["axis_is_constant"].mode()[0]
            if not is_constant:
                sweeps.append(segment.drop(['axis_is_constant', 'segment_id']))

        return sweeps

    # =========================================================
    # MODE: Smart Split (Fast & Slow Axis - Auto Detect)
    # =========================================================
    def process_smart_axis_split(self, df, file_path):
        """Ask user to select Fast Axis and Slow Axis columns."""
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
            return

        col_window = tk.Toplevel(self.root)
        col_window.title("Select Axis Columns")
        col_window.geometry("350x250")
        col_window.lift()

        # Fast Axis selection
        tk.Label(col_window, text="Fast Axis (swept while slow axis holds):",
                 font=("Arial", 10)).pack(pady=(15, 2))
        fast_var = tk.StringVar()
        fast_box = ttk.Combobox(col_window, textvariable=fast_var, values=columns,
                                state="readonly", width=35)
        fast_box.current(0)
        fast_box.pack(pady=2)

        # Slow Axis selection
        tk.Label(col_window, text="Slow Axis (holds while fast axis sweeps):",
                 font=("Arial", 10)).pack(pady=(15, 2))
        slow_var = tk.StringVar()
        slow_box = ttk.Combobox(col_window, textvariable=slow_var, values=columns,
                                state="readonly", width=35)
        slow_box.current(min(1, len(columns) - 1))
        slow_box.pack(pady=2)

        def on_confirm():
            if fast_var.get() == slow_var.get():
                messagebox.showwarning("Warning", "Fast and Slow axis must be different columns.",
                                       parent=col_window)
                return
            col_window.destroy()
            self.run_smart_split_logic(df, file_path, fast_var.get(), slow_var.get())

        tk.Button(col_window, text="Confirm", command=on_confirm, width=15).pack(pady=20)
        self.root.wait_window(col_window)

    def run_smart_split_logic(self, df, file_path, fast_col, slow_col):
        """Detect segments and classify into Fast Fwd/Bwd and Slow@setpoint groups."""
        # --- Threshold Settings ---
        fast_range = df[fast_col].max() - df[fast_col].min()
        default_fast_thresh = fast_range * 0.01

        fast_threshold = simpledialog.askfloat(
            "Fast Axis Threshold",
            f"Enter Fast Axis ('{fast_col}') Change Threshold:\n"
            f"(If |change| < this value, fast axis is considered constant)\n"
            f"Default (1% of range): {default_fast_thresh:.6g}",
            initialvalue=default_fast_thresh, parent=self.root)
        if fast_threshold is None:
            return

        slow_range = df[slow_col].max() - df[slow_col].min()
        default_slow_tol = slow_range * 0.01

        slow_tolerance = simpledialog.askfloat(
            "Slow Axis Tolerance",
            f"Enter Slow Axis ('{slow_col}') Setpoint Tolerance:\n"
            f"(Values within this tolerance are grouped into the same setpoint)\n"
            f"Default (1% of range): {default_slow_tol:.6g}",
            initialvalue=default_slow_tol, parent=self.root)
        if slow_tolerance is None:
            return

        # --- Segment Detection on Fast Axis ---
        df = df.with_columns([
            (pl.col(fast_col).diff().abs() < fast_threshold).alias("fast_is_constant")
        ])
        df = df.with_columns([
            (pl.col("fast_is_constant") != pl.col("fast_is_constant").shift(1))
            .cum_sum().alias("segment_id")
        ])

        # --- Classify fast-sweep vs slow-sweep segments ---
        grouped = df.group_by('segment_id', maintain_order=True)

        fast_fwd_segments = []
        fast_bwd_segments = []
        slow_segments = []
        slow_mean_values = []

        for seg_id, segment in grouped:
            if len(segment) < 3:
                continue

            is_constant = segment["fast_is_constant"].mode()[0]

            if is_constant:
                avg_slow = segment[slow_col].mean()
                slow_segments.append(segment)
                slow_mean_values.append(avg_slow)
            else:
                start_val = segment[fast_col][0]
                end_val = segment[fast_col][-1]

                if end_val > start_val:
                    fast_fwd_segments.append(segment)
                else:
                    fast_bwd_segments.append(segment)

        # --- Cluster Slow Axis Setpoints ---
        setpoint_map = self._cluster_setpoints(slow_mean_values, slow_tolerance)

        slow_by_setpoint = {sp: [] for sp in setpoint_map.values()}
        for segment, mean_val in zip(slow_segments, slow_mean_values):
            sp_key = setpoint_map[mean_val]
            slow_by_setpoint[sp_key].append(segment)

        # --- Clean up helper columns ---
        for seg_list in [fast_fwd_segments, fast_bwd_segments] + list(slow_by_setpoint.values()):
            for i, chunk in enumerate(seg_list):
                seg_list[i] = chunk.drop(['fast_is_constant', 'segment_id'])

        # --- Save Files ---
        self.save_files_smart(file_path, fast_col, slow_col,
                              fast_fwd_segments, fast_bwd_segments, slow_by_setpoint)

    @staticmethod
    def _cluster_setpoints(values, tolerance):
        """Cluster numeric values into setpoints within the given tolerance."""
        if not values:
            return {}

        sorted_vals = sorted(values)
        clusters = []
        current_cluster = [sorted_vals[0]]

        for val in sorted_vals[1:]:
            if val - current_cluster[-1] <= tolerance:
                current_cluster.append(val)
            else:
                clusters.append(current_cluster)
                current_cluster = [val]
        clusters.append(current_cluster)

        cluster_means = [sum(c) / len(c) for c in clusters]

        mapping = {}
        for val in values:
            nearest_idx = min(range(len(cluster_means)),
                              key=lambda i: abs(cluster_means[i] - val))
            mapping[val] = cluster_means[nearest_idx]

        return mapping

    def save_files_smart(self, original_path, fast_col, slow_col,
                         fast_fwd, fast_bwd, slow_by_setpoint):
        """Save split files with generic naming based on axis columns."""
        directory = os.path.dirname(original_path)
        name = os.path.splitext(os.path.basename(original_path))[0]

        df_fwd = pl.concat(fast_fwd) if fast_fwd else pl.DataFrame()
        df_bwd = pl.concat(fast_bwd) if fast_bwd else pl.DataFrame()

        df_fwd.write_csv(os.path.join(directory, f"{name}_{fast_col}_Fwd.csv"))
        df_bwd.write_csv(os.path.join(directory, f"{name}_{fast_col}_Bwd.csv"))

        slow_info = []
        sorted_setpoints = sorted(slow_by_setpoint.keys())
        for idx, sp_val in enumerate(sorted_setpoints, start=1):
            segments = slow_by_setpoint[sp_val]
            if not segments:
                continue
            df_sp = pl.concat(segments)
            sp_str = f"{sp_val:.6g}"
            df_sp.write_csv(os.path.join(directory, f"{name}_{slow_col}_at_{sp_str}.csv"))
            slow_info.append(f"  {slow_col} @ {sp_str} -> {len(df_sp)} rows")

        msg_lines = [
            "Processing Complete!\n",
            f"Fast Axis: '{fast_col}'",
            f"  Fwd sweep: {len(df_fwd)} rows",
            f"  Bwd sweep: {len(df_bwd)} rows\n",
            f"Slow Axis: '{slow_col}' - {len(slow_info)} setpoint(s):"
        ]
        msg_lines.extend(slow_info)

        msg = "\n".join(msg_lines)
        print(msg)
        messagebox.showinfo("Success", msg)
        self.root.quit()

    # =========================================================
    # MODE: Snake - Auto Detect
    # =========================================================
    def process_snake(self, df, file_path):
        """Auto-detect sweeps and alternate them into Fwd/Bwd."""
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Sweep Axis")
        if axis_col is None:
            return

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return

        fwd, bwd = [], []
        for i, sweep in enumerate(sweeps):
            if i % 2 == 0:
                fwd.append(sweep)
            else:
                bwd.append(sweep)

        self.save_simple(file_path, fwd, bwd, f"Snake_{axis_col}")

    # =========================================================
    # MODE: Standard Loop - Auto Detect
    # =========================================================
    def process_standard_loop(self, df, file_path):
        """Auto-detect sweeps, group into cycles, split into Fwd/Bwd."""
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Loop Axis")
        if axis_col is None:
            return

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return

        sweeps_per_cycle = simpledialog.askinteger(
            "Config", f"Detected {len(sweeps)} sweeps.\nSweeps per cycle:",
            initialvalue=2, parent=self.root)
        if not sweeps_per_cycle:
            return

        split = simpledialog.askinteger(
            "Config", "Forward sweeps per cycle:",
            initialvalue=sweeps_per_cycle // 2, parent=self.root)
        if split is None:
            return

        fwd, bwd = [], []
        for i in range(0, len(sweeps), sweeps_per_cycle):
            block = sweeps[i:i + sweeps_per_cycle]
            if len(block) < sweeps_per_cycle:
                break
            fwd.extend(block[:split])
            bwd.extend(block[split:])

        self.save_simple(file_path, fwd, bwd, f"StandardLoop_{axis_col}")

    # =========================================================
    # MODE: Hysteresis - Auto Detect
    # =========================================================
    def process_hysteresis(self, df, file_path):
        """Auto-detect sweeps, group into hysteresis blocks, split by sweep indices."""
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Hysteresis Axis")
        if axis_col is None:
            return

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return

        sweeps_per_block = simpledialog.askinteger(
            "Config", f"Detected {len(sweeps)} sweeps.\nSweeps per hysteresis block:",
            initialvalue=3, parent=self.root)
        if not sweeps_per_block:
            return

        s1 = simpledialog.askinteger(
            "Config",
            "Split 1 (sweep index where backward starts):\n"
            "(Sweeps 0..s1-1 are Forward part 1)",
            initialvalue=1, parent=self.root)
        if s1 is None:
            return

        s2 = simpledialog.askinteger(
            "Config",
            "Split 2 (sweep index where forward resumes):\n"
            f"(Sweeps {s1}..s2-1 are Backward, sweeps {s1}..end are Forward part 2)",
            initialvalue=2, parent=self.root)
        if s2 is None:
            return

        fwd, bwd = [], []
        for i in range(0, len(sweeps), sweeps_per_block):
            block = sweeps[i:i + sweeps_per_block]
            if len(block) < sweeps_per_block:
                break
            fwd.extend(block[:s1])
            fwd.extend(block[s2:])
            bwd.extend(block[s1:s2])

        self.save_simple(file_path, fwd, bwd, f"Hysteresis_{axis_col}")

    # =========================================================
    # SHARED SAVER (Snake, Standard Loop, Hysteresis)
    # =========================================================
    def save_simple(self, path, fwd, bwd, suffix):
        df_f = pl.concat(fwd) if fwd else pl.DataFrame()
        df_b = pl.concat(bwd) if bwd else pl.DataFrame()
        d = os.path.dirname(path)
        n = os.path.splitext(os.path.basename(path))[0]

        msg_lines = [f"Processing Complete! ({suffix})\n"]
        if len(df_f) > 0:
            df_f.write_csv(os.path.join(d, f"{n}_{suffix}_Fwd.csv"))
            msg_lines.append(f"Fwd: {len(df_f)} rows")
        if len(df_b) > 0:
            df_b.write_csv(os.path.join(d, f"{n}_{suffix}_Bwd.csv"))
            msg_lines.append(f"Bwd: {len(df_b)} rows")

        msg = "\n".join(msg_lines)
        print(msg)
        messagebox.showinfo("Success", msg)
        self.root.quit()


if __name__ == "__main__":
    app = ScanOrganizer()
    app.root.mainloop()