import csv
import os
import tkinter as tk
from tkinter import filedialog

def convert_txt_to_csv(input_file, output_file):
    """
    Converts a text file separated by spaces or tabs into a CSV.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            
            writer = csv.writer(outfile)
            
            for line in infile:
                row = line.split()
                if row: 
                    writer.writerow(row)
                    
        print(f"\n✅ Success! Your file has been saved as:\n{output_file}")
        
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

def main():
    # 1. Set up the file picker and hide the empty background window
    root = tk.Tk()
    root.withdraw()
    
    # Force the window to appear on top of other windows (helpful on Mac/Windows)
    root.attributes('-topmost', True)

    print("Opening file picker... Please select your text file.")

    # 2. Open the file dialog
    input_filepath = filedialog.askopenfilename(
        title="Select the Text File to Convert",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    # 3. Check if the user clicked "Cancel"
    if not input_filepath:
        print("No file selected. Exiting script.")
        return

    # 4. Auto-generate the output name (swap .txt for .csv)
    # This splits the path into everything before the extension, and the extension itself
    base_name, _ = os.path.splitext(input_filepath)
    output_filepath = base_name + '.csv'

    # 5. Run the conversion
    print(f"Converting: {input_filepath} ...")
    convert_txt_to_csv(input_filepath, output_filepath)

if __name__ == "__main__":
    main()