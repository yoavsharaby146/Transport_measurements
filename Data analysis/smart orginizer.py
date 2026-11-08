import polars as pl
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os

from csv_utils import read_data_csv, show_help


HELP_TEXT = (
    "HOW TO USE — Scan Organizer\n"
    "\n"
    "Splits one or more measurement CSVs into Forward / Backward (and\n"
    "fast / slow) sweep files. Pick a mode, then select the CSV(s) —\n"
    "every mode auto-detects the sweeps from one chosen axis column.\n"
    "\n"
    "Modes:\n"
    "1. Smart Split (Fast & Slow Axis - Auto Detect)\n"
    "   Two-axis scans (e.g. bias fast + gate slow): fast Fwd/Bwd sweeps\n"
    "   and slow-axis move regions are separated automatically\n"
    "2. Forward/Backward Organizer (Direction Split)\n"
    "   One-axis sweep loops: rows split into forward and backward files\n"
    "   by sweep direction\n"
    "3. Hysteresis - Auto Detect (0 -> SP1 -> SP2 -> 0)\n"
    "   Hysteresis loops: segments identified and merged per loop\n"
    "4. Standard Loop - Auto Detect (0 -> Max -> 0)\n"
    "   Standard up/down loops around zero\n"
    "5. Snake - Auto Detect (Alternating)\n"
    "   Snake scans: alternating sweep direction, no return sweeps\n"
    "\n"
    "For every mode: select the file(s), pick the axis column, and review\n"
    "the auto-detected change threshold (steps smaller than it count as\n"
    "noise/pauses). Outputs are saved beside each source file.\n"
    "\n"
    "Multiple files: you can select several CSVs at once. Either reuse\n"
    "the settings chosen for the first file (axis columns, thresholds,\n"
    "sweep counts) for all files, or configure each file separately.\n"
    "A file that fails is reported and the batch can continue."
)


