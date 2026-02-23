import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os


class ScanOrganizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Scan Organizer")
        self.root.geometry("350x200")

        # --- ADD THESE LINES HERE ---
        self.root.lift()  # Bring window to top of stack
        self.root.attributes('-topmost', True)  # Force it to be the top-most window
        self.root.after_idle(self.root.attributes, '-topmost', False)  # Allow it to be moved behind later
        # ----------------------------

        # --- UI Setup ---
        tk.Label(self.root, text="Select Scan Type:", font=("Arial", 11, "bold")).pack(pady=15)

        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(self.root, textvariable=self.mode_var, state="readonly", width=30)
        self.mode_combo['values'] = (
            "Hysteresis (0 -> SP1 -> SP2 -> 0)",
            "Standard Loop (0 -> Max -> 0)",
            "Snake (Alternating)"
        )
        self.mode_combo.current(0)
        self.mode_combo.pack(pady=5)

        tk.Button(self.root, text="Select File & Run", command=self.process_selection, height=2, width=20).pack(pady=25)

    def process_selection(self):
        mode = self.mode_var.get()

        # 1. Ask for file
        file_path = filedialog.askopenfilename(
            title="Select your Data CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            # 2. Load Data
            df = pd.read_csv(file_path)

            # 3. Route to correct logic
            if mode == "Hysteresis (0 -> SP1 -> SP2 -> 0)":
                self.process_hysteresis(df, file_path)
            elif mode == "Standard Loop (0 -> Max -> 0)":
                self.process_standard_loop(df, file_path)
            elif mode == "Snake (Alternating)":
                self.process_snake(df, file_path)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    # ---------------------------------------------------------
    # MODE 1: Hysteresis (Customizable)
    # Pattern: Fwd1 -> Bwd -> Fwd2
    # ---------------------------------------------------------
    def process_hysteresis(self, df, file_path):
        # 1. Get User Inputs
        block_size = simpledialog.askinteger("Configuration", "Enter TOTAL rows per block (e.g. 303):",
                                             parent=self.root)
        if not block_size: return

        split_1 = simpledialog.askinteger("Configuration", f"Enter 1st Split Index (End of Fwd 1)\n(e.g. 76):",
                                          parent=self.root)
        if split_1 is None: return

        split_2 = simpledialog.askinteger("Configuration", f"Enter 2nd Split Index (End of Bwd)\n(e.g. 227):",
                                          parent=self.root)
        if split_2 is None: return

        forward_chunks = []
        backward_chunks = []

        # 2. Process
        for i in range(0, len(df), block_size):
            block = df.iloc[i: i + block_size].reset_index(drop=True)

            # Skip incomplete blocks if they don't match the user's expected size
            if len(block) < block_size:
                print(f"Skipping incomplete block at index {i} (Length: {len(block)})")
                break

            # Slicing based on user input
            fwd_part1 = block.iloc[0:split_1]  # 0 to Split 1
            bwd_part = block.iloc[split_1:split_2]  # Split 1 to Split 2
            fwd_part2 = block.iloc[split_2:block_size]  # Split 2 to End

            forward_chunks.extend([fwd_part1, fwd_part2])
            backward_chunks.append(bwd_part)

        self.save_files(file_path, forward_chunks, backward_chunks, "Hysteresis")

    # ---------------------------------------------------------
    # MODE 2: Standard Loop (Customizable)
    # Pattern: 0 -> Max (Forward) -> 0 (Backward)
    # ---------------------------------------------------------
    def process_standard_loop(self, df, file_path):
        # 1. Get User Inputs
        cycle_len = simpledialog.askinteger("Configuration", "Enter TOTAL rows per cycle (e.g. 200):", parent=self.root)
        if not cycle_len: return

        default_split = cycle_len // 2
        split_idx = simpledialog.askinteger("Configuration",
                                            f"Enter Split Point (End of Forward)\nDefault is {default_split}:",
                                            initialvalue=default_split, parent=self.root)
        if split_idx is None: return

        forward_chunks = []
        backward_chunks = []

        # 2. Process
        for i in range(0, len(df), cycle_len):
            block = df.iloc[i: i + cycle_len].reset_index(drop=True)
            if len(block) < cycle_len: break

            fwd = block.iloc[0:split_idx]
            bwd = block.iloc[split_idx:cycle_len]

            forward_chunks.append(fwd)
            backward_chunks.append(bwd)

        self.save_files(file_path, forward_chunks, backward_chunks, "StandardLoop")

    # ---------------------------------------------------------
    # MODE 3: Snake (Customizable)
    # Pattern: Scan 1 (Fwd), Scan 2 (Bwd), Scan 3 (Fwd)...
    # ---------------------------------------------------------
    def process_snake(self, df, file_path):
        # 1. Get User Inputs
        sweep_len = simpledialog.askinteger("Configuration", "Enter rows per SINGLE sweep (e.g. 100):",
                                            parent=self.root)
        if not sweep_len: return

        forward_chunks = []
        backward_chunks = []

        # 2. Process
        chunk_counter = 0
        for i in range(0, len(df), sweep_len):
            block = df.iloc[i: i + sweep_len].reset_index(drop=True)
            # You might want to process partial blocks for snake, but usually not.
            if len(block) < sweep_len: break

            if chunk_counter % 2 == 0:
                # Even: Forward
                forward_chunks.append(block)
            else:
                # Odd: Backward
                backward_chunks.append(block)

            chunk_counter += 1

        self.save_files(file_path, forward_chunks, backward_chunks, "Snake")

    # ---------------------------------------------------------
    # Helper: Save Files
    # ---------------------------------------------------------
    def save_files(self, original_path, fwd_list, bwd_list, suffix):
        if not fwd_list and not bwd_list:
            messagebox.showwarning("Warning", "No data blocks found. Please check your settings.")
            return

        final_fwd = pd.concat(fwd_list, ignore_index=True) if fwd_list else pd.DataFrame()
        final_bwd = pd.concat(bwd_list, ignore_index=True) if bwd_list else pd.DataFrame()

        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        name_no_ext = os.path.splitext(filename)[0]

        fwd_name = os.path.join(directory, f"{name_no_ext}_{suffix}_Forward.csv")
        bwd_name = os.path.join(directory, f"{name_no_ext}_{suffix}_Backward.csv")

        if not final_fwd.empty: final_fwd.to_csv(fwd_name, index=False)
        if not final_bwd.empty: final_bwd.to_csv(bwd_name, index=False)

        msg = (f"Processing Complete ({suffix})!\n\n"
               f"Forward Rows: {len(final_fwd)}\n"
               f"Backward Rows: {len(final_bwd)}\n\n"
               f"Saved to:\n{directory}")

        print(msg)
        messagebox.showinfo("Success", msg)
        self.root.quit()


if __name__ == "__main__":
    app = ScanOrganizer()
    app.root.mainloop()