# CSV Data Processing Scripts

A suite of GUI-based Python tools for merging, organizing, and reversing CSV measurement data.  
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

## Typical Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  csv_merger │ ──► │  smart orginizer │ ──► │  reverser   │
│             │     │                  │     │             │
│ Merge multi │     │ Split into       │     │ Reverse     │
│ CSV files   │     │ Fwd / Bwd sweeps │     │ blocks if   │
│ into one    │     │ by scan type     │     │ needed      │
└─────────────┘     └──────────────────┘     └─────────────┘
```

1. **Merge** — Combine multiple measurement CSV files into one using `csv_merger.py`
2. **Organize** — Split the merged data into forward/backward sweep files using `smart orginizer.py`
3. **Reverse** — Flip sweep direction of any output file using `reverser.py`