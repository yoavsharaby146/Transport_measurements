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
            "Gate Map - Direction Split (Fwd/Bwd)",
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
            elif "Gate Map" in mode:
                self.process_gate_map(df, file_path)
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

    def _ask_axis_column(self, df, title_prefix="Axis"):
        """Ask user to select an axis column only. Returns col_name or None."""
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
            return None

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

        return result['col']

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
    # MODE: Gate Map - Direction Split (Fwd/Bwd)
    # =========================================================
    def _detect_direction_segments(self, df, axis_col, threshold,
                                   slow_col=None, slow_threshold=0.0):
        """Detect sweep segments based on direction (sign) of change.

        Uses backward-fill for zero-diff rows so that boundary repetitions
        are correctly assigned to the *upcoming* sweep direction.
        E.g. at the forward→backward turn-around where the value 3 repeats:
            ..., 2.995, 3, 3, 2.995, ...
        the first 3 (arriving via +0.005 diff) stays Forward,
        the second 3 (diff=0, back-filled with next non-zero = -1) goes Backward.

        If `slow_col` is provided, zero-diff regions where the slow axis is
        *actively changing* (e.g. a magnetic-field sweep between fast sweeps)
        are NOT back-filled — they are kept as 'flat' segments so they can be
        separated out. Only genuine turn-around pauses (slow axis constant)
        are back-filled into the upcoming sweep direction.

        Returns list of (segment_df, direction_str) tuples.
        direction_str is 'forward', 'backward', or 'flat'.
        """
        values = df[axis_col].to_numpy()
        n = len(values)

        if n < 2:
            return [(df, 'forward')]

        # 1. Compute diffs: diffs[i] = values[i+1] - values[i]
        diffs = np.diff(values)                       # length n-1

        # 2. Compute raw signs; zero out near-zero diffs
        signs = np.sign(diffs).astype(int)
        signs[np.abs(diffs) < threshold] = 0

        # 2b. Determine where the slow axis is actively changing (length n-1).
        #     Used to avoid back-filling through magnet/B-field sweeps.
        if slow_col is not None:
            slow_diffs = np.abs(np.diff(df[slow_col].to_numpy()))
            slow_active = slow_diffs > slow_threshold
        else:
            slow_active = np.zeros(len(signs), dtype=bool)

        # 3. Backward-fill zeros (propagate next non-zero direction backward),
        #    but NOT through rows where the slow axis is actively changing.
        for i in range(len(signs) - 2, -1, -1):
            if signs[i] == 0:
                if slow_col is not None and slow_active[i]:
                    continue  # slow axis sweeping here (e.g. magnet move): keep flat
                signs[i] = signs[i + 1]

        # 4. Forward-fill any remaining leading zeros, again skipping rows
        #    where the slow axis is actively changing.
        if len(signs) > 0 and signs[0] == 0:
            for i in range(1, len(signs)):
                if signs[i] != 0:
                    fill_end = i
                    if slow_col is not None:
                        actives = np.where(slow_active[:i])[0]
                        if len(actives) > 0:
                            fill_end = actives[0]
                    if fill_end > 0:
                        signs[:fill_end] = signs[i]
                    break

        # 5. Assign a direction to every row:
        #    row 0 inherits signs[0]; row j (j>0) inherits signs[j-1]
        row_dirs = np.zeros(n, dtype=int)
        row_dirs[0] = signs[0] if len(signs) > 0 else 0
        row_dirs[1:] = signs

        # 6. Detect direction changes → segment boundaries
        changes = np.where(np.diff(row_dirs) != 0)[0] + 1
        boundaries = np.concatenate([[0], changes, [n]])

        segments = []
        for i in range(len(boundaries) - 1):
            start = int(boundaries[i])
            end = int(boundaries[i + 1])
            segment = df.slice(start, end - start)
            d = int(row_dirs[start])
            if d > 0:
                dir_str = 'forward'
            elif d < 0:
                dir_str = 'backward'
            else:
                dir_str = 'flat'
            segments.append((segment, dir_str))

        return segments

    def process_gate_map(self, df, file_path):
        """Split gate map data into forward and backward sweeps using
        direction (sign) detection instead of magnitude thresholding."""
        axis_col = self._ask_axis_column(df, title_prefix="Gate Map Axis")
        if axis_col is None:
            return

        # Auto-compute a sensible threshold from the data:
        #   half the median absolute non-zero diff
        values = df[axis_col].to_numpy()
        abs_diffs = np.abs(np.diff(values))
        non_zero = abs_diffs[abs_diffs > 0]
        if len(non_zero) > 0:
            auto_threshold = float(np.median(non_zero)) * 0.5
        else:
            auto_threshold = float(values.max() - values.min()) * 0.01

        threshold = simpledialog.askfloat(
            "Direction Threshold",
            f"Auto-detected step threshold: {auto_threshold:.6g}\n"
            f"(Diffs smaller than this are treated as flat/zero)\n\n"
            f"Adjust if needed:",
            initialvalue=auto_threshold, parent=self.root)
        if threshold is None:
            return

        segments = self._detect_direction_segments(df, axis_col, threshold)

        if not segments:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return

        fwd, bwd = [], []
        for segment, direction in segments:
            if direction == 'forward':
                fwd.append(segment)
            elif direction == 'backward':
                bwd.append(segment)
            # 'flat' segments (if any) are discarded

        fwd_rows = sum(len(s) for s in fwd)
        bwd_rows = sum(len(s) for s in bwd)
        print(f"Gate Map Split: {len(df)} total rows → {fwd_rows} fwd, {bwd_rows} bwd "
              f"({len(df) - fwd_rows - bwd_rows} flat discarded)")

        self.save_simple(file_path, fwd, bwd, f"GateMap_{axis_col}")

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
        """Detect segments and classify into Fast Fwd/Bwd and Slow Fwd/Bwd groups.

        Produces 4 outputs:
          - {fast_col}_Fwd / {fast_col}_Bwd : fast axis sweeping (gate forward/backward)
          - {slow_col}_Fwd / {slow_col}_Bwd : slow axis sweeping (e.g. magnet up/down)

        Uses direction-sign-based detection to correctly handle repeated boundary
        values at sweep turnarounds (no data loss).

        The slow axis is monitored so that regions where the slow axis is *actively
        sweeping* between fast sweeps are kept as 'flat' segments (w.r.t. the fast
        axis) and then split into Slow Fwd/Bwd by the slow axis direction.
        """
        # --- Fast Axis Threshold ---
        fast_range = df[fast_col].max() - df[fast_col].min()
        default_fast_thresh = fast_range * 0.01

        fast_threshold = simpledialog.askfloat(
            "Fast Axis Threshold",
            f"Enter Fast Axis ('{fast_col}') Change Threshold:\n"
            f"(Diffs smaller than this are treated as flat/zero)\n"
            f"Default (1% of range): {default_fast_thresh:.6g}",
            initialvalue=default_fast_thresh, parent=self.root)
        if fast_threshold is None:
            return

        # --- Slow Axis Step Threshold (auto, used internally to detect sweeps) ---
        #   Half the median non-zero slow-axis step: distinguishes a real sweep
        #   (magnet moving between setpoints) from noise/hold jitter.
        slow_range = df[slow_col].max() - df[slow_col].min()
        slow_values = df[slow_col].to_numpy()
        slow_abs_diffs = np.abs(np.diff(slow_values))
        slow_nonzero = slow_abs_diffs[slow_abs_diffs > 0]
        if len(slow_nonzero) > 0:
            slow_threshold = float(np.median(slow_nonzero)) * 0.5
        else:
            slow_threshold = float(slow_range) * 0.01

        print(f"Smart Split: slow axis '{slow_col}' step threshold = {slow_threshold:.6g} "
              f"(auto, used to separate slow-axis sweeps from fast sweeps)")

        # --- Segment Detection using direction-sign method ---
        segments = self._detect_direction_segments(
            df, fast_col, fast_threshold,
            slow_col=slow_col, slow_threshold=slow_threshold)

        fast_fwd_segments = []
        fast_bwd_segments = []
        slow_fwd_segments = []
        slow_bwd_segments = []

        for segment, direction in segments:
            if direction == 'forward':
                fast_fwd_segments.append(segment)
            elif direction == 'backward':
                fast_bwd_segments.append(segment)
            elif direction == 'flat':
                # Slow axis is active here → classify by its direction (up/down)
                slow_vals = segment[slow_col].to_numpy()
                slow_diffs = np.diff(slow_vals)
                # Net direction via sum of diffs (robust to noise)
                net = float(np.sum(slow_diffs))
                if net > 0:
                    slow_fwd_segments.append(segment)
                elif net < 0:
                    slow_bwd_segments.append(segment)
                else:
                    # Genuinely constant (not expected, but skip just in case)
                    print(f"  Skipping {len(segment)} flat rows "
                          f"({slow_col} not changing)")

        # --- Save Files ---
        self.save_files_smart(file_path, fast_col, slow_col,
                              fast_fwd_segments, fast_bwd_segments,
                              slow_fwd_segments, slow_bwd_segments)

    def save_files_smart(self, original_path, fast_col, slow_col,
                         fast_fwd, fast_bwd, slow_fwd, slow_bwd):
        """Save 4 split files: fast axis Fwd/Bwd + slow axis Fwd/Bwd.

        Only writes files that contain data (skips empty groups).
        """
        directory = os.path.dirname(original_path)
        name = os.path.splitext(os.path.basename(original_path))[0]

        msg_lines = [
            "Processing Complete!\n",
            f"Fast Axis: '{fast_col}'",
        ]

        if fast_fwd:
            df = pl.concat(fast_fwd)
            df.write_csv(os.path.join(directory, f"{name}_{fast_col}_Fwd.csv"))
            msg_lines.append(f"  Fwd sweep: {len(df)} rows ({len(fast_fwd)} segments)")
        if fast_bwd:
            df = pl.concat(fast_bwd)
            df.write_csv(os.path.join(directory, f"{name}_{fast_col}_Bwd.csv"))
            msg_lines.append(f"  Bwd sweep: {len(df)} rows ({len(fast_bwd)} segments)")

        msg_lines.append("")
        msg_lines.append(f"Slow Axis: '{slow_col}'")

        if slow_fwd:
            df = pl.concat(slow_fwd)
            df.write_csv(os.path.join(directory, f"{name}_{slow_col}_Fwd.csv"))
            msg_lines.append(f"  Fwd sweep: {len(df)} rows ({len(slow_fwd)} segments)")
        if slow_bwd:
            df = pl.concat(slow_bwd)
            df.write_csv(os.path.join(directory, f"{name}_{slow_col}_Bwd.csv"))
            msg_lines.append(f"  Bwd sweep: {len(df)} rows ({len(slow_bwd)} segments)")

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
            f"(Sweeps {s1}..{s2-1} are Backward, sweeps {s1}..end are Forward part 2)",
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