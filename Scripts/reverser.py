import polars as pl
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
from itertools import permutations


class BlockReverser:
    """Reverses measurement blocks in CSV data files.

    Handles measurement types produced by the smart organizer:
    - Simple (Fwd/Bwd, Snake): Single continuous sweep per block
    - Hysteresis: Multiple segments per block that need merging
      (e.g. 0->3 and -3->0 are reordered into -3->0->3, deduplicated, then reversed)

    Auto-detects block boundaries and segment structure from a user-selected sweep column.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Block Reverser")
        self.root.geometry("420x220")

        # Force window to front
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        # --- UI ---
        tk.Label(self.root, text="CSV Block Reverser",
                 font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(self.root,
                 text="Auto-detects blocks, merges segments, and reverses",
                 font=("Arial", 9), fg="gray").pack()
        tk.Button(self.root, text="Select File & Run",
                  command=self.run, height=2, width=20).pack(pady=20)

    # ═══════════════════════════════════════════════════════════
    #  UI HELPERS
    # ═══════════════════════════════════════════════════════════

    def _ask_column(self, df):
        """Show dialog for user to select the sweep column."""
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV has no columns.")
            return None

        win = tk.Toplevel(self.root)
        win.title("Select Sweep Column")
        win.geometry("350x180")
        win.lift()

        result = {'col': None}

        tk.Label(win, text="Select the sweep axis column:",
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
    #  DETECTION HELPERS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _compute_jump_threshold(values):
        """Auto-compute threshold for segment-splitting jumps.

        Any |diff| larger than this is considered a segment/block boundary.
        Uses median step × 5, which separates the regular measurement steps
        from the large jumps that occur at segment or block transitions.
        """
        abs_diffs = np.abs(np.diff(values))
        nonzero = abs_diffs[abs_diffs > 0]
        if len(nonzero) == 0:
            return 1e-10
        return float(np.median(nonzero)) * 5

    @staticmethod
    def _compute_step_tolerance(values):
        """Tolerance for matching values at segment junctions (duplicate detection).

        Uses median step × 2 — close enough to be considered the same measurement point.
        """
        abs_diffs = np.abs(np.diff(values))
        nonzero = abs_diffs[abs_diffs > 0]
        if len(nonzero) == 0:
            return 1e-10
        return float(np.median(nonzero)) * 2

    @staticmethod
    def _split_into_segments(df, sweep_col, threshold):
        """Split dataframe into segments at large jumps in the sweep column.

        A segment is a contiguous region where the sweep column changes smoothly
        (no large jumps). Segment boundaries occur where |diff| > threshold.
        """
        values = df[sweep_col].to_numpy()
        abs_diffs = np.abs(np.diff(values))

        jump_indices = np.where(abs_diffs > threshold)[0] + 1  # +1 for diff offset
        boundaries = np.concatenate([[0], jump_indices, [len(df)]])

        segments = []
        for i in range(len(boundaries) - 1):
            start = int(boundaries[i])
            end = int(boundaries[i + 1])
            if end - start > 0:
                segments.append(df.slice(start, end - start))

        return segments

    @staticmethod
    def _detect_block_size(segments, sweep_col, tolerance):
        """Detect how many segments form one measurement block.

        Examines whether segment start-values follow a repeating pattern:
        - Simple (Fwd/Bwd, Snake): [0, 0, 0, ...] → block_size = 1
        - Hysteresis:              [0, -3, 0, -3, ...] → block_size = 2

        Returns the smallest repeating period found (up to 6).
        """
        n = len(segments)
        if n <= 1:
            return 1

        starts = np.array([float(seg[sweep_col][0]) for seg in segments])

        for k in range(1, min(n, 6) + 1):
            is_repeating = True
            for i in range(k, n):
                if abs(starts[i] - starts[i % k]) > tolerance:
                    is_repeating = False
                    break
            if is_repeating:
                return k

        return 1

    # ═══════════════════════════════════════════════════════════
    #  SEGMENT MERGING
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _order_segments_for_continuity(segments, sweep_col):
        """Reorder segments within a block to form a continuous sweep.

        Tries all permutations and picks the ordering with the smallest
        total gap between consecutive segment endpoints. For 2-3 segments
        this is trivially fast.

        Example (hysteresis fwd):
            Seg A: 0 → 3,  Seg B: -3 → 0
            A→B has gap |3 - (-3)| = 6
            B→A has gap |0 - 0|   = 0  ← winner → continuous sweep
        """
        if len(segments) <= 1:
            return segments

        n = len(segments)
        ends = [float(seg[sweep_col][-1]) for seg in segments]
        starts = [float(seg[sweep_col][0]) for seg in segments]

        best_order = list(range(n))
        best_gap = float('inf')

        for perm in permutations(range(n)):
            total_gap = 0
            for i in range(len(perm) - 1):
                total_gap += abs(ends[perm[i]] - starts[perm[i + 1]])
            if total_gap < best_gap:
                best_gap = total_gap
                best_order = list(perm)

        return [segments[i] for i in best_order]

    @staticmethod
    def _merge_segments(ordered_segments, sweep_col, tolerance):
        """Merge ordered segments into one continuous block.

        Removes duplicate rows at junctions where the end value of one segment
        matches the start value of the next (within tolerance).
        """
        if len(ordered_segments) == 1:
            return ordered_segments[0]

        parts = [ordered_segments[0]]
        for i in range(1, len(ordered_segments)):
            prev = parts[-1]
            curr = ordered_segments[i]

            prev_last = float(prev[sweep_col][-1])
            curr_first = float(curr[sweep_col][0])

            if abs(prev_last - curr_first) <= tolerance:
                # Duplicate at junction — drop first row of current segment
                if len(curr) > 1:
                    parts.append(curr.slice(1))
                # else: segment is only the duplicate row, skip entirely
            else:
                parts.append(curr)

        return pl.concat(parts)

    # ═══════════════════════════════════════════════════════════
    #  MAIN LOGIC
    # ═══════════════════════════════════════════════════════════

    def run(self):
        """Main processing pipeline: load → detect → reverse → save."""

        # 1. Select file
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Data CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            # 2. Load
            df = pl.read_csv(file_path, infer_schema_length=10000)
            print(f"Loaded: {os.path.basename(file_path)} ({len(df)} rows)")

            # 3. Ask for sweep column
            sweep_col = self._ask_column(df)
            if sweep_col is None:
                return

            values = df[sweep_col].to_numpy()

            # 4. Compute thresholds
            auto_thresh = self._compute_jump_threshold(values)
            step_tol = self._compute_step_tolerance(values)

            threshold = simpledialog.askfloat(
                "Jump Threshold",
                f"Auto-detected jump threshold: {auto_thresh:.6g}\n"
                f"(Jumps larger than this indicate segment/block boundaries)\n\n"
                f"Adjust if needed:",
                initialvalue=auto_thresh, parent=self.root
            )
            if threshold is None:
                return

            # 5. Split into segments
            segments = self._split_into_segments(df, sweep_col, threshold)
            print(f"Detected {len(segments)} segments")

            if not segments:
                messagebox.showinfo("Info", "No segments detected.")
                return

            # 6. Detect block structure
            block_size = self._detect_block_size(segments, sweep_col, step_tol)
            n_complete_blocks = len(segments) // block_size

            block_type = "Hysteresis" if block_size > 1 else "Simple"
            print(f"Block structure: {block_type} — "
                  f"{block_size} segment(s)/block × {n_complete_blocks} blocks")

            # 7. Process each block
            processed_blocks = []

            for i in range(n_complete_blocks):
                block_segs = segments[i * block_size: (i + 1) * block_size]

                if block_size > 1:
                    # Hysteresis: reorder → merge → reverse
                    ordered = self._order_segments_for_continuity(
                        block_segs, sweep_col)
                    merged = self._merge_segments(
                        ordered, sweep_col, step_tol)
                    processed_blocks.append(merged.reverse())
                else:
                    # Simple: just reverse
                    processed_blocks.append(block_segs[0].reverse())

            # Handle leftover segments that don't form a complete block
            remaining_start = n_complete_blocks * block_size
            if remaining_start < len(segments):
                remaining = segments[remaining_start:]
                print(f"Note: {len(remaining)} trailing segment(s) not forming "
                      f"a complete block — processing anyway.")
                if len(remaining) > 1:
                    ordered = self._order_segments_for_continuity(
                        remaining, sweep_col)
                    merged = self._merge_segments(ordered, sweep_col, step_tol)
                    processed_blocks.append(merged.reverse())
                else:
                    processed_blocks.append(remaining[0].reverse())

            # 8. Concatenate and save
            final_df = pl.concat(processed_blocks)

            directory = os.path.dirname(file_path)
            name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(directory, f"{name}_reversed.csv")

            final_df.write_csv(output_path)

            # 9. Report
            msg = (
                f"Processing Complete!\n\n"
                f"Type detected: {block_type}\n"
                f"Input rows: {len(df)}\n"
                f"Segments: {len(segments)}\n"
                f"Block size: {block_size} segment(s)/block\n"
                f"Complete blocks: {n_complete_blocks}\n"
                f"Output rows: {len(final_df)}\n\n"
                f"Saved to:\n{output_path}"
            )
            print(msg)
            messagebox.showinfo("Success", msg)
            self.root.quit()

        except Exception as e:
            error_msg = f"An error occurred:\n{str(e)}"
            print(error_msg)
            messagebox.showerror("Error", error_msg)


if __name__ == "__main__":
    app = BlockReverser()
    app.root.mainloop()