import polars as pl
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os


class MapSplitter:
    """Splits a map measurement CSV into individual files, one per slow-axis setpoint.

    After a map measurement (e.g. gate map), the data contains many fast-axis
    sweeps recorded at different slow-axis values. This tool extracts each
    slow-axis setpoint into its own CSV file so you can examine a single
    sweep at a time.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Map Splitter — Slow Axis Sweep Extractor")
        self.root.geometry("440x200")

        # Force window to front
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        # --- UI ---
        tk.Label(self.root, text="Map Splitter",
                 font=("Arial", 14, "bold")).pack(pady=(15, 2))
        tk.Label(self.root,
                 text="Split a map measurement into individual slow-axis sweeps",
                 font=("Arial", 9), fg="gray").pack(pady=(0, 10))
        tk.Button(self.root, text="Select File & Run",
                  command=self.run, height=2, width=22).pack(pady=10)

    # ═══════════════════════════════════════════════════════════
    #  UI HELPERS
    # ═══════════════════════════════════════════════════════════

    def _ask_column(self, df, title="Select Slow Axis Column"):
        """Show dialog for user to select the slow axis column."""
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV has no columns.")
            return None

        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("350x180")
        win.lift()

        result = {'col': None}

        tk.Label(win, text="Select the slow sweep axis column:",
                 font=("Arial", 10)).pack(pady=10)
        col_var = tk.StringVar()
        combo = ttk.Combobox(win, textvariable=col_var, values=columns,
                             state="readonly", width=35)
        combo.current(0)
        combo.pack(pady=5)

        def confirm():
            result['col'] = col_var.get()
            win.destroy()

        tk.Button(win, text="Confirm", command=confirm, width=15).pack(pady=20)
        self.root.wait_window(win)
        return result['col']

    # ═══════════════════════════════════════════════════════════
    #  SETPOINT CLUSTERING
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _cluster_setpoints(values, tolerance):
        """Cluster numeric values into setpoints within the given tolerance.

        Returns a dict mapping each unique value to its cluster mean.
        """
        if len(values) == 0:
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

    @staticmethod
    def _auto_compute_tolerance(values):
        """Auto-compute a tolerance for setpoint clustering.

        Uses half the minimum absolute non-zero gap between sorted unique values,
        which naturally separates distinct setpoints while allowing for noise.
        """
        unique_vals = np.sort(np.unique(values))
        if len(unique_vals) <= 1:
            return float(np.ptp(values)) * 0.01 if len(values) > 1 else 1e-6

        gaps = np.diff(unique_vals)
        nonzero_gaps = gaps[gaps > 0]

        if len(nonzero_gaps) == 0:
            return float(np.ptp(values)) * 0.01

        # Half the minimum gap between distinct values
        return float(nonzero_gaps.min() * 0.5)

    # ═══════════════════════════════════════════════════════════
    #  MAIN LOGIC
    # ═══════════════════════════════════════════════════════════

    def run(self):
        """Main processing pipeline: load → select axis → cluster → split → save."""

        # 1. Select file
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Map Measurement CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            # 2. Load
            df = pl.read_csv(file_path, infer_schema_length=10000)
            print(f"Loaded: {os.path.basename(file_path)} ({len(df)} rows, {len(df.columns)} columns)")

            # 3. Ask for slow axis column
            slow_col = self._ask_column(df)
            if slow_col is None:
                return

            values = df[slow_col].to_numpy()

            # 4. Compute tolerance and ask user
            auto_tol = self._auto_compute_tolerance(values)

            tolerance = simpledialog.askfloat(
                "Setpoint Tolerance",
                f"Slow axis: '{slow_col}'\n"
                f"Range: {values.min():.6g} → {values.max():.6g}\n"
                f"Unique values detected: {len(np.unique(values))}\n\n"
                f"Tolerance for grouping into setpoints:\n"
                f"(values within this range are considered the same setpoint)\n\n"
                f"Auto-detected: {auto_tol:.6g}",
                initialvalue=auto_tol, parent=self.root
            )
            if tolerance is None:
                return

            # 5. Cluster setpoints
            unique_vals = np.unique(values)
            cluster_map = self._cluster_setpoints(list(unique_vals), tolerance)
            setpoint_values = sorted(set(cluster_map.values()))

            print(f"\nDetected {len(setpoint_values)} setpoint(s) for '{slow_col}':")
            for sp in setpoint_values:
                print(f"  {sp:.6g}")

            if not setpoint_values:
                messagebox.showinfo("Info", "No setpoints detected.")
                return

            # 6. Choose output folder
            output_dir = filedialog.askdirectory(
                parent=self.root,
                title="Select Output Folder for Split Files"
            )
            if not output_dir:
                return

            # 7. Split and save
            name = os.path.splitext(os.path.basename(file_path))[0]
            saved_files = []

            # Add a cluster-mean column to the dataframe for grouping
            # Map each row's slow_col value to its cluster mean
            mapping_series = {float(v): float(cluster_map[v]) for v in cluster_map}
            df = df.with_columns(
                pl.col(slow_col).map_elements(lambda x: mapping_series.get(float(x), float(x))).alias("_setpoint")
            )

            for sp_val in setpoint_values:
                segment = df.filter(pl.col("_setpoint") == sp_val).drop("_setpoint")
                if len(segment) == 0:
                    continue

                sp_str = f"{sp_val:.6g}"
                output_filename = f"{slow_col}_at_{sp_str}_{name}.csv"
                output_path = os.path.join(output_dir, output_filename)
                segment.write_csv(output_path)
                saved_files.append((sp_str, len(segment)))
                print(f"  Saved: {output_filename} ({len(segment)} rows)")

            # 8. Summary
            summary_lines = [
                f"Map Split Complete!\n",
                f"Source: {os.path.basename(file_path)}",
                f"Slow axis: '{slow_col}'",
                f"Setpoints found: {len(saved_files)}",
                f"Output folder:\n{output_dir}\n",
                f"Files created:"
            ]
            for sp_str, row_count in saved_files:
                summary_lines.append(f"  {slow_col}_at_{sp_str}_{name}.csv  ({row_count} rows)")

            msg = "\n".join(summary_lines)
            print(f"\n{msg}")
            messagebox.showinfo("Success", msg)
            self.root.quit()

        except Exception as e:
            error_msg = f"An error occurred:\n{str(e)}"
            print(error_msg)
            messagebox.showerror("Error", error_msg)


if __name__ == "__main__":
    app = MapSplitter()
    app.root.mainloop()