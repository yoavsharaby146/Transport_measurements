import os
import tkinter as tk
from tkinter import filedialog, ttk
import polars as pl


def pick_files():
    """Open a file dialog to select multiple CSV files."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    print("Select CSV files to merge (hold Ctrl/Shift to select multiple):")
    files = filedialog.askopenfilenames(
        title="Select CSV Files to Merge",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not files:
        print("No files selected. Exiting.")
        root.destroy()
        return None, root

    for i, f in enumerate(files, 1):
        print(f"  File {i}: {f}")

    root.destroy()
    return list(files), root


def pick_sort_column(columns):
    """Show a dialog to let the user pick which column to sort by."""
    root = tk.Tk()
    root.title("Select Sort Column")
    root.attributes('-topmost', True)
    root.geometry("400x150")
    root.resizable(False, False)

    selected_column = None

    tk.Label(root, text="Choose the column to sort the merged data by:", font=("Arial", 11)).pack(pady=(15, 5))

    combo = ttk.Combobox(root, values=columns, state="readonly", width=40)
    combo.set(columns[0])  # default to first column
    combo.pack(pady=5)

    def on_confirm():
        nonlocal selected_column
        selected_column = combo.get()
        root.destroy()

    btn = tk.Button(root, text="OK", command=on_confirm, width=10)
    btn.pack(pady=10)

    # Center on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()
    return selected_column


def detect_header_row(filepath, max_lines=20):
    """Detect the row index where the actual header starts (looks for 'Time(s)' or similar)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            stripped = line.strip().lower()
            if stripped.startswith("time(s)") or stripped.startswith("time (s)"):
                return i
    return 0


def main():
    # Step 1: Pick the CSV files to merge
    files, root = pick_files()
    if not files:
        return
    if len(files) < 2:
        print("Please select at least 2 files to merge. Exiting.")
        return

    # Step 2: Read all CSV files
    dfs = []
    first_skip_rows = detect_header_row(files[0])

    for i, filepath in enumerate(files):
        skip_rows = detect_header_row(filepath)
        print(f"\nReading file {i+1}/{len(files)} (skipping {skip_rows} header lines): {os.path.basename(filepath)}")
        df = pl.read_csv(filepath, skip_rows=skip_rows, infer_schema_length=10000)
        print(f"  Shape: {df.shape}  |  Columns: {df.columns}")

        # Validate compatible columns with first file
        if i > 0 and dfs[0].columns != df.columns:
            print(f"  ⚠️  Warning: Columns differ from file 1!")
            print(f"    File 1: {dfs[0].columns}")
            print(f"    File {i+1}: {df.columns}")

            common_cols = [c for c in dfs[0].columns if c in df.columns]
            if not common_cols:
                print("  ❌ No common columns. Skipping this file.")
                continue

            print(f"  Using {len(common_cols)} common columns.")
            df = df.select(common_cols)
            # Also trim previously stored dataframes to common columns
            dfs[:] = [d.select(common_cols) for d in dfs]

        dfs.append(df)

    if len(dfs) < 2:
        print("\n❌ Need at least 2 compatible files to merge. Exiting.")
        return

    # Step 3: Concatenate all
    merged = pl.concat(dfs)
    print(f"\nMerged shape (before sort): {merged.shape}")

    # Step 4: Let user pick the sort column
    sort_col = pick_sort_column(merged.columns)
    if not sort_col:
        print("No sort column selected. Using unsorted merge.")
    else:
        print(f"\nSorting by column: '{sort_col}'")
        merged = merged.sort(sort_col)

    # Step 5: Save the merged file
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    # Generate default output name based on first file
    base_dir = os.path.dirname(files[0])
    default_name = "merged_" + os.path.basename(files[0])

    output_path = filedialog.asksaveasfilename(
        title="Save Merged CSV File As",
        initialdir=base_dir,
        initialfile=default_name,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    root.destroy()

    if not output_path:
        print("No save location selected. Exiting without saving.")
        return

    # Write the header lines from first file (metadata before the column header) then the data
    if first_skip_rows > 0:
        with open(files[0], 'r', encoding='utf-8') as f:
            header_lines = [f.readline() for _ in range(first_skip_rows)]

        with open(output_path, 'w', encoding='utf-8') as f:
            for line in header_lines:
                f.write(line)

        with open(output_path, 'a', encoding='utf-8') as f:
            csv_data = merged.write_csv()
            f.write(csv_data)
    else:
        merged.write_csv(output_path)

    print(f"\n✅ Success! Merged {len(dfs)} files saved as:\n{output_path}")
    print(f"   Final shape: {merged.shape}")


if __name__ == "__main__":
    main()