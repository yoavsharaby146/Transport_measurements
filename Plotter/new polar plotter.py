# ==================== IMPORTS ====================
import os
import json
from datetime import datetime

import numpy as np
import polars as pl

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the '3d' projection)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

# ==================== CONSTANTS ====================

COLORMAPS = [
    'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
    'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
    'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn',
    'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone',
    'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
    'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper',
    'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu', 'RdYlBu',
    'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic',
    'twilight', 'twilight_shifted', 'hsv',
    'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2',
    'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b', 'tab20c',
    'flag', 'prism', 'ocean', 'gist_earth', 'terrain',
    'gist_stern', 'gnuplot', 'gnuplot2', 'CMRmap',
    'cubehelix', 'brg', 'gist_rainbow', 'rainbow', 'jet',
    'turbo', 'nipy_spectral', 'gist_ncar'
]

POLAR_THETA_UNITS = ["Degrees", "Radians"]
POLAR_THETA_ZERO = ["E (0 deg, standard)", "N (top)", "W", "S"]
POLAR_THETA_ZERO_MAP = {"E (0 deg, standard)": "E", "N (top)": "N", "W": "W", "S": "S"}
POLAR_DIRECTION = ["Counter-clockwise", "Clockwise"]
POLAR_MARKERS = ["None", "o", "s", "^", "D", "x", "+", "*"]

PLOT_MODES = ["2D Polar", "3D Sphere"]
SPHERE_PHI_CONVENTION = ["Elevation (-90 to 90, 0=equator)", "Inclination (0 to 180, 0=north pole)"]
SPHERE_TRACE_STYLE = ["Line", "Scatter", "Line + Markers"]


