import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import os


def reverse_blocks():
    # 1. Setup GUI (hidden root window)
    root = tk.Tk()
    root.withdraw()

    print("--- CSV ROW REVERSER ---")
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
        # Header is row 1 (automatically handled). Data starts at Excel Row 2 (Index 0).
        df = pd.read_csv(file_path)

        total_rows = len(df)
        period_size = 152 # Total rows per period (45 + 44)

        print(f"File loaded: {os.path.basename(file_path)}")
        print(f"Total rows: {total_rows}")

        processed_chunks = []

        # 3. Iterate through the file in blocks of 89 rows
        for i in range(0, total_rows, period_size):
            # Define range for Part 1 (Excel Rows 2-46 relative to start of block)
            # Length: 45 rows
            start_p1 = i
            end_p1 = i + 76

            # Define range for Part 2 (Excel Rows 47-90 relative to start of block)
            # Length: 44 rows (Total 89)
            start_p2 = end_p1
            end_p2 = i + 152

            # Slice the parts
            # Note: Pandas handles the last block gracefully even if it's shorter than 89
            part1 = df.iloc[start_p1:end_p1]
            part2 = df.iloc[start_p2:end_p2]

            # 4. REVERSE the order of rows in each part
            part1_reversed = part1.iloc[::-1]
            part2_reversed = part2.iloc[::-1]

            # 5. Add to our list (Part 1 first, then Part 2)
            processed_chunks.append(part1_reversed)
            processed_chunks.append(part2_reversed)

        # 6. Concatenate all processed chunks
        final_df = pd.concat(processed_chunks, ignore_index=True)

        # 7. Generate output filename
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        output_filename = os.path.join(directory, f"{name_no_ext}_reversed_blocks.csv")

        # 8. Save
        final_df.to_csv(output_filename, index=False)

        success_msg = (f"Processing Complete!\n\n"
                       f"Original Rows: {total_rows}\n"
                       f"Processed Rows: {len(final_df)}\n\n"
                       f"Saved to:\n{output_filename}")

        print(success_msg)
        messagebox.showinfo("Success", success_msg)

    except Exception as e:
        error_msg = f"An error occurred:\n{str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)


if __name__ == "__main__":
    reverse_blocks()