def split_by_activity(df, fast_col, slow_col, fast_threshold, slow_threshold,
                      fast_min=None, fast_max=None):
    """Split a two-axis measurement into fast Fwd/Bwd and slow Fwd/Bwd segments.

    Pure function (no tkinter) so the logic is testable.

    Fast axis: rows outside slow-sweep regions form contiguous chunks, and
    each chunk is segmented with the exact direction-sign method used by the
    Forward/Backward Organizer mode — identical turnaround/pause behavior.

    Slow axis: maximal regions where the slow axis sweeps (and the fast axis
    is quiet) become slow segments, classified by net slow-axis change.
    Each slow region includes one preceding row — the last point of the
    preceding fast sweep — so that boundary row appears in both the fast
    and the slow output files (intentional duplication).

    Returns dict: 'fast_fwd'/'fast_bwd'/'slow_fwd'/'slow_bwd' (lists of
    DataFrames) and 'dropped' (unclassifiable row count).
    """
    n = len(df)
    out = {"fast_fwd": [], "fast_bwd": [], "slow_fwd": [], "slow_bwd": [], "dropped": 0}
    if n < 2:
        out["dropped"] = n
        return out

    fast_vals = df[fast_col].to_numpy()
    fdiff = np.diff(fast_vals)
    sdiff = np.diff(df[slow_col].to_numpy())
    fast_active = np.abs(fdiff) > fast_threshold
    slow_sweeping = (np.abs(sdiff) > slow_threshold) & (~fast_active)

    # optional fast-axis sweep limits: steps outside [min, max] are slow-side
    if fast_min is not None or fast_max is not None:
        lo = fast_min if fast_min is not None else -np.inf
        hi = fast_max if fast_max is not None else np.inf
        outside = ((fast_vals[:-1] < lo) | (fast_vals[:-1] > hi) |
                   (fast_vals[1:] < lo) | (fast_vals[1:] > hi))
        fast_active &= ~outside
        slow_sweeping |= outside

    nsteps = len(slow_sweeping)

    # --- slow regions: only sustained slow sweeps are excised ---
    #   A run counts as a real slow sweep only if its net slow-axis travel
    #   exceeds 3× slow_threshold. Short jitter/approach runs stay in the
    #   fast chunks, where the organizer's fill logic treats them as pauses
    #   — keeping fast-axis behavior identical to the Fwd/Bwd Organizer.
    min_net = 3.0 * slow_threshold
    removed = np.zeros(n, dtype=bool)
    edges = np.concatenate([[0], np.where(np.diff(slow_sweeping.astype(int)) != 0)[0] + 1,
                            [nsteps]])
    for i in range(len(edges) - 1):
        s, e = int(edges[i]), int(edges[i + 1])       # step span [s, e)
        if not slow_sweeping[s]:
            continue
        net = float(np.sum(sdiff[s:e]))
        if abs(net) < min_net:
            continue   # jitter/approach movement, not a real slow sweep
        # rows s+2..e are slow-only. Row s+1 — the first row where the slow
        # axis moved — is the first point of the slow sweep AND the last
        # measured point of the fast sweep, so it stays in the fast chunk
        # too (appears in both outputs).
        removed[0 if s == 0 else s + 2: e + 1] = True
        rows = df.slice(s + 1, e - s)
        if net > 0:
            out["slow_fwd"].append(rows)
        elif net < 0:
            out["slow_bwd"].append(rows)
        else:
            out["dropped"] += len(rows)

    # --- fast chunks: contiguous rows outside slow regions ---
    keep = (~removed).astype(int)
    pad = np.diff(np.concatenate([[0], keep, [0]]))
    chunk_starts = np.where(pad == 1)[0]
    chunk_ends = np.where(pad == -1)[0]
    for a, b in zip(chunk_starts, chunk_ends):
        chunk = df.slice(int(a), int(b) - int(a))
        segments = ScanOrganizer._detect_direction_segments(chunk, fast_col,
                                                            fast_threshold)
        for k, (segment, direction) in enumerate(segments):
            if direction == 'forward':
                out["fast_fwd"].append(segment)
            elif direction == 'backward':
                out["fast_bwd"].append(segment)
            else:
                # trailing quiet rows: keep with the preceding sweep chunk
                if k > 0 and segments[k - 1][1] in ('forward', 'backward'):
                    prev_dir = segments[k - 1][1]
                    seg_list = out["fast_fwd" if prev_dir == 'forward' else "fast_bwd"]
                    seg_list[-1] = pl.concat([seg_list[-1], segment])
                else:
                    out["dropped"] += len(segment)

    return out


class ScanOrganizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Scan Organizer")
        self.root.geometry("400x250")

        # True while processing a multi-file batch (suppresses the
        # per-file success dialogs / root.quit until the batch is done)
        self._batch = False

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
            "Forward/Backward Organizer (Direction Split)",
            "Hysteresis - Auto Detect (0 -> SP1 -> SP2 -> 0)",
            "Standard Loop - Auto Detect (0 -> Max -> 0)",
            "Snake - Auto Detect (Alternating)"
        )
        self.mode_combo.current(0)
        self.mode_combo.pack(pady=5)

        tk.Label(self.root, text="Note: All modes auto-detect sweeps from a chosen axis column.",
                 font=("Arial", 8), fg="gray").pack(pady=0)

        tk.Button(self.root, text="Select Files & Run", command=self.process_selection, height=2, width=20).pack(pady=20)
        tk.Button(self.root, text="How to Use",
                  command=lambda: show_help(
                      self.root, "Scan Organizer — Help", HELP_TEXT)
                  ).pack()

    def process_selection(self):
        mode = self.mode_var.get()

        file_paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Select your Data CSV(s)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_paths:
            return
        file_paths = list(file_paths)
        multi = len(file_paths) > 1
        self._batch = multi

        # Multiple files: optionally ask the settings once (based on the
        # first file) and reuse them for every remaining file.
        settings = {}
        reuse = False
        if multi:
            reuse = messagebox.askyesno(
                "Multiple Files",
                f"You selected {len(file_paths)} files.\n\n"
                "Use the same axis column(s), thresholds and sweep counts\n"
                "for ALL files? (Asked once, based on the first file.)\n\n"
                "Yes: same settings for all files\n"
                "No: configure each file separately")
            if reuse is None:
                self._batch = False
                return

        done, failed = 0, []
        for i, file_path in enumerate(file_paths, 1):
            try:
                df = read_data_csv(file_path)
                if multi:
                    print(f"\n=== File {i}/{len(file_paths)}: {os.path.basename(file_path)} ===")

                # In per-file mode the settings cache is reset for each file;
                # in reuse mode the answers from the first file carry over.
                file_settings = settings if reuse else {}

                # Route to correct logic; False = user cancelled a dialog
                if "Smart Split" in mode:
                    ok = self.process_smart_axis_split(df, file_path, file_settings)
                elif "Forward/Backward" in mode:
                    ok = self.process_gate_map(df, file_path, file_settings)
                elif "Hysteresis" in mode:
                    ok = self.process_hysteresis(df, file_path, file_settings)
                elif "Standard Loop" in mode:
                    ok = self.process_standard_loop(df, file_path, file_settings)
                elif "Snake" in mode:
                    ok = self.process_snake(df, file_path, file_settings)
                else:
                    messagebox.showerror("Error", f"Unknown mode: {mode}")
                    ok = False

                if ok is False:
                    print("Processing cancelled by user.")
                    break
                done += 1

            except Exception as e:
                failed.append(f"{os.path.basename(file_path)}: {e}")
                if multi:
                    cont = messagebox.askyesno(
                        "Error",
                        f"An error occurred while processing\n{file_path}:\n\n{str(e)}\n\n"
                        "Continue with the remaining files?")
                    if not cont:
                        break
                else:
                    messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

        if multi:
            msg = f"Batch complete: {done}/{len(file_paths)} file(s) processed."
            if failed:
                msg += "\n\nFailed:\n" + "\n".join(failed)
            messagebox.showinfo("Done", msg)

        self._batch = False
        if done > 0 or multi:
            self.root.quit()

    # =========================================================
    # SHARED HELPERS
    # =========================================================
    def _ask_axis_and_threshold(self, df, title_prefix="Axis", settings=None):
        """Ask user to select an axis column and change threshold.
        Returns (col_name, threshold) or (None, None) if cancelled.

        If `settings` (dict) already holds 'axis_col' + 'threshold' (from a
        previous file in a batch), they are reused without asking again."""
        if (settings is not None and settings.get("axis_col") is not None
                and settings.get("threshold") is not None):
            return settings["axis_col"], settings["threshold"]

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

        if settings is not None:
            settings["axis_col"] = col
            settings["threshold"] = threshold

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
    # MODE: Forward/Backward Organizer (Direction Split)
    # =========================================================
    @staticmethod
    def _detect_direction_segments(df, axis_col, threshold,
                                   slow_col=None, slow_threshold=0.0,
                                   fast_min=None, fast_max=None):
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

        If `fast_min`/`fast_max` are provided, any diff step where either
        endpoint falls outside [fast_min, fast_max] is forced flat and blocked
        from fill — those rows are guaranteed to land in the slow-axis output.

        Row direction is assigned as the *incoming* diff (signs[i-1] → row i),
        so each sweep's turnaround point (its last row — the peak at a
        forward→backward turn, the valley at a backward→forward turn) stays
        with the sweep that produced it rather than leaking into the next one.

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

        # 2c. If fast axis limits are provided, force any diff step where either
        #     endpoint is outside [fast_min, fast_max] to flat, and block fill
        #     through those positions — they belong to the slow-axis segment.
        if fast_min is not None or fast_max is not None:
            lo = fast_min if fast_min is not None else -np.inf
            hi = fast_max if fast_max is not None else  np.inf
            outside = ((values[:-1] < lo) | (values[:-1] > hi) |
                       (values[1:]  < lo) | (values[1:]  > hi))
            signs[outside] = 0
            slow_active = slow_active | outside

        # 3. Backward-fill zeros (propagate next non-zero direction backward),
        #    but NOT through positions where the slow axis is actively changing.
        for i in range(len(signs) - 2, -1, -1):
            if signs[i] == 0 and not slow_active[i]:
                signs[i] = signs[i + 1]

        # 3b. Forward-fill the single trailing zero immediately after a non-zero
        #     run, but only if it is not slow-active.
        #     Needed for the turnaround peak (e.g. last row of fwd): its outgoing
        #     diff is zero (fast axis pauses before the slow axis starts moving),
        #     but the backward-fill above couldn't reach it because the next sign
        #     was also zero (slow_active blocked). Carrying the incoming direction
        #     forward by one step correctly keeps the peak in the fast sweep.
        for i in range(len(signs) - 1):
            if signs[i] != 0 and signs[i + 1] == 0 and not slow_active[i + 1]:
                signs[i + 1] = signs[i]

        # 4. Forward-fill any remaining leading zeros, again skipping slow-active.
        if len(signs) > 0 and signs[0] == 0:
            for i in range(1, len(signs)):
                if signs[i] != 0:
                    fill_end = i
                    actives = np.where(slow_active[:i])[0]
                    if len(actives) > 0:
                        fill_end = actives[0]
                    if fill_end > 0:
                        signs[:fill_end] = signs[i]
                    break

        # 5 & 6. Convert step signs → per-row direction, then segment.
        #
        # Each row is labelled by the *incoming* step — the step that arrived
        # at it: row i ← signs[i-1]. This is what keeps a sweep's turnaround
        # point attached to the sweep that produced it, instead of dropping it
        # into the following sweep. At a forward→backward turn:
        #   values:   ..., 2,   3,   3,   2,   ...   (3 = forward peak)
        #   signs:    ..., +,   +,   0/-, -,   ...
        #   row_sign: ..., +,   +,   +,   -,   ...   (the peak keeps '+')
        # so the peak row stays in Forward and the Backward sweep starts on the
        # next (already descending) row. Row 0 has no incoming step, so it
        # inherits the first step's direction (it opens that first sweep).
        #
        # Rows then collapse into maximal runs of equal row_sign — clean,
        # non-overlapping segments with no per-row boundary ambiguity.
        if len(signs) == 0:
            return [(df, 'flat')]

        row_sign = np.empty(n, dtype=int)
        row_sign[0] = signs[0]
        row_sign[1:] = signs            # row_sign[i] = signs[i-1]  (incoming step)

        # Maximal runs of equal row_sign → segment boundaries (row indices).
        changes = np.where(np.diff(row_sign) != 0)[0] + 1
        boundaries = np.concatenate([[0], changes, [n]])

        segments = []
        for i in range(len(boundaries) - 1):
            s = int(boundaries[i])
            e = int(boundaries[i + 1])   # exclusive
            segment = df.slice(s, e - s)

            # Label by net sign of this row block (robust to per-row noise)
            net = int(np.sign(np.sum(row_sign[s:e])))
            if net > 0:
                dir_str = 'forward'
            elif net < 0:
                dir_str = 'backward'
            else:
                dir_str = 'flat'
            segments.append((segment, dir_str))

        return segments

    def process_gate_map(self, df, file_path, settings=None):
        """Split single-axis data into forward and backward sweeps using
        direction (sign) detection instead of magnitude thresholding.
        Returns False if the user cancelled a dialog."""
        settings = settings if settings is not None else {}

        axis_col = settings.get("axis_col")
        if axis_col is None:
            axis_col = self._ask_axis_column(df, title_prefix="Sweep Axis")
            if axis_col is None:
                return False
            settings["axis_col"] = axis_col
        if axis_col not in df.columns:
            raise ValueError(f"Column '{axis_col}' not found in this file "
                             f"(available: {', '.join(df.columns)})")

        threshold = settings.get("threshold")
        if threshold is None:
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
                return False
            settings["threshold"] = threshold

        segments = self._detect_direction_segments(df, axis_col, threshold)

        if not segments:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return True

        fwd, bwd = [], []
        for segment, direction in segments:
            if direction == 'forward':
                fwd.append(segment)
            elif direction == 'backward':
                bwd.append(segment)
            # 'flat' segments (if any) are discarded

        fwd_rows = sum(len(s) for s in fwd)
        bwd_rows = sum(len(s) for s in bwd)
        print(f"Forward/Backward Split: {len(df)} total rows → {fwd_rows} fwd, {bwd_rows} bwd "
              f"({len(df) - fwd_rows - bwd_rows} flat discarded)")

        self.save_simple(file_path, fwd, bwd, f"FwdBwd_{axis_col}")
        return True

    # =========================================================
    # MODE: Smart Split (Fast & Slow Axis - Auto Detect)
    # =========================================================
    def process_smart_axis_split(self, df, file_path, settings=None):
        """Ask user to select Fast Axis and Slow Axis columns.
        Returns False if the user cancelled a dialog."""
        settings = settings if settings is not None else {}
        columns = df.columns
        if not columns:
            messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
            return False

        # Batch: reuse the axis columns chosen for the first file
        if settings.get("fast_col") and settings.get("slow_col"):
            return self.run_smart_split_logic(df, file_path,
                                              settings["fast_col"],
                                              settings["slow_col"], settings)

        result = {'ok': False}

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
            settings["fast_col"] = fast_var.get()
            settings["slow_col"] = slow_var.get()
            result['ok'] = self.run_smart_split_logic(df, file_path,
                                                      fast_var.get(), slow_var.get(),
                                                      settings)

        tk.Button(col_window, text="Confirm", command=on_confirm, width=15).pack(pady=20)
        self.root.wait_window(col_window)
        return result['ok']

    def run_smart_split_logic(self, df, file_path, fast_col, slow_col, settings=None):
        """Detect segments and classify into Fast Fwd/Bwd and Slow Fwd/Bwd groups.

        Produces 4 outputs:
          - {fast_col}_Fwd / {fast_col}_Bwd : fast axis sweeping (gate forward/backward)
          - {slow_col}_Fwd / {slow_col}_Bwd : slow axis sweeping (e.g. magnet up/down)

        Uses activity-based segmentation (split_by_activity): each step is
        classified by which axis is moving; pauses attach to the preceding
        region so turnaround rows stay with the sweep that produced them,
        and fast regions split internally into Fwd/Bwd direction runs.
        Handles both fast fwd/bwd sweeps and slow-axis sweeps between them.
        Returns False if the user cancelled a dialog.
        """
        settings = settings if settings is not None else {}
        for col in (fast_col, slow_col):
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in this file "
                                 f"(available: {', '.join(df.columns)})")

        # --- Fast Axis Threshold ---
        #   Same auto rule as the Forward/Backward Organizer: half the median
        #   absolute non-zero diff — separates real sweep steps from noise.
        fast_data_min = float(df[fast_col].min())
        fast_data_max = float(df[fast_col].max())
        fast_threshold = settings.get("fast_threshold")
        if fast_threshold is None:
            fast_abs_diffs = np.abs(np.diff(df[fast_col].to_numpy()))
            fast_nonzero = fast_abs_diffs[fast_abs_diffs > 0]
            if len(fast_nonzero) > 0:
                default_fast_thresh = float(np.median(fast_nonzero)) * 0.5
            else:
                default_fast_thresh = (fast_data_max - fast_data_min) * 0.01

            fast_threshold = simpledialog.askfloat(
                "Fast Axis Threshold",
                f"Enter Fast Axis ('{fast_col}') Change Threshold:\n"
                f"(Diffs smaller than this are treated as flat/zero)\n"
                f"Default (1% of range): {default_fast_thresh:.6g}",
                initialvalue=default_fast_thresh, parent=self.root)
            if fast_threshold is None:
                return False
            settings["fast_threshold"] = fast_threshold

        # --- Fast Axis Limits (optional) ---
        #   Rows where the fast axis falls outside [fast_min, fast_max] are
        #   forced into the slow-axis output regardless of their diff sign.
        #   This cleanly separates the slow-axis sweep region from the fast
        #   sweep region without relying solely on diff magnitudes.
        fast_min = fast_max = None
        if settings.get("limits_set"):
            # Batch: reuse the fast-axis limits decided for the first file
            fast_min = settings.get("fast_min")
            fast_max = settings.get("fast_max")
        else:
            use_limits = messagebox.askyesno(
                "Fast Axis Limits",
                f"Set fast axis sweep limits for '{fast_col}'?\n\n"
                f"Rows outside [min, max] will be treated as slow-axis data.\n"
                f"Data range: [{fast_data_min:.6g}, {fast_data_max:.6g}]\n\n"
                f"Recommended if the first row of each forward sweep\n"
                f"is being misclassified as slow-axis data.",
                parent=self.root)
            if use_limits:
                fast_min = simpledialog.askfloat(
                    "Fast Axis Min",
                    f"Fast axis minimum sweep value:\n(data min = {fast_data_min:.6g})",
                    initialvalue=fast_data_min, parent=self.root)
                if fast_min is None:
                    return False
                fast_max = simpledialog.askfloat(
                    "Fast Axis Max",
                    f"Fast axis maximum sweep value:\n(data max = {fast_data_max:.6g})",
                    initialvalue=fast_data_max, parent=self.root)
                if fast_max is None:
                    return False
            settings["limits_set"] = True
            settings["fast_min"] = fast_min
            settings["fast_max"] = fast_max

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
        if fast_min is not None or fast_max is not None:
            print(f"Smart Split: fast axis limits = [{fast_min:.6g}, {fast_max:.6g}]")

        # --- Segment Detection using activity-based split ---
        result = split_by_activity(df, fast_col, slow_col, fast_threshold,
                                   slow_threshold, fast_min=fast_min, fast_max=fast_max)

        counts = {k: (len(result[k]), sum(len(s) for s in result[k]))
                  for k in ("fast_fwd", "fast_bwd", "slow_fwd", "slow_bwd")}
        print(f"Smart Split: fast fwd {counts['fast_fwd'][0]} segs / {counts['fast_fwd'][1]} rows, "
              f"fast bwd {counts['fast_bwd'][0]} segs / {counts['fast_bwd'][1]} rows, "
              f"slow fwd {counts['slow_fwd'][0]} segs / {counts['slow_fwd'][1]} rows, "
              f"slow bwd {counts['slow_bwd'][0]} segs / {counts['slow_bwd'][1]} rows, "
              f"dropped {result['dropped']} rows")

        # --- Save Files ---
        self.save_files_smart(file_path, fast_col, slow_col,
                              result["fast_fwd"], result["fast_bwd"],
                              result["slow_fwd"], result["slow_bwd"])
        return True

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
        if not self._batch:
            messagebox.showinfo("Success", msg)
            self.root.quit()
        return msg

    # =========================================================
    # MODE: Snake - Auto Detect
    # =========================================================
    def process_snake(self, df, file_path, settings=None):
        """Auto-detect sweeps and alternate them into Fwd/Bwd."""
        settings = settings if settings is not None else {}
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Sweep Axis",
                                                           settings=settings)
        if axis_col is None:
            return False
        if axis_col not in df.columns:
            raise ValueError(f"Column '{axis_col}' not found in this file "
                             f"(available: {', '.join(df.columns)})")

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return True

        fwd, bwd = [], []
        for i, sweep in enumerate(sweeps):
            if i % 2 == 0:
                fwd.append(sweep)
            else:
                bwd.append(sweep)

        self.save_simple(file_path, fwd, bwd, f"Snake_{axis_col}")
        return True

    # =========================================================
    # MODE: Standard Loop - Auto Detect
    # =========================================================
    def process_standard_loop(self, df, file_path, settings=None):
        """Auto-detect sweeps, group into cycles, split into Fwd/Bwd."""
        settings = settings if settings is not None else {}
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Loop Axis",
                                                           settings=settings)
        if axis_col is None:
            return False
        if axis_col not in df.columns:
            raise ValueError(f"Column '{axis_col}' not found in this file "
                             f"(available: {', '.join(df.columns)})")

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return True

        sweeps_per_cycle = settings.get("sweeps_per_cycle")
        if sweeps_per_cycle is None:
            sweeps_per_cycle = simpledialog.askinteger(
                "Config", f"Detected {len(sweeps)} sweeps.\nSweeps per cycle:",
                initialvalue=2, parent=self.root)
            if not sweeps_per_cycle:
                return False
            settings["sweeps_per_cycle"] = sweeps_per_cycle

        split = settings.get("split")
        if split is None:
            split = simpledialog.askinteger(
                "Config", "Forward sweeps per cycle:",
                initialvalue=sweeps_per_cycle // 2, parent=self.root)
            if split is None:
                return False
            settings["split"] = split

        fwd, bwd = [], []
        for i in range(0, len(sweeps), sweeps_per_cycle):
            block = sweeps[i:i + sweeps_per_cycle]
            if len(block) < sweeps_per_cycle:
                break
            fwd.extend(block[:split])
            bwd.extend(block[split:])

        self.save_simple(file_path, fwd, bwd, f"StandardLoop_{axis_col}")
        return True

    # =========================================================
    # MODE: Hysteresis - Auto Detect
    # =========================================================
    def process_hysteresis(self, df, file_path, settings=None):
        """Auto-detect sweeps, group into hysteresis blocks, split by sweep indices."""
        settings = settings if settings is not None else {}
        axis_col, threshold = self._ask_axis_and_threshold(df, title_prefix="Hysteresis Axis",
                                                           settings=settings)
        if axis_col is None:
            return False
        if axis_col not in df.columns:
            raise ValueError(f"Column '{axis_col}' not found in this file "
                             f"(available: {', '.join(df.columns)})")

        sweeps = self._auto_detect_sweeps(df, axis_col, threshold)
        if not sweeps:
            messagebox.showinfo("Info", "No sweep segments detected.")
            return True

        sweeps_per_block = settings.get("sweeps_per_block")
        if sweeps_per_block is None:
            sweeps_per_block = simpledialog.askinteger(
                "Config", f"Detected {len(sweeps)} sweeps.\nSweeps per hysteresis block:",
                initialvalue=3, parent=self.root)
            if not sweeps_per_block:
                return False
            settings["sweeps_per_block"] = sweeps_per_block

        s1 = settings.get("hyst_split1")
        if s1 is None:
            s1 = simpledialog.askinteger(
                "Config",
                "Split 1 (sweep index where backward starts):\n"
                "(Sweeps 0..s1-1 are Forward part 1)",
                initialvalue=1, parent=self.root)
            if s1 is None:
                return False
            settings["hyst_split1"] = s1

        s2 = settings.get("hyst_split2")
        if s2 is None:
            s2 = simpledialog.askinteger(
                "Config",
                "Split 2 (sweep index where forward resumes):\n"
                f"(Sweeps {s1}..(Split 2 - 1) are Backward, sweeps Split 2..end are Forward part 2)",
                initialvalue=2, parent=self.root)
            if s2 is None:
                return False
            settings["hyst_split2"] = s2

        fwd, bwd = [], []
        for i in range(0, len(sweeps), sweeps_per_block):
            block = sweeps[i:i + sweeps_per_block]
            if len(block) < sweeps_per_block:
                break
            fwd.extend(block[:s1])
            fwd.extend(block[s2:])
            bwd.extend(block[s1:s2])

        self.save_simple(file_path, fwd, bwd, f"Hysteresis_{axis_col}")
        return True

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
        if not self._batch:
            messagebox.showinfo("Success", msg)
            self.root.quit()
        return msg


def _self_test():
    """Synthetic two-axis map: fwd+bwd fast sweeps at 2 slow setpoints, slow
    ramp up between them, slow ramp down at the end, pauses at every
    turnaround. Verifies fast axis matches the Forward/Backward Organizer
    behavior, slow sweeps get their own segments, and the boundary row is
    intentionally duplicated between fast and slow outputs."""
    vals = []
    for sp in (0.0, 1.0):
        vals += [(f, sp) for f in np.arange(0.0, 3.0 + 1e-9, 0.1)]    # fwd sweep
        if sp == 0.0:
            # peak pause with slow-axis jitter: steps exceed slow_threshold
            # but net travel ~0 — must NOT be excised as a slow region
            vals += [(3.0, 0.0), (3.0, 0.08), (3.0, 0.0)]
        else:
            vals += [(3.0, sp)] * 2                                   # peak pause
        vals += [(f, sp) for f in np.arange(2.9, -1e-9, -0.1)]        # bwd sweep
        vals += [(0.0, sp)] * 2                                       # valley pause
        if sp == 0.0:
            vals += [(0.0, s) for s in np.arange(0.1, 1.0 + 1e-9, 0.1)]  # slow up
    vals += [(0.0, s) for s in np.arange(0.9, -1e-9, -0.1)]           # slow down
    df = pl.DataFrame({"time(s)": np.arange(len(vals), dtype=float),
                       "gate(V)": [v[0] for v in vals],
                       "field(T)": [v[1] for v in vals]})

    res = split_by_activity(df, "gate(V)", "field(T)", 0.05, 0.05)

    # fast axis, organizer convention: fwd ends at its peak row; the pause
    # (incl. the jitter rows) back-fills into the upcoming bwd sweep
    assert [len(s) for s in res["fast_fwd"]] == [31, 31], [len(s) for s in res["fast_fwd"]]
    assert [len(s) for s in res["fast_bwd"]] == [36, 35], [len(s) for s in res["fast_bwd"]]
    assert all(s["gate(V)"].max() == 3.0 for s in res["fast_fwd"])
    assert all(abs(float(s["gate(V)"].min())) < 1e-9 for s in res["fast_bwd"])

    # slow axis: one up ramp, one down ramp, each opening at the first row
    # where the slow axis moved — that row is also the last row of the
    # preceding fast bwd sweep (duplication). The jitter rows (gate = 3.0)
    # must not appear in any slow segment.
    assert [len(s) for s in res["slow_fwd"]] == [10], [len(s) for s in res["slow_fwd"]]
    assert [len(s) for s in res["slow_bwd"]] == [10], [len(s) for s in res["slow_bwd"]]
    assert all(float(s["gate(V)"].max()) == 0.0
               for s in res["slow_fwd"] + res["slow_bwd"])
    assert float(res["fast_bwd"][0]["time(s)"][-1]) == float(res["slow_fwd"][0]["time(s)"][0])
    assert float(res["fast_bwd"][1]["time(s)"][-1]) == float(res["slow_bwd"][0]["time(s)"][0])
    assert res["dropped"] == 0, res["dropped"]

    # no slow-axis movement (pure gate map): no slow segments at all
    vals2 = []
    vals2 += [(f, 0.0) for f in np.arange(0.0, 3.0 + 1e-9, 0.1)]
    vals2 += [(3.0, 0.0)] * 2
    vals2 += [(f, 0.0) for f in np.arange(2.9, -1e-9, -0.1)]
    vals2 += [(0.0, 0.0)] * 2
    df2 = pl.DataFrame({"time(s)": np.arange(len(vals2), dtype=float),
                        "gate(V)": [v[0] for v in vals2],
                        "field(T)": [v[1] for v in vals2]})
    res2 = split_by_activity(df2, "gate(V)", "field(T)", 0.05, 0.05)
    assert res2["slow_fwd"] == [] and res2["slow_bwd"] == []
    assert [len(s) for s in res2["fast_fwd"]] == [31]
    assert [len(s) for s in res2["fast_bwd"]] == [34]
    print("smart orginizer self-test OK")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _self_test()
    else:
        app = ScanOrganizer()
        app.root.mainloop()