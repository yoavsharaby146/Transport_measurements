import polars as pl
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os


def _ask_axis_and_threshold(df, root):
    """Ask user to select an axis column and change threshold.
    Returns (col_name, threshold) or (None, None) if cancelled."""
    columns = df.columns
    if not columns:
        messagebox.showerror("Error", "CSV appears to be empty or has no headers.")
        return None, None

    # --- Column selection dialog ---
    col_window = tk.Toplevel(root)
    col_window.title("Select Axis Column")
    col_window.geometry("320x180")
    col_window.lift()

    result = {'col': None}

    tk.Label(col_window, text="Which column is the sweep axis?",
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
    root.wait_window(col_window)

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
        initialvalue=default_thresh, parent=root)

    if threshold is None:
        return None, None

    return col, threshold


def _auto_detect_blocks_by_direction(df, axis_col, threshold):
    """Detect contiguous blocks by monitoring direction changes in axis_col.

    How it works:
    1. Compute diff of axis column
    2. Classify each diff as +1 (increasing), -1 (decreasing), or 0 (below threshold)
    3. Forward-fill zeros with previous real direction
    4. Detect direction flips -> those are block boundaries
    5. Each same-direction segment is one block

    Returns a list of DataFrames, each being one contiguous block.
    """
    df = df.with_columns([
        pl.col(axis_col).diff().alias("_diff")
    ])

    df = df.with_columns([
        pl.when(pl.col("_diff") > threshold)
        .then(1)
        .when(pl.col("_diff") < -threshold)
        .then(-1)
        .otherwise(0)
        .alias("_dir_raw")
    ])

    # Forward-fill 0s with the last known direction
    # Replace leading 0s with the first non-zero direction found
    df = df.with_columns([
        pl.when(pl.col("_dir_raw") == 0)
        .then(None)
        .otherwise(pl.col("_dir_raw"))
        .alias("_dir_ff")
    ])

    # Forward fill, then backward fill for any remaining nulls at the start
    df = df.with_columns([
        pl.col("_dir_ff").fill_null(strategy="forward").fill_null(strategy="backward").alias("_dir")
    ])

    # Detect direction changes (block boundaries)
    df = df.with_columns([
        (pl.col("_dir") != pl.col("_dir").shift(1))
        .fill_null(True)
        .cum_sum()
        .alias("_block_id")
    ])

    # Split into blocks
    blocks = []
    grouped = df.group_by('_block_id', maintain_order=True)
    for block_id, block in grouped:
        # Drop helper columns
        clean_block = block.drop(['_diff', '_dir_raw', '_dir_ff', '_dir', '_block_id'])
        if len(clean_block) >= 2:
            blocks.append(clean_block)

    return blocks


def reverse_blocks():
    """Main function: load CSV, auto-detect blocks by direction, reverse each block."""
    # 1. Setup GUI (hidden root window)
    root = tk.Tk()
    root.withdraw()

    print("--- CSV BLOCK REVERSER (Auto-Detect) ---")
    print("Please select your CSV file...")

    file_path = filedialog.askopenfilename(
        title="Select Data CSV",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        print("No file selected.")
        return

    try:
        # 2. Read the CSV file
        df = pl.read_csv(file_path, infer_schema_length=10000)

        total_rows = len(df)
        print(f"File loaded: {os.path.basename(file_path)}")
        print(f"Total rows: {total_rows}")
        print(f"Columns: {df.columns}")

        # 3. Ask user for axis column and threshold
        axis_col, threshold = _ask_axis_and_threshold(df, root)
        if axis_col is None:
            print("Cancelled.")
            return

        # 4. Auto-detect blocks by direction changes
        blocks = _auto_detect_blocks_by_direction(df, axis_col, threshold)

        if not blocks:
            messagebox.showinfo("Info", "No sweep blocks detected.")
            return

        print(f"Detected {len(blocks)} blocks")
        for i, block in enumerate(blocks):
            start_val = block[axis_col][0]
            end_val = block[axis_col][-1]
            direction = "↑" if end_val > start_val else "↓"
            print(f"  Block {i+1}: {len(block)} rows, "
                  f"{axis_col} {start_val:.4g} → {end_val:.4g} {direction}")

        # 5. Reverse each block independently
        reversed_blocks = [block.reverse() for block in blocks]

        # 6. Concatenate all reversed blocks (preserving block order)
        final_df = pl.concat(reversed_blocks)

        # 7. Generate output filename
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        output_filename = os.path.join(directory, f"{name_no_ext}_reversed_blocks.csv")

        # 8. Save
        final_df.write_csv(output_filename)

        success_msg = (f"Processing Complete!\n\n"
                       f"Axis column: '{axis_col}'\n"
                       f"Threshold: {threshold:.6g}\n"
                       f"Blocks detected: {len(blocks)}\n"
                       f"Original rows: {total_rows}\n"
                       f"Output rows: {len(final_df)}\n\n"
                       f"Saved to:\n{output_filename}")

        print(success_msg)
        messagebox.showinfo("Success", success_msg)

    except Exception as e:
        error_msg = f"An error occurred:\n{str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)


if __name__ == "__main__":
    reverse_blocks()