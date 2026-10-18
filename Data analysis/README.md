# CSV Data Processing Scripts

A suite of GUI-based Python tools for merging, organizing, reversing, and computing across CSV measurement data.  
Designed for transport-measurement workflows (e.g., gate maps, hysteresis loops, standard sweeps).

All tools that read measurement CSVs automatically skip any metadata preamble before the
column-title row (via the shared `csv_utils` helper, described below), so they operate only
on the titled data columns — for files both with and without a preamble.

---

## Dependencies

| Package   | Install                        |
|-----------|--------------------------------|
| polars    | `pip install polars`           |
| numpy     | `pip install numpy`            |
| tkinter   | Included with standard Python  |

---

## Shared Helper: `csv_utils.py`

All CSV-loading scripts use this module to handle measurement files that start
with metadata lines (general settings, sweep config, …) before the column titles.

- **`detect_header_row(filepath)`** — returns the line index of the column-title
  row. Detection: first line (within the first 50) containing `time(s)`
  (case-insensitive), the convention used by all measurement procedures. If no
  such line exists, the file has no preamble and `0` is returned.
- **`read_data_csv(filepath, **kwargs)`** — loads a CSV via polars, skipping any
  preamble so callers see only titled data columns. Defaults
  (`infer_schema_length=10000`, `truncate_ragged_lines=True`, `ignore_errors=True`)
  can be overridden via kwargs.

Run `python csv_utils.py` for a built-in self-check of the detection logic.

---

## Scripts

### 1. `csv_merger.py` — CSV File Merger

Merges multiple CSV measurement files into a single sorted file.

**Features:**
- **File picker** — select two or more CSV files via a dialog
- **Auto header detection** — skips metadata lines before the column header using `csv_utils` (see above)
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
  - **Smart Split (Fast & Slow Axis)** — fast-axis Fwd/Bwd split uses the exact direction-sign detection of the Forward/Backward Organizer mode (identical turnaround behavior). Slow-axis sweep regions (slow axis sweeping with real net travel, ≥ 3× the slow step threshold — short jitter/approach movements are ignored and stay with the fast data) are extracted separately into their own Fwd/Bwd files — created only when slow-axis sweeps exist. The boundary row (last fast-sweep point = first slow-sweep point) intentionally appears in both files
  - **Forward/Backward Organizer — Direction Split** — single-axis split into forward and backward sweeps using direction-sign detection (handles repeated boundary values)
  - **Hysteresis — Auto Detect** — groups sweeps into hysteresis blocks (e.g., 0 → SP1 → SP2 → 0), splits by configurable sweep indices
  - **Standard Loop — Auto Detect** — groups sweeps into cycles (e.g., 0 → Max → 0), configurable sweeps-per-cycle and forward/backward split
  - **Snake — Auto Detect** — alternates detected sweeps into forward and backward groups
- **Auto thresholding** — suggests sensible change thresholds based on data range/median step
- **Setpoint clustering** — for Smart Split mode, groups slow-axis hold values into distinct setpoints

**Usage:**
```bash
python "smart orginizer.py"
```

**Self-test** (synthetic two-axis map with turnarounds, pauses, and slow ramps):
```bash
python "smart orginizer.py" --test
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

### 6. `txt_csv converter.py` — Text-to-CSV Converter

Converts whitespace/tab-separated text files (e.g., LabView logs from the dilution setup) into proper comma-separated CSV files.

**Usage:**
```bash
python "txt_csv converter.py"
```

**Workflow:**
1. Select one or more `.txt` input files
2. Choose an output location — converted `.csv` files are written alongside

### 7. `csv_integrator.py` — Cumulative Trapezoid Integrator

Adds a cumulative trapezoid integral of a Y column over an X column (e.g. ∫V dI over a bias sweep) to a measurement CSV.

**Features:**
- **Start/direction agnostic** — the trapezoid uses the actual per-step dx, so sweeps that start anywhere (not necessarily 0) and run up or down integrate correctly with no special handling
- **Map aware** — pick a slow-axis column (gate voltage, field); integration resets at every slow-axis setpoint (same clustering logic as `map_splitter.py`) so it never runs across setpoint jumps. Auto-detected tolerance with manual override
- **Hysteresis aware** — optionally reset at every sweep-direction reversal (each monotonic run gets its own integral, starting at 0). Turnaround points are shared between runs; jitter/repeated boundary values don't cause false splits
- **5 reset modes** — never (whole file), per setpoint, per direction reversal, per setpoint + reversal, per zero crossing of X (both sides anchored at zero: Φ(I) = ∫₀^I y dx from 0 to the positive edge and from 0 to the negative edge, independently of sweep order; map-aware, splits within each slow-axis setpoint)
- **Batch mode** — select multiple CSVs in the file dialog: same settings applied to every file, each saved automatically as `<name>_integrated.csv` beside its source. Files missing required columns are skipped and reported
- **Multiple Y columns** — ctrl/shift-click several integrands (e.g. several lock-in channels); each gets its own `integ_<Ycolumn>` output column, sharing the same X, scales, and reset mode
- **X scale / Y divide** — constant conversions applied before integrating: X multiplied by `x_scale` (e.g. 1/R when X is a stored voltage representing current = U/R), Y divided by `y_div` (e.g. lock-in AC excitation current I_ac — Y/I_ac = dV/dI, so the integral reconstructs voltage); defaults 1.0
- **Preamble-safe loading** via shared `csv_utils` helper

**Usage:**
```bash
python csv_integrator.py
```

**Self-check** (exact linear integral, setpoint reset, direction reset, jitter guard, end-to-end):
```bash
python csv_integrator.py --selfcheck
```

**Workflow:**
1. Select a CSV data file
2. Pick the X column (integrate over, e.g. bias current), Y column (integrand, e.g. voltage), slow axis (or "None"), and reset mode
3. If a slow axis is used with setpoint reset, review the auto-detected tolerance
4. Save — output = all original columns + new `integ_<Ycolumn>` column

**Physics note:** for a bias sweep +30µA → −30µA in 0.1µA steps, each output point k holds the running trapezoid sum Σ (V_j + V_{j+1})/2 · (I_{j+1} − I_j) from the sweep start to k. Result units are V·A.

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
