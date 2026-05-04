================================================================================
                INTERACTIVE DATA PLOTTER - User Guide
================================================================================

DESCRIPTION
-----------
A feature-rich interactive plotting application with a Tkinter GUI.
Supports CSV and Excel files, multiple plot types, extensive customization,
session save/load, and an Origin Pro-inspired interface.

REQUIREMENTS
------------
- Python 3.8+
- polars        (pip install polars)
- matplotlib     (pip install matplotlib)
- numpy          (pip install numpy)
- scipy          (pip install scipy)
- openpyxl       (pip install openpyxl)   -- optional, for Excel file support

Tkinter comes bundled with most Python installations.

RUNNING
-------
    python "Plot data.py"

The main window opens with a control panel on the left and a plot area on
the right. The window automatically sizes to 85% of your screen resolution
(max 1400x980) and centers on screen.


================================================================================
QUICK START
================================================================================

1. LOAD DATA
   - Click "Load Data File" to open the File Loading Wizard.
   - The wizard supports adding files from MULTIPLE folders in one session:
       * "Add Files" — browse and select CSV/Excel files from any folder.
       * "Add Folder" — batch-import all CSV/Excel files from a directory.
       * Remove or clear queued files before loading.
   - Click "Load All" to import the queued files, or select specific files
     and click "Load Selected Only".
   - Files appear in the dataset listbox. Click to select (Ctrl+click for
     multiple).
   - "Dataset Manager" opens a larger window for managing loaded files
     (shows row/column counts, syncs selection with main list).
   - "Unload" removes selected files from the list.

2. SELECT COLUMNS
   - Choose an "Axis Ref. File" (determines which columns appear in the
     dropdowns).
   - Check "Show All Columns (Union)" to see columns from ALL files.
   - Pick an X-axis column and one or more Y-axis columns.
   - For Dual Y-Axis mode: choose separate left/right Y columns.

3. CLICK "Update Plot"
   The plot renders in the right panel. You can also press "Export Plot" to
   save as PNG, PDF, or SVG (300 DPI).


================================================================================
PLOT TYPES
================================================================================

- Line            Standard line plot (default).
- Scatter         Scatter plot with points.
- Broken Y-Axis   Two vertically stacked subplots with a break in the Y axis.
                   Set "Break Start" and "Break End" in Ranges & Data.
- Color Map       2D heatmap using X, Y, Z columns with interpolation.
                   Requires exactly 1 file and 1 Y column + 1 Z column.
- Dual Y-Axis     Left and right Y axes. Two Y columns are mapped to the
                   two axes. If 2 files are selected, each goes to its own
                   axis.


================================================================================
CONTROL PANEL REFERENCE
================================================================================

DATA FILES section:
  Load Data File      Opens the File Loading Wizard (multi-folder, batch import
                       of CSV, XLSX, XLS files). Add files from different
                       folders, review the queue, then load all or selected.
  Dataset list        Click to select active datasets.
  Unload              Remove selected datasets.
  Dataset Manager     Opens a separate management window with file details
                       (row/column counts) and synced selection.

SESSION section:
  Save Session        Saves ALL data + settings to a JSON file.
  Load Session        Restores a previously saved session.
  Set Cache Folder    Choose default folder for session files.

PLOT SETTINGS section:
  Plot Type           Line / Scatter / Broken Y-Axis / Color Map / Dual Y-Axis.
  Color Mode          "Cycle" (default colors) or "Gradient" (colormap spread).
  Colormap dropdown   Select from 80+ matplotlib colormaps (viridis, plasma,
                       jet, etc.).
  Colormap Preview    A horizontal gradient bar below the dropdown shows the
                       selected colormap with Min/Max labels (auto-updates on
                       selection and resize).
  X Axis / Y Axis     Column selectors for axes.
  Z Axis (Color)      Column selector for Color Map Z values.
  X/Y Log Scale       Toggle logarithmic axis scaling.

CONFIGURATION section:
  Ranges & Data       Axis limits, data divisors, Y and X axis breaks
                       (tabbed dialog).
  Styles              Per-series color, line width, line style, legend name,
                       show/hide in legend.
  Labels & Titles     Title, axis labels, legend text, colors, positions,
                       rotation, legend layout, secondary top X-axis,
                       transparency (7-tab dialog).
  Ticks & Fonts       Tick spacing, notation, direction, font settings,
                       grid control (4-tab dialog).
  Legend Order         Reorder legend entries with Top/Up/Down/Bottom buttons.

ACTION BUTTONS:
  Update Plot         Re-render the plot with current settings.
  Export Plot         Save the plot as an image file.
  Show All Lines      Restore any lines hidden via the context menu.


================================================================================
CONFIGURATION DIALOGS
================================================================================

RANGES & DATA (2 tabs: Ranges & Transform, Axis Breaks)

  Tab: Ranges & Transform
    Divide X/Y/Y2/Z  Divide data by a constant (e.g., "1000" to convert
                       mA to A). Y2 applies to the right axis in Dual Y-Axis.
    Axis Ranges       Min/Max for X, Y, Z axes. Leave blank for auto.
    Y2 Ranges         Min/Max for the right Y axis (Dual Y-Axis mode).

  Tab: Axis Breaks
    Y Axis Break      Omit a range from the Y axis (Start/End). Works with
                       Line, Scatter, and Dual Y-Axis plots. Data inside the
                       break is hidden; data above is shifted down. A diagonal
                       slash indicator is drawn on the spine.
    X Axis Break      Same as Y break, but for the X axis. Works with Line,
                       Scatter, and Dual Y-Axis plots.

  Reset Ranges        Clear all range fields (both tabs).