class PolarPlotter:
    """Interactive multi-file Polar / 3D Sphere plotter.

    Load CSV/Excel files, pick a Theta (angle) and R (radius) column per
    series, and plot them either on a 2D polar axes or as a trace on a
    3D sphere (Theta = azimuth, Phi = elevation/inclination, with an
    optional R column or fixed radius), with configurable angle units,
    zero location, direction, R-axis limits, custom gridlines, markers,
    fill-under-curve, and full styling/legend/session-save support.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Interactive Polar Plotter")

        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            w = min(1300, int(screen_width * 0.85))
            h = min(900, int(screen_height * 0.85))
            x_pos = (screen_width - w) // 2
            y_pos = (screen_height - h) // 2
            self.root.geometry(f"{w}x{h}+{x_pos}+{y_pos}")
        except Exception:
            self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.datasets = {}
        self.styles = {}

        # --- COLOR SETTINGS ---
        self.v_color_mode = tk.StringVar(value="Cycle")
        self.v_cmap_name = tk.StringVar(value="viridis")

        # --- TEXT / LEGEND ---
        self.v_title = tk.StringVar(value="Polar Plot")
        self.v_legend = tk.StringVar()
        self.show_legend = tk.BooleanVar(value=True)
        self.show_grid = tk.BooleanVar(value=True)
        self.legend_columns = tk.StringVar(value="1")
        self.legend_draggable = tk.BooleanVar(value=False)

        # --- COLORS ---
        self.title_color = 'black'
        self.rlabel_color = 'black'
        self.tick_color = 'black'
        self.plot_bg_color = 'white'
        self.fig_bg_color = 'white'
        self.legend_fill_color = 'white'
        self.legend_frame_color = 'black'
        self.polar_gridline_color = 'gray'

        # --- FONTS ---
        self.v_font_fam = tk.StringVar(value="Arial")
        self.v_t_size = tk.StringVar(value="14")
        self.v_l_size = tk.StringVar(value="12")
        self.v_leg_size = tk.StringVar(value="10")
        self.v_tick_size = tk.StringVar(value="10")

        # --- POLAR-SPECIFIC SETTINGS ---
        self.v_theta_div = tk.StringVar(value="1")
        self.v_r_div = tk.StringVar(value="1")
        self.v_theta_unit = tk.StringVar(value="Degrees")
        self.v_theta_zero = tk.StringVar(value="N (top)")
        self.v_polar_direction = tk.StringVar(value="Clockwise")
        self.v_r_min = tk.StringVar()
        self.v_r_max = tk.StringVar()
        self.v_theta_min = tk.StringVar()
        self.v_theta_max = tk.StringVar()
        self.v_r_label = tk.StringVar()
        self.v_r_gridlines = tk.StringVar()
        self.v_polar_fill = tk.BooleanVar(value=False)
        self.v_polar_fill_alpha = tk.StringVar(value="0.25")
        self.v_polar_marker = tk.StringVar(value="None")

        # --- TICK CONTROL (2D Polar) ---
        self.v_theta_tick_step = tk.StringVar()   # degrees between angular ticks, blank = auto (45deg default look)
        self.v_r_tick_count = tk.StringVar()      # number of automatic R ticks, blank = matplotlib default
        self.v_r_dec = tk.StringVar()             # decimal places for R tick labels, blank = auto
        self.v_tick_pad = tk.StringVar(value="5")
        self.show_theta_ticks = tk.BooleanVar(value=True)
        self.show_r_ticks = tk.BooleanVar(value=True)

        # --- PLOT MODE (2D Polar vs 3D Sphere) ---
        self.v_plot_mode = tk.StringVar(value="2D Polar")

        # --- 3D SPHERE-SPECIFIC SETTINGS ---
        self.v_phi_div = tk.StringVar(value="1")
        self.v_phi_convention = tk.StringVar(value="Elevation (-90 to 90, 0=equator)")
        self.v_sphere_use_r_col = tk.BooleanVar(value=False)   # False = fixed radius
        self.v_sphere_fixed_r = tk.StringVar(value="1.0")
        self.v_sphere_trace_style = tk.StringVar(value="Line")
        self.v_sphere_show_wireframe = tk.BooleanVar(value=True)
        self.v_sphere_wireframe_alpha = tk.StringVar(value="0.15")
        self.v_sphere_elev = tk.StringVar(value="20")
        self.v_sphere_azim = tk.StringVar(value="-60")
        self.v_sphere_equal_aspect = tk.BooleanVar(value=True)
        self.sphere_wireframe_color = 'gray'

        self.dataset_window = None

        self.setup_ui()

    # ---------------------------------------------------------------
    # DIALOG SIZE HELPERS
    # ---------------------------------------------------------------

    def get_dialog_size(self, width_pct=0.35, height_pct=0.8, max_width=None, max_height=None,
                         min_width=350, min_height=300):
        w = int(self.screen_width * width_pct)
        h = int(self.screen_height * height_pct)
        if max_width: w = min(max_width, w)
        if max_height: h = min(max_height, h)
        w = max(min_width, w)
        h = max(min_height, h)
        return w, h

    def create_scrollable_dialog(self, parent, title, width_pct=0.35, height_pct=0.8,
                                  max_width=None, max_height=None, min_width=350, min_height=300):
        d = tk.Toplevel(parent)
        d.title(title)
        w, h = self.get_dialog_size(width_pct, height_pct, max_width, max_height, min_width, min_height)
        w = max(w, 450)
        d.geometry(f"{w}x{h}")
        d.transient(parent)

        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)

        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)

        canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas, padding=10)

        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", on_mw)
        content_frame.bind("<MouseWheel>", on_mw)

        def on_close():
            canvas.unbind("<MouseWheel>")
            content_frame.unbind("<MouseWheel>")
            d.destroy()
        d.protocol("WM_DELETE_WINDOW", on_close)

        return d, content_frame, canvas, main_container, btn_container

    # ---------------------------------------------------------------
    # UI SETUP
    # ---------------------------------------------------------------

    def setup_ui(self):
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        control_container = ttk.Frame(main_container)
        main_container.add(control_container, width=400)

        canvas_scroll = tk.Canvas(control_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(control_container, orient="vertical", command=canvas_scroll.yview)
        control_frame = ttk.Frame(canvas_scroll, padding="10")
        control_frame.bind("<Configure>", lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=control_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas_scroll.pack(side="left", fill="both", expand=True)

        def _bind_mw(event): canvas_scroll.bind_all("<MouseWheel>", lambda e: canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        def _unbind_mw(event): canvas_scroll.unbind_all("<MouseWheel>")
        canvas_scroll.bind('<Enter>', _bind_mw)
        canvas_scroll.bind('<Leave>', _unbind_mw)

        plot_frame = ttk.Frame(main_container)
        main_container.add(plot_frame)

        row = 0
        ttk.Label(control_frame, text="DATA FILES", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4, sticky='w', pady=(0, 5))
        row += 1
        ttk.Button(control_frame, text="Load Data File", command=self.load_files).grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        row += 1

        ds_frame = ttk.Frame(control_frame)
        ds_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        ds_sb = ttk.Scrollbar(ds_frame, orient='vertical')
        self.dataset_listbox = tk.Listbox(ds_frame, selectmode='extended', height=4, yscrollcommand=ds_sb.set, exportselection=False)
        ds_sb.config(command=self.dataset_listbox.yview)
        self.dataset_listbox.pack(side='left', fill='both', expand=True)
        ds_sb.pack(side='right', fill='y')
        self.dataset_listbox.bind('<<ListboxSelect>>', lambda e: self.update_plot())
        row += 1

        ds_btn_frame = ttk.Frame(control_frame)
        ds_btn_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=2)
        ttk.Button(ds_btn_frame, text="Unload", command=self.unload_files, width=10).pack(side='left', padx=2)
        ttk.Button(ds_btn_frame, text="Dataset Manager", command=self.open_dataset_window, width=16).pack(side='left', padx=2)
        row += 1

        cache_frame = ttk.Frame(control_frame)
        cache_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        ttk.Button(cache_frame, text="Save Session", command=self.save_session).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(cache_frame, text="Load Session", command=self.load_session).pack(side='left', expand=True, fill='x', padx=2)
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # === PLOT MODE ===
        mode_frame = ttk.Frame(control_frame)
        mode_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=2)
        ttk.Label(mode_frame, text="Plot Mode:", font=('Arial', 10, 'bold')).pack(side='left')
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.v_plot_mode, values=PLOT_MODES,
                                   state='readonly', width=14)
        mode_combo.pack(side='left', fill='x', expand=True, padx=4)
        mode_combo.bind('<<ComboboxSelected>>', self.on_plot_mode_change)
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=8)
        row += 1

        # === AXIS SELECTION (Theta is common; R vs Phi+R differ by mode) ===
        ttk.Label(control_frame, text="AXES", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4, sticky='w', pady=(0, 5))
        row += 1
        ttk.Label(control_frame, text="Reference File (for column list):").grid(row=row, column=0, columnspan=4, sticky='w')
        row += 1
        self.axis_ref_combo = ttk.Combobox(control_frame, state='readonly', width=20)
        self.axis_ref_combo.grid(row=row, column=0, columnspan=4, sticky='ew', pady=2)
        self.axis_ref_combo.bind('<<ComboboxSelected>>', self.populate_column_selectors)
        row += 1
        ttk.Label(control_frame, text="Theta Column (azimuth angle):").grid(row=row, column=0, columnspan=4, sticky='w', pady=(6, 0))
        row += 1
        self.polar_theta_combo = ttk.Combobox(control_frame, state='readonly', width=20)
        self.polar_theta_combo.grid(row=row, column=0, columnspan=4, sticky='ew', pady=2)
        row += 1

        # --- 2D Polar: R Column row ---
        self.r_col_row = ttk.Frame(control_frame)
        ttk.Label(self.r_col_row, text="R Column (radius):").pack(anchor='w', pady=(6, 0))
        self.polar_r_combo = ttk.Combobox(self.r_col_row, state='readonly', width=20)
        self.polar_r_combo.pack(fill='x', pady=2)
        self.r_col_row.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        # --- 3D Sphere: Phi Column row ---
        self.phi_col_row = ttk.Frame(control_frame)
        ttk.Label(self.phi_col_row, text="Phi Column (elevation/inclination):").pack(anchor='w', pady=(6, 0))
        self.polar_phi_combo = ttk.Combobox(self.phi_col_row, state='readonly', width=20)
        self.polar_phi_combo.pack(fill='x', pady=2)
        self.phi_col_row.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        # --- 3D Sphere: Phi convention row ---
        self.phi_conv_row = ttk.Frame(control_frame)
        ttk.Label(self.phi_conv_row, text="Phi Convention:").pack(anchor='w')
        ttk.Combobox(self.phi_conv_row, textvariable=self.v_phi_convention, values=SPHERE_PHI_CONVENTION,
                     state='readonly').pack(fill='x', pady=2)
        self.phi_conv_row.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        # --- 3D Sphere: use R column toggle + fixed radius ---
        self.sphere_r_row = ttk.Frame(control_frame)
        ttk.Checkbutton(self.sphere_r_row, text="Use R Column (else fixed radius)",
                        variable=self.v_sphere_use_r_col, command=self._toggle_sphere_r_mode).pack(anchor='w', pady=(4, 0))
        self.sphere_r_col_sub = ttk.Frame(self.sphere_r_row)
        ttk.Label(self.sphere_r_col_sub, text="R Column:").pack(side='left')
        self.polar_sphere_r_combo = ttk.Combobox(self.sphere_r_col_sub, state='readonly', width=16)
        self.polar_sphere_r_combo.pack(side='left', fill='x', expand=True, padx=4)
        self.sphere_fixed_r_sub = ttk.Frame(self.sphere_r_row)
        ttk.Label(self.sphere_fixed_r_sub, text="Fixed Radius:").pack(side='left')
        ttk.Entry(self.sphere_fixed_r_sub, textvariable=self.v_sphere_fixed_r, width=10).pack(side='left', padx=4)
        self.sphere_r_row.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # === COLOR MODE ===
        ttk.Label(control_frame, text="Color Mode:").grid(row=row, column=0, sticky='w')
        c_mode = ttk.Combobox(control_frame, textvariable=self.v_color_mode, values=["Cycle", "Gradient"], state='readonly', width=10)
        c_mode.grid(row=row, column=1, sticky='ew', padx=2)
        c_mode.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        c_map = ttk.Combobox(control_frame, textvariable=self.v_cmap_name, values=COLORMAPS, state='readonly', width=12)
        c_map.grid(row=row, column=2, columnspan=2, sticky='ew', padx=2)
        c_map.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # === MODE-SPECIFIC SETTINGS PANEL (shared row placeholder) ===
        self.settings_panel_row = row
        row += 1

        # --- 2D Polar settings (angle unit / zero / direction / marker / fill) ---
        self.polar_settings_frame = ttk.Frame(control_frame)
        f = self.polar_settings_frame
        ttk.Label(f, text="POLAR SETTINGS", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        u_row = ttk.Frame(f); u_row.pack(fill='x', pady=2)
        ttk.Label(u_row, text="Theta Unit:", width=12).pack(side='left')
        ttk.Combobox(u_row, textvariable=self.v_theta_unit, values=POLAR_THETA_UNITS, state='readonly', width=12).pack(side='left', fill='x', expand=True)
        z_row = ttk.Frame(f); z_row.pack(fill='x', pady=2)
        ttk.Label(z_row, text="Theta Zero:", width=12).pack(side='left')
        ttk.Combobox(z_row, textvariable=self.v_theta_zero, values=POLAR_THETA_ZERO, state='readonly', width=18).pack(side='left', fill='x', expand=True)
        d_row = ttk.Frame(f); d_row.pack(fill='x', pady=2)
        ttk.Label(d_row, text="Direction:", width=12).pack(side='left')
        ttk.Combobox(d_row, textvariable=self.v_polar_direction, values=POLAR_DIRECTION, state='readonly', width=16).pack(side='left', fill='x', expand=True)
        m_row = ttk.Frame(f); m_row.pack(fill='x', pady=2)
        ttk.Label(m_row, text="Marker:", width=12).pack(side='left')
        ttk.Combobox(m_row, textvariable=self.v_polar_marker, values=POLAR_MARKERS, state='readonly', width=12).pack(side='left', fill='x', expand=True)
        ttk.Checkbutton(f, text="Fill area under curve", variable=self.v_polar_fill,
                        command=self.update_plot).pack(anchor='w', pady=(4, 0))
        gl_row = ttk.Frame(f); gl_row.pack(fill='x', pady=2)
        ttk.Checkbutton(gl_row, text="Show Grid", variable=self.show_grid, command=self.update_plot).pack(side='left')
        ttk.Checkbutton(gl_row, text="Show Legend", variable=self.show_legend, command=self.update_plot).pack(side='left', padx=10)

        # --- 3D Sphere settings ---
        self.sphere_settings_frame = ttk.Frame(control_frame)
        f3 = self.sphere_settings_frame
        ttk.Label(f3, text="SPHERE SETTINGS", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        u3_row = ttk.Frame(f3); u3_row.pack(fill='x', pady=2)
        ttk.Label(u3_row, text="Theta/Phi Unit:", width=13).pack(side='left')
        ttk.Combobox(u3_row, textvariable=self.v_theta_unit, values=POLAR_THETA_UNITS, state='readonly', width=12).pack(side='left', fill='x', expand=True)
        ts_row = ttk.Frame(f3); ts_row.pack(fill='x', pady=2)
        ttk.Label(ts_row, text="Trace Style:", width=13).pack(side='left')
        ttk.Combobox(ts_row, textvariable=self.v_sphere_trace_style, values=SPHERE_TRACE_STYLE, state='readonly', width=14).pack(side='left', fill='x', expand=True)
        m3_row = ttk.Frame(f3); m3_row.pack(fill='x', pady=2)
        ttk.Label(m3_row, text="Marker:", width=13).pack(side='left')
        ttk.Combobox(m3_row, textvariable=self.v_polar_marker, values=POLAR_MARKERS, state='readonly', width=12).pack(side='left', fill='x', expand=True)

        ttk.Separator(f3, orient='horizontal').pack(fill='x', pady=6)
        ttk.Checkbutton(f3, text="Show Reference Sphere Wireframe", variable=self.v_sphere_show_wireframe,
                        command=self.update_plot).pack(anchor='w', pady=2)
        wf_row = ttk.Frame(f3); wf_row.pack(fill='x', pady=2)
        ttk.Label(wf_row, text="Wireframe Alpha:", width=15).pack(side='left')
        ttk.Entry(wf_row, textvariable=self.v_sphere_wireframe_alpha, width=8).pack(side='left', padx=4)

        ttk.Separator(f3, orient='horizontal').pack(fill='x', pady=6)
        view_row = ttk.Frame(f3); view_row.pack(fill='x', pady=2)
        ttk.Label(view_row, text="Elevation:", width=13).pack(side='left')
        ttk.Entry(view_row, textvariable=self.v_sphere_elev, width=8).pack(side='left', padx=4)
        ttk.Label(view_row, text="Azimuth:", width=10).pack(side='left')
        ttk.Entry(view_row, textvariable=self.v_sphere_azim, width=8).pack(side='left', padx=4)
        ttk.Checkbutton(f3, text="Equal Aspect Ratio", variable=self.v_sphere_equal_aspect,
                        command=self.update_plot).pack(anchor='w', pady=2)

        gl3_row = ttk.Frame(f3); gl3_row.pack(fill='x', pady=2)
        ttk.Checkbutton(gl3_row, text="Show Grid", variable=self.show_grid, command=self.update_plot).pack(side='left')
        ttk.Checkbutton(gl3_row, text="Show Legend", variable=self.show_legend, command=self.update_plot).pack(side='left', padx=10)

        self.polar_settings_frame.grid(row=self.settings_panel_row, column=0, columnspan=4, sticky='ew')
        self.sphere_settings_frame.grid(row=self.settings_panel_row, column=0, columnspan=4, sticky='ew')

        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # === CONFIGURATION BUTTONS ===
        ttk.Label(control_frame, text="CONFIGURATION", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4, sticky='w', pady=(0, 5))
        row += 1
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1
        ttk.Button(btn_frame, text="Ranges & Data", command=self.open_ranges_dialog).grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        ttk.Button(btn_frame, text="Styles", command=self.open_style_dialog).grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        ttk.Button(btn_frame, text="Labels & Titles", command=self.open_labels_dialog).grid(row=1, column=0, padx=2, pady=2, sticky='ew')
        ttk.Button(btn_frame, text="Ticks & Fonts", command=self.open_ticks_dialog).grid(row=1, column=1, padx=2, pady=2, sticky='ew')
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1
        ttk.Button(control_frame, text="Update Plot", command=self.update_plot).grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        row += 1
        ttk.Button(control_frame, text="Export Plot", command=self.export_plot).grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        row += 1

        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)

        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.ax.text(0, 0, 'Load data file to begin', ha='center', va='center', fontsize=14, color='gray')
        self.canvas.draw()

        self.on_plot_mode_change(None)

    def on_plot_mode_change(self, event):
        """Show/hide the axis-selector and settings rows for the active plot mode."""
        is_sphere = self.v_plot_mode.get() == "3D Sphere"

        if is_sphere:
            self.r_col_row.grid_remove()
            self.phi_col_row.grid()
            self.phi_conv_row.grid()
            self.sphere_r_row.grid()
            self.polar_settings_frame.grid_remove()
            self.sphere_settings_frame.grid()
            self._toggle_sphere_r_mode()
        else:
            self.phi_col_row.grid_remove()
            self.phi_conv_row.grid_remove()
            self.sphere_r_row.grid_remove()
            self.sphere_settings_frame.grid_remove()
            self.r_col_row.grid()
            self.polar_settings_frame.grid()

        self.update_plot()

    def _toggle_sphere_r_mode(self):
        """Show either the R-column picker or the fixed-radius entry inside the sphere axis row."""
        self.sphere_r_col_sub.pack_forget()
        self.sphere_fixed_r_sub.pack_forget()
        if self.v_sphere_use_r_col.get():
            self.sphere_r_col_sub.pack(fill='x', pady=(4, 0))
        else:
            self.sphere_fixed_r_sub.pack(fill='x', pady=(4, 0))
        self.update_plot()

    # ---------------------------------------------------------------
    # DATA LOADING
    # ---------------------------------------------------------------

    def _load_csv(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        header_line = 0
        for i, line in enumerate(lines[:50]):
            if 'time(s)' in line.lower():
                header_line = i
                break
        skip_footer = 0
        header_cols = len(lines[header_line].split(','))
        for i in range(len(lines) - 1, header_line, -1):
            line = lines[i].strip()
            if not line:
                skip_footer += 1; continue
            if line.startswith(';') or line.startswith('#'):
                skip_footer += 1; continue
            if len(line.split(',')) != header_cols:
                skip_footer += 1; continue
            break
        if skip_footer > 0:
            return pl.read_csv(filepath, skip_rows=header_line,
                                n_rows=len(lines) - header_line - skip_footer,
                                truncate_ragged_lines=True, ignore_errors=True)
        return pl.read_csv(filepath, skip_rows=header_line, truncate_ragged_lines=True, ignore_errors=True)

    def _load_excel(self, filepath):
        try:
            import openpyxl  # noqa: F401  (presence check only)
        except ImportError:
            raise ImportError("Excel support requires 'openpyxl'.\nInstall it with:  pip install openpyxl")
        return pl.read_excel(filepath)

    def load_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Select data file(s)",
            filetypes=[("Data files", "*.csv *.xlsx *.xls"),
                       ("CSV files", "*.csv"),
                       ("Excel files", "*.xlsx *.xls"),
                       ("All files", "*.*")])
        if not filepaths:
            return
        errors = []
        for filepath in filepaths:
            try:
                ext = os.path.splitext(filepath)[1].lower()
                df = self._load_excel(filepath) if ext in ('.xlsx', '.xls') else self._load_csv(filepath)
                filename = os.path.basename(filepath)
                key = filename
                if key in self.datasets:
                    parent_folder = os.path.basename(os.path.dirname(filepath))
                    key = f"{filename} ({parent_folder})"
                    counter = 2
                    while key in self.datasets:
                        key = f"{filename} ({parent_folder}_{counter})"
                        counter += 1
                self.datasets[key] = df
            except Exception as e:
                errors.append(f"{os.path.basename(filepath)}: {e}")
        if errors:
            messagebox.showerror("Load Errors", "Errors loading files:\n\n" + "\n".join(errors))
        self.refresh_dataset_list(new_load=True)

    def unload_files(self):
        sel = self.dataset_listbox.curselection()
        if not sel:
            return
        keys = [self.dataset_listbox.get(i) for i in sel]
        for k in keys:
            if k in self.datasets:
                del self.datasets[k]
        self.refresh_dataset_list(new_load=False)
        self.update_plot()

    def refresh_dataset_list(self, new_load=False):
        self.dataset_listbox.delete(0, tk.END)
        keys = list(self.datasets.keys())
        for k in keys:
            self.dataset_listbox.insert(tk.END, k)
        self.axis_ref_combo['values'] = keys
        if keys:
            if new_load and not self.dataset_listbox.curselection():
                self.dataset_listbox.selection_set(0)
            if self.axis_ref_combo.get() not in keys:
                self.axis_ref_combo.current(0)
            self.populate_column_selectors(None)
        else:
            self.axis_ref_combo.set('')
            self.polar_theta_combo.set('')
            self.polar_r_combo.set('')
            self.polar_phi_combo.set('')
            self.polar_sphere_r_combo.set('')
            self.fig.clear()
            self.ax = self.fig.add_subplot(111, projection='polar')
            self.canvas.draw()

    def populate_column_selectors(self, event):
        key = self.axis_ref_combo.get()
        columns = self.datasets[key].columns if key in self.datasets else []
        self.polar_theta_combo['values'] = columns
        self.polar_r_combo['values'] = columns
        self.polar_phi_combo['values'] = columns
        self.polar_sphere_r_combo['values'] = columns
        if columns:
            if self.polar_theta_combo.get() not in columns:
                self.polar_theta_combo.set(columns[0])
            if self.polar_r_combo.get() not in columns:
                self.polar_r_combo.set(columns[1] if len(columns) > 1 else columns[0])
            if self.polar_phi_combo.get() not in columns:
                self.polar_phi_combo.set(columns[1] if len(columns) > 1 else columns[0])
            if self.polar_sphere_r_combo.get() not in columns:
                self.polar_sphere_r_combo.set(columns[2] if len(columns) > 2 else columns[0])
        else:
            self.polar_theta_combo.set('')
            self.polar_r_combo.set('')
            self.polar_phi_combo.set('')
            self.polar_sphere_r_combo.set('')
        self.update_plot()

    def get_selected_datasets(self):
        idxs = self.dataset_listbox.curselection()
        keys = [self.dataset_listbox.get(i) for i in idxs]
        return [(k, self.datasets[k]) for k in keys]

    # ---------------------------------------------------------------
    # DATASET MANAGER WINDOW
    # ---------------------------------------------------------------

    def open_dataset_window(self):
        if self.dataset_window is not None and self.dataset_window.winfo_exists():
            self.dataset_window.lift()
            return
        w, h = self.get_dialog_size(0.40, 0.7, max_width=600, max_height=650, min_width=400, min_height=350)
        self.dataset_window = tk.Toplevel(self.root)
        self.dataset_window.title("Dataset Manager")
        self.dataset_window.geometry(f"{w}x{h}")
        self.dataset_window.transient(self.root)

        frame = ttk.Frame(self.dataset_window, padding=10)
        frame.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text="Load Data File", command=self.load_files).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Unload Selected", command=self.unload_files).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_dataset_window_list).pack(side='left', padx=2)

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        self.ds_window_listbox = tk.Listbox(list_frame, selectmode='extended', yscrollcommand=sb.set,
                                             exportselection=False, font=('Consolas', 10))
        sb.config(command=self.ds_window_listbox.yview)
        self.ds_window_listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.ds_window_listbox.bind('<<ListboxSelect>>', self.on_ds_window_selection_change)

        self.ds_info_label = ttk.Label(frame, text="", font=('Arial', 9))
        self.ds_info_label.pack(fill='x', pady=(10, 5))

        self.refresh_dataset_window_list()
        self.dataset_window.protocol("WM_DELETE_WINDOW", self.on_ds_window_close)

    def refresh_dataset_window_list(self):
        if self.dataset_window is None or not self.dataset_window.winfo_exists():
            return
        self.ds_window_listbox.delete(0, tk.END)
        for k in self.datasets:
            df = self.datasets[k]
            self.ds_window_listbox.insert(tk.END, f"{k}  ({len(df)} rows, {len(df.columns)} cols)")
        main_sel = list(self.dataset_listbox.curselection())
        self.ds_window_listbox.selection_clear(0, tk.END)
        for idx in main_sel:
            if idx < self.ds_window_listbox.size():
                self.ds_window_listbox.selection_set(idx)
        total_rows = sum(len(df) for df in self.datasets.values())
        self.ds_info_label.config(text=f"Total: {len(self.datasets)} datasets, {total_rows} rows")

    def on_ds_window_selection_change(self, event):
        sel_idxs = list(self.ds_window_listbox.curselection())
        self.dataset_listbox.selection_clear(0, tk.END)
        for idx in sel_idxs:
            if idx < self.dataset_listbox.size():
                self.dataset_listbox.selection_set(idx)
        self.update_plot()

    def on_ds_window_close(self):
        if self.dataset_window:
            self.dataset_window.destroy()
        self.dataset_window = None

    # ---------------------------------------------------------------
    # STYLE DIALOG
    # ---------------------------------------------------------------

    def open_style_dialog(self):
        sel_ds = self.get_selected_datasets()
        if self.v_plot_mode.get() == "3D Sphere":
            key_col = self.polar_sphere_r_combo.get() if self.v_sphere_use_r_col.get() else self.polar_phi_combo.get()
            if not sel_ds or not key_col:
                return messagebox.showinfo("Info", "Select data files and a Phi/R column first.")
        else:
            key_col = self.polar_r_combo.get()
            if not sel_ds or not key_col:
                return messagebox.showinfo("Info", "Select data files and an R column first.")
        pairs = [(fk, key_col) for fk, _ in sel_ds]

        d, fr, cv, main_container, btn_container = self.create_scrollable_dialog(
            self.root, "Style Config", width_pct=0.55, height_pct=0.7,
            max_width=900, max_height=650, min_width=650, min_height=300)

        ttk.Label(fr, text="Series").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(fr, text="Color").grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(fr, text="Width").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(fr, text="Type").grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(fr, text="Legend").grid(row=0, column=4, padx=5, pady=5)
        r = 1

        def pick_c(btn, k):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                self.styles.setdefault(k, {})['color'] = c
                btn.config(bg=c)
                d.lift()

        def up_w(v, k):
            self.styles.setdefault(k, {})
            try:
                self.styles[k]['width'] = float(v)
            except Exception:
                pass

        def up_ls(v, k):
            self.styles.setdefault(k, {})['linestyle'] = v

        def up_leg(v, k):
            self.styles.setdefault(k, {})['legend'] = v.get()

        for k in pairs:
            fk, yc = k
            st = self.styles.get(k, {})
            c = st.get('color', '#d3d3d3')
            w = st.get('width', 2.0)
            ls = st.get('linestyle', '-')
            ttk.Label(fr, text=f"{fk}\n{yc}").grid(row=r, column=0, padx=5, sticky='w')
            btn = tk.Button(fr, text=" ", bg=c, width=4)
            btn.config(command=lambda b=btn, kk=k: pick_c(b, kk))
            btn.grid(row=r, column=1, padx=2)
            wv = tk.StringVar(value=str(w))
            wv.trace("w", lambda n, i, m, v=wv, kk=k: up_w(v.get(), kk))
            ttk.Entry(fr, textvariable=wv, width=6).grid(row=r, column=2)
            lsb = ttk.Combobox(fr, values=['-', '--', '-.', ':'], width=5, state='readonly')
            lsb.set(ls)
            lsb.bind("<<ComboboxSelected>>", lambda e, b=lsb, kk=k: up_ls(b.get(), kk))
            lsb.grid(row=r, column=3)
            leg_val = tk.StringVar(value=st.get('legend', ''))
            ttk.Entry(fr, textvariable=leg_val, width=18).grid(row=r, column=4, padx=5)
            leg_val.trace("w", lambda n, i, m, v=leg_val, kk=k: up_leg(v, kk))
            r += 1

        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)

    # ---------------------------------------------------------------
    # RANGES & DATA DIALOG
    # ---------------------------------------------------------------

    def open_ranges_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Ranges & Data Transformation")
        w, h = self.get_dialog_size(0.42, 0.75, max_width=560, max_height=650, min_width=460, min_height=480)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)

        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        def add_entry(parent, txt, var, width=15):
            f = ttk.Frame(parent); f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=width).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')

        # ---- TAB 1: 2D Polar ----
        tab_polar = ttk.Frame(notebook, padding=10)
        notebook.add(tab_polar, text="2D Polar")

        ttk.Label(tab_polar, text="Data Transformation (Divide by)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_polar, "Divide Theta:", self.v_theta_div)
        add_entry(tab_polar, "Divide R:", self.v_r_div)

        ttk.Separator(tab_polar, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_polar, text="R-Axis Range", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_polar, "R Min:", self.v_r_min)
        add_entry(tab_polar, "R Max:", self.v_r_max)

        ttk.Separator(tab_polar, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_polar, text="Theta Window (optional, in Theta Unit)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Label(tab_polar, text="Leave blank to show the full 360°/2π circle.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(anchor='w')
        add_entry(tab_polar, "Theta Min:", self.v_theta_min)
        add_entry(tab_polar, "Theta Max:", self.v_theta_max)

        ttk.Separator(tab_polar, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_polar, text="Custom R Gridlines (comma-separated, blank = auto)",
                  font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_polar, "R Gridlines:", self.v_r_gridlines)

        ttk.Separator(tab_polar, orient='horizontal').pack(fill='x', pady=10)
        add_entry(tab_polar, "Fill Alpha:", self.v_polar_fill_alpha)

        # ---- TAB 2: 3D Sphere ----
        tab_sphere = ttk.Frame(notebook, padding=10)
        notebook.add(tab_sphere, text="3D Sphere")

        ttk.Label(tab_sphere, text="Data Transformation (Divide by)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_sphere, "Divide Theta:", self.v_theta_div)
        add_entry(tab_sphere, "Divide Phi:", self.v_phi_div)
        add_entry(tab_sphere, "Divide R:", self.v_r_div)

        ttk.Separator(tab_sphere, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sphere, text="Fixed Radius (used when not using an R column)",
                  font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_sphere, "Fixed Radius:", self.v_sphere_fixed_r)

        ttk.Separator(tab_sphere, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sphere, text="Reference Sphere Wireframe", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_sphere, "Wireframe Alpha:", self.v_sphere_wireframe_alpha)

        ttk.Separator(tab_sphere, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sphere, text="View Angle", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_sphere, "Elevation (deg):", self.v_sphere_elev)
        add_entry(tab_sphere, "Azimuth (deg):", self.v_sphere_azim)

        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Reset Ranges", command=self.reset_ranges, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)

    def reset_ranges(self):
        for v in [self.v_r_min, self.v_r_max, self.v_theta_min, self.v_theta_max, self.v_r_gridlines]:
            v.set("")
        self.update_plot()

    # ---------------------------------------------------------------
    # LABELS & TITLES DIALOG
    # ---------------------------------------------------------------

    def open_labels_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Labels, Titles & Colors")
        w, h = self.get_dialog_size(0.42, 0.7, max_width=560, max_height=600, min_width=460, min_height=440)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)

        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        def add_entry(parent, txt, var, width=15):
            f = ttk.Frame(parent); f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=width).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')

        def choose_col(attr, btn):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                setattr(self, attr, c)
                btn.config(bg=c)
                d.lift()

        def add_col(parent, txt, attr, default):
            f = ttk.Frame(parent); f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=18).pack(side='left')
            b = tk.Button(f, text=" ", bg=default, width=8)
            b.config(command=lambda: choose_col(attr, b))
            b.pack(side='right')

        tab_text = ttk.Frame(notebook, padding=10)
        notebook.add(tab_text, text="Text")
        add_entry(tab_text, "Plot Title:", self.v_title)
        add_entry(tab_text, "R Label:", self.v_r_label)
        ttk.Separator(tab_text, orient='horizontal').pack(fill='x', pady=10)
        add_entry(tab_text, "Legend (csv):", self.v_legend)
        ttk.Checkbutton(tab_text, text="Show Legend", variable=self.show_legend).pack(pady=2, anchor='w')
        ttk.Checkbutton(tab_text, text="Show Grid", variable=self.show_grid).pack(pady=2, anchor='w')

        tab_colors = ttk.Frame(notebook, padding=10)
        notebook.add(tab_colors, text="Colors")
        add_col(tab_colors, "Title Color:", "title_color", self.title_color)
        add_col(tab_colors, "R Label Color:", "rlabel_color", self.rlabel_color)
        add_col(tab_colors, "Tick Color:", "tick_color", self.tick_color)
        ttk.Separator(tab_colors, orient='horizontal').pack(fill='x', pady=10)
        add_col(tab_colors, "Plot Background:", "plot_bg_color", self.plot_bg_color)
        add_col(tab_colors, "Figure Background:", "fig_bg_color", self.fig_bg_color)
        add_col(tab_colors, "Legend Fill:", "legend_fill_color", self.legend_fill_color)
        add_col(tab_colors, "Legend Frame:", "legend_frame_color", self.legend_frame_color)
        add_col(tab_colors, "Polar Gridlines:", "polar_gridline_color", self.polar_gridline_color)

        tab_legend = ttk.Frame(notebook, padding=10)
        notebook.add(tab_legend, text="Legend")
        col_frame = ttk.Frame(tab_legend); col_frame.pack(fill='x', pady=2)
        ttk.Label(col_frame, text="Legend Columns:", width=15).pack(side='left')
        ttk.Combobox(col_frame, textvariable=self.legend_columns, values=[str(i) for i in range(1, 9)],
                     width=10, state='readonly').pack(side='left')
        ttk.Checkbutton(tab_legend, text="Draggable Legend", variable=self.legend_draggable).pack(pady=8, anchor='w')

        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)

    # ---------------------------------------------------------------
    # TICKS & FONTS DIALOG
    # ---------------------------------------------------------------

    def open_ticks_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Ticks & Fonts")
        w, h = self.get_dialog_size(0.4, 0.65, max_width=520, max_height=550, min_width=440, min_height=420)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)

        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        def add_sz(parent, txt, var, width=10):
            f = ttk.Frame(parent); f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt).pack(side='left')
            ttk.Entry(f, textvariable=var, width=width).pack(side='right')

        # ---- TAB 1: Fonts ----
        tab_font = ttk.Frame(notebook, padding=10)
        notebook.add(tab_font, text="Fonts")
        ttk.Label(tab_font, text="Font Settings", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))

        f_fam = ttk.Frame(tab_font); f_fam.pack(fill='x', pady=2)
        ttk.Label(f_fam, text="Font Family:").pack(side='left')
        from matplotlib.font_manager import fontManager
        available_fonts = sorted(set(f.name for f in fontManager.ttflist))
        ttk.Combobox(f_fam, textvariable=self.v_font_fam, values=available_fonts, width=22).pack(side='right')

        add_sz(tab_font, "Title Size:", self.v_t_size)
        add_sz(tab_font, "R Label Size:", self.v_l_size)
        add_sz(tab_font, "Legend Size:", self.v_leg_size)
        add_sz(tab_font, "Tick Label Size:", self.v_tick_size)

        # ---- TAB 2: Tick Control (2D Polar) ----
        tab_tick = ttk.Frame(notebook, padding=10)
        notebook.add(tab_tick, text="Tick Control")
        ttk.Label(tab_tick, text="Applies to 2D Polar mode", font=('Arial', 9, 'italic'),
                  foreground='gray').pack(anchor='w', pady=(0, 8))

        ttk.Label(tab_tick, text="Angular (Theta) Ticks", font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Checkbutton(tab_tick, text="Show Theta Tick Labels", variable=self.show_theta_ticks).pack(anchor='w', pady=2)
        add_sz(tab_tick, "Theta Tick Step (deg):", self.v_theta_tick_step, width=10)
        ttk.Label(tab_tick, text="Blank = matplotlib default (8 ticks).",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(anchor='w', pady=(0, 8))

        ttk.Separator(tab_tick, orient='horizontal').pack(fill='x', pady=8)
        ttk.Label(tab_tick, text="Radial (R) Ticks", font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Checkbutton(tab_tick, text="Show R Tick Labels", variable=self.show_r_ticks).pack(anchor='w', pady=2)
        add_sz(tab_tick, "Number of R Ticks:", self.v_r_tick_count, width=10)
        add_sz(tab_tick, "R Tick Decimal Places:", self.v_r_dec, width=10)
        ttk.Label(tab_tick, text="Both blank = matplotlib default. Overridden by\ncustom 'R Gridlines' in the Ranges & Data dialog.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(anchor='w', pady=(0, 8))

        ttk.Separator(tab_tick, orient='horizontal').pack(fill='x', pady=8)
        add_sz(tab_tick, "Tick Label Padding:", self.v_tick_pad, width=10)

        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(side='left', expand=True, fill='x', padx=2)

    # ---------------------------------------------------------------
    # MAIN PLOTTING LOGIC
    # ---------------------------------------------------------------

    def update_plot(self):
        sel_ds = self.get_selected_datasets()
        theta_col = self.polar_theta_combo.get()
        if not sel_ds or not theta_col:
            return

        self.fig.clear()

        def val(var, default=None, type_fn=float):
            try:
                return type_fn(var.get())
            except Exception:
                return default

        font = self.v_font_fam.get()
        t_sz = val(self.v_t_size, 14)
        l_sz = val(self.v_l_size, 12)
        leg_sz = val(self.v_leg_size, 10)
        tick_sz = val(self.v_tick_size, 10)

        try:
            if self.v_plot_mode.get() == "3D Sphere":
                self._plot_sphere3d(sel_ds, val, font, t_sz, l_sz, leg_sz, tick_sz)
            else:
                self._plot_polar2d(sel_ds, val, font, t_sz, l_sz, leg_sz, tick_sz)

            self.fig.patch.set_facecolor(self.fig_bg_color)
            self.fig.tight_layout(pad=3.0)
            self.canvas.draw()
        except Exception as e:
            print(f"Error plotting: {e}")
            messagebox.showerror("Plot Error", str(e))

    # --- 2D POLAR ------------------------------------------------

    def _plot_polar2d(self, sel_ds, val, font, t_sz, l_sz, leg_sz, tick_sz):
        theta_col = self.polar_theta_combo.get()
        r_col = self.polar_r_combo.get()
        if not r_col:
            raise ValueError("Select an R column for the 2D Polar plot.")

        theta_f = val(self.v_theta_div, 1.0)
        r_f = val(self.v_r_div, 1.0)
        unit = self.v_theta_unit.get()

        self.ax = self.fig.add_subplot(111, projection='polar')

        zero_choice = POLAR_THETA_ZERO_MAP.get(self.v_theta_zero.get(), "N")
        self.ax.set_theta_zero_location(zero_choice)
        self.ax.set_theta_direction(-1 if self.v_polar_direction.get() == "Clockwise" else 1)

        l_txt = self.v_legend.get().strip()
        cust_legs = [l.strip() for l in l_txt.split(',')] if l_txt else []

        total_lines = len(sel_ds)
        if self.v_color_mode.get() == "Gradient" and total_lines > 0:
            cmap = plt.get_cmap(self.v_cmap_name.get())
            generated_colors = [cmap(x) for x in np.linspace(0, 1, total_lines)] if total_lines > 1 else [cmap(0.5)]
        else:
            cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
            generated_colors = [cycle[i % len(cycle)] for i in range(total_lines)]

        fill_alpha = val(self.v_polar_fill_alpha, 0.25)
        marker = self.v_polar_marker.get()
        marker = None if marker == "None" else marker

        lines, labels = [], []
        for c_idx, (fk, df) in enumerate(sel_ds):
            if theta_col not in df.columns or r_col not in df.columns:
                continue
            theta_raw = df[theta_col].to_numpy() / theta_f
            r_plot = df[r_col].to_numpy() / r_f
            theta_plot = np.deg2rad(theta_raw) if unit == "Degrees" else theta_raw

            sk = (fk, r_col)
            st = self.styles.get(sk, {})
            c = st.get('color', generated_colors[c_idx])
            w = st.get('width', 2.0)
            ls = st.get('linestyle', '-')
            style_leg = st.get('legend', '').strip()
            if style_leg:
                lbl = style_leg
            elif c_idx < len(cust_legs) and cust_legs[c_idx]:
                lbl = cust_legs[c_idx]
            else:
                lbl = f"{fk}: {r_col}"

            ln, = self.ax.plot(theta_plot, r_plot, label=lbl, color=c, linewidth=w,
                                linestyle=ls, marker=marker, markersize=6)
            if self.v_polar_fill.get():
                self.ax.fill(theta_plot, r_plot, color=c, alpha=fill_alpha)
            lines.append(ln)
            labels.append(lbl)

        self.ax.set_facecolor(self.plot_bg_color)
        self.ax.set_title(self.v_title.get(), fontsize=t_sz, fontweight='bold', fontname=font,
                           color=self.title_color, pad=20)

        tick_pad = val(self.v_tick_pad, 5)
        self.ax.tick_params(axis='x', labelsize=tick_sz, colors=self.tick_color, pad=tick_pad)
        self.ax.tick_params(axis='y', labelsize=tick_sz, colors=self.tick_color, pad=tick_pad)

        # --- Theta tick control ---
        if not self.show_theta_ticks.get():
            self.ax.set_xticklabels([])
        else:
            theta_step = val(self.v_theta_tick_step)
            if theta_step and theta_step > 0:
                n_ticks = max(int(round(360.0 / theta_step)), 1)
                theta_ticks = np.linspace(0, 2 * np.pi, n_ticks, endpoint=False)
                self.ax.set_xticks(theta_ticks)
                if unit == "Degrees":
                    self.ax.set_xticklabels([f"{np.rad2deg(t):g}°" for t in theta_ticks])

        r_label = self.v_r_label.get().strip() or r_col
        self.ax.set_rlabel_position(135)

        # --- R tick control ---
        r_grid_txt = self.v_r_gridlines.get().strip()
        if r_grid_txt:
            try:
                r_ticks = [float(v.strip()) for v in r_grid_txt.split(',') if v.strip()]
                if r_ticks:
                    self.ax.set_rticks(r_ticks)
            except Exception:
                pass
        else:
            r_tick_count = val(self.v_r_tick_count, None, type_fn=int)
            if r_tick_count and r_tick_count > 0:
                self.ax.yaxis.set_major_locator(plt.MaxNLocator(nbins=r_tick_count))

        r_dec = val(self.v_r_dec, None, type_fn=int)
        if r_dec is not None:
            self.ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.{r_dec}f}")

        if not self.show_r_ticks.get():
            self.ax.set_yticklabels([])

        r_min_v, r_max_v = val(self.v_r_min), val(self.v_r_max)
        if r_min_v is not None or r_max_v is not None:
            lo, hi = self.ax.get_ylim()
            self.ax.set_ylim(bottom=r_min_v if r_min_v is not None else lo,
                              top=r_max_v if r_max_v is not None else hi)

        th_min_raw, th_max_raw = val(self.v_theta_min), val(self.v_theta_max)
        if th_min_raw is not None and th_max_raw is not None:
            if unit == "Degrees":
                self.ax.set_thetamin(th_min_raw)
                self.ax.set_thetamax(th_max_raw)
            else:
                self.ax.set_thetamin(np.rad2deg(th_min_raw))
                self.ax.set_thetamax(np.rad2deg(th_max_raw))

        if self.show_grid.get():
            self.ax.grid(True, color=self.polar_gridline_color, alpha=0.4)
        else:
            self.ax.grid(False)

        if self.show_legend.get() and lines:
            ncol = int(self.legend_columns.get())
            legend = self.ax.legend(lines, labels, loc='upper right', bbox_to_anchor=(1.3, 1.1),
                                     ncol=ncol, prop={'size': leg_sz, 'family': font})
            legend.get_frame().set_facecolor(self.legend_fill_color)
            legend.get_frame().set_edgecolor(self.legend_frame_color)
            if self.legend_draggable.get():
                legend.set_draggable(True)

        self.fig.text(0.02, 0.02, f"R: {r_label}", fontsize=max(l_sz - 2, 8), color=self.rlabel_color)

    # --- 3D SPHERE -------------------------------------------------

    def _plot_sphere3d(self, sel_ds, val, font, t_sz, l_sz, leg_sz, tick_sz):
        theta_col = self.polar_theta_combo.get()
        phi_col = self.polar_phi_combo.get()
        if not phi_col:
            raise ValueError("Select a Phi (elevation/inclination) column for the 3D Sphere plot.")

        theta_f = val(self.v_theta_div, 1.0)
        phi_f = val(self.v_phi_div, 1.0)
        r_f = val(self.v_r_div, 1.0)
        unit = self.v_theta_unit.get()
        use_r_col = self.v_sphere_use_r_col.get()
        r_col = self.polar_sphere_r_combo.get()
        fixed_r = val(self.v_sphere_fixed_r, 1.0)
        convention = self.v_phi_convention.get()

        self.ax = self.fig.add_subplot(111, projection='3d')

        # --- Reference sphere wireframe ---
        if self.v_sphere_show_wireframe.get():
            ref_r = fixed_r if not use_r_col else 1.0
            u = np.linspace(0, 2 * np.pi, 40)
            v = np.linspace(0, np.pi, 24)
            xs = ref_r * np.outer(np.cos(u), np.sin(v))
            ys = ref_r * np.outer(np.sin(u), np.sin(v))
            zs = ref_r * np.outer(np.ones_like(u), np.cos(v))
            wf_alpha = val(self.v_sphere_wireframe_alpha, 0.15)
            self.ax.plot_wireframe(xs, ys, zs, color=self.sphere_wireframe_color,
                                    linewidth=0.5, alpha=wf_alpha, rstride=2, cstride=2)

        l_txt = self.v_legend.get().strip()
        cust_legs = [l.strip() for l in l_txt.split(',')] if l_txt else []

        total_lines = len(sel_ds)
        if self.v_color_mode.get() == "Gradient" and total_lines > 0:
            cmap = plt.get_cmap(self.v_cmap_name.get())
            generated_colors = [cmap(x) for x in np.linspace(0, 1, total_lines)] if total_lines > 1 else [cmap(0.5)]
        else:
            cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
            generated_colors = [cycle[i % len(cycle)] for i in range(total_lines)]

        trace_style = self.v_sphere_trace_style.get()
        marker = self.v_polar_marker.get()
        marker = None if marker == "None" else marker

        lines, labels = [], []
        for c_idx, (fk, df) in enumerate(sel_ds):
            if theta_col not in df.columns or phi_col not in df.columns:
                continue
            if use_r_col and (not r_col or r_col not in df.columns):
                continue

            theta_raw = df[theta_col].to_numpy() / theta_f
            phi_raw = df[phi_col].to_numpy() / phi_f
            theta_rad = np.deg2rad(theta_raw) if unit == "Degrees" else theta_raw

            # Convert phi to standard inclination (0 = north pole, pi = south pole)
            if "Elevation" in convention:
                # elevation: -90 (south) .. +90 (north), 0 = equator
                phi_deg = phi_raw if unit == "Degrees" else np.rad2deg(phi_raw)
                inclination = np.deg2rad(90.0 - phi_deg)
            else:
                # inclination already 0..180 from north pole
                inclination = np.deg2rad(phi_raw) if unit == "Degrees" else phi_raw

            r_plot = (df[r_col].to_numpy() / r_f) if use_r_col else np.full_like(theta_raw, fixed_r, dtype=float)

            x = r_plot * np.sin(inclination) * np.cos(theta_rad)
            y = r_plot * np.sin(inclination) * np.sin(theta_rad)
            z = r_plot * np.cos(inclination)

            style_key_col = r_col if (use_r_col and r_col) else phi_col
            sk = (fk, style_key_col)
            st = self.styles.get(sk, {})
            c = st.get('color', generated_colors[c_idx])
            w = st.get('width', 2.0)
            ls = st.get('linestyle', '-')
            style_leg = st.get('legend', '').strip()
            if style_leg:
                lbl = style_leg
            elif c_idx < len(cust_legs) and cust_legs[c_idx]:
                lbl = cust_legs[c_idx]
            else:
                lbl = f"{fk}: {theta_col}/{phi_col}"

            if trace_style == "Scatter":
                ln = self.ax.scatter(x, y, z, label=lbl, color=c, s=(w * 8), marker=(marker or 'o'))
            elif trace_style == "Line + Markers":
                ln, = self.ax.plot(x, y, z, label=lbl, color=c, linewidth=w, linestyle=ls,
                                    marker=(marker or 'o'), markersize=5)
            else:
                ln, = self.ax.plot(x, y, z, label=lbl, color=c, linewidth=w, linestyle=ls)
            lines.append(ln)
            labels.append(lbl)

        self.ax.set_facecolor(self.plot_bg_color)
        self.ax.set_title(self.v_title.get(), fontsize=t_sz, fontweight='bold', fontname=font,
                           color=self.title_color, pad=15)
        self.ax.tick_params(labelsize=tick_sz, colors=self.tick_color)

        self.ax.set_xlabel("X", fontsize=max(l_sz - 2, 8), color=self.rlabel_color)
        self.ax.set_ylabel("Y", fontsize=max(l_sz - 2, 8), color=self.rlabel_color)
        self.ax.set_zlabel("Z", fontsize=max(l_sz - 2, 8), color=self.rlabel_color)

        if self.v_sphere_equal_aspect.get():
            try:
                self.ax.set_box_aspect((1, 1, 1))
            except Exception:
                pass

        elev = val(self.v_sphere_elev, 20)
        azim = val(self.v_sphere_azim, -60)
        self.ax.view_init(elev=elev, azim=azim)

        if self.show_grid.get():
            self.ax.grid(True)
        else:
            self.ax.grid(False)

        if self.show_legend.get() and lines:
            ncol = int(self.legend_columns.get())
            legend = self.ax.legend(lines, labels, loc='upper left', bbox_to_anchor=(1.02, 1.0),
                                     ncol=ncol, prop={'size': leg_sz, 'family': font})
            legend.get_frame().set_facecolor(self.legend_fill_color)
            legend.get_frame().set_edgecolor(self.legend_frame_color)

    # ---------------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------------

    def export_plot(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".png",
                                                  filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")])
        if filepath:
            try:
                self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Success", f"Plot saved to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ---------------------------------------------------------------
    # SESSION SAVE / LOAD
    # ---------------------------------------------------------------

    def save_session(self):
        if not self.datasets:
            messagebox.showwarning("No Data", "No datasets loaded to save.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            initialfile=f"polar_session_{timestamp}", defaultextension=".json",
            filetypes=[("JSON Cache", "*.json"), ("All files", "*.*")], title="Save Session")
        if not filepath:
            return
        try:
            session_data = {"timestamp": datetime.now().isoformat()}
            session_data["datasets"] = {
                fn: {"columns": df.columns, "data": df.to_numpy().tolist()}
                for fn, df in self.datasets.items()
            }
            session_data["styles"] = {f"{k[0]}|||{k[1]}": v for k, v in self.styles.items()}
            session_data["plot_settings"] = {
                "color_mode": self.v_color_mode.get(),
                "colormap": self.v_cmap_name.get(),
                "plot_mode": self.v_plot_mode.get(),
            }
            session_data["titles_labels"] = {
                "title": self.v_title.get(), "r_label": self.v_r_label.get(),
                "legend_csv": self.v_legend.get(),
                "show_legend": self.show_legend.get(), "show_grid": self.show_grid.get(),
            }
            session_data["axis_selections"] = {
                "ref_file": self.axis_ref_combo.get(),
                "theta_column": self.polar_theta_combo.get(), "r_column": self.polar_r_combo.get(),
                "phi_column": self.polar_phi_combo.get(), "sphere_r_column": self.polar_sphere_r_combo.get(),
            }
            session_data["polar_settings"] = {
                "theta_div": self.v_theta_div.get(), "r_div": self.v_r_div.get(),
                "theta_unit": self.v_theta_unit.get(), "theta_zero": self.v_theta_zero.get(),
                "direction": self.v_polar_direction.get(),
                "r_min": self.v_r_min.get(), "r_max": self.v_r_max.get(),
                "theta_min": self.v_theta_min.get(), "theta_max": self.v_theta_max.get(),
                "r_gridlines": self.v_r_gridlines.get(),
                "fill": self.v_polar_fill.get(), "fill_alpha": self.v_polar_fill_alpha.get(),
                "marker": self.v_polar_marker.get(),
            }
            session_data["tick_settings"] = {
                "theta_tick_step": self.v_theta_tick_step.get(),
                "r_tick_count": self.v_r_tick_count.get(),
                "r_dec": self.v_r_dec.get(),
                "tick_pad": self.v_tick_pad.get(),
                "show_theta_ticks": self.show_theta_ticks.get(),
                "show_r_ticks": self.show_r_ticks.get(),
            }
            session_data["sphere_settings"] = {
                "phi_div": self.v_phi_div.get(), "phi_convention": self.v_phi_convention.get(),
                "use_r_col": self.v_sphere_use_r_col.get(), "fixed_r": self.v_sphere_fixed_r.get(),
                "trace_style": self.v_sphere_trace_style.get(),
                "show_wireframe": self.v_sphere_show_wireframe.get(),
                "wireframe_alpha": self.v_sphere_wireframe_alpha.get(),
                "elev": self.v_sphere_elev.get(), "azim": self.v_sphere_azim.get(),
                "equal_aspect": self.v_sphere_equal_aspect.get(),
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            messagebox.showinfo("Session Saved", f"Saved {len(self.datasets)} dataset(s) to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save session:\n{e}")

    def load_session(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON Cache", "*.json"), ("All files", "*.*")],
                                                title="Load Session")
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            self.datasets = {}
            self.styles = {}
            for filename, df_data in session_data.get("datasets", {}).items():
                self.datasets[filename] = pl.DataFrame(df_data["data"], schema=df_data["columns"], orient="row")
            for str_key, style_val in session_data.get("styles", {}).items():
                parts = str_key.split("|||")
                if len(parts) == 2:
                    self.styles[(parts[0], parts[1])] = style_val

            plot_settings = session_data.get("plot_settings", {})
            if plot_settings:
                self.v_color_mode.set(plot_settings.get("color_mode", "Cycle"))
                self.v_cmap_name.set(plot_settings.get("colormap", "viridis"))
                mode = plot_settings.get("plot_mode", "2D Polar")
                if mode in PLOT_MODES:
                    self.v_plot_mode.set(mode)

            tl = session_data.get("titles_labels", {})
            if tl:
                self.v_title.set(tl.get("title", "Polar Plot"))
                self.v_r_label.set(tl.get("r_label", ""))
                self.v_legend.set(tl.get("legend_csv", ""))
                self.show_legend.set(tl.get("show_legend", True))
                self.show_grid.set(tl.get("show_grid", True))

            ps = session_data.get("polar_settings", {})
            if ps:
                self.v_theta_div.set(ps.get("theta_div", "1"))
                self.v_r_div.set(ps.get("r_div", "1"))
                self.v_theta_unit.set(ps.get("theta_unit", "Degrees"))
                self.v_theta_zero.set(ps.get("theta_zero", "N (top)"))
                self.v_polar_direction.set(ps.get("direction", "Clockwise"))
                self.v_r_min.set(ps.get("r_min", ""))
                self.v_r_max.set(ps.get("r_max", ""))
                self.v_theta_min.set(ps.get("theta_min", ""))
                self.v_theta_max.set(ps.get("theta_max", ""))
                self.v_r_gridlines.set(ps.get("r_gridlines", ""))
                self.v_polar_fill.set(ps.get("fill", False))
                self.v_polar_fill_alpha.set(ps.get("fill_alpha", "0.25"))
                self.v_polar_marker.set(ps.get("marker", "None"))

            ts = session_data.get("tick_settings", {})
            if ts:
                self.v_theta_tick_step.set(ts.get("theta_tick_step", ""))
                self.v_r_tick_count.set(ts.get("r_tick_count", ""))
                self.v_r_dec.set(ts.get("r_dec", ""))
                self.v_tick_pad.set(ts.get("tick_pad", "5"))
                self.show_theta_ticks.set(ts.get("show_theta_ticks", True))
                self.show_r_ticks.set(ts.get("show_r_ticks", True))

            ss = session_data.get("sphere_settings", {})
            if ss:
                self.v_phi_div.set(ss.get("phi_div", "1"))
                if ss.get("phi_convention") in SPHERE_PHI_CONVENTION:
                    self.v_phi_convention.set(ss["phi_convention"])
                self.v_sphere_use_r_col.set(ss.get("use_r_col", False))
                self.v_sphere_fixed_r.set(ss.get("fixed_r", "1.0"))
                if ss.get("trace_style") in SPHERE_TRACE_STYLE:
                    self.v_sphere_trace_style.set(ss["trace_style"])
                self.v_sphere_show_wireframe.set(ss.get("show_wireframe", True))
                self.v_sphere_wireframe_alpha.set(ss.get("wireframe_alpha", "0.15"))
                self.v_sphere_elev.set(ss.get("elev", "20"))
                self.v_sphere_azim.set(ss.get("azim", "-60"))
                self.v_sphere_equal_aspect.set(ss.get("equal_aspect", True))

            self.refresh_dataset_list(new_load=True)
            self.dataset_listbox.selection_set(0, tk.END)

            axsel = session_data.get("axis_selections", {})
            if axsel:
                if axsel.get("ref_file") in self.axis_ref_combo['values']:
                    self.axis_ref_combo.set(axsel["ref_file"])
                    self.populate_column_selectors(None)
                if axsel.get("theta_column") in self.polar_theta_combo['values']:
                    self.polar_theta_combo.set(axsel["theta_column"])
                if axsel.get("r_column") in self.polar_r_combo['values']:
                    self.polar_r_combo.set(axsel["r_column"])
                if axsel.get("phi_column") in self.polar_phi_combo['values']:
                    self.polar_phi_combo.set(axsel["phi_column"])
                if axsel.get("sphere_r_column") in self.polar_sphere_r_combo['values']:
                    self.polar_sphere_r_combo.set(axsel["sphere_r_column"])

            self.on_plot_mode_change(None)
            messagebox.showinfo("Session Loaded", f"Loaded {len(self.datasets)} dataset(s) from:\n{filepath}")
            self.update_plot()
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load session:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PolarPlotter(root)
    root.mainloop()