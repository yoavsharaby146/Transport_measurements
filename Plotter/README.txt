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
the right.


================================================================================
QUICK START
================================================================================

1. LOAD DATA
   - Click "Load Data File" to open the File Loading Wizard.
   - Add files from multiple folders, then click "Load All" or
     "Load Selected Only".
   - Files appear in the dataset listbox. Click to select (Ctrl+click for
     multiple).
   - "Dataset Manager" opens a larger window for managing loaded files.
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
- Color Map       2D heatmap using X, Y, Z columns with interpolation.
                   Requires exactly 1 file and 1 Y column + 1 Z column.
- Dual Y-Axis     Left and right Y axes with independent scaling.
                   Each selected file contributes its Y1 column to the
                   left axis and Y2 column to the right axis.
                   Select N files → N lines on each axis (2N total).


================================================================================
CONTROL PANEL REFERENCE
================================================================================

DATA FILES section:
  Load Data File      Open the File Loading Wizard (supports CSV, XLSX, XLS;
                       multi-folder selection).
  Dataset list        Click to select active datasets.
  Unload              Remove selected datasets.
  Dataset Manager     Opens a separate management window.

SESSION section:
  Save Session        Saves ALL data + settings to a JSON file.
  Load Session        Restores a previously saved session.
  Set Cache Folder    Choose default folder for session files.

PLOT SETTINGS section:
  Plot Type           Line / Scatter / Color Map / Dual Y-Axis.
  Color Mode          "Cycle" (default colors) or "Gradient" (colormap spread).
  Colormap dropdown   Select a matplotlib colormap (viridis, plasma, etc.).
                       A preview bar shows the gradient from Min to Max.
  X Axis / Y Axis     Column selectors for axes.
  Z Axis (Color)      Column selector for Color Map Z values.
  X/Y Log Scale       Toggle logarithmic axis scaling.

CONFIGURATION section:
  Ranges & Data       Axis limits, data divisors, axis breaks (X & Y).
  Styles              Per-series color, line width, line style, legend name.
  Labels & Titles     Title, axis labels, legend text, colors, positions,
                       rotation, secondary X-axis, transparency (tabbed).
  Ticks & Fonts       Tick spacing, notation, direction, font settings,
                       grid control (tabbed dialog).
  Legend Order         Drag-and-drop reorder of legend entries.

ACTION BUTTONS:
  Update Plot         Re-render the plot with current settings.
  Export Plot         Save the plot as an image file.
  Show All Lines      Restore any lines hidden via the context menu.


================================================================================
CONFIGURATION DIALOGS
================================================================================

RANGES & DATA (2 tabs)
  Tab: Ranges & Transform
    Divide X/Y/Y2/Z    Divide data by a constant (e.g., "1000" to convert
                         mA to A). Y2 applies to the right axis in Dual Y-Axis.
    Axis Ranges         Min/Max for X, Y, Z axes. Leave blank for auto.
    Y2 Ranges           Min/Max for the right Y axis (Dual Y-Axis mode).

  Tab: Axis Breaks
    Y Axis Break        Omit a range from the Y axis. Specify Start and End.
                         Works with Line, Scatter, and Dual Y-Axis plots.
    X Axis Break        Omit a range from the X axis. Specify Start and End.
                         Leave blank to disable. Origin Pro-style slash
                         indicators are drawn automatically.

  Reset Ranges        Clear all range and break fields.

STYLES
  A table showing each series (file + column) with controls for:
  - Color      Click to pick a custom color. "Reset" reverts to default.
  - Width      Line width (default: 2.0 for lines, 20 for scatter).
  - Type       Line style: solid (-), dashed (--), dash-dot (-.),
               dotted (:), or None.
  - Legend     Custom legend label for this series.
  - In Leg.    Toggle whether this series appears in the legend.

