import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import os


def split_scans():
    # 1. Setup GUI to ask for file
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    print("Please select your CSV file...")
    file_path = filedialog.askopenfilename(
        title="Select your Data CSV",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        print("No file selected.")
        return

    try:
        # 2. Read the CSV file
        # Pandas uses the first row (Excel Row 1) as the header automatically.
        # Data starts at Excel Row 2 (which is Index 0).
        df = pd.read_csv(file_path)

        total_rows = len(df)
        block_size = 303    # (2 to 180 is 179 rows total)

        print(f"File loaded. Total rows: {total_rows}")

        # Lists to hold the chunks of data
        forward_chunks = []
        backward_chunks = []

        # 3. Iterate through the file in blocks of 179
        for i in range(0, total_rows, block_size):
            # Get the current block
            block = df.iloc[i: i + block_size]

            # Reset index to 0..178 for easier relative slicing
            current_block_reset = block.reset_index(drop=True)

            # --- SLICING LOGIC ---
            # Note: Pandas is 0-indexed and excludes the header.
            # Excel Row 2  = Index 0
            # Excel Row 46 = Index 44 (Slice 0:45)

            # 1. Forward Part 1 (Excel Rows 2-46)
            # 45 Rows total
            fwd_part1 = current_block_reset.iloc[0:76]

            # 2. Backward (Excel Rows 47-135)
            # 47 to 135 is 89 rows.
            # Starts at Index 45. Ends at Index 133. Slice 45:134.
            bwd_part = current_block_reset.iloc[76:227]

            # 3. Forward Part 2 (Excel Rows 136-180)
            # 136 to 180 is 45 rows.
            # Starts at Index 134. Ends at Index 178. Slice 134:179.
            fwd_part2 = current_block_reset.iloc[227:303]

            # Add to lists
            forward_chunks.append(fwd_part1)
            forward_chunks.append(fwd_part2)
            backward_chunks.append(bwd_part)

        # 4. Concatenate all chunks back into single DataFrames
        final_forward = pd.concat(forward_chunks, ignore_index=True)
        final_backward = pd.concat(backward_chunks, ignore_index=True)

        # 5. Generate output filenames
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        fwd_filename = os.path.join(directory, f"{name_no_ext}_forward.csv")
        bwd_filename = os.path.join(directory, f"{name_no_ext}_backward.csv")

        # 6. Save to CSV
        final_forward.to_csv(fwd_filename, index=False)
        final_backward.to_csv(bwd_filename, index=False)

        success_msg = (f"Processing Complete!\n\n"
                       f"Original Rows: {total_rows}\n"
                       f"Forward Rows: {len(final_forward)}\n"
                       f"Backward Rows: {len(final_backward)}\n\n"
                       f"Saved:\n{fwd_filename}\n{bwd_filename}")

        print(success_msg)
        messagebox.showinfo("Success", success_msg)

    except Exception as e:
        error_msg = f"An error occurred:\n{str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)


if __name__ == "__main__":
    split_scans()