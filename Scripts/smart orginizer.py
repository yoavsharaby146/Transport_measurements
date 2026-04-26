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
            "Smart Split (V & B Sweep - Auto Detect)",  # NEW MODE
            "Hysteresis (0 -> SP1 -> SP2 -> 0)",
            "Standard Loop (0 -> Max -> 0)",
            "Snake (Alternating)"
        )
        self.mode_combo.current(0)
        self.mode_combo.pack(pady=5)

        tk.Label(self.root, text="Note: 'Smart Split' requires identifying the Voltage column.",
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
                self.process_smart_vb_sweep(df, file_path)
            elif "Hysteresis" in mode:
                self.process_hysteresis(df, file_path)
            elif "Standard Loop" in mode:
                self.process_standard_loop(df, file_path)
            elif "Snake" in mode:
                self.process_snake(df, file_path)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    # =========================================================
    # NEW MODE: Smart V & B Sweep (Variable Lengths)
    # =========================================================
    def process_smart_vb_sweep(self, df, file_path):
        # 1. Ask User to identify the Voltage Column
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
            return

        col_window = tk.Toplevel(self.root)
        col_window.title("Select Voltage Column")
        col_window.geometry("300x150")
        col_window.lift()

        tk.Label(col_window, text="Which column is Voltage?").pack(pady=10)
        col_var = tk.StringVar()
        col_box = ttk.Combobox(col_window, textvariable=col_var, values=columns, state="readonly")
        col_box.current(0)
        col_box.pack(pady=5)

        def on_confirm():
            col_window.destroy()
            self.run_smart_split_logic(df, file_path, col_var.get())

        tk.Button(col_window, text="Confirm", command=on_confirm).pack(pady=20)
        self.root.wait_window(col_window)  # Pause main script until selection is made

    def run_smart_split_logic(self, df, file_path, v_col):
        # 2. Settings for detection
        # We need a threshold to decide if Voltage is "Changing" or "Constant".
        # Default: 1% of the total voltage range.
        v_range = df[v_col].max() - df[v_col].min()
        default_thresh = v_range * 0.01

        threshold = simpledialog.askfloat("Settings",
                                          f"Enter Voltage Change Threshold:\n(If change < this, it's considered constant)\nDefault: {default_thresh:.4f}",
                                          initialvalue=default_thresh, parent=self.root)
        if threshold is None: return

        # 3. Analyze Data
        # Calculate absolute change between rows using Polars expressions
        df = df.with_columns([
            (pl.col(v_col).diff().abs() < threshold).alias("matches_prev")
        ])
        
        # Identify "Segments" of consecutive True/False
        # This creates a unique ID for each contiguous block of behavior
        df = df.with_columns([
            (pl.col("matches_prev") != pl.col("matches_prev").shift(1)).cum_sum().alias("segment_id")
        ])

        # Lists to hold the 4 categories
        fwd_voltage = []  # Voltage Sweep (Low -> High)
        bwd_voltage = []  # Voltage Sweep (High -> Low)
        mag_at_sp1 = []  # Constant V (Low Level)
        mag_at_sp2 = []  # Constant V (High Level)

        # Calculate global high/low reference to identify SP1 vs SP2
        global_max_v = df[v_col].max()
        global_min_v = df[v_col].min()
        midpoint_v = (global_max_v + global_min_v) / 2

        # 4. Loop through Segments and Classify
        grouped = df.group_by('segment_id',maintain_order=True)

        for seg_id, segment in grouped:
            # Skip noise (very short segments, e.g. < 3 rows)
            if len(segment) < 3:
                continue

            # Check behavior of this segment
            # Is Voltage Changing? (We check the boolean flag we created)
            # The flag 'matches_prev' might be mixed in the first row of a group, so we take the mode
            is_constant = segment["matches_prev"].mode()[0]

            if is_constant:
                # --- Magnetic Sweep (Voltage is Constant) ---
                avg_val = segment[v_col].mean()
                if avg_val > midpoint_v:
                    mag_at_sp2.append(segment)  # High Voltage (SP2)
                else:
                    mag_at_sp1.append(segment)  # Low Voltage (SP1)
            else:
                # --- Voltage Sweep (Voltage is Changing) ---
                start_v = segment[v_col][0]
                end_v = segment[v_col][-1]

                if end_v > start_v:
                    fwd_voltage.append(segment)  # Low -> High
                else:
                    bwd_voltage.append(segment)  # High -> Low

        # 5. Clean up columns before saving
        for lst in [fwd_voltage, bwd_voltage, mag_at_sp1, mag_at_sp2]:
            for i, chunk in enumerate(lst):
                lst[i] = chunk.drop(['matches_prev', 'segment_id'])

        # 6. Save Files
        self.save_files_smart(file_path, fwd_voltage, bwd_voltage, mag_at_sp1, mag_at_sp2)

    def save_files_smart(self, original_path, fwd, bwd, mag1, mag2):
        directory = os.path.dirname(original_path)
        name = os.path.splitext(os.path.basename(original_path))[0]

        # Concatenate lists using Polars
        df_fwd = pl.concat(fwd) if fwd else pl.DataFrame()
        df_bwd = pl.concat(bwd) if bwd else pl.DataFrame()
        df_sp1 = pl.concat(mag1) if mag1 else pl.DataFrame()
        df_sp2 = pl.concat(mag2) if mag2 else pl.DataFrame()

        # Save
        df_fwd.write_csv(os.path.join(directory, f"{name}_Volt_Fwd.csv"))
        df_bwd.write_csv(os.path.join(directory, f"{name}_Volt_Bwd.csv"))
        df_sp1.write_csv(os.path.join(directory, f"{name}_Mag_at_SP1.csv"))
        df_sp2.write_csv(os.path.join(directory, f"{name}_Mag_at_SP2.csv"))

        msg = (f"Processing Complete!\n\n"
               f"1. Fwd Voltage Rows: {len(df_fwd)}\n"
               f"2. Bwd Voltage Rows: {len(df_bwd)}\n"
               f"3. Mag @ SP1 Rows: {len(df_sp1)}\n"
               f"4. Mag @ SP2 Rows: {len(df_sp2)}")

        print(msg)
        messagebox.showinfo("Success", msg)
        self.root.quit()

    # =========================================================
    # PREVIOUS MODES (Retained)
    # =========================================================
    def process_hysteresis(self, df, file_path):
        block_size = simpledialog.askinteger("Config", "Rows per block:", parent=self.root)
        if not block_size: return
        s1 = simpledialog.askinteger("Config", "Split 1 Index:", parent=self.root)
        s2 = simpledialog.askinteger("Config", "Split 2 Index:", parent=self.root)

        fwd, bwd = [], []
        for i in range(0, len(df), block_size):
            block = df.slice(i, block_size)
            if len(block) < block_size: break
            fwd.extend([block.slice(0, s1), block.slice(s2, block_size)])
            bwd.append(block.slice(s1, s2))
        self.save_simple(file_path, fwd, bwd, "Hysteresis")

    def process_standard_loop(self, df, file_path):
        cycle_len = simpledialog.askinteger("Config", "Rows per cycle:", parent=self.root)
        if not cycle_len: return
        split = simpledialog.askinteger("Config", "Split Index:", initialvalue=cycle_len // 2, parent=self.root)
        fwd, bwd = [], []
        for i in range(0, len(df), cycle_len):
            block = df.slice(i, cycle_len)
            if len(block) < cycle_len: break
            fwd.append(block.slice(0, split))
            bwd.append(block.slice(split, cycle_len))
        self.save_simple(file_path, fwd, bwd, "StandardLoop")

    def process_snake(self, df, file_path):
        sweep_len = simpledialog.askinteger("Config", "Rows per sweep:", parent=self.root)
        if not sweep_len: return
        fwd, bwd = [], []
        cnt = 0
        for i in range(0, len(df), sweep_len):
            block = df.slice(i, sweep_len)
            if len(block) < sweep_len: break
            if cnt % 2 == 0:
                fwd.append(block)
            else:
                bwd.append(block)
            cnt += 1
        self.save_simple(file_path, fwd, bwd, "Snake")

    def save_simple(self, path, fwd, bwd, suffix):
        # Basic saver for the old modes
        df_f = pl.concat(fwd) if fwd else pl.DataFrame()
        df_b = pl.concat(bwd) if bwd else pl.DataFrame()
        d = os.path.dirname(path)
        n = os.path.splitext(os.path.basename(path))[0]
        if len(df_f) > 0: df_f.write_csv(os.path.join(d, f"{n}_{suffix}_Fwd.csv"))
        if len(df_b) > 0: df_b.write_csv(os.path.join(d, f"{n}_{suffix}_Bwd.csv"))
        messagebox.showinfo("Success", "Files Saved!")
        self.root.quit()


if __name__ == "__main__":
    app = ScanOrganizer()
    app.root.mainloop()