STYLES
  A scrollable table showing each series (file + column) with controls for:
  - Color      Click to pick a custom color. "Reset" reverts to default
               (uses Cycle or Gradient color).
  - Width      Line width (default: 2.0 for lines, 20 for scatter).
  - Type       Line style: solid (-), dashed (--), dash-dot (-.),
               dotted (:), or None.
  - Legend     Custom legend label for this series.
  - In Leg.    Toggle whether this series appears in the legend.

LABELS & TITLES (7 tabs)
  Text Content    Title, axis labels, legend CSV, show legend toggle, padding.
  Colors          Label colors, tick colors, background colors, legend colors.
  Positions       Custom X/Y positions for each label (figure coordinates 0-1).
                   Enable with "Use Custom Label Positions" checkbox.
                   Coordinates: (0,0) = bottom-left, (1,1) = top-right.
  Rotation        Custom rotation angles for labels (degrees).
                   Enable with "Use Custom Text Rotation" checkbox.
                   Default: Title=0°, X label=0°, Y label=90° (vertical).
  Legend          Column count (1-8), position (Best/Upper Right/etc.),
                   draggable toggle. Positions include "Outside Right" and
                   "Outside Bottom" for external placement.
  Secondary X     Enable a secondary top X-axis with custom transformation.
                   Forward formula maps bottom-axis values to top-axis values.
                   Inverse formula is auto-derived for common transforms
                   (x*K, x/K, x+K, x-K, 1/x, x**K, np.sqrt, np.log10, etc.).
                   Supports numpy functions: np.sqrt(x), np.log10(x), x**2.
                   Set top axis label, label color, tick size, major/minor
                   tick settings.
  Transparency    Alpha values for plot background, figure background,
                   legend fill (0.0 = invisible, 1.0 = opaque).

TICKS & FONTS (4 tabs)
  Tick Control    Major tick step, minor divisions, padding per axis.
                   Notation: Scientific / Plain / Engineering.
  Font Settings   Font family (autocomplete dropdown — type to filter), sizes
                   for title, labels, legend, ticks.
  Tick Appearance Tick direction (in/out/inout/none) per axis for major
                   and minor ticks. Tick length. Per-side visibility
                   (bottom/top for X, left/right for Y).
  Grid Settings   Major/minor grid visibility, alpha, style, width.


================================================================================
INTERACTIVE FEATURES
================================================================================

LEGEND TOGGLE
  - Left-click a legend entry to hide/show that line.
  - Right-click anywhere on the plot canvas for a context menu listing all
    series with checkmark (✓/✗) toggle. The menu stays open after each toggle.
  - Right-click the legend for the same context menu.
  - "Show All Lines" button in the control panel restores all hidden lines.

DRAGGABLE LEGEND
  Enable in Labels & Titles > Legend tab. Click and drag the legend to
  reposition it on the plot.

MATPLOTLIB TOOLBAR
  The bottom toolbar provides pan, zoom, home, forward/backward, and
  save-figure controls (standard matplotlib navigation).


================================================================================
SESSION SAVE / LOAD
================================================================================

SAVE SESSION
  Exports everything to a single JSON file:
  - All loaded datasets (data + column names)
  - Per-series styles (colors, widths, legend labels, show/hide in legend)
  - Legend order and legend settings (columns, position, draggable)
  - All axis ranges, tick settings, font settings
  - Tick appearance (direction, length) and per-side visibility
  - Grid settings (major/minor, alpha, style, width)
  - Title/label text, colors, positions, rotations
  - Secondary X-axis settings (formulas, label, tick settings)
  - Axis breaks (Y and X)
  - Transparency (alpha) settings
  - Plot type, color mode, colormap, log scale settings
  - Column selections (X, Y, Y1, Y2, Z)
  - Which datasets were selected

LOAD SESSION
  Restores the full session from JSON. The cache folder is automatically
  set to the directory of the loaded file.


================================================================================
COLOR MODES
================================================================================

CYCLE (default)
  Uses matplotlib's default color cycle. Each series gets a different
  color from the built-in palette.

GRADIENT
  Distributes colors evenly across the selected colormap (e.g., viridis).
  Useful for visualizing a sequence of curves as a color progression.
  Select from 80+ colormaps in the dropdown.


================================================================================
DATA FILE REQUIREMENTS
================================================================================

CSV files:
- Standard comma-separated format.
- First row(s) may contain metadata; the plotter auto-detects the header
  by searching for 'time(s)' in the first 50 lines.
- Trailing empty lines, comments (; or #), and inconsistent column counts
  are handled automatically.
- UTF-8 encoding assumed.

Excel files (.xlsx / .xls):
- Requires the 'openpyxl' package (pip install openpyxl).
- The first sheet is read automatically.
- Column names are taken from the first row.


================================================================================
TIPS
================================================================================

- Multiple Y columns: Select several in the Y-axis listbox (Ctrl+click).
- Cross-file X axis: Check "Use X from Ref. File (Cross-File)" to overlay
  datasets with different X values onto a common axis.
- Origin Pro-style ticks: Set tick direction to "out" and adjust length
  in Ticks & Fonts > Tick Appearance.
- Export at 300 DPI for publication-quality figures.
- Use "Show All Columns (Union)" when loading files with different column
  names to see all available columns.
- File Loading Wizard: Add files from multiple folders before loading.
  Use "Add Folder" to batch-import all CSV/Excel files from a directory.
- Axis Breaks: Omit a data range on X or Y axes (works with Line, Scatter,
  Dual Y-Axis). The plotter collapses the gap and draws slash indicators.
- Secondary Top X-Axis: Display a transformed scale on top (e.g., convert
  wavelength to energy). The inverse formula is auto-derived for common
  transforms.
- Right-click context menu: Toggle individual line visibility without
  opening any dialog. The menu stays open after each click.

================================================================================