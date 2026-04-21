================================================================================
               INTERACTIVE CSV PLOTTER - User Guide
================================================================================

DESCRIPTION
-----------
A feature-rich interactive CSV plotting application with a Tkinter GUI.
Supports multiple plot types, extensive customization, session save/load,
and an Origin Pro-inspired interface.

REQUIREMENTS
------------
- Python 3.8+
- polars        (pip install polars)
- matplotlib     (pip install matplotlib)
- numpy          (pip install numpy)
- scipy          (pip install scipy)

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
   - Click "Load CSV File(s)" to select one or more CSV files.
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
  Load CSV File(s)    Open file dialog (supports multi-select).
  Dataset list        Click to select active datasets.
  Unload              Remove selected datasets.
  Dataset Manager     Opens a separate management window.

SESSION section:
  Save Session        Saves ALL data + settings to a JSON file.
  Load Session        Restores a previously saved session.
  Set Cache Folder    Choose default folder for session files.

PLOT SETTINGS section:
  Plot Type           Line / Scatter / Broken Y-Axis / Color Map / Dual Y-Axis.
  Color Mode          "Cycle" (default colors) or "Gradient" (colormap spread).
  Colormap dropdown   Select a matplotlib colormap (viridis, plasma, etc.).
  X Axis / Y Axis     Column selectors for axes.
  Z Axis (Color)      Column selector for Color Map Z values.
  X/Y Log Scale       Toggle logarithmic axis scaling.

CONFIGURATION section:
  Ranges & Data       Axis limits, data divisors, broken-axis settings.
  Styles              Per-series color, line width, line style, legend name.
  Labels & Titles     Title, axis labels, legend text, colors, positions,
                       rotation, transparency (tabbed dialog).
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

RANGES & DATA
  Divide X/Y/Y2/Z    Divide data by a constant (e.g., "1000" to convert
                       mA to A). Y2 applies to the right axis in Dual Y-Axis.
  Axis Ranges         Min/Max for X, Y, Z axes. Leave blank for auto.
  Broken Axis         Break Start/End values for the Y-axis gap.
  Y2 Ranges           Min/Max for the right Y axis (Dual Y-Axis mode).
  Reset Ranges        Clear all range fields.

STYLES
  A table showing each series (file + column) with controls for:
  - Color      Click to pick a custom color. "Reset" reverts to default.
  - Width      Line width (default: 2.0 for lines, 20 for scatter).
  - Type       Line style: solid (-), dashed (--), dash-dot (-.),
               dotted (:), or None.
  - Legend     Custom legend label for this series.
  - In Leg.    Toggle whether this series appears in the legend.

LABELS & TITLES (6 tabs)
  Text Content    Title, axis labels, legend CSV, show legend toggle, padding.
  Colors          Label colors, tick colors, background colors, legend colors.
  Positions       Custom X/Y positions for each label (figure coordinates 0-1).
  Rotation        Custom rotation angles for labels (degrees).
  Legend          Column count, position, draggable toggle.
  Transparency    Alpha values for plot background, figure background,
                   legend fill (0.0 = invisible, 1.0 = opaque).

TICKS & FONTS (4 tabs)
  Tick Control    Major tick step, minor divisions, padding per axis.
                   Notation: Scientific / Plain / Engineering.
  Font Settings   Font family (autocomplete dropdown), sizes for title,
                   labels, legend, ticks.
  Tick Appearance Tick direction (in/out/inout/none) per axis for major
                   and minor ticks. Tick length. Per-side visibility
                   (bottom/top for X, left/right for Y).
  Grid Settings   Major/minor grid visibility, alpha, style, width.


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
CSV FILE REQUIREMENTS
================================================================================

- Standard comma-separated format.
- First row(s) may contain metadata; the plotter auto-detects the header
  by searching for 'time(s)' in the first 50 lines.
- Trailing empty lines, comments (; or #), and inconsistent column counts
  are handled automatically.
- UTF-8 encoding assumed.


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

================================================================================