LABELS & TITLES (7 tabs)
  Text Content      Title, axis labels, legend CSV, show legend toggle,
                      label padding.
  Colors            Label colors, tick colors, background colors, legend colors.
  Positions         Custom X/Y positions for each label (figure coordinates
                      0-1). Enable with "Use Custom Label Positions".
  Rotation          Custom rotation angles for labels (degrees).
                      Enable with "Use Custom Text Rotation".
  Legend            Column count, position (12 options including outside
                      right/bottom), draggable toggle.
  Secondary X       Secondary top X-axis with transformation formulas.
                      Supports arithmetic (x*K, x/K, x+K, x-K), powers
                      (x**K), inverse (1/x), and numpy functions
                      (np.sqrt, np.log10, np.exp). Inverse is auto-derived
                      for common patterns.
  Transparency      Alpha values for plot background, figure background,
                      legend fill (0.0 = invisible, 1.0 = opaque).

TICKS & FONTS (4 tabs)
  Tick Control      Major tick step, minor divisions, padding per axis.
                     Notation: Scientific / Plain / Engineering.
  Font Settings     Font family (autocomplete dropdown), sizes for title,
                     labels, legend, ticks.
  Tick Appearance   Tick direction (in/out/inout/none) per axis for major
                     and minor ticks. Tick length. Per-side visibility
                     (bottom/top for X, left/right for Y).
  Grid Settings     Major/minor grid visibility, alpha, style, width.


================================================================================
INTERACTIVE FEATURES
================================================================================

LEGEND TOGGLE
  - Left-click a legend entry to hide/show that line.
  - Right-click the legend or the plot area for a context menu with
    checkboxes for every series.
  - "Show All Lines" button restores all hidden lines.

DRAGGABLE LEGEND
  Enable in Labels & Titles > Legend tab. Click and drag the legend to
  reposition it on the plot.

MATPLOTLIB TOOLBAR
  The bottom toolbar provides pan, zoom, home, forward/backward, and
  save-figure controls (standard matplotlib navigation).

CONTEXT MENU
  Right-click anywhere on the plot canvas to toggle individual series
  visibility — even when no legend is displayed.


================================================================================
SESSION SAVE / LOAD
================================================================================

SAVE SESSION
  Exports everything to a single JSON file:
  - All loaded datasets (data + column names)
  - Per-series styles (colors, widths, legend labels)
  - Legend order
  - All axis ranges, tick settings, font settings
  - Title/label text, colors, positions, rotations
  - Plot type, color mode, log scale settings
  - Column selections (X, Y, Y1, Y2, Z)
  - Axis breaks (X and Y)
  - Grid settings, tick appearance, tick side visibility
  - Secondary X-axis settings
  - Which datasets were selected

LOAD SESSION
  Restores the full session from JSON. The cache folder is automatically
  set to the directory of the loaded file. Backward compatible with
  sessions saved by older versions.


================================================================================
COLOR MODES
================================================================================

CYCLE (default)
  Uses matplotlib's default color cycle. Each series gets a different
  color from the built-in palette.

GRADIENT
  Distributes colors evenly across the selected colormap (e.g., viridis).
  Useful for visualizing a sequence of curves as a color progression.
  Select from 80+ colormaps in the dropdown. A preview bar shows the
  gradient range.


================================================================================
AXIS BREAKS
================================================================================

Axis breaks allow you to omit a range of values from an axis, collapsing
the gap so the remaining data is displayed continuously. This is useful
when data has a large gap with no interesting values.

- Works with Line, Scatter, and Dual Y-Axis plot types.
- Available for both X and Y axes.
- Set Start and End values in Ranges & Data > Axis Breaks tab.
- Origin Pro-style diagonal slash indicators are drawn on the spines.
- Data points inside the break range are hidden (NaN).
- Tick labels automatically show the original (unbroken) values.


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
- Cross-file X axis: Check "Use X from Ref. File" to overlay datasets
  with different X values onto a common axis.
- Origin Pro-style ticks: Set tick direction to "out" and adjust length
  in Ticks & Fonts > Tick Appearance.
- Export at 300 DPI for publication-quality figures.
- Use "Show All Columns (Union)" when loading files with different column
  names to see all available columns.
- Use Axis Breaks instead of separate plot types to remove empty ranges
  from your axes while keeping everything in one plot.

================================================================================