# CSV Data Processing Scripts

A suite of GUI-based Python tools for merging, organizing, reversing, and computing across CSV measurement data.  
Designed for transport-measurement workflows (e.g., gate maps, hysteresis loops, standard sweeps).

---

## Dependencies

| Package   | Install                        |
|-----------|--------------------------------|
| polars    | `pip install polars`           |
| numpy     | `pip install numpy`            |
| tkinter   | Included with standard Python  |

---

## Scripts

### 1. `csv_merger.py` — CSV File Merger

Merges multiple CSV measurement files into a single sorted file.

**Features:**
- **File picker** — select two or more CSV files via a dialog
- **Auto header detection** — skips metadata lines before the actual column header (looks for `Time(s)` / `Time (s)`)
- **Column validation** — warns if files have different columns; falls back to common columns automatically
- **Sort-by-column** — after merging, a dialog lets you pick which column to sort by
- **Metadata preservation** — pre-header lines from the first file are carried over to the output

**Usage:**
```bash
python csv_merger.py
```

**Workflow:**
1. Select CSV files to merge (at least 2)
2. Files are read and validated
3. Choose a sort column from the merged data
4. Choose a save location for the output file

---

### 2. `smart orginizer.py` — Scan Organizer

Splits a single measurement CSV into organized Forward (Fwd) and Backward (Bwd) sweep files based on the selected scan mode.

**Features:**
- **5 scan modes** (all with auto-detection):
  - **Smart Split (Fast & Slow Axis)** — separates fast-axis sweeps from slow-axis hold segments; clusters slow-axis setpoints
  - **Gate Map — Direction Split** — uses direction-sign detection to split forward and backward sweeps (handles repeated boundary values)
  - **Hysteresis — Auto Detect** — groups sweeps into hysteresis blocks (e.g., 0 → SP1 → SP2 → 0), splits by configurable sweep indices
  - **Standard Loop — Auto Detect** — groups sweeps into cycles (e.g., 0 → Max → 0), configurable sweeps-per-cycle and forward/backward split
  - **Snake — Auto Detect** — alternates detected sweeps into forward and backward groups
- **Auto thresholding** — suggests sensible change thresholds based on data range/median step
- **Setpoint clustering** — for Smart Split mode, groups slow-axis hold values into distinct setpoints

**Usage:**
```bash
python "smart orginizer.py"
```

**Workflow:**
1. Select a scan mode from the dropdown
2. Open a CSV data file
3. Follow the dialogs to select axis columns and thresholds
4. Output files are saved in the same directory with descriptive names, e.g.:
   - `filename_Vg_Fwd.csv`, `filename_Vg_Bwd.csv`
   - `filename_Snake_Vg_Fwd.csv`, `filename_Snake_Vg_Bwd.csv`

---

### 3. `reverser.py` — Block Reverser

Reverses measurement blocks in a CSV file — the counterpart operation to the Scan Organizer.  
Useful when you need the sweep direction flipped (e.g., to align forward and backward data).

**Features:**
- **Auto-detects block structure** from a user-selected sweep column:
  - **Simple blocks** (Fwd/Bwd, Snake) — single continuous sweep per block, just reversed
  - **Hysteresis blocks** — multiple segments per block that are reordered into a continuous sweep, deduplicated, then reversed
- **Segment splitting** — detects large jumps in the sweep column to identify segment boundaries
- **Smart segment reordering** — tries all permutations to find the ordering with minimal gaps between endpoints
- **Duplicate removal** — removes overlapping rows at segment junctions
- **Configurable thresholds** — auto-computed with option to manually adjust

**Usage:**
```bash
python reverser.py
```

**Workflow:**
1. Select a CSV data file
2. Choose the sweep axis column
3. Review/adjust the auto-detected jump threshold
4. The script detects segments, identifies block structure, reverses each block, and saves the result as `filename_reversed.csv`

---

### 4. `map_splitter.py` — Slow Axis Sweep Extractor

Splits a map measurement CSV into individual files — one per slow-axis setpoint — so you can examine a single sweep at a time.

**Features:**
- **Slow axis selection** — pick which column is the slow sweep axis (e.g., gate voltage)
- **Auto-detected tolerance** — automatically computes a sensible tolerance for grouping nearby values into distinct setpoints (half the minimum gap between unique values)
- **Adjustable tolerance** — user can tweak the tolerance before splitting
- **Output folder picker** — choose where all the split files are saved
- **Descriptive filenames** — each file is named with the original filename, axis, and setpoint value (e.g., `data_Vg(V)_at_-3.csv`)

**Usage:**
```bash
python map_splitter.py
```

**Workflow:**
1. Select a map measurement CSV file
2. Choose the slow sweep axis column
3. Review/adjust the auto-detected setpoint tolerance
4. Choose an output folder
5. The script creates one CSV per slow-axis setpoint, each containing all rows at that setpoint value

---

### 5. `csv_operations.py` — Cross-File Column Math Tool

Load multiple CSV files, reference their columns in math expressions, and export a new CSV with computed + copied columns.

**Features:**
- **Multi-file support (up to 5)** — each file is color-coded and aliased (`f1`, `f2`, …). Row counts are shown per file; a warning appears if they differ (the minimum count is used)
- **Column references** — click a reference chip (e.g. `f1.Voltage`) to insert it into the focused formula. Bare names like `a+b` resolve against file 1
- **Formula columns** — define computed columns with arbitrary math expressions (supports the `math` module, e.g. `sqrt(f1.x**2 + f1.y**2)`). Live preview updates as you type
- **Copy columns** — pass raw columns through to the output unchanged via checkboxes, grouped by file in scrollable columns
- **Formula I/O** — load/save formula definitions from a `.txt` file (format: `name<TAB>expression`, one per line; supports append or replace)
- **Preview & export** — on-screen table preview (first 20 rows) before exporting to CSV

**Usage:**
```bash
python csv_operations.py
```

**Workflow:**
1. Click **Add CSV files…** and select one or more CSVs (up to 5)
2. In **Column references**, click chips to insert them into a formula entry
3. In **Copy columns**, tick any raw columns you want passed through to the output
4. In **Computed columns**, add formula columns (optionally load them from a `.txt` file)
5. Review the preview table, then **Export CSV…** to save the result

**UI layout note:** file lists, column references, and copy columns are displayed in fixed-height scrollable panels (vertical columns per file) so the window stays narrow even when files have many columns.

---

## Typical Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌──────────────┐
│  csv_merger │ ──► │  smart orginizer │ ──► │  reverser   │     │ map_splitter │
│             │     │                  │     │             │     │              │
│ Merge multi │     │ Split into       │     │ Reverse     │     │ Split map    │
│ CSV files   │     │ Fwd / Bwd sweeps │     │ blocks if   │     │ into single  │
│ into one    │     │ by scan type     │     │ needed      │     │ slow-axis    │
└─────────────┘     └──────────────────┘     └─────────────┘     │ sweeps       │
                                                                └──────────────┘
```

1. **Merge** — Combine multiple measurement CSV files into one using `csv_merger.py`
2. **Organize** — Split the merged data into forward/backward sweep files using `smart orginizer.py`
3. **Reverse** — Flip sweep direction of any output file using `reverser.py`
4. **Map Split** — Extract individual slow-axis sweeps from a map measurement using `map_splitter.py`
