# ==================== IMPORTS ====================

# --- Standard Library ---
import sys
import json
import os
from datetime import datetime

# --- Third-Party: Data & Math ---
import numpy as np
import polars as pl
from scipy.interpolate import griddata

# --- Third-Party: Matplotlib ---
import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec
from matplotlib import cm
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# --- Third-Party: Tkinter GUI ---
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
    'berlin', 'managua', 'vanimo',

    'twilight', 'twilight_shifted', 'hsv',

    'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2',
    'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b',
    'tab20c',

    'flag', 'prism', 'ocean', 'gist_earth', 'terrain',
    'gist_stern', 'gnuplot', 'gnuplot2', 'CMRmap',
    'cubehelix', 'brg', 'gist_rainbow', 'rainbow', 'jet',
    'turbo', 'nipy_spectral', 'gist_ncar'
]


class InteractivePlotter:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive  Plotter")

        # --- DYNAMIC WINDOW SIZING ---
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            w = int(screen_width * 0.85)
            h = int(screen_height * 0.85)
            w = min(1400, w)
            h = min(980, h)
            x_pos = (screen_width - w) // 2
            y_pos = (screen_height - h) // 2
            self.root.geometry(f"{w}x{h}+{x_pos}+{y_pos}")
        except:
            self.root.geometry("1200x800")
        self.root.deiconify()

        self.datasets = {}
        self.current_dataset_key = None
        self.styles = {}
        self.merge_cols_var = tk.BooleanVar(value=False)
        self.use_ref_x_var = tk.BooleanVar(value=False)

        # --- COLOR SETTINGS ---
        self.v_color_mode = tk.StringVar(value="Cycle")  # "Cycle" or "Gradient"
        self.v_cmap_name = tk.StringVar(value="viridis")

        # --- DATA VARIABLES ---
        self.v_x_div = tk.StringVar(value="1")
        self.v_y_div = tk.StringVar(value="1")
        self.v_y2_div = tk.StringVar(value="1")
        self.v_z_div = tk.StringVar(value="1")

        self.v_x_min = tk.StringVar()
        self.v_x_max = tk.StringVar()
        self.v_y_min = tk.StringVar()
        self.v_y_max = tk.StringVar()
        self.v_y2_min = tk.StringVar()
        self.v_y2_max = tk.StringVar()
        self.v_z_min = tk.StringVar()
        self.v_z_max = tk.StringVar()
        self.v_break_start = tk.StringVar()  # Backward compat → Y Break 1 Start
        self.v_break_end = tk.StringVar()    # Backward compat → Y Break 1 End

        # --- AXIS BREAKS (universal — works with any plot type) ---
        self.v_y_breaks = [(tk.StringVar(), tk.StringVar()) for _ in range(1)]
        self.v_x_breaks = [(tk.StringVar(), tk.StringVar()) for _ in range(1)]

        self.v_title = tk.StringVar(value="My Plot")
        self.v_xlabel = tk.StringVar()
        self.v_ylabel = tk.StringVar()
        self.v_y2label = tk.StringVar()
        self.v_zlabel = tk.StringVar()
        self.v_legend = tk.StringVar()
        self.show_legend = tk.BooleanVar(value=True)
        self.show_grid = tk.BooleanVar(value=True)
        
        # --- LEGEND SETTINGS ---
        self.legend_columns = tk.StringVar(value="1")
        self.legend_draggable = tk.BooleanVar(value=False)
        self.legend_position = tk.StringVar(value="Best")
        
        # --- LABEL POSITION SETTINGS (figure coordinates 0-1) ---
        self.title_x = tk.StringVar(value="0.5")  # Default center
        self.title_y = tk.StringVar(value="0.98")  # Default top
        self.xlabel_x = tk.StringVar(value="0.5")  # Default center
        self.xlabel_y = tk.StringVar(value="0.04")  # Default bottom
        self.ylabel_x = tk.StringVar(value="0.04")  # Default left
        self.ylabel_y = tk.StringVar(value="0.5")  # Default center
        self.y2label_x = tk.StringVar(value="0.96")  # Default right
        self.y2label_y = tk.StringVar(value="0.5")  # Default center
        self.zlabel_x = tk.StringVar(value="0.96")  # Default right (for colorbar)
        self.zlabel_y = tk.StringVar(value="0.5")  # Default center
        self.use_custom_label_positions = tk.BooleanVar(value=False)  # Enable custom positions
        
        # --- TEXT ROTATION SETTINGS (degrees) ---
        self.title_rotation = tk.StringVar(value="0")  # 0 = horizontal
        self.xlabel_rotation = tk.StringVar(value="0")
        self.ylabel_rotation = tk.StringVar(value="90")  # 90 = vertical
        self.y2label_rotation = tk.StringVar(value="90")  # 90 = vertical (inverted for right side)
        self.zlabel_rotation = tk.StringVar(value="90")  # 90 = vertical (for colorbar)
        self.use_custom_rotation = tk.BooleanVar(value=False)  # Enable custom rotation

        self.v_x_pad = tk.StringVar(value="4.0")
        self.v_y_pad = tk.StringVar(value="4.0")
        self.v_y_broken_offset = tk.StringVar(value="-0.15")
        self.v_z_pad = tk.StringVar(value="10.0")

        self.title_color = 'black'
        self.xlabel_color = 'black'
        self.ylabel_color = 'black'
        self.zlabel_color = 'black'
        self.xtick_color = 'black'
        self.ytick_color = 'black'
        self.plot_bg_color = 'white'
        self.fig_bg_color = 'white'
        self.legend_fill_color = 'white'
        self.legend_frame_color = 'black'
        
        # --- TRANSPARENCY (ALPHA) SETTINGS ---
        self.plot_bg_alpha = tk.StringVar(value="1.0")
        self.fig_bg_alpha = tk.StringVar(value="1.0")
        self.legend_fill_alpha = tk.StringVar(value="1.0")

        self.v_x_maj = tk.StringVar()
        self.v_y_maj = tk.StringVar()
        self.v_y1_maj = tk.StringVar()
        self.v_y2_maj = tk.StringVar()
        self.v_z_maj = tk.StringVar()
        self.v_x_min_div = tk.StringVar()
        self.v_y_min_div = tk.StringVar()
        self.v_y1_min_div = tk.StringVar()
        self.v_y2_min_div = tk.StringVar()
        self.v_z_min_div = tk.StringVar()

        self.v_x_tick_pad = tk.StringVar(value="3.5")
        self.v_y_tick_pad = tk.StringVar(value="3.5")
        self.v_y1_pad = tk.StringVar(value="3.5")
        self.v_y2_pad = tk.StringVar(value="3.5")
        self.v_z_tick_pad = tk.StringVar(value="3.5")

        self.v_font_fam = tk.StringVar(value="Arial")
        self.v_t_size = tk.StringVar(value="14")
        self.v_l_size = tk.StringVar(value="12")
        self.v_leg_size = tk.StringVar(value="10")
        self.v_xtick_size = tk.StringVar(value="10")
        self.v_ytick_size = tk.StringVar(value="10")
        self.v_x_not = tk.StringVar(value="Scientific")
        self.v_y_not = tk.StringVar(value="Scientific")
        self.x_log = tk.BooleanVar()
        self.y_log = tk.BooleanVar()

        # --- TICK DIRECTION & LENGTH (Origin Pro-like) ---
        self.v_tick_dir_x = tk.StringVar(value="out")       # "out", "in", "inout", "none"
        self.v_tick_dir_y = tk.StringVar(value="out")
        self.v_tick_dir_y2 = tk.StringVar(value="out")
        self.v_tick_dir_z = tk.StringVar(value="out")
        self.v_minor_tick_dir_x = tk.StringVar(value="out")
        self.v_minor_tick_dir_y = tk.StringVar(value="out")
        self.v_minor_tick_dir_y2 = tk.StringVar(value="out")
        self.v_minor_tick_dir_z = tk.StringVar(value="out")
        self.v_major_tick_length = tk.StringVar(value="4.0")
        self.v_minor_tick_length = tk.StringVar(value="2.0")

        # --- TICK VISIBILITY PER SIDE ---
        self.v_x_tick_bottom = tk.BooleanVar(value=True)
        self.v_x_tick_top = tk.BooleanVar(value=False)
        self.v_y_tick_left = tk.BooleanVar(value=True)
        self.v_y_tick_right = tk.BooleanVar(value=False)

        # --- GRID SETTINGS ---
        self.show_major_grid = tk.BooleanVar(value=False)
        self.show_minor_grid = tk.BooleanVar(value=False)
        self.v_grid_alpha = tk.StringVar(value="0.3")
        self.v_grid_linestyle = tk.StringVar(value="-")
        self.v_grid_linewidth = tk.StringVar(value="0.5")

        # --- SECONDARY X-AXIS (Top Axis) ---
        self.enable_secondary_x = tk.BooleanVar(value=False)
        self.v_sec_x_forward = tk.StringVar(value="x")  # Forward transform formula (bottom -> top)
        self.v_sec_x_inverse = tk.StringVar(value="x")  # Inverse transform formula (top -> bottom)
        self.v_sec_x_label = tk.StringVar(value="")     # Label for secondary top X-axis
        self.v_sec_x_tick_size = tk.StringVar(value="10")  # Tick font size for top X-axis
        self.v_sec_x_maj = tk.StringVar(value="")       # Major tick step for top X-axis
        self.v_sec_x_min_div = tk.StringVar(value="")   # Minor tick divisions for top X-axis
        self.sec_x_label_color = 'black'                 # Label color for secondary X-axis

        # --- CACHE SETTINGS ---
        self.cache_folder = None  # User-selected folder for cache files
        
        # --- LEGEND ORDER ---
        self.legend_order = []  # List of (filename, column) tuples in desired order - persists across selections
        
        # --- LINE VISIBILITY STATE ---
        self.line_visibility = {}  # (filename, column) -> bool for toggling lines via legend
        self.current_lines = []  # Store current plot lines for legend toggle
        self.current_legend_labels = []  # Store legend labels for context menu
        self.hidden_legend_items = set()  # Set of (filename, column) tuples that are hidden
        self._series_line_groups = {}  # (filename, column) -> [Line2D, ...] for ALL axes (broken Y-axis support)
        self._all_series_keys = []  # All series keys for context menu toggle (works without legend)
        
        # --- DATASET WINDOW ---
        self.dataset_window = None
        
        # --- SCREEN DIMENSIONS (for responsive design) ---
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.setup_ui()

    def setup_ui(self):
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        control_container = ttk.Frame(main_container)
        main_container.add(control_container, width=420)

        canvas_scroll = tk.Canvas(control_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(control_container, orient="vertical", command=canvas_scroll.yview)
        control_frame = ttk.Frame(canvas_scroll, padding="10")

        control_frame.bind("<Configure>", lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=control_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas_scroll.pack(side="left", fill="both", expand=True)
        #canvas_scroll.bind_all("<MouseWheel>", lambda e: canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        #plot_frame = ttk.Frame(main_container)
        def _on_main_mousewheel(event):
            canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_main_mousewheel(event):
            canvas_scroll.bind_all("<MouseWheel>", _on_main_mousewheel)
        def _unbind_main_mousewheel(event):
            canvas_scroll.unbind_all("<MouseWheel>")
        canvas_scroll.bind('<Enter>', _bind_main_mousewheel)
        canvas_scroll.bind('<Leave>', _unbind_main_mousewheel)
        control_frame.bind('<Enter>', _bind_main_mousewheel)
        control_frame.bind('<Leave>', _unbind_main_mousewheel)

        plot_frame = ttk.Frame(main_container)
        main_container.add(plot_frame)

        # === Control Panel ===
        row = 0
        ttk.Label(control_frame, text="DATA FILES", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4,
                                                                                     sticky='w', pady=(0, 5))
        row += 1
        ttk.Button(control_frame, text="Load Data File", command=self.load_files).grid(row=row, column=0,
                                                                                          columnspan=4, sticky='ew',
                                                                                          pady=5)
        row += 1

        # Compact dataset list with button to open separate window
        ds_frame = ttk.Frame(control_frame)
        ds_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        ds_sb = ttk.Scrollbar(ds_frame, orient='vertical')
        self.dataset_listbox = tk.Listbox(ds_frame, selectmode='extended', height=3, yscrollcommand=ds_sb.set,
                                          exportselection=False)
        ds_sb.config(command=self.dataset_listbox.yview)
        self.dataset_listbox.pack(side='left', fill='both', expand=True)
        ds_sb.pack(side='right', fill='y')
        self.dataset_listbox.bind('<<ListboxSelect>>', self.on_dataset_selection_change)
        row += 1
        
        # Button frame for dataset management
        ds_btn_frame = ttk.Frame(control_frame)
        ds_btn_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=2)
        ttk.Button(ds_btn_frame, text="Unload", command=self.unload_files, width=10).pack(side='left', padx=2)
        ttk.Button(ds_btn_frame, text="Dataset Manager", command=self.open_dataset_window, width=16).pack(side='left', padx=2)
        row += 1

        # --- SESSION CACHE BUTTONS ---
        cache_frame = ttk.Frame(control_frame)
        cache_frame.grid(row=row, column=0, columnspan=4, sticky='ew', pady=5)
        ttk.Button(cache_frame, text="Save Session", command=self.save_session).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(cache_frame, text="Load Session", command=self.load_session).pack(side='left', expand=True, fill='x', padx=2)
        row += 1
        ttk.Button(control_frame, text="Set Cache Folder", command=self.set_cache_folder).grid(row=row, column=0,
                                                                                               columnspan=4, sticky='ew',
                                                                                               pady=2)
        row += 1

        ttk.Label(control_frame, text="Axis Ref. File:").grid(row=row, column=0, columnspan=2, sticky='w')
        self.axis_ref_combo = ttk.Combobox(control_frame, state='readonly', width=20)
        self.axis_ref_combo.grid(row=row, column=2, columnspan=2, sticky='ew', pady=5)
        self.axis_ref_combo.bind('<<ComboboxSelected>>', self.populate_column_selectors)
        row += 1
        ttk.Checkbutton(control_frame, text="Show All Columns (Union)", variable=self.merge_cols_var,
                        command=lambda: self.populate_column_selectors(None)).grid(row=row, column=0, columnspan=4,
                                                                                   sticky='w', pady=2)
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # --- PLOT SETTINGS ---
        ttk.Label(control_frame, text="PLOT SETTINGS", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4,
                                                                                        sticky='w', pady=(0, 5))
        row += 1
        ttk.Label(control_frame, text="Plot Type:").grid(row=row, column=0, columnspan=2, sticky='w')
        self.plot_type = ttk.Combobox(control_frame,
                                      values=["Line", "Scatter", "Broken Y-Axis", "Color Map", "Dual Y-Axis"],
                                      state='readonly', width=20)
        self.plot_type.current(0)
        self.plot_type.grid(row=row, column=2, columnspan=2, sticky='ew', pady=5)
        self.plot_type.bind('<<ComboboxSelected>>', self.on_plot_type_change)
        row += 1

        # --- Color Controls ---
        ttk.Label(control_frame, text="Color Mode:").grid(row=row, column=0, sticky='w')
        c_mode = ttk.Combobox(control_frame, textvariable=self.v_color_mode, values=["Cycle", "Gradient"],
                              state='readonly', width=10)
        c_mode.grid(row=row, column=1, sticky='ew', padx=2)
        c_mode.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

        c_map = ttk.Combobox(control_frame, textvariable=self.v_cmap_name, values=COLORMAPS,
                             state='readonly', width=12)
        c_map.grid(row=row, column=2, columnspan=2, sticky='ew', padx=2)
        c_map.bind('<<ComboboxSelected>>', lambda e: (self._draw_cmap_preview(), self.update_plot()))
        row += 1

        # --- Colormap Preview Bar (labels drawn inside canvas to avoid clipping on small screens) ---
        self.cmap_preview_canvas = tk.Canvas(control_frame, height=20, highlightthickness=1, 
                                              highlightbackground='#cccccc')
        self.cmap_preview_canvas.grid(row=row, column=0, columnspan=4, sticky='ew', pady=(0, 5), padx=2)
        self._cmap_preview_photo = None  # Keep reference to prevent garbage collection
        # Bind resize to redraw the preview when control panel width changes
        self.cmap_preview_canvas.bind('<Configure>', lambda e: self._draw_cmap_preview())
        row += 1

        ttk.Label(control_frame, text="X Axis:").grid(row=row, column=0, sticky='w')
        self.x_combo = ttk.Combobox(control_frame, state='readonly', width=20)
        self.x_combo.grid(row=row, column=2, columnspan=2, sticky='ew', pady=5)
        row += 1
        ttk.Checkbutton(control_frame, text="Use X from Ref. File (Cross-File)", variable=self.use_ref_x_var).grid(
            row=row, column=0, columnspan=4, sticky='w', pady=2)
        row += 1

        self.y_container_frame = ttk.Frame(control_frame)
        self.y_container_frame.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        self.y_list_frame = ttk.Frame(self.y_container_frame)
        self.y_list_frame.pack(fill='both', expand=True)
        ttk.Label(self.y_list_frame, text="Y Axis (Multiple):").pack(anchor='w')
        y_sb = ttk.Scrollbar(self.y_list_frame, orient='vertical')
        self.y_listbox = tk.Listbox(self.y_list_frame, selectmode='multiple', height=6, yscrollcommand=y_sb.set,
                                    exportselection=False)
        y_sb.config(command=self.y_listbox.yview)
        self.y_listbox.pack(side='left', fill='both', expand=True)
        y_sb.pack(side='right', fill='y')

        self.y_dual_frame = ttk.Frame(self.y_container_frame)
        ttk.Label(self.y_dual_frame, text="Left Axis Y:", foreground="blue").pack(anchor='w', pady=(5, 0))
        self.y1_combo = ttk.Combobox(self.y_dual_frame, state='readonly')
        self.y1_combo.pack(fill='x', pady=2)
        ttk.Label(self.y_dual_frame, text="Right Axis Y:", foreground="red").pack(anchor='w', pady=(5, 0))
        self.y2_combo = ttk.Combobox(self.y_dual_frame, state='readonly')
        self.y2_combo.pack(fill='x', pady=2)

        ttk.Label(control_frame, text="Z Axis (Color):").grid(row=row, column=0, sticky='w')
        self.z_combo = ttk.Combobox(control_frame, state='readonly', width=20)
        self.z_combo.grid(row=row, column=2, columnspan=2, sticky='ew', pady=5)
        row += 1

        ttk.Checkbutton(control_frame, text="X Log Scale", variable=self.x_log).grid(row=row, column=0, columnspan=2,
                                                                                     sticky='w', pady=2)
        ttk.Checkbutton(control_frame, text="Y Log Scale", variable=self.y_log).grid(row=row, column=2, columnspan=2,
                                                                                     sticky='w', pady=2)
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1

        # --- CONFIGURATION ---
        ttk.Label(control_frame, text="CONFIGURATION", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4,
                                                                                        sticky='w', pady=(0, 5))
        row += 1
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1
        ttk.Button(btn_frame, text="Ranges & Data", command=self.open_ranges_dialog).grid(row=0, column=0, padx=2,
                                                                                          pady=2, sticky='ew')
        ttk.Button(btn_frame, text="Styles", command=self.open_style_dialog).grid(row=0, column=1, padx=2, pady=2,
                                                                                  sticky='ew')
        ttk.Button(btn_frame, text="Labels & Titles", command=self.open_labels_dialog).grid(row=1, column=0, padx=2,
                                                                                            pady=2, sticky='ew')
        ttk.Button(btn_frame, text="Ticks & Fonts", command=self.open_ticks_dialog).grid(row=1, column=1, padx=2,
                                                                                         pady=2, sticky='ew')
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        # Legend Order button
        ttk.Button(btn_frame, text="Legend Order", command=self.open_legend_order_dialog).grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky='ew')

        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1
        ttk.Button(control_frame, text="Update Plot", command=self.update_plot).grid(row=row, column=0, columnspan=4,
                                                                                     sticky='ew', pady=5)
        row += 1
        ttk.Button(control_frame, text="Export Plot", command=self.export_plot).grid(row=row, column=0, columnspan=4,
                                                                                     sticky='ew', pady=5)
        row += 1
        # Show All button for restoring hidden lines
        ttk.Button(control_frame, text="Show All Lines", command=self.show_all_lines).grid(row=row, column=0, columnspan=4,
                                                                                     sticky='ew', pady=5)
        row += 1
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)

        # Set minimum window size to ensure toolbar is visible on smaller screens
        self.root.minsize(900, 600)
        
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        
        # Create and pack toolbar FIRST at the bottom so it's always visible
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
        # Then pack canvas with expand - this ensures toolbar stays visible
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.ax.text(0.5, 0.5, 'Load data file to begin', ha='center', va='center', fontsize=16, color='gray')
        self.ax.set_xticks([]);
        self.ax.set_yticks([])
        self.canvas.draw()
        
        # Bind right-click on canvas for context menu (works even when no legend is visible)
        self.canvas.mpl_connect('button_press_event', self._on_canvas_right_click)
        
        # Draw initial colormap preview
        self.root.after(100, self._draw_cmap_preview)

    def _draw_cmap_preview(self):
        """Render the currently selected colormap as a horizontal gradient bar in the control panel."""
        try:
            canvas = self.cmap_preview_canvas
            # Wait until the canvas is displayed to get its actual width
            canvas.update_idletasks()
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2 or h < 2:
                # Canvas not yet rendered, retry after a short delay
                self.root.after(100, self._draw_cmap_preview)
                return
            
            # Get the colormap
            cmap_name = self.v_cmap_name.get()
            try:
                cmap = plt.get_cmap(cmap_name)
            except ValueError:
                return
            
            # Build the gradient image pixel by pixel (full canvas width)
            from tkinter import PhotoImage
            img = PhotoImage(width=w, height=h)
            
            # Sample the colormap across the width
            row_colors = []
            for x in range(w):
                val = x / max(w - 1, 1)
                r, g, b, _ = cmap(val)
                hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                row_colors.append(hex_color)
            
            # Build a single row string and replicate for all rows
            row_str = "{" + " ".join(row_colors) + "}"
            img.put(" ".join([row_str] * h))
            
            # Keep reference to prevent garbage collection
            self._cmap_preview_photo = img
            
            # Draw on canvas — full-width gradient with Min/Max text overlaid
            canvas.delete("all")
            canvas.create_image(0, 0, anchor='nw', image=img)
            # Pick contrasting text color based on edge colors
            r0, g0, b0, _ = cmap(0.0)
            r1, g1, b1, _ = cmap(1.0)
            lum0 = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
            lum1 = 0.299 * r1 + 0.587 * g1 + 0.114 * b1
            col0 = 'white' if lum0 < 0.5 else 'black'
            col1 = 'white' if lum1 < 0.5 else 'black'
            canvas.create_text(4, h // 2, text="Min", anchor='w', font=('Arial', 7, 'bold'), fill=col0)
            canvas.create_text(w - 4, h // 2, text="Max", anchor='e', font=('Arial', 7, 'bold'), fill=col1)
        except Exception as e:
            print(f"Colormap preview error: {e}")

    # --- HELPER METHODS FOR RESPONSIVE DESIGN ---
    
    def get_dialog_size(self, width_pct=0.35, height_pct=0.85, max_width=None, max_height=None, min_width=350, min_height=300):
        """Calculate dialog size based on screen dimensions.
        
        Args:
            width_pct: Percentage of screen width (default 35%)
            height_pct: Percentage of screen height (default 85%)
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            min_width: Minimum width in pixels
            min_height: Minimum height in pixels
        
        Returns:
            Tuple of (width, height) in pixels
        """
        w = int(self.screen_width * width_pct)
        h = int(self.screen_height * height_pct)
        
        if max_width:
            w = min(max_width, w)
        if max_height:
            h = min(max_height, h)
        
        w = max(min_width, w)
        h = max(min_height, h)
        
        return w, h
    
    def create_scrollable_dialog(self, parent, title, width_pct=0.35, height_pct=0.85, 
                                  max_width=None, max_height=None, min_width=350, min_height=300,
                                  auto_width=False):
        """Create a scrollable dialog window.
        
        Args:
            auto_width: If True, adjust width based on content after dialog is built (disabled by default)
        
        Returns:
            Tuple of (dialog, content_frame, canvas) where content_frame is the scrollable area
        """
        d = tk.Toplevel(parent)
        d.title(title)
        
        # Calculate size based on screen - use min_width as the actual width to ensure buttons fit
        w, h = self.get_dialog_size(width_pct, height_pct, max_width, max_height, min_width, min_height)
        
        # Ensure minimum width of 450 to accommodate buttons (3 buttons x 12 chars + padding)
        w = max(w, 450)
        
        # Center the dialog on parent
        d.geometry(f"{w}x{h}")
        d.transient(parent)
        
        # Create main container to hold scrollable area and button frame
        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        
        # Create button frame FIRST at bottom (before canvas so it stays visible)
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        
        # Create scrollable frame (fills remaining space above buttons)
        canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas, padding=10)
        
        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Enable mousewheel scrolling for this dialog only
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", on_mousewheel)
        content_frame.bind("<MouseWheel>", on_mousewheel)
        
        # Function to adjust width based on content (disabled by default)
        def adjust_width():
            pass  # No-op since auto_width is disabled
        
        # Cleanup binding when dialog closes
        def on_close():
            canvas.unbind("<MouseWheel>")
            content_frame.unbind("<MouseWheel>")
            d.destroy()
        d.protocol("WM_DELETE_WINDOW", on_close)
        
        # Store adjust function on dialog for later use (no-op)
        d.adjust_width = adjust_width
        
        return d, content_frame, canvas, main_container, btn_container

    def add_dialog_buttons(self, parent, dialog, update_cmd, ok_cmd=None, cancel_cmd=None, 
                           extra_buttons=None):
        """Add standardized button frame to a dialog.
        
        Args:
            parent: Parent frame to pack buttons into (should be content_frame, not main_container)
            dialog: The dialog window (for closing on OK/Cancel)
            update_cmd: Command for Update Plot button
            ok_cmd: Optional command for OK button (default: update + close)
            cancel_cmd: Optional command for Cancel button (default: just close)
            extra_buttons: List of (text, command) tuples for additional buttons
        
        Returns:
            The button frame
        """
        # Default commands
        if ok_cmd is None:
            ok_cmd = lambda: [update_cmd(), dialog.destroy()]
        if cancel_cmd is None:
            cancel_cmd = lambda: dialog.destroy()
        
        # Create button frame at the bottom of the content
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=(15, 5), side='bottom')
        
        # Create buttons - they will expand to fill available width within the frame
        ttk.Button(btn_frame, text="Update Plot", command=update_cmd).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_frame, text="OK", command=ok_cmd).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_frame, text="Cancel", command=cancel_cmd).pack(
            side='left', expand=True, fill='x', padx=2)
        
        # Add extra buttons if provided
        if extra_buttons:
            for text, cmd in extra_buttons:
                ttk.Button(btn_frame, text=text, command=cmd).pack(
                    side='left', expand=True, fill='x', padx=2)
        
        return btn_frame

    # --- DIALOG BUILDERS (FIXED FONTS) ---

    def open_ranges_dialog(self):
        """Open the Ranges & Data dialog with a tabbed interface."""
        d = tk.Toplevel(self.root)
        d.title("Ranges & Data Transformation")
        w, h = self.get_dialog_size(0.40, 0.80, max_width=550, max_height=700, min_width=450, min_height=500)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)

        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)

        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        def add_entry(parent, txt, var, width=15):
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=width).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')

        # ============================================
        # TAB 1: Ranges & Transform
        # ============================================
        tab_ranges = ttk.Frame(notebook, padding=10)
        notebook.add(tab_ranges, text="Ranges & Transform")

        ttk.Label(tab_ranges, text="Data Transformation (Divide by)", font=('Arial', 10, 'bold')).pack(pady=5)
        add_entry(tab_ranges, "Divide X:", self.v_x_div)
        add_entry(tab_ranges, "Divide Y:", self.v_y_div)
        add_entry(tab_ranges, "Divide Y2:", self.v_y2_div)
        add_entry(tab_ranges, "Divide Z:", self.v_z_div)

        ttk.Separator(tab_ranges, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_ranges, text="Axis Ranges", font=('Arial', 10, 'bold')).pack(pady=5)
        add_entry(tab_ranges, "X Min:", self.v_x_min)
        add_entry(tab_ranges, "X Max:", self.v_x_max)
        add_entry(tab_ranges, "Y Min:", self.v_y_min)
        add_entry(tab_ranges, "Y Max:", self.v_y_max)
        add_entry(tab_ranges, "Z Min (Color):", self.v_z_min)
        add_entry(tab_ranges, "Z Max (Color):", self.v_z_max)

        ttk.Separator(tab_ranges, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_ranges, text="Dual Y-Axis Ranges", font=('Arial', 10, 'bold')).pack(pady=5)
        add_entry(tab_ranges, "Y2 Min:", self.v_y2_min)
        add_entry(tab_ranges, "Y2 Max:", self.v_y2_max)

        # ============================================
        # TAB 2: Axis Breaks
        # ============================================
        tab_breaks = ttk.Frame(notebook, padding=10)
        notebook.add(tab_breaks, text="Axis Breaks")

        ttk.Label(tab_breaks, text="Y Axis Break", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Label(tab_breaks, text="Omit a range from the Y axis. Leave blank to disable.\nWorks with Line, Scatter, and Dual Y-Axis plots.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(anchor='w', pady=(0, 5))
        bf = ttk.Frame(tab_breaks)
        bf.pack(fill='x', pady=2)
        ttk.Label(bf, text="Y Break:", width=10).pack(side='left')
        ttk.Label(bf, text="Start:").pack(side='left', padx=(5, 2))
        ttk.Entry(bf, textvariable=self.v_y_breaks[0][0], width=10).pack(side='left', padx=2)
        ttk.Label(bf, text="End:").pack(side='left', padx=(10, 2))
        ttk.Entry(bf, textvariable=self.v_y_breaks[0][1], width=10).pack(side='left', padx=2)

        ttk.Separator(tab_breaks, orient='horizontal').pack(fill='x', pady=15)

        ttk.Label(tab_breaks, text="X Axis Break", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Label(tab_breaks, text="Omit a range from the X axis. Leave blank to disable.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(anchor='w', pady=(0, 5))
        bf = ttk.Frame(tab_breaks)
        bf.pack(fill='x', pady=2)
        ttk.Label(bf, text="X Break:", width=10).pack(side='left')
        ttk.Label(bf, text="Start:").pack(side='left', padx=(5, 2))
        ttk.Entry(bf, textvariable=self.v_x_breaks[0][0], width=10).pack(side='left', padx=2)
        ttk.Label(bf, text="End:").pack(side='left', padx=(10, 2))
        ttk.Entry(bf, textvariable=self.v_x_breaks[0][1], width=10).pack(side='left', padx=2)

        # ============================================
        # Button frame at bottom
        # ============================================
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Reset Ranges", command=self.reset_ranges, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)

    def open_labels_dialog(self):
        """Open the Labels & Titles dialog with a tabbed interface."""
        # Create dialog window
        d = tk.Toplevel(self.root)
        d.title("Labels, Titles & Colors")
        
        # Calculate size - wider for tabs
        w, h = self.get_dialog_size(0.45, 0.90, max_width=650, max_height=850, min_width=500, min_height=600)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)
        
        # Main container
        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        
        # Create notebook (tab container)
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Helper functions
        def add_entry(parent, txt, var, width=15):
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=width).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')
        
        def add_pos_entry(parent, label, x_var, y_var):
            """Add X/Y position entry pair."""
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=label, width=12).pack(side='left')
            ttk.Label(f, text="X:").pack(side='left', padx=(5, 2))
            ttk.Entry(f, textvariable=x_var, width=8).pack(side='left', padx=2)
            ttk.Label(f, text="Y:").pack(side='left', padx=(10, 2))
            ttk.Entry(f, textvariable=y_var, width=8).pack(side='left', padx=2)
        
        def add_rot_entry(parent, label, var):
            """Add rotation entry with degree symbol."""
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=label, width=15).pack(side='left')
            ttk.Entry(f, textvariable=var, width=8).pack(side='left', padx=2)
            ttk.Label(f, text="°").pack(side='left')
        
        def choose_col(attr, btn):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                setattr(self, attr, c)
                btn.config(bg=c)
                d.lift()
        
        def add_col(parent, txt, attr, default):
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=18).pack(side='left')
            b = tk.Button(f, text=" ", bg=default, width=8)
            b.config(command=lambda: choose_col(attr, b))
            b.pack(side='right')
        
        # ============================================
        # TAB 1: Text Content
        # ============================================
        tab_text = ttk.Frame(notebook, padding=10)
        notebook.add(tab_text, text="Text Content")
        
        ttk.Label(tab_text, text="Plot Labels & Title", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_text, "Plot Title:", self.v_title)
        add_entry(tab_text, "X Label:", self.v_xlabel)
        add_entry(tab_text, "Y Label:", self.v_ylabel)
        add_entry(tab_text, "Y2 Label:", self.v_y2label)
        add_entry(tab_text, "Z Label (Color):", self.v_zlabel)
        
        ttk.Separator(tab_text, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_text, text="Legend Text", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_text, "Legend (csv):", self.v_legend, width=15)
        ttk.Checkbutton(tab_text, text="Show Legend", variable=self.show_legend).pack(pady=2, anchor='w')
        
        ttk.Separator(tab_text, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_text, text="Label Spacing (Padding)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_text, "X Pad:", self.v_x_pad)
        add_entry(tab_text, "Y Pad:", self.v_y_pad)
        add_entry(tab_text, "Y Broken Offset:", self.v_y_broken_offset)
        add_entry(tab_text, "Z Pad:", self.v_z_pad)
        
        # ============================================
        # TAB 2: Colors
        # ============================================
        tab_colors = ttk.Frame(notebook, padding=10)
        notebook.add(tab_colors, text="Colors")
        
        ttk.Label(tab_colors, text="Label Colors", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_col(tab_colors, "Title Color:", "title_color", self.title_color)
        add_col(tab_colors, "X Label Color:", "xlabel_color", self.xlabel_color)
        add_col(tab_colors, "Y Label Color:", "ylabel_color", self.ylabel_color)
        add_col(tab_colors, "Z Label Color:", "zlabel_color", self.zlabel_color)
        
        ttk.Separator(tab_colors, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_colors, text="Tick Colors", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_col(tab_colors, "X Tick Color:", "xtick_color", self.xtick_color)
        add_col(tab_colors, "Y Tick Color:", "ytick_color", self.ytick_color)
        
        ttk.Separator(tab_colors, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_colors, text="Background Colors", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_col(tab_colors, "Plot Background:", "plot_bg_color", self.plot_bg_color)
        add_col(tab_colors, "Figure Background:", "fig_bg_color", self.fig_bg_color)
        
        ttk.Separator(tab_colors, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_colors, text="Legend Colors", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_col(tab_colors, "Legend Fill:", "legend_fill_color", self.legend_fill_color)
        add_col(tab_colors, "Legend Frame:", "legend_frame_color", self.legend_frame_color)
        
        # ============================================
        # TAB 3: Positions
        # ============================================
        tab_positions = ttk.Frame(notebook, padding=10)
        notebook.add(tab_positions, text="Positions")
        
        ttk.Checkbutton(tab_positions, text="Use Custom Label Positions", 
                        variable=self.use_custom_label_positions).pack(pady=5, anchor='w')
        ttk.Label(tab_positions, text="Figure coordinates: (0,0) = bottom-left, (1,1) = top-right", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 10), anchor='w')
        
        ttk.Label(tab_positions, text="Title Position", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_pos_entry(tab_positions, "Title:", self.title_x, self.title_y)
        
        ttk.Separator(tab_positions, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_positions, text="X Label Position", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_pos_entry(tab_positions, "X Label:", self.xlabel_x, self.xlabel_y)
        
        ttk.Separator(tab_positions, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_positions, text="Y Label Position", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_pos_entry(tab_positions, "Y Label:", self.ylabel_x, self.ylabel_y)
        
        ttk.Separator(tab_positions, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_positions, text="Y2 Label Position (Dual Y-Axis)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_pos_entry(tab_positions, "Y2 Label:", self.y2label_x, self.y2label_y)
        
        ttk.Separator(tab_positions, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_positions, text="Z Label Position (Color Map)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_pos_entry(tab_positions, "Z Label:", self.zlabel_x, self.zlabel_y)
        
        # ============================================
        # TAB 4: Rotation
        # ============================================
        tab_rotation = ttk.Frame(notebook, padding=10)
        notebook.add(tab_rotation, text="Rotation")
        
        ttk.Checkbutton(tab_rotation, text="Use Custom Text Rotation", 
                        variable=self.use_custom_rotation).pack(pady=5, anchor='w')
        ttk.Label(tab_rotation, text="Rotation angle in degrees (0 = horizontal, 90 = vertical)", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 10), anchor='w')
        
        ttk.Label(tab_rotation, text="Title Rotation", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_rot_entry(tab_rotation, "Title Rotation:", self.title_rotation)
        
        ttk.Separator(tab_rotation, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_rotation, text="X Label Rotation", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_rot_entry(tab_rotation, "X Label Rotation:", self.xlabel_rotation)
        
        ttk.Separator(tab_rotation, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_rotation, text="Y Label Rotation", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_rot_entry(tab_rotation, "Y Label Rotation:", self.ylabel_rotation)
        ttk.Label(tab_rotation, text="(Default: 90° = vertical, reading bottom-to-top)", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 5), anchor='w')
        
        ttk.Separator(tab_rotation, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_rotation, text="Y2 Label Rotation (Dual Y-Axis)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_rot_entry(tab_rotation, "Y2 Label Rotation:", self.y2label_rotation)
        ttk.Label(tab_rotation, text="(Default: 90° = vertical, reading bottom-to-top)", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 5), anchor='w')
        
        ttk.Separator(tab_rotation, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_rotation, text="Z Label Rotation (Color Map)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_rot_entry(tab_rotation, "Z Label Rotation:", self.zlabel_rotation)
        ttk.Label(tab_rotation, text="(Default: 90° = vertical, for colorbar label)", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 5), anchor='w')
        
        # ============================================
        # TAB 5: Legend
        # ============================================
        tab_legend = ttk.Frame(notebook, padding=10)
        notebook.add(tab_legend, text="Legend")
        
        ttk.Label(tab_legend, text="Legend Layout", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        
        # Legend columns
        col_frame = ttk.Frame(tab_legend)
        col_frame.pack(fill='x', pady=2)
        ttk.Label(col_frame, text="Legend Columns:", width=15).pack(side='left')
        col_combo = ttk.Combobox(col_frame, textvariable=self.legend_columns, 
                                  values=["1", "2", "3", "4", "5", "6", "7", "8"], width=10, state='readonly')
        col_combo.pack(side='left')
        
        # Legend position
        pos_frame = ttk.Frame(tab_legend)
        pos_frame.pack(fill='x', pady=5)
        ttk.Label(pos_frame, text="Position:", width=15).pack(side='left')
        pos_combo = ttk.Combobox(pos_frame, textvariable=self.legend_position,
                                  values=["Best", "Upper Right", "Upper Left", "Lower Right", "Lower Left",
                                          "Center Left", "Center Right", "Lower Center", "Upper Center", "Center",
                                          "Outside Right", "Outside Bottom"],
                                  width=18, state='readonly')
        pos_combo.pack(side='left')
        
        ttk.Separator(tab_legend, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_legend, text="Legend Interaction", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Checkbutton(tab_legend, text="Draggable Legend (click & drag to reposition)", 
                        variable=self.legend_draggable).pack(pady=2, anchor='w')
        
        # ============================================
        # TAB 6: Secondary X-Axis (Top Axis)
        # ============================================
        tab_sec_x = ttk.Frame(notebook, padding=10)
        notebook.add(tab_sec_x, text="Secondary X")
        
        ttk.Label(tab_sec_x, text="Secondary Top X-Axis", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Checkbutton(tab_sec_x, text="Enable Secondary Top X-Axis", 
                        variable=self.enable_secondary_x).pack(pady=5, anchor='w')
        
        ttk.Separator(tab_sec_x, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sec_x, text="Transformation Formulas", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Label(tab_sec_x, text="Use 'x' as the variable. Examples: x / 1e10, x * 4.1357e-15, 1 / x",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 5), anchor='w')
        ttk.Label(tab_sec_x, text="Supports numpy as np: np.sqrt(x), np.log10(x), x**2, etc.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 10), anchor='w')
        
        add_entry(tab_sec_x, "Transform:", self.v_sec_x_forward, width=12)
        ttk.Label(tab_sec_x, text="Inverse auto-derived for: x*K, x/K, x+K, x-K, 1/x, x**K, np.sqrt, np.log10, etc.",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(2, 5), anchor='w')
        
        ttk.Separator(tab_sec_x, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sec_x, text="Top Axis Label", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        add_entry(tab_sec_x, "Top X Label:", self.v_sec_x_label, width=15)
        
        # Label color for secondary X-axis
        add_col(tab_sec_x, "Top X Label Color:", "sec_x_label_color", self.sec_x_label_color)
        
        ttk.Separator(tab_sec_x, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_sec_x, text="Top Axis Tick Settings", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        
        f_sz = ttk.Frame(tab_sec_x)
        f_sz.pack(fill='x', pady=2)
        ttk.Label(f_sz, text="Tick Font Size:", width=15).pack(side='left')
        ttk.Entry(f_sz, textvariable=self.v_sec_x_tick_size, width=10).pack(side='left', padx=2)
        
        f_maj = ttk.Frame(tab_sec_x)
        f_maj.pack(fill='x', pady=2)
        ttk.Label(f_maj, text="Major Tick Step:", width=15).pack(side='left')
        ttk.Entry(f_maj, textvariable=self.v_sec_x_maj, width=10).pack(side='left', padx=2)
        ttk.Label(f_maj, text="(blank = auto)", font=('Arial', 8, 'italic'), foreground='gray').pack(side='left', padx=5)
        
        f_min = ttk.Frame(tab_sec_x)
        f_min.pack(fill='x', pady=2)
        ttk.Label(f_min, text="Minor Divisions:", width=15).pack(side='left')
        ttk.Entry(f_min, textvariable=self.v_sec_x_min_div, width=10).pack(side='left', padx=2)
        ttk.Label(f_min, text="(blank = auto)", font=('Arial', 8, 'italic'), foreground='gray').pack(side='left', padx=5)
        
        # ============================================
        # TAB 7: Transparency
        # ============================================
        tab_transparency = ttk.Frame(notebook, padding=10)
        notebook.add(tab_transparency, text="Transparency")
        
        ttk.Label(tab_transparency, text="Alpha Values (0.0 - 1.0)", font=('Arial', 10, 'bold')).pack(pady=5, anchor='w')
        ttk.Label(tab_transparency, text="0 = fully transparent, 1 = fully opaque", 
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 10), anchor='w')
        
        add_entry(tab_transparency, "Plot Background Alpha:", self.plot_bg_alpha)
        add_entry(tab_transparency, "Figure Background Alpha:", self.fig_bg_alpha)
        add_entry(tab_transparency, "Legend Fill Alpha:", self.legend_fill_alpha)
        
        # ============================================
        # Button frame at bottom
        # ============================================
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        
        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)

    def open_ticks_dialog(self):
        """Open the Ticks & Fonts dialog with a tabbed interface."""
        d = tk.Toplevel(self.root)
        d.title("Ticks & Fonts")
        
        w, h = self.get_dialog_size(0.45, 0.80, max_width=600, max_height=700, min_width=500, min_height=500)
        d.geometry(f"{w}x{h}")
        d.transient(self.root)
        
        main_container = ttk.Frame(d)
        main_container.pack(fill='both', expand=True)
        
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        dir_options = ["out", "in", "inout", "none"]

        # ============================================
        # TAB 1: Tick Control
        # ============================================
        tab_tick = ttk.Frame(notebook, padding=10)
        notebook.add(tab_tick, text="Tick Control")
        
        ttk.Label(tab_tick, text="Tick Step & Padding", font=('Arial', 10, 'bold')).pack(pady=5)

        gf = ttk.Frame(tab_tick)
        gf.pack(fill='x')
        ttk.Label(gf, text="Axis", width=8, font=('Arial', 10, 'bold')).grid(row=0, column=0)
        ttk.Label(gf, text="Maj Step", width=10, font=('Arial', 10, 'bold')).grid(row=0, column=1)
        ttk.Label(gf, text="Min Divs", width=10, font=('Arial', 10, 'bold')).grid(row=0, column=2)
        ttk.Label(gf, text="Pad", width=10, font=('Arial', 10, 'bold')).grid(row=0, column=3)

        def add_t_row(txt, v_maj, v_min, v_pad, r):
            ttk.Label(gf, text=txt).grid(row=r, column=0)
            ttk.Entry(gf, textvariable=v_maj, width=10).grid(row=r, column=1, padx=2)
            ttk.Entry(gf, textvariable=v_min, width=10).grid(row=r, column=2, padx=2)
            ttk.Entry(gf, textvariable=v_pad, width=10).grid(row=r, column=3, padx=2)

        add_t_row("X", self.v_x_maj, self.v_x_min_div, self.v_x_tick_pad, 1)
        add_t_row("Y1 (Left)", self.v_y1_maj, self.v_y1_min_div, self.v_y1_pad, 2)
        add_t_row("Y2 (Right)", self.v_y2_maj, self.v_y2_min_div, self.v_y2_pad, 3)
        add_t_row("Z (Color)", self.v_z_maj, self.v_z_min_div, self.v_z_tick_pad, 4)

        ttk.Separator(tab_tick, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_tick, text="Notation", font=('Arial', 10, 'bold')).pack(pady=5)
        f_not = ttk.Frame(tab_tick)
        f_not.pack(fill='x')
        ttk.Label(f_not, text="X Notation:").pack(side='left')
        ttk.Combobox(f_not, textvariable=self.v_x_not, values=["Scientific", "Plain", "Engineering"], width=15,
                      state='readonly').pack(side='left', padx=5)
        ttk.Label(f_not, text="Y Notation:").pack(side='left')
        ttk.Combobox(f_not, textvariable=self.v_y_not, values=["Scientific", "Plain", "Engineering"], width=15,
                      state='readonly').pack(side='left', padx=5)

        # ============================================
        # TAB 2: Font Settings
        # ============================================
        tab_font = ttk.Frame(notebook, padding=10)
        notebook.add(tab_font, text="Font Settings")

        ttk.Label(tab_font, text="Font Settings", font=('Arial', 10, 'bold')).pack(pady=5)
        ttk.Label(tab_font, text="(Type in the font dropdown to search/filter fonts)",
                  font=('Arial', 8, 'italic'), foreground='gray').pack(pady=(0, 5))

        f_fam = ttk.Frame(tab_font)
        f_fam.pack(fill='x', pady=2)
        ttk.Label(f_fam, text="Font Family:").pack(side='left')
        from matplotlib.font_manager import fontManager
        available_fonts = sorted(set([f.name for f in fontManager.ttflist]))
        font_combo = ttk.Combobox(f_fam, textvariable=self.v_font_fam,
                                   values=available_fonts, width=25)
        font_combo.pack(side='right')
        self._setup_autocomplete_combobox(font_combo, available_fonts, d)

        def add_sz(parent, txt, var):
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt).pack(side='left')
            ttk.Entry(f, textvariable=var, width=10).pack(side='right')

        add_sz(tab_font, "Title Size:", self.v_t_size)
        add_sz(tab_font, "Axis Label Size:", self.v_l_size)
        add_sz(tab_font, "Legend Size:", self.v_leg_size)
        add_sz(tab_font, "X Tick Size:", self.v_xtick_size)
        add_sz(tab_font, "Y Tick Size:", self.v_ytick_size)

        # ============================================
        # TAB 3: Tick Appearance
        # ============================================
        tab_appear = ttk.Frame(notebook, padding=10)
        notebook.add(tab_appear, text="Tick Appearance")

        ttk.Label(tab_appear, text="Major Tick Direction:", font=('Arial', 9, 'bold')).pack(anchor='w', pady=(5, 2))
        dir_frame = ttk.Frame(tab_appear)
        dir_frame.pack(fill='x', pady=2)
        ttk.Label(dir_frame, text="X:", width=8).grid(row=0, column=0)
        ttk.Combobox(dir_frame, textvariable=self.v_tick_dir_x, values=dir_options, width=8, state='readonly').grid(row=0, column=1, padx=2)
        ttk.Label(dir_frame, text="Y:", width=8).grid(row=0, column=2)
        ttk.Combobox(dir_frame, textvariable=self.v_tick_dir_y, values=dir_options, width=8, state='readonly').grid(row=0, column=3, padx=2)
        ttk.Label(dir_frame, text="Y2:", width=8).grid(row=1, column=0)
        ttk.Combobox(dir_frame, textvariable=self.v_tick_dir_y2, values=dir_options, width=8, state='readonly').grid(row=1, column=1, padx=2)
        ttk.Label(dir_frame, text="Z:", width=8).grid(row=1, column=2)
        ttk.Combobox(dir_frame, textvariable=self.v_tick_dir_z, values=dir_options, width=8, state='readonly').grid(row=1, column=3, padx=2)

        ttk.Label(tab_appear, text="Minor Tick Direction:", font=('Arial', 9, 'bold')).pack(anchor='w', pady=(10, 2))
        mdir_frame = ttk.Frame(tab_appear)
        mdir_frame.pack(fill='x', pady=2)
        ttk.Label(mdir_frame, text="X:", width=8).grid(row=0, column=0)
        ttk.Combobox(mdir_frame, textvariable=self.v_minor_tick_dir_x, values=dir_options, width=8, state='readonly').grid(row=0, column=1, padx=2)
        ttk.Label(mdir_frame, text="Y:", width=8).grid(row=0, column=2)
        ttk.Combobox(mdir_frame, textvariable=self.v_minor_tick_dir_y, values=dir_options, width=8, state='readonly').grid(row=0, column=3, padx=2)
        ttk.Label(mdir_frame, text="Y2:", width=8).grid(row=1, column=0)
        ttk.Combobox(mdir_frame, textvariable=self.v_minor_tick_dir_y2, values=dir_options, width=8, state='readonly').grid(row=1, column=1, padx=2)
        ttk.Label(mdir_frame, text="Z:", width=8).grid(row=1, column=2)
        ttk.Combobox(mdir_frame, textvariable=self.v_minor_tick_dir_z, values=dir_options, width=8, state='readonly').grid(row=1, column=3, padx=2)

        ttk.Label(tab_appear, text="Tick Length (points):", font=('Arial', 9, 'bold')).pack(anchor='w', pady=(10, 2))
        len_frame = ttk.Frame(tab_appear)
        len_frame.pack(fill='x', pady=2)
        ttk.Label(len_frame, text="Major:", width=8).pack(side='left')
        ttk.Entry(len_frame, textvariable=self.v_major_tick_length, width=8).pack(side='left', padx=2)
        ttk.Label(len_frame, text="Minor:", width=8).pack(side='left', padx=(10, 0))
        ttk.Entry(len_frame, textvariable=self.v_minor_tick_length, width=8).pack(side='left', padx=2)

        ttk.Separator(tab_appear, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_appear, text="Tick Visibility per Side", font=('Arial', 10, 'bold')).pack(pady=5)
        side_frame = ttk.Frame(tab_appear)
        side_frame.pack(fill='x', pady=2)
        ttk.Label(side_frame, text="X Axis:", width=8, font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(side_frame, text="Bottom", variable=self.v_x_tick_bottom).grid(row=0, column=1, padx=5)
        ttk.Checkbutton(side_frame, text="Top", variable=self.v_x_tick_top).grid(row=0, column=2, padx=5)
        ttk.Label(side_frame, text="Y Axis:", width=8, font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky='w')
        ttk.Checkbutton(side_frame, text="Left", variable=self.v_y_tick_left).grid(row=1, column=1, padx=5)
        ttk.Checkbutton(side_frame, text="Right", variable=self.v_y_tick_right).grid(row=1, column=2, padx=5)

        # ============================================
        # TAB 4: Grid Settings
        # ============================================
        tab_grid = ttk.Frame(notebook, padding=10)
        notebook.add(tab_grid, text="Grid Settings")

        ttk.Label(tab_grid, text="Grid Visibility", font=('Arial', 10, 'bold')).pack(pady=5)
        grid_frame = ttk.Frame(tab_grid)
        grid_frame.pack(fill='x', pady=2)
        ttk.Checkbutton(grid_frame, text="Major Grid", variable=self.show_major_grid).grid(row=0, column=0, sticky='w', padx=5)
        ttk.Checkbutton(grid_frame, text="Minor Grid", variable=self.show_minor_grid).grid(row=0, column=1, sticky='w', padx=5)

        ttk.Separator(tab_grid, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(tab_grid, text="Grid Style", font=('Arial', 10, 'bold')).pack(pady=5)

        def add_grid_entry(parent, txt, var):
            f = ttk.Frame(parent)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=15).pack(side='left')
            ttk.Entry(f, textvariable=var, width=8).pack(side='left', padx=2)

        add_grid_entry(tab_grid, "Grid Alpha:", self.v_grid_alpha)
        add_grid_entry(tab_grid, "Grid Width:", self.v_grid_linewidth)

        g_ls_frame = ttk.Frame(tab_grid)
        g_ls_frame.pack(fill='x', pady=2)
        ttk.Label(g_ls_frame, text="Grid Style:", width=15).pack(side='left')
        ttk.Combobox(g_ls_frame, textvariable=self.v_grid_linestyle,
                     values=['-', '--', ':', '-.'], width=8, state='readonly').pack(side='left', padx=2)

        # ============================================
        # Button frame at bottom
        # ============================================
        btn_container = ttk.Frame(main_container)
        btn_container.pack(side='bottom', fill='x', pady=10, padx=10)
        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)

    # --- MAIN LOGIC ---

    def _load_csv(self, filepath):
        """Load a CSV file with header detection and footer skipping."""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        header_line = 0
        for i, line in enumerate(lines[:50]):
            if 'time(s)' in line.lower(): header_line = i; break

        skip_footer = 0
        header_cols = len(lines[header_line].split(','))
        for i in range(len(lines) - 1, header_line, -1):
            line = lines[i].strip()
            if not line: skip_footer += 1; continue
            if line.startswith(';') or line.startswith('#'): skip_footer += 1; continue
            if len(line.split(',')) != header_cols: skip_footer += 1; continue
            break

        if skip_footer > 0:
            return pl.read_csv(filepath, skip_rows=header_line,
                               n_rows=len(lines) - header_line - skip_footer,
                               truncate_ragged_lines=True, ignore_errors=True)
        else:
            return pl.read_csv(filepath, skip_rows=header_line,
                               truncate_ragged_lines=True, ignore_errors=True)

    def _load_excel(self, filepath):
        """Load an Excel file (.xlsx/.xls). Requires openpyxl."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("Excel support requires 'openpyxl'.\nInstall it with:  pip install openpyxl")
        return pl.read_excel(filepath)

    def load_files(self):
        """Open the File Loading Wizard for multi-folder file selection."""
        self.open_load_wizard()

    def open_load_wizard(self):
        """Open a File Loading Wizard that allows selecting files from multiple folders."""
        w, h = self.get_dialog_size(0.55, 0.75, max_width=800, max_height=650, min_width=550, min_height=450)
        
        wizard = tk.Toplevel(self.root)
        wizard.title("File Loading Wizard")
        wizard.geometry(f"{w}x{h}")
        wizard.transient(self.root)
        
        # Queue of file paths to load
        file_queue = []
        
        # --- TOP FRAME: Instructions ---
        top_frame = ttk.Frame(wizard, padding=(10, 10, 10, 5))
        top_frame.pack(fill='x')
        ttk.Label(top_frame, text="Add files from multiple folders, then click 'Load All' to import them.",
                  font=('Arial', 10, 'italic'), foreground='gray').pack(anchor='w')
        
        # --- MIDDLE FRAME: Listbox with file queue ---
        list_frame = ttk.Frame(wizard, padding=(10, 5, 10, 5))
        list_frame.pack(fill='both', expand=True)
        
        # Columns: # | Filename | Folder Path
        cols = ("#", "Filename", "Folder")
        tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='extended')
        tree.heading("#", text="#")
        tree.heading("Filename", text="Filename")
        tree.heading("Folder", text="Folder Path")
        tree.column("#", width=40, anchor='center', stretch=False)
        tree.column("Filename", width=200, minwidth=120)
        tree.column("Folder", width=350, minwidth=200)
        
        tree_sb = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=tree_sb.set)
        tree.pack(side='left', fill='both', expand=True)
        tree_sb.pack(side='right', fill='y')
        
        # --- INFO LABEL ---
        info_var = tk.StringVar(value="No files queued.")
        info_label = ttk.Label(wizard, textvariable=info_var, font=('Arial', 9), foreground='gray')
        info_label.pack(fill='x', padx=10, pady=(0, 5))
        
        def refresh_tree():
            """Refresh the treeview with current file_queue."""
            tree.delete(*tree.get_children())
            for i, fpath in enumerate(file_queue):
                fname = os.path.basename(fpath)
                folder = os.path.dirname(fpath)
                tree.insert('', 'end', values=(i + 1, fname, folder))
            info_var.set(f"{len(file_queue)} file(s) queued.")
        
        def add_files():
            """Open file dialog to add files (can be called multiple times from different folders)."""
            new_files = filedialog.askopenfilenames(
                parent=wizard,
                title="Select data file(s) from any folder",
                filetypes=[("Data files", "*.csv *.xlsx *.xls"),
                           ("CSV files", "*.csv"),
                           ("Excel files", "*.xlsx *.xls"),
                           ("All files", "*.*")])
            if new_files:
                # Avoid duplicates
                existing = set(file_queue)
                for f in new_files:
                    if f not in existing:
                        file_queue.append(f)
                        existing.add(f)
                refresh_tree()
        
        def add_folder():
            """Select a folder and add all CSV/Excel files from it."""
            folder = filedialog.askdirectory(parent=wizard, title="Select folder with data files")
            if not folder:
                return
            valid_ext = {'.csv', '.xlsx', '.xls'}
            existing = set(file_queue)
            count = 0
            for fname in os.listdir(folder):
                ext = os.path.splitext(fname)[1].lower()
                if ext in valid_ext:
                    full_path = os.path.join(folder, fname)
                    if full_path not in existing:
                        file_queue.append(full_path)
                        existing.add(full_path)
                        count += 1
            refresh_tree()
            if count == 0:
                messagebox.showinfo("No Files Found", f"No CSV or Excel files found in:\n{folder}", parent=wizard)
        
        def remove_selected():
            """Remove selected files from the queue."""
            sel = tree.selection()
            if not sel:
                return
            # Get indices of selected items (sorted descending to remove safely)
            indices = sorted([tree.index(item) for item in sel], reverse=True)
            for idx in indices:
                if 0 <= idx < len(file_queue):
                    file_queue.pop(idx)
            refresh_tree()
        
        def clear_all():
            """Clear the entire file queue."""
            file_queue.clear()
            refresh_tree()
        
        def load_all():
            """Load all queued files into the plotter."""
            if not file_queue:
                messagebox.showinfo("No Files", "No files queued to load. Add files first.", parent=wizard)
                return
            wizard.destroy()
            self._load_files_from_list(file_queue)
        
        def load_selected_only():
            """Load only the selected files from the queue."""
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("No Selection", "Select files in the queue to load.", parent=wizard)
                return
            indices = sorted([tree.index(item) for item in sel])
            selected_paths = [file_queue[i] for i in indices if i < len(file_queue)]
            wizard.destroy()
            self._load_files_from_list(selected_paths)
        
        # --- BUTTON FRAME ---
        btn_frame = ttk.Frame(wizard, padding=(10, 5, 10, 10))
        btn_frame.pack(fill='x')
        
        # Row 1: Add/Remove buttons
        row1 = ttk.Frame(btn_frame)
        row1.pack(fill='x', pady=(0, 5))
        ttk.Button(row1, text="📁 Add Files", command=add_files, width=14).pack(side='left', padx=2)
        ttk.Button(row1, text="📂 Add Folder", command=add_folder, width=14).pack(side='left', padx=2)
        ttk.Button(row1, text="Remove Selected", command=remove_selected, width=16).pack(side='left', padx=2)
        ttk.Button(row1, text="Clear All", command=clear_all, width=10).pack(side='left', padx=2)
        
        # Row 2: Load/Cancel buttons
        row2 = ttk.Frame(btn_frame)
        row2.pack(fill='x')
        ttk.Button(row2, text="Load All", command=load_all, width=14).pack(side='left', padx=2, expand=True, fill='x')
        ttk.Button(row2, text="Load Selected Only", command=load_selected_only, width=16).pack(side='left', padx=2, expand=True, fill='x')
        ttk.Button(row2, text="Cancel", command=wizard.destroy, width=10).pack(side='left', padx=2, expand=True, fill='x')
        
        # Enable mousewheel scrolling on the tree
        def on_mousewheel(event):
            tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        tree.bind("<MouseWheel>", on_mousewheel)
        wizard.protocol("WM_DELETE_WINDOW", lambda: (tree.unbind("<MouseWheel>"), wizard.destroy()))

    def _load_files_from_list(self, filepaths):
        """Load a list of file paths into the datasets dictionary."""
        if not filepaths:
            return
        errors = []
        for filepath in filepaths:
            try:
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ('.xlsx', '.xls'):
                    df = self._load_excel(filepath)
                else:
                    df = self._load_csv(filepath)
                filename = os.path.basename(filepath)
                self.datasets[filename] = df
            except Exception as e:
                errors.append(f"{os.path.basename(filepath)}: {e}")
        if errors:
            messagebox.showerror("Load Errors", "Errors loading files:\n\n" + "\n".join(errors))
        self.refresh_dataset_list(new_load=True)

    def unload_files(self):
        sel = self.dataset_listbox.curselection()
        if not sel: return
        keys = [self.dataset_listbox.get(i) for i in sel]
        for k in keys:
            if k in self.datasets: del self.datasets[k]
        self.refresh_dataset_list(new_load=False)
        self.update_plot()

    def refresh_dataset_list(self, new_load=False):
        self.dataset_listbox.delete(0, tk.END)
        keys = list(self.datasets.keys())
        for k in keys: self.dataset_listbox.insert(tk.END, k)
        self.axis_ref_combo['values'] = keys
        if keys:
            if new_load and not self.dataset_listbox.curselection(): self.dataset_listbox.selection_set(0)
            if self.axis_ref_combo.get() not in keys: self.axis_ref_combo.current(0)
            self.populate_column_selectors(None)
        else:
            self.axis_ref_combo.set('');
            self.x_combo.set('');
            self.y_listbox.delete(0, tk.END)
            self.current_dataset_key = None;
            self.fig.clear();
            self.ax = self.fig.add_subplot(111);
            self.canvas.draw()

    def on_dataset_selection_change(self, event):
        self.update_plot()

    def on_axis_ref_change(self, event):
        self.populate_column_selectors(event)

    def populate_column_selectors(self, event):
        columns = []
        if self.merge_cols_var.get():
            unique_cols = set()
            for df in self.datasets.values(): unique_cols.update(df.columns)
            columns = sorted(list(unique_cols))
            if self.datasets: self.current_dataset_key = list(self.datasets.keys())[0]
        else:
            key = self.axis_ref_combo.get()
            if key in self.datasets:
                self.current_dataset_key = key;
                columns = self.datasets[key].columns
        self.x_combo['values'] = columns;
        self.z_combo['values'] = columns;
        self.y_listbox.delete(0, tk.END)
        for c in columns: self.y_listbox.insert(tk.END, c)
        self.y1_combo['values'] = columns;
        self.y2_combo['values'] = columns
        if columns:
            self.y1_combo.current(0)
            if len(columns) > 1:
                self.y2_combo.current(1)
            else:
                self.y2_combo.current(0)
            if self.x_combo.get() not in columns: self.x_combo.set(columns[0])
            if not self.y_listbox.curselection():
                idx = 1 if len(columns) > 1 else 0
                self.y_listbox.selection_set(idx)
        else:
            self.x_combo.set('')

    def on_plot_type_change(self, event):
        ptype = self.plot_type.get()
        if ptype == "Dual Y-Axis":
            self.y_list_frame.pack_forget();
            self.y_dual_frame.pack(fill='both', expand=True)
        else:
            self.y_dual_frame.pack_forget();
            self.y_list_frame.pack(fill='both', expand=True)
        self.update_plot()

    def get_selected_datasets(self):
        idxs = self.dataset_listbox.curselection()
        keys = [self.dataset_listbox.get(i) for i in idxs]
        return [(k, self.datasets[k]) for k in keys]

    def open_style_dialog(self):
        sel_ds = self.get_selected_datasets()
        ptype = self.plot_type.get()
        if not sel_ds: return messagebox.showinfo("Info", "Select data first.")
        pairs_to_style = []
        if ptype == "Dual Y-Axis":
            y1, y2 = self.y1_combo.get(), self.y2_combo.get()
            if len(sel_ds) > 1:
                if y1: pairs_to_style.append((sel_ds[0][0], y1))
                if y2: pairs_to_style.append((sel_ds[1][0], y2))
            elif len(sel_ds) == 1:
                if y1: pairs_to_style.append((sel_ds[0][0], y1))
                if y2: pairs_to_style.append((sel_ds[0][0], y2))
        else:
            y_idxs = self.y_listbox.curselection()
            y_cols = [self.y_listbox.get(i) for i in y_idxs]
            for fk, _ in sel_ds:
                for yc in y_cols: pairs_to_style.append((fk, yc))
        if not pairs_to_style: return messagebox.showinfo("Info", "Select Y axes first.")

        # Use create_scrollable_dialog for consistent structure with wider window
        d, fr, cv, main_container, btn_container = self.create_scrollable_dialog(
            self.root, "Style Config",
            width_pct=0.60, height_pct=0.75, max_width=1000, max_height=650, min_width=700, min_height=300
        )

        ttk.Label(fr, text="Series").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(fr, text="Color").grid(row=0, column=1, padx=5, pady=5, columnspan=2)
        ttk.Label(fr, text="Width").grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(fr, text="Type").grid(row=0, column=4, padx=5, pady=5)
        ttk.Label(fr, text="Legend").grid(row=0, column=5, padx=5, pady=5)
        ttk.Label(fr, text="In Leg.").grid(row=0, column=6, padx=5, pady=5)
        r = 1

        def pick_c(btn, k, default_color):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                if k not in self.styles: self.styles[k] = {}
                self.styles[k]['color'] = c;
                btn.config(bg=c);
                d.lift()

        def reset_c(btn, k):
            """Reset color to default (remove custom color from styles)."""
            if k in self.styles and 'color' in self.styles[k]:
                del self.styles[k]['color']
                # If styles dict is now empty, remove it
                if not self.styles[k]:
                    del self.styles[k]
            # Update button to show default state (gray placeholder)
            btn.config(bg='#d3d3d3')

        def up_w(v, k):
            if k not in self.styles: self.styles[k] = {}
            try:
                self.styles[k]['width'] = float(v)
            except:
                pass

        def up_ls(v, k):
            if k not in self.styles: self.styles[k] = {}
            self.styles[k]['linestyle'] = v

        def up_leg(v, k):
            if k not in self.styles: self.styles[k] = {}
            self.styles[k]['legend'] = v.get()

        def up_show_leg(var, k):
            """Update show_in_legend setting."""
            if k not in self.styles: self.styles[k] = {}
            self.styles[k]['show_in_legend'] = var.get()

        for fk, yc in pairs_to_style:
            k = (fk, yc);
            st = self.styles.get(k, {})
            # Show gray placeholder if no custom color is set
            has_custom_color = 'color' in st
            c = st.get('color', '#d3d3d3')
            w = st.get('width', 2.0);
            ls = st.get('linestyle', '-')
            show_in_leg = st.get('show_in_legend', True)
            
            ttk.Label(fr, text=f"{fk}\n{yc}").grid(row=r, column=0, padx=5, sticky='w')
            
            # Color button frame with color picker and reset button
            color_frame = ttk.Frame(fr)
            color_frame.grid(row=r, column=1, columnspan=2, padx=2)
            
            btn = tk.Button(color_frame, text=" ", bg=c, width=4)
            btn.config(command=lambda b=btn, k=k, dc=c: pick_c(b, k, dc))
            btn.pack(side='left', padx=1)
            
            # Reset button
            reset_btn = ttk.Button(color_frame, text="Reset", width=5)
            reset_btn.config(command=lambda b=btn, k=k: reset_c(b, k))
            reset_btn.pack(side='left', padx=1)
            
            wv = tk.StringVar(value=str(w))
            wv.trace("w", lambda n, i, m, v=wv, k=k: up_w(v.get(), k))
            ttk.Entry(fr, textvariable=wv, width=6).grid(row=r, column=3)
            lsb = ttk.Combobox(fr, values=['-', '--', '-.', ':', 'None'], width=5, state='readonly')
            lsb.set(ls);
            lsb.bind("<<ComboboxSelected>>", lambda e, b=lsb, k=k: up_ls(b.get(), k))
            lsb.grid(row=r, column=4);
            # Legend entry field
            leg_val = tk.StringVar(value=st.get('legend', ''))
            leg_entry = ttk.Entry(fr, textvariable=leg_val, width=15)
            leg_entry.grid(row=r, column=5, padx=5)
            leg_val.trace("w", lambda n, i, m, v=leg_val, k=k: up_leg(v, k))
            
            # Show in legend checkbox
            show_leg_var = tk.BooleanVar(value=show_in_leg)
            show_leg_cb = ttk.Checkbutton(fr, variable=show_leg_var, width=3)
            show_leg_cb.grid(row=r, column=6, padx=5)
            show_leg_var.trace("w", lambda n, i, m, v=show_leg_var, k=k: up_show_leg(v, k))
            
            r += 1
        
        # Add buttons to the fixed button container (outside scrollable area)
        btn_width = 12
        ttk.Button(btn_container, text="Update Plot", command=self.update_plot, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="OK", command=lambda: [self.update_plot(), d.destroy()], width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_container, text="Cancel", command=d.destroy, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)

    def open_legend_order_dialog(self):
        """Open dialog to adjust legend order."""
        sel_ds = self.get_selected_datasets()
        ptype = self.plot_type.get()
        if not sel_ds: 
            return messagebox.showinfo("Info", "Select data first.")
        
        # Build list of series keys (same logic as update_plot)
        pairs_to_order = []
        if ptype == "Dual Y-Axis":
            y1, y2 = self.y1_combo.get(), self.y2_combo.get()
            if len(sel_ds) > 1:
                if y1: pairs_to_order.append((sel_ds[0][0], y1))
                if y2: pairs_to_order.append((sel_ds[1][0], y2))
            elif len(sel_ds) == 1:
                if y1: pairs_to_order.append((sel_ds[0][0], y1))
                if y2: pairs_to_order.append((sel_ds[0][0], y2))
        else:
            y_idxs = self.y_listbox.curselection()
            y_cols = [self.y_listbox.get(i) for i in y_idxs]
            for fk, _ in sel_ds:
                for yc in y_cols:
                    pairs_to_order.append((fk, yc))
        
        if not pairs_to_order:
            return messagebox.showinfo("Info", "Select Y axes first.")
        
        # If legend_order is set and has valid items, use it; otherwise use default order
        # Filter legend_order to only include items that are currently in pairs_to_order
        current_order = []
        for item in self.legend_order:
            if item in pairs_to_order and item not in current_order:
                current_order.append(item)
        # Add any new items that weren't in legend_order
        for item in pairs_to_order:
            if item not in current_order:
                current_order.append(item)
        
        # Create dialog with dynamic sizing - ensure minimum width of 450 for buttons
        w, h = self.get_dialog_size(0.35, 0.70, max_width=500, max_height=500, min_width=450, min_height=350)
        
        d = tk.Toplevel(self.root)
        d.title("Legend Order")
        d.geometry(f"{w}x{h}")
        d.transient(self.root)
        frame = ttk.Frame(d, padding=10)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="Adjust the order of legend entries.\nTop item appears first in legend.", 
                  font=('Arial', 10)).pack(pady=(0, 10))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        listbox = tk.Listbox(list_frame, yscrollcommand=sb.set, selectmode='single', height=10)
        sb.config(command=listbox.yview)
        listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        
        # Populate listbox - show legend name if available, otherwise show key
        def get_display_text(key):
            st = self.styles.get(key, {})
            leg = st.get('legend', '').strip()
            if leg:
                return f"{leg} ({key[0]}: {key[1]})"
            return f"{key[0]}: {key[1]}"
        
        def refresh_listbox():
            listbox.delete(0, tk.END)
            for key in current_order:
                listbox.insert(tk.END, get_display_text(key))
        
        refresh_listbox()
        
        # Movement functions
        def move_up():
            sel_idx = listbox.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            if idx > 0:
                # Swap in current_order
                current_order[idx], current_order[idx-1] = current_order[idx-1], current_order[idx]
                refresh_listbox()
                listbox.selection_set(idx - 1)
        
        def move_down():
            sel_idx = listbox.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            if idx < len(current_order) - 1:
                # Swap in current_order
                current_order[idx], current_order[idx+1] = current_order[idx+1], current_order[idx]
                refresh_listbox()
                listbox.selection_set(idx + 1)
        
        def move_to_top():
            sel_idx = listbox.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            if idx > 0:
                item = current_order.pop(idx)
                current_order.insert(0, item)
                refresh_listbox()
                listbox.selection_set(0)
        
        def move_to_bottom():
            sel_idx = listbox.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            if idx < len(current_order) - 1:
                item = current_order.pop(idx)
                current_order.append(item)
                refresh_listbox()
                listbox.selection_set(len(current_order) - 1)
        
        def reset_order():
            nonlocal current_order
            current_order = pairs_to_order.copy()
            refresh_listbox()
        
        # Button frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        
        ttk.Button(btn_frame, text="↑ Top", command=move_to_top, width=8).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="↑ Up", command=move_up, width=8).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="↓ Down", command=move_down, width=8).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="↓ Bottom", command=move_to_bottom, width=8).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Reset", command=reset_order, width=8).pack(side='right', padx=2)
        
        # Standardized button frame at bottom
        def apply_order(close_dialog=True):
            """Apply the current order and optionally close the dialog."""
            # Merge current_order with existing legend_order
            # Preserve existing order for items not in current selection
            # Update order for items in current selection (keeping their relative positions)
            new_order = []
            added_keys = set()
            
            # First, preserve items from existing legend_order that aren't in current selection
            for key in self.legend_order:
                if key not in pairs_to_order:
                    new_order.append(key)
                    added_keys.add(key)
            
            # Then, add items from current_order (which has the user's desired order for current selection)
            for key in current_order:
                if key not in added_keys:
                    new_order.append(key)
                    added_keys.add(key)
            
            self.legend_order = new_order
            self.update_plot()
            if close_dialog:
                d.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        # Use fixed width buttons to prevent overflow
        btn_width = 12
        ttk.Button(btn_frame, text="Update Plot", command=lambda: apply_order(close_dialog=False), width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_frame, text="OK", command=lambda: apply_order(close_dialog=True), width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)
        ttk.Button(btn_frame, text="Cancel", command=d.destroy, width=btn_width).pack(
            side='left', expand=True, fill='x', padx=2)

    @staticmethod
    def _auto_derive_inverse(formula_str):
        """Auto-derive the inverse of common transform formulas.
        
        Returns the inverse formula string, or None if pattern not recognized.
        """
        import re
        s = formula_str.strip()
        
        # Pattern: x * K or x*K → x / K
        m = re.match(r'^x\s*\*\s*(.+)$', s)
        if m:
            return f"x / {m.group(1)}"
        
        # Pattern: x / K or x/K → x * K
        m = re.match(r'^x\s*/\s*(.+)$', s)
        if m:
            return f"x * {m.group(1)}"
        
        # Pattern: x + K → x - K
        m = re.match(r'^x\s*\+\s*(.+)$', s)
        if m:
            return f"x - {m.group(1)}"
        
        # Pattern: x - K → x + K
        m = re.match(r'^x\s*-\s*(.+)$', s)
        if m:
            return f"x + {m.group(1)}"
        
        # Pattern: 1 / x → 1 / x (self-inverse)
        if s.strip() in ['1/x', '1 / x']:
            return '1 / x'
        
        # Pattern: K / x or K*x → swap (K*x → x/K, K/x → x/K ... actually these are trickier)
        # Pattern: K * x → x / K
        m = re.match(r'^(.+?)\s*\*\s*x$', s)
        if m:
            return f"x / {m.group(1)}"
        
        # Pattern: K / x → K / x (needs special handling — for now, not auto-inverted)
        
        # Pattern: x ** K → x ** (1/K)
        m = re.match(r'^x\s*\*\*\s*(.+)$', s)
        if m:
            try:
                k = float(m.group(1))
                inv_k = 1.0 / k
                # Use clean representation
                if inv_k == int(inv_k):
                    inv_k = int(inv_k)
                return f"x ** {inv_k}"
            except:
                pass
        
        # Pattern: np.sqrt(x) → x ** 2
        if s.strip() in ['np.sqrt(x)', 'np.sqrt( x )']:
            return 'x ** 2'
        
        # Pattern: np.log10(x) → 10 ** x
        if s.strip() in ['np.log10(x)', 'np.log10( x )']:
            return '10 ** x'
        
        # Pattern: np.log(x) → np.exp(x)
        if s.strip() in ['np.log(x)', 'np.log( x )']:
            return 'np.exp(x)'
        
        # Pattern: np.exp(x) → np.log(x)
        if s.strip() in ['np.exp(x)', 'np.exp( x )']:
            return 'np.log(x)'
        
        # Not recognized
        return None

    # --- AXIS BREAK HELPERS ---

    @staticmethod
    def _parse_breaks(break_list):
        """Parse a list of (start_var, end_var) tuples into sorted (start, end) pairs.
        Returns list of (start, end) tuples sorted by start, with gaps > 0."""
        breaks = []
        for s_var, e_var in break_list:
            try:
                s = float(s_var.get())
                e = float(e_var.get())
                if s < e:
                    breaks.append((s, e))
            except (ValueError, TypeError):
                pass
        breaks.sort(key=lambda x: x[0])
        # Merge overlapping breaks
        merged = []
        for s, e in breaks:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        return merged

    @staticmethod
    def _transform_data(data, breaks):
        """Transform data by subtracting cumulative break gaps.
        
        Args:
            data: numpy array of values
            breaks: sorted list of (start, end) tuples
            
        Returns:
            Transformed data array where gaps are collapsed.
            Points inside breaks are set to NaN so they are NOT drawn.
        """
        result = data.astype(float).copy()
        for s, e in breaks:
            gap = e - s
            # Use ORIGINAL data for masks to avoid incorrectly NaN'ing shifted values
            inside_original = (data >= s) & (data <= e)
            above_original = data > e
            result[inside_original] = np.nan
            result[above_original] -= gap
        return result

    @staticmethod
    def _make_break_formatter(original_breaks):
        """Create a FuncFormatter that maps display values back to original values.
        
        The formatter reverses the break transformation for tick labels.
        """
        def formatter(x, pos):
            val = x
            # Reverse: add back gaps for each break
            for s, e in original_breaks:
                gap = e - s
                if val >= s:
                    val += gap
                # Handle points that were clipped to break start
            return f'{val:.4g}'
        return formatter

    @staticmethod
    def _draw_break_indicators(ax, breaks, axis='y'):
        """Draw Origin-style axis break marks — two small diagonal slashes on the spine."""
        for s_disp, e_disp in breaks:
            mid = (s_disp + e_disp) / 2.0
            if axis == 'y':
                span = abs(ax.get_ylim()[1] - ax.get_ylim()[0]) or 1.0
                d = span * 0.01  # half-height of slash
                offset = span * 0.005  # vertical offset between the two slashes
                # Draw two parallel slashes on left and right spine
                for sx in [0.0, 1.0]:
                    for dy in [-offset, offset]:
                        ax.plot([sx - 0.010, sx + 0.010], [mid + dy - d, mid + dy + d],
                                transform=ax.get_yaxis_transform(),
                                color='k', clip_on=False, linewidth=0.8, zorder=10)
            else:
                span = abs(ax.get_xlim()[1] - ax.get_xlim()[0]) or 1.0
                d = span * 0.01
                offset = span * 0.005
                for sy in [0.0, 1.0]:
                    for dx in [-offset, offset]:
                        ax.plot([mid + dx - d, mid + dx + d], [sy - 0.010, sy + 0.010],
                                transform=ax.get_xaxis_transform(),
                                color='k', clip_on=False, linewidth=0.8, zorder=10)

    def update_plot(self):
        sel_ds = self.get_selected_datasets()
        if not sel_ds or self.current_dataset_key is None: return
        self.fig.clear()

        def val(var, default=None, type_fn=float):
            try:
                return type_fn(var.get())
            except:
                return default
        
        # Get custom label positions if enabled
        use_custom_pos = self.use_custom_label_positions.get()
        custom_title_pos = (0.5, 0.98)
        custom_xlabel_pos = (0.5, 0.04)
        custom_ylabel_pos = (0.04, 0.5)
        custom_y2label_pos = (0.96, 0.5)
        custom_zlabel_pos = (0.96, 0.5)
        
        if use_custom_pos:
            try:
                custom_title_pos = (val(self.title_x, 0.5), val(self.title_y, 0.98))
                custom_xlabel_pos = (val(self.xlabel_x, 0.5), val(self.xlabel_y, 0.04))
                custom_ylabel_pos = (val(self.ylabel_x, 0.04), val(self.ylabel_y, 0.5))
                custom_y2label_pos = (val(self.y2label_x, 0.96), val(self.y2label_y, 0.5))
                custom_zlabel_pos = (val(self.zlabel_x, 0.96), val(self.zlabel_y, 0.5))
            except Exception as e:
                print(f"Error parsing custom positions: {e}")
                use_custom_pos = False
        
         # Get custom rotation settings if enabled
        use_custom_rot = self.use_custom_rotation.get()
        title_rot = 0
        xlabel_rot = 0
        ylabel_rot = 90
        y2label_rot = 90
        zlabel_rot = 90
        
        if use_custom_rot:
            title_rot = val(self.title_rotation, 0)
            xlabel_rot = val(self.xlabel_rotation, 0)
            ylabel_rot = val(self.ylabel_rotation, 90)
            y2label_rot = val(self.y2label_rotation, 90)
            zlabel_rot = val(self.zlabel_rotation, 90)

        xf = val(self.v_x_div, 1.0);
        yf = val(self.v_y_div, 1.0)
        y2f = val(self.v_y2_div, 1.0);
        zf = val(self.v_z_div, 1.0)
        t_sz = val(self.v_t_size, 14);
        l_sz = val(self.v_l_size, 12)
        leg_sz = val(self.v_leg_size, 10);
        xt_sz = val(self.v_xtick_size, 10);
        yt_sz = val(self.v_ytick_size, 10)
        font = self.v_font_fam.get()

        def get_tick_vals(prefix):
            maj = val(getattr(self, f"{prefix}_maj"), None)
            min_d = int(val(getattr(self, f"{prefix}_min_div"), 0))
            pad_attr = f"{prefix}_pad"
            if prefix == "v_x": pad_attr = "v_x_tick_pad"
            pad = val(getattr(self, pad_attr), 3.5)
            return maj, min_d, pad

        x_maj, x_min, x_pad_val = get_tick_vals("v_x")
        y1_maj, y1_min, y1_pad_val = get_tick_vals("v_y1")
        y2_maj, y2_min, y2_pad_val = get_tick_vals("v_y2")
        z_maj, z_min, z_pad_val = get_tick_vals("v_z")
        y_maj, y_min, y_pad_val = y1_maj, y1_min, y1_pad_val

        x_lab_pad = val(self.v_x_pad, 4.0);
        y_lab_pad = val(self.v_y_pad, 4.0)
        y_brk_off = val(self.v_y_broken_offset, -0.15);
        z_lab_pad = val(self.v_z_pad, 10.0)
        z_min_val = val(self.v_z_min);
        z_max_val = val(self.v_z_max)

        try:
            ptype = self.plot_type.get()
            xcol = self.x_combo.get()
            ycols = []
            if ptype == "Dual Y-Axis":
                if self.y1_combo.get(): ycols.append(self.y1_combo.get())
                if self.y2_combo.get(): ycols.append(self.y2_combo.get())
            else:
                y_idxs = self.y_listbox.curselection()
                ycols = [self.y_listbox.get(i) for i in y_idxs]

            if not xcol or not ycols: raise ValueError("Select X and Y axes.")

            l_txt = self.v_legend.get().strip()
            cust_legs = [l.strip() for l in l_txt.split(',')] if l_txt else []

            # --- BUILD SERIES LIST ---
            series_to_plot = []
            for fk, df in sel_ds:
                if ptype == "Dual Y-Axis":
                    if len(sel_ds) > 1:
                        if fk == sel_ds[0][0] and ycols[0] in df.columns: series_to_plot.append((fk, ycols[0], 0))
                        if fk == sel_ds[1][0] and len(ycols) > 1 and ycols[1] in df.columns: series_to_plot.append(
                            (fk, ycols[1], 1))
                    else:
                        for i, yc in enumerate(ycols):
                            if yc in df.columns: series_to_plot.append((fk, yc, i))
                else:
                    for yc in ycols:
                        if yc in df.columns: series_to_plot.append((fk, yc, 0))

            # --- APPLY LEGEND ORDER TO PLOTTING ORDER ---
            # This ensures gradient colors are assigned in the correct order
            if self.legend_order:
                # Build a dict mapping (filename, column) to the full tuple (including ax_idx)
                series_dict = {}
                for item in series_to_plot:
                    key = (item[0], item[1])  # (filename, column)
                    if key not in series_dict:  # Keep first occurrence
                        series_dict[key] = item
                
                # Reorder series_to_plot according to legend_order
                ordered_series = []
                used_keys = set()
                for key in self.legend_order:
                    if key in series_dict and key not in used_keys:
                        ordered_series.append(series_dict[key])
                        used_keys.add(key)
                # Add any remaining items not in legend_order
                for item in series_to_plot:
                    key = (item[0], item[1])
                    if key not in used_keys:
                        ordered_series.append(item)
                        used_keys.add(key)
                
                if ordered_series:
                    series_to_plot = ordered_series

            # --- COLOR LOGIC: GRADIENT vs CYCLE ---
            total_lines = len(series_to_plot)
            generated_colors = []
            if self.v_color_mode.get() == "Gradient" and total_lines > 0:
                cmap = plt.get_cmap(self.v_cmap_name.get())
                generated_colors = [cmap(x) for x in np.linspace(0.0, 1.0, total_lines)] if total_lines > 1 else [
                    cmap(0.5)]
            else:
                cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
                generated_colors = [cycle[i % len(cycle)] for i in range(total_lines)]

            X_master = None
            if self.use_ref_x_var.get():
                ref = self.axis_ref_combo.get()
                if ref in self.datasets and xcol in self.datasets[ref].columns:
                    X_master = self.datasets[ref][xcol].to_numpy() / xf

            # --- PARSE AXIS BREAKS (universal — works with any plot type except Broken Y-Axis) ---
            y_breaks_orig = self._parse_breaks(self.v_y_breaks)
            x_breaks_orig = self._parse_breaks(self.v_x_breaks)
            has_y_breaks = len(y_breaks_orig) > 0 and ptype not in ["Broken Y-Axis", "Color Map"]
            has_x_breaks = len(x_breaks_orig) > 0 and ptype not in ["Broken Y-Axis", "Color Map"]

            axes_list = []
            if ptype == "Broken Y-Axis":
                gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], hspace=0.2)
                ax1 = self.fig.add_subplot(gs[0]);
                ax2 = self.fig.add_subplot(gs[1], sharex=ax1)
                self.ax = ax1;
                axes_list = [ax1, ax2]
            elif ptype == "Dual Y-Axis":
                self.ax = self.fig.add_subplot(111);
                ax_right = self.ax.twinx()
                axes_list = [self.ax, ax_right]
            else:
                self.ax = self.fig.add_subplot(111);
                axes_list = [self.ax]

            lines, labels = [], []
            c_idx = 0
            
            # Track ALL line objects per series (for broken Y-axis, each series has 2 lines)
            self._series_line_groups = {}
            
            # Initialize label text objects (for custom positioning later) - MUST be before plot type sections
            xlabel_text = None
            title_text = None
            ylabel_text = None
            y2label_text = None
            zlabel_text = None

            if ptype in ["Line", "Scatter", "Broken Y-Axis", "Dual Y-Axis"]:
                for (fk, yc, ax_idx) in series_to_plot:
                    df = self.datasets[fk]
                    curr_yf = yf if ax_idx == 0 else y2f

                    if X_master is not None:
                        X_plot = X_master[:min(len(X_master), len(df))]
                        Y_plot = (df[yc].to_numpy() / curr_yf)[:len(X_plot)]
                    elif xcol in df.columns:
                        X_plot = df[xcol].to_numpy() / xf
                        Y_plot = df[yc].to_numpy() / curr_yf
                    else:
                        continue

                    # --- Apply axis break transformations ---
                    if has_x_breaks:
                        X_plot = self._transform_data(X_plot, x_breaks_orig)
                    if has_y_breaks:
                        Y_plot = self._transform_data(Y_plot, y_breaks_orig)

                    sk = (fk, yc);
                    st = self.styles.get(sk, {})
                    c = st.get('color', generated_colors[c_idx])
                    w = st.get('width', 2.0 if "Scatter" not in ptype else 20.0)
                    ls = st.get('linestyle', '-')
                    # Use per-series legend from styles, fallback to csv legend, then default
                    style_leg = st.get('legend', '').strip()
                    if style_leg:
                        lbl = style_leg
                    elif c_idx < len(cust_legs) and cust_legs[c_idx]:
                        lbl = cust_legs[c_idx]
                    else:
                        lbl = f"{fk}: {yc}"

                    target_axes = axes_list if ptype == "Broken Y-Axis" else [axes_list[ax_idx]]

                    # Track all line objects for this series (for visibility toggling)
                    series_lines = []
                    for ax_t in target_axes:
                        if "Scatter" in ptype:
                            ln = ax_t.scatter(X_plot, Y_plot, label=lbl, color=c, s=w, alpha=0.6)
                        else:
                            ln, = ax_t.plot(X_plot, Y_plot, label=lbl, color=c, linewidth=w, linestyle=ls)
                        series_lines.append(ln)
                        if ax_t == target_axes[0]:
                            lines.append(ln);
                            labels.append(lbl)
                            if ptype == "Dual Y-Axis": ax_t.tick_params(axis='y', labelcolor=c)
                    # Store all lines for this series key (important for broken Y-axis)
                    self._series_line_groups[sk] = series_lines
                    c_idx += 1

            elif ptype == "Color Map":
                # ... (Existing Color Map Logic) ...
                if len(sel_ds) != 1 or len(ycols) != 1: raise ValueError("Color Map: 1 File, 1 Y.")
                df = sel_ds[0][1]
                X = df[xcol].to_numpy() / xf;
                Y = df[ycols[0]].to_numpy() / yf;
                Z = df[self.z_combo.get()].to_numpy() / zf
                xi, yi = np.meshgrid(np.linspace(X.min(), X.max(), 300), np.linspace(Y.min(), Y.max(), 300))
                zi = griddata((X, Y), Z, (xi, yi), method='cubic')
                im = self.ax.imshow(zi, extent=(X.min(), X.max(), Y.min(), Y.max()), origin='lower', aspect='auto',
                                    cmap=self.v_cmap_name.get(), vmin=z_min_val, vmax=z_max_val)
                # Track ylabel_text for custom positioning
                ylabel_text = self.ax.set_ylabel(self.v_ylabel.get() or ycols[0], fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color, rotation=ylabel_rot)
                cbar = self.fig.colorbar(im, ax=self.ax)
                # Set colorbar label and get the text object for custom positioning
                cbar.set_label(self.v_zlabel.get() or self.z_combo.get(), fontsize=l_sz, labelpad=z_lab_pad,
                               fontname=font, color=self.zlabel_color, rotation=zlabel_rot)
                # Get the actual label text object from the colorbar
                zlabel_text = cbar.ax.yaxis.label
                if z_maj: cbar.ax.yaxis.set_major_locator(ticker.MultipleLocator(z_maj))
                if z_min > 1: cbar.ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(z_min))
                cbar.ax.tick_params(labelsize=yt_sz, pad=z_pad_val)

            # --- COMMON FORMATTING ---
            def apply_format(ax_obj, char, mode):
                if mode == "Scientific":
                    ax_obj.ticklabel_format(axis=char, style='sci', scilimits=(-2, 2), useMathText=True)
                elif mode == "Plain":
                    ax_obj.ticklabel_format(axis=char, style='plain', useOffset=False)
                elif mode == "Engineering":
                    (ax_obj.xaxis if char == 'x' else ax_obj.yaxis).set_major_formatter(ticker.EngFormatter())

            # Apply figure background color and alpha
            self.fig.patch.set_facecolor(self.fig_bg_color)
            try:
                fig_alpha = float(self.fig_bg_alpha.get())
                self.fig.patch.set_alpha(max(0.0, min(1.0, fig_alpha)))
            except:
                pass
            
            # Apply plot background color with alpha
            try:
                plot_alpha = float(self.plot_bg_alpha.get())
                plot_alpha = max(0.0, min(1.0, plot_alpha))
            except:
                plot_alpha = 1.0
            
            for ax_curr in axes_list:
                # Apply background color with alpha
                ax_curr.set_facecolor(self.plot_bg_color)
                ax_curr.patch.set_alpha(plot_alpha)
                
                if not self.x_log.get():
                    apply_format(ax_curr, 'x', self.v_x_not.get())
                    if x_maj: ax_curr.xaxis.set_major_locator(ticker.MultipleLocator(x_maj))
                    if x_min > 1: ax_curr.xaxis.set_minor_locator(ticker.AutoMinorLocator(x_min))
                # Tick direction, length, and side visibility
                x_dir = self.v_tick_dir_x.get()
                y_dir = self.v_tick_dir_y.get()
                maj_len = val(self.v_major_tick_length, 4.0)
                min_len = val(self.v_minor_tick_length, 2.0)
                min_x_dir = self.v_minor_tick_dir_x.get()
                min_y_dir = self.v_minor_tick_dir_y.get()

                x_tick_len = 0 if x_dir == "none" else maj_len
                ax_curr.tick_params(axis='x', direction=x_dir if x_dir != "none" else "out",
                    length=x_tick_len, labelsize=xt_sz, pad=x_pad_val, labelcolor=self.xtick_color,
                    bottom=self.v_x_tick_bottom.get(), top=self.v_x_tick_top.get())
                # Apply minor tick direction for X (also apply side visibility)
                if x_min > 1:
                    min_x_len = 0 if min_x_dir == "none" else min_len
                    ax_curr.tick_params(axis='x', which='minor', direction=min_x_dir if min_x_dir != "none" else "out",
                        length=min_x_len,
                        bottom=self.v_x_tick_bottom.get(), top=self.v_x_tick_top.get())

                if ptype != "Dual Y-Axis":
                    y_tick_len = 0 if y_dir == "none" else maj_len
                    ax_curr.tick_params(axis='y', direction=y_dir if y_dir != "none" else "out",
                        length=y_tick_len, labelsize=yt_sz, pad=y_pad_val, labelcolor=self.ytick_color,
                        left=self.v_y_tick_left.get(), right=self.v_y_tick_right.get())
                    # Apply minor tick direction for Y (also apply side visibility)
                    if y_min > 1:
                        min_y_len = 0 if min_y_dir == "none" else min_len
                        ax_curr.tick_params(axis='y', which='minor', direction=min_y_dir if min_y_dir != "none" else "out",
                            length=min_y_len,
                            left=self.v_y_tick_left.get(), right=self.v_y_tick_right.get())
                    if not self.y_log.get():
                        if  ptype != "Color Map":
                            apply_format(ax_curr, 'y', self.v_y_not.get())
                        if y_maj: ax_curr.yaxis.set_major_locator(ticker.MultipleLocator(y_maj))
                        if y_min > 1: ax_curr.yaxis.set_minor_locator(ticker.AutoMinorLocator(y_min))

            target_ax = axes_list[-1] if ptype == "Broken Y-Axis" else self.ax
            if self.x_log.get() and ptype != "Color Map":
                target_ax.set_xscale('log')
                if ptype == "Broken Y-Axis": axes_list[0].set_xscale('log')

            # Set xlabel with rotation
            xlabel_text = target_ax.set_xlabel(self.v_xlabel.get() or xcol, fontsize=l_sz, labelpad=x_lab_pad, fontname=font,
                                 color=self.xlabel_color, rotation=xlabel_rot)
            
            # Set title with rotation
            title_ax = axes_list[0] if ptype == "Broken Y-Axis" else self.ax
            title_text = title_ax.set_title(self.v_title.get(), fontsize=t_sz,
                                                                              fontweight='bold', fontname=font,
                                                                              color=self.title_color, rotation=title_rot)

            # --- Apply axis break formatters and indicators ---
            if has_y_breaks or has_x_breaks:
                for ax_curr in axes_list:
                    if has_y_breaks:
                        ax_curr.yaxis.set_major_formatter(ticker.FuncFormatter(
                            self._make_break_formatter(y_breaks_orig)))
                        # Transform Y axis limits
                        y_min_val = val(self.v_y_min)
                        y_max_val = val(self.v_y_max)
                        if y_min_val is not None:
                            ax_curr.set_ylim(bottom=self._transform_data(np.array([y_min_val]), y_breaks_orig)[0])
                        if y_max_val is not None:
                            ax_curr.set_ylim(top=self._transform_data(np.array([y_max_val]), y_breaks_orig)[0])
                    if has_x_breaks:
                        ax_curr.xaxis.set_major_formatter(ticker.FuncFormatter(
                            self._make_break_formatter(x_breaks_orig)))
                        # Transform X axis limits
                        x_min_val = val(self.v_x_min)
                        x_max_val = val(self.v_x_max)
                        if x_min_val is not None:
                            ax_curr.set_xlim(left=self._transform_data(np.array([x_min_val]), x_breaks_orig)[0])
                        if x_max_val is not None:
                            ax_curr.set_xlim(right=self._transform_data(np.array([x_max_val]), x_breaks_orig)[0])
                # Draw break indicators on the primary axis
                if has_y_breaks:
                    y_breaks_display = [(s, s) for s, e in y_breaks_orig]
                    self._draw_break_indicators(axes_list[0], y_breaks_display, axis='y')
                if has_x_breaks:
                    x_breaks_display = [(s, s) for s, e in x_breaks_orig]
                    self._draw_break_indicators(axes_list[0], x_breaks_display, axis='x')

            if val(self.v_x_min) and not has_x_breaks: target_ax.set_xlim(left=val(self.v_x_min))
            if val(self.v_x_max) and not has_x_breaks: target_ax.set_xlim(right=val(self.v_x_max))
            if ptype == "Broken Y-Axis": axes_list[0].set_xlim(target_ax.get_xlim())

            if ptype == "Broken Y-Axis":
                b_s, b_e = val(self.v_break_start), val(self.v_break_end)
                if b_s and b_e: axes_list[0].set_ylim(bottom=b_e); axes_list[1].set_ylim(top=b_s)
                if val(self.v_y_max): axes_list[0].set_ylim(top=val(self.v_y_max))
                if val(self.v_y_min): axes_list[1].set_ylim(bottom=val(self.v_y_min))
                axes_list[0].spines['bottom'].set_visible(False);
                axes_list[1].spines['top'].set_visible(False)
                axes_list[0].xaxis.tick_top();
                axes_list[0].tick_params(labeltop=False);
                axes_list[1].xaxis.tick_bottom()
                d = .015;
                kw = dict(transform=axes_list[0].transAxes, color='k', clip_on=False)
                axes_list[0].plot((-d, +d), (-d, +d), **kw);
                axes_list[0].plot((1 - d, 1 + d), (-d, +d), **kw)
                kw.update(transform=axes_list[1].transAxes)
                axes_list[1].plot((-d, +d), (1 - d, 1 + d), **kw);
                axes_list[1].plot((1 - d, 1 + d), (1 - d, 1 + d), **kw)
                # Set Y label for broken axis - centered between the two subplots
                ylabel_text = self.fig.supylabel(self.v_ylabel.get() or "Values", fontsize=l_sz, 
                                   x=0.04, y=0.5, fontname=font, color=self.ylabel_color)
                if use_custom_pos:
                    ylabel_text.set_position(custom_ylabel_pos)
                    ylabel_text.set_transform(self.fig.transFigure)
            elif ptype == "Dual Y-Axis":
                # Set Y1 (left axis) label with rotation
                y1_label = self.v_ylabel.get() or (ycols[0] if ycols else "Y1")
                ylabel_text = self.ax.set_ylabel(y1_label, fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color, rotation=ylabel_rot)
                if use_custom_pos:
                    ylabel_text.set_position(custom_ylabel_pos)
                    ylabel_text.set_transform(self.fig.transFigure)
                # Set Y2 (right axis) label with rotation
                y2_label = self.v_y2label.get() or (ycols[1] if len(ycols) > 1 else "Y2")
                y2label_text = axes_list[1].set_ylabel(y2_label, fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                        color=self.ylabel_color, rotation=y2label_rot)
                if use_custom_pos:
                    y2label_text.set_position(custom_y2label_pos)
                    y2label_text.set_transform(self.fig.transFigure)
                # Set Y1 axis range
                if val(self.v_y_min): self.ax.set_ylim(bottom=val(self.v_y_min))
                if val(self.v_y_max): self.ax.set_ylim(top=val(self.v_y_max))
                # Set Y2 axis range
                if val(self.v_y2_min): axes_list[1].set_ylim(bottom=val(self.v_y2_min))
                if val(self.v_y2_max): axes_list[1].set_ylim(top=val(self.v_y2_max))
            elif ptype != "Color Map":
                ylabel_text = self.ax.set_ylabel(self.v_ylabel.get() or "Values", fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color, rotation=ylabel_rot)
                if use_custom_pos:
                    ylabel_text.set_position(custom_ylabel_pos)
                    ylabel_text.set_transform(self.fig.transFigure)
                if val(self.v_y_min) and not has_y_breaks: self.ax.set_ylim(bottom=val(self.v_y_min))
                if val(self.v_y_max) and not has_y_breaks: self.ax.set_ylim(top=val(self.v_y_max))
            elif ptype == "Color Map":
                if val(self.v_y_min): self.ax.set_ylim(bottom=val(self.v_y_min))
                if val(self.v_y_max): self.ax.set_ylim(top=val(self.v_y_max))

            # --- ALWAYS track series keys for context menu toggle (even without legend) ---
            series_keys_all = [(fk, yc) for (fk, yc, _) in series_to_plot]
            
            # Apply hidden_legend_items visibility (works with or without legend)
            for key in series_keys_all:
                if key in self.hidden_legend_items:
                    if key in self._series_line_groups:
                        for line_obj in self._series_line_groups[key]:
                            line_obj.set_visible(False)
            
            # Store all series keys for context menu toggle
            self._all_series_keys = series_keys_all
            
            if self.show_legend.get() and ptype != "Color Map":
                # Apply legend order if set
                if self.legend_order:
                    # Build a mapping from series keys to their lines and labels
                    series_keys = [(fk, yc) for (fk, yc, _) in series_to_plot]
                    key_to_line_label = {}
                    for i, key in enumerate(series_keys):
                        if i < len(lines) and i < len(labels):
                            key_to_line_label[key] = (lines[i], labels[i])
                    
                    # Reorder lines and labels according to legend_order
                    ordered_lines = []
                    ordered_labels = []
                    used_keys = set()
                    
                    # First add items in legend_order
                    for key in self.legend_order:
                        if key in key_to_line_label and key not in used_keys:
                            ordered_lines.append(key_to_line_label[key][0])
                            ordered_labels.append(key_to_line_label[key][1])
                            used_keys.add(key)
                    
                    # Then add any remaining items not in legend_order
                    for i, key in enumerate(series_keys):
                        if key not in used_keys and i < len(lines) and i < len(labels):
                            ordered_lines.append(lines[i])
                            ordered_labels.append(labels[i])
                    
                    if ordered_lines:
                        lines, labels = ordered_lines, ordered_labels
                
                # Filter lines/labels based on show_in_legend setting AND hidden_legend_items
                series_keys_for_legend = [(fk, yc) for (fk, yc, _) in series_to_plot]
                filtered_lines = []
                filtered_labels = []
                filtered_keys = []  # Track which keys are still visible
                for i, (ln, lbl) in enumerate(zip(lines, labels)):
                    if i < len(series_keys_for_legend):
                        key = series_keys_for_legend[i]
                        st = self.styles.get(key, {})
                        # Default to TRUE if show_in_legend is not set
                        # Also check if item is in hidden_legend_items
                        if st.get('show_in_legend', True) and key not in self.hidden_legend_items:
                            filtered_lines.append(ln)
                            filtered_labels.append(lbl)
                            filtered_keys.append(key)
                        else:
                            # Hide ALL lines for this series (important for broken Y-axis)
                            if key in self._series_line_groups:
                                for line_obj in self._series_line_groups[key]:
                                    line_obj.set_visible(False)
                            else:
                                ln.set_visible(False)
                    else:
                        # Keep items we can't map (shouldn't happen, but safety)
                        filtered_lines.append(ln)
                        filtered_labels.append(lbl)
                
                lines, labels = filtered_lines, filtered_labels
                
                # Store the keys for legend toggle functionality
                self.current_legend_keys = filtered_keys
                
                # If no visible lines, skip legend creation but still render the plot
                if not lines:
                    self.current_lines = []
                    self.current_legend_keys = []
                
                if lines:
                    # Get legend settings
                    ncol = int(self.legend_columns.get())
                    position = self.legend_position.get()
                    
                    # Map position string to matplotlib loc and bbox_to_anchor
                    loc_map = {
                        "Best": "best",
                        "Upper Right": "upper right",
                        "Upper Left": "upper left",
                        "Lower Right": "lower right",
                        "Lower Left": "lower left",
                        "Center Left": "center left",
                        "Center Right": "center right",
                        "Lower Center": "lower center",
                        "Upper Center": "upper center",
                        "Center": "center",
                        "Outside Right": "center left",
                        "Outside Bottom": "upper center"
                    }
                    
                    loc = loc_map.get(position, "best")
                    bbox_to_anchor = None
                    
                    if position == "Outside Right":
                        bbox_to_anchor = (1.02, 0.5)
                    elif position == "Outside Bottom":
                        bbox_to_anchor = (0.5, -0.15)
                    
                    # Store lines for legend toggle functionality
                    self.current_lines = lines
                    
                    # Create legend
                    legend_ax = axes_list[0] if ptype == "Broken Y-Axis" else self.ax
                    legend = legend_ax.legend(lines, labels, loc=loc, ncol=ncol,
                                              bbox_to_anchor=bbox_to_anchor,
                                              prop={'size': leg_sz, 'family': font})
                    
                    # Apply legend fill color and transparency
                    legend.get_frame().set_facecolor(self.legend_fill_color)
                    legend.get_frame().set_edgecolor(self.legend_frame_color)
                    try:
                        leg_alpha = float(self.legend_fill_alpha.get())
                        legend.get_frame().set_alpha(max(0.0, min(1.0, leg_alpha)))
                    except:
                        pass
                    
                    # Make legend draggable if enabled
                    if self.legend_draggable.get():
                        legend.set_draggable(True)
                    
                    # Connect pick event for legend toggle (click on legend to hide/show lines)
                    self.canvas.mpl_connect('pick_event', self.on_legend_pick)
                    legend.set_picker(10)  # Set pick radius for legend

            # --- GRID SETTINGS (Origin Pro-like: major/minor grid control) ---
            grid_alpha = val(self.v_grid_alpha, 0.3)
            grid_ls = self.v_grid_linestyle.get()
            grid_lw = val(self.v_grid_linewidth, 0.5)
            for a in axes_list:
                if self.show_major_grid.get():
                    a.grid(True, which='major', alpha=grid_alpha, linestyle=grid_ls, linewidth=grid_lw)
                else:
                    a.grid(False, which='major')
                if self.show_minor_grid.get():
                    a.grid(True, which='minor', alpha=grid_alpha * 0.7, linestyle=grid_ls, linewidth=grid_lw * 0.7)
                else:
                    a.grid(False, which='minor')

            # --- SECONDARY TOP X-AXIS ---
            if self.enable_secondary_x.get() and ptype != "Broken Y-Axis":
                try:
                    fwd_formula = self.v_sec_x_forward.get().strip()
                    
                    if fwd_formula:
                        # Auto-derive inverse if not manually set
                        inv_formula = self.v_sec_x_inverse.get().strip()
                        if not inv_formula or inv_formula == fwd_formula:
                            auto_inv = self._auto_derive_inverse(fwd_formula)
                            if auto_inv:
                                inv_formula = auto_inv
                        
                        if inv_formula:
                            # Create safe lambda functions from the formulas
                            # Support numpy operations via 'np' in the namespace
                            safe_dict = {"np": np, "__builtins__": {}}
                            fwd_func = eval(f"lambda x: {fwd_formula}", safe_dict)
                            inv_func = eval(f"lambda x: {inv_formula}", safe_dict)
                            
                            # Create the secondary axis
                            sec_x_ax = target_ax.secondary_xaxis('top', functions=(fwd_func, inv_func))
                            
                            # Apply label
                            sec_label = self.v_sec_x_label.get().strip()
                            if sec_label:
                                sec_x_ax.set_xlabel(sec_label, fontsize=l_sz, fontname=font,
                                                    color=self.sec_x_label_color)
                            
                            # Apply tick settings
                            sec_xt_sz = val(self.v_sec_x_tick_size, 10)
                            sec_x_ax.tick_params(axis='x', labelsize=sec_xt_sz, labelcolor=self.xtick_color)
                            
                            # Apply major tick step if specified
                            sec_x_maj_val = val(self.v_sec_x_maj)
                            if sec_x_maj_val:
                                sec_x_ax.xaxis.set_major_locator(ticker.MultipleLocator(sec_x_maj_val))
                            
                            # Apply minor tick divisions if specified
                            sec_x_min_div = int(val(self.v_sec_x_min_div, 0))
                            if sec_x_min_div > 1:
                                sec_x_ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(sec_x_min_div))
                            
                            # Apply tick direction to match top ticks
                            x_dir = self.v_tick_dir_x.get()
                            maj_len = val(self.v_major_tick_length, 4.0)
                            min_len = val(self.v_minor_tick_length, 2.0)
                            x_tick_len = 0 if x_dir == "none" else maj_len
                            sec_x_ax.tick_params(axis='x', direction=x_dir if x_dir != "none" else "out",
                                                length=x_tick_len)
                            # Apply minor tick direction for secondary X
                            if sec_x_min_div > 1:
                                min_x_dir = self.v_minor_tick_dir_x.get()
                                min_x_len = 0 if min_x_dir == "none" else min_len
                                sec_x_ax.tick_params(axis='x', which='minor', 
                                    direction=min_x_dir if min_x_dir != "none" else "out",
                                    length=min_x_len)
                except Exception as sec_e:
                    print(f"Secondary X-Axis error: {sec_e}")

            self.fig.tight_layout()
            
            # Apply custom label positions AFTER tight_layout
            if use_custom_pos:
                # Title - use fig.text for reliable figure coordinates
                if title_text is not None:
                    # Remove the axis-level title and create a figure-level text
                    title_text.set_visible(False)
                    self.fig.text(custom_title_pos[0], custom_title_pos[1], 
                                  self.v_title.get(), fontsize=t_sz,
                                  fontweight='bold', fontname=font,
                                  color=self.title_color, ha='center', va='top', rotation=title_rot)
                # X label
                if xlabel_text is not None:
                    xlabel_text.set_visible(False)
                    self.fig.text(custom_xlabel_pos[0], custom_xlabel_pos[1],
                                  self.v_xlabel.get() or xcol, fontsize=l_sz,
                                  fontname=font, color=self.xlabel_color, ha='center', va='bottom', rotation=xlabel_rot)
                # Y label
                if ylabel_text is not None:
                    ylabel_text.set_visible(False)
                    self.fig.text(custom_ylabel_pos[0], custom_ylabel_pos[1],
                                  self.v_ylabel.get() or "Values", fontsize=l_sz,
                                  fontname=font, color=self.ylabel_color, ha='left', va='center', rotation=ylabel_rot)
                # Y2 label (for Dual Y-Axis)
                if y2label_text is not None:
                    y2label_text.set_visible(False)
                    self.fig.text(custom_y2label_pos[0], custom_y2label_pos[1],
                                  self.v_y2label.get() or (ycols[1] if len(ycols) > 1 else "Y2"), 
                                  fontsize=l_sz, fontname=font, color=self.ylabel_color, ha='right', va='center', rotation=y2label_rot)
                # Z label (for Color Map)
                if zlabel_text is not None:
                    zlabel_text.set_visible(False)
                    self.fig.text(custom_zlabel_pos[0], custom_zlabel_pos[1],
                                  self.v_zlabel.get() or self.z_combo.get(), fontsize=l_sz,
                                  fontname=font, color=self.zlabel_color, ha='left', va='center', rotation=zlabel_rot)
            
            self.canvas.draw()

        except Exception as e:
            print(f"Error plotting: {e}")
            messagebox.showerror("Plot Error", str(e))

    def _setup_autocomplete_combobox(self, combobox, all_values, parent_window):
        """Setup autocomplete functionality for a combobox.
        
        When typing in the combobox, it filters the list to show only matching fonts.
        - Type letters to filter the list
        - Press Down arrow to open dropdown with filtered results
        - Press Enter or Tab to accept the selection
        """
        # Store all values for filtering
        combobox._all_values = all_values
        
        def on_keyrelease(event):
            """Handle key release to filter combobox values."""
            typed = combobox.get().lower()
            
            # Filter values that start with or contain the typed text
            if typed:
                # First prioritize fonts that start with the typed text
                starts_with = [v for v in all_values if v.lower().startswith(typed)]
                contains = [v for v in all_values if typed in v.lower() and v not in starts_with]
                filtered = starts_with + contains
            else:
                filtered = all_values
            
            # Update combobox values
            combobox['values'] = filtered
            
            # If we have a match and user typed something, show the dropdown
            if filtered and typed:
                # Find the best match and set it
                if filtered:
                    combobox.event_generate('<Down>')
        
        def on_enter(event):
            """Handle Enter key to accept selection."""
            # If there's a filtered list and the current text matches a font, select it
            current = combobox.get()
            if current in all_values:
                combobox.set(current)
            elif combobox['values']:
                # Select the first match
                combobox.set(combobox['values'][0])
            return "break"  # Prevent default behavior
        
        def on_focus_out(event):
            """Handle focus out - reset to full list if valid selection."""
            current = combobox.get()
            if current in all_values:
                # Valid selection, keep it
                pass
            elif not current:
                # Empty, reset to default
                pass
            # Reset the full list for next time
            combobox['values'] = all_values
        
        # Bind events
        combobox.bind('<KeyRelease>', on_keyrelease)
        combobox.bind('<Return>', on_enter)
        combobox.bind('<FocusOut>', on_focus_out)
        
        # Make combobox editable so user can type
        combobox.configure(state='normal')
    
    def reset_ranges(self):
        for v in [self.v_x_min, self.v_x_max, self.v_y_min, self.v_y_max, self.v_y2_min, self.v_y2_max, self.v_z_min,
                  self.v_z_max, self.v_break_start, self.v_break_end]:
            v.set("")
        for s_var, e_var in self.v_y_breaks + self.v_x_breaks:
            s_var.set("")
            e_var.set("")
        self.update_plot()

    def export_plot(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".png",
                                                filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")])
        if filepath:
            try:
                self.fig.savefig(filepath, dpi=300, bbox_inches='tight'); messagebox.showinfo("Success",
                                                                                              f"Plot saved to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # --- SESSION CACHE METHODS ---
    def set_cache_folder(self):
        """Let user choose a folder for saving/loading cache files."""
        folder = filedialog.askdirectory(title="Select Cache Folder")
        if folder:
            self.cache_folder = folder
            messagebox.showinfo("Cache Folder Set", f"Cache files will be saved to:\n{folder}")

    def save_session(self):
        """Save current session (datasets + all settings) to a JSON cache file."""
        if not self.datasets:
            messagebox.showwarning("No Data", "No datasets loaded to save.")
            return
        
        # Determine where to save
        if self.cache_folder:
            initial_dir = self.cache_folder
        else:
            # Ask user to select folder first if not set
            folder = filedialog.askdirectory(title="Select Folder to Save Cache")
            if not folder:
                return
            self.cache_folder = folder
            initial_dir = folder
        
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"session_{timestamp}"
        
        filepath = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON Cache", "*.json"), ("All files", "*.*")],
            title="Save Session Cache"
        )
        
        if not filepath:
            return
        
        try:
            # Prepare session data
            session_data = {
                "timestamp": datetime.now().isoformat(),
                "plot_type": self.plot_type.get(),
            }
            
            # === DATASETS ===
            session_data["datasets"] = {}
            for filename, df in self.datasets.items():
                session_data["datasets"][filename] = {
                    "columns": df.columns,
                    "data": df.to_numpy().tolist()
                }
            
            # === STYLES (per-series) ===
            session_data["styles"] = {}
            for k, v in self.styles.items():
                str_key = f"{k[0]}|||{k[1]}"
                session_data["styles"][str_key] = v
            
            # === LEGEND ORDER ===
            session_data["legend_order"] = [f"{k[0]}|||{k[1]}" for k in self.legend_order]
            
            # === LEGEND SETTINGS ===
            session_data["legend_settings"] = {
                "columns": self.legend_columns.get(),
                "position": self.legend_position.get(),
                "draggable": self.legend_draggable.get(),
                "show_legend": self.show_legend.get(),
                "legend_size": self.v_leg_size.get(),
                "legend_csv": self.v_legend.get(),
            }
            
            # === TITLES & LABELS ===
            session_data["titles_labels"] = {
                "title": self.v_title.get(),
                "xlabel": self.v_xlabel.get(),
                "ylabel": self.v_ylabel.get(),
                "y2label": self.v_y2label.get(),
                "zlabel": self.v_zlabel.get(),
                "title_color": self.title_color,
                "xlabel_color": self.xlabel_color,
                "ylabel_color": self.ylabel_color,
                "zlabel_color": self.zlabel_color,
                "xtick_color": self.xtick_color,
                "ytick_color": self.ytick_color,
            }
            
            # === DATA TRANSFORMATION ===
            session_data["data_transformation"] = {
                "x_div": self.v_x_div.get(),
                "y_div": self.v_y_div.get(),
                "y2_div": self.v_y2_div.get(),
                "z_div": self.v_z_div.get(),
            }
            
            # === AXIS RANGES ===
            session_data["axis_ranges"] = {
                "x_min": self.v_x_min.get(),
                "x_max": self.v_x_max.get(),
                "y_min": self.v_y_min.get(),
                "y_max": self.v_y_max.get(),
                "y2_min": self.v_y2_min.get(),
                "y2_max": self.v_y2_max.get(),
                "z_min": self.v_z_min.get(),
                "z_max": self.v_z_max.get(),
                "break_start": self.v_break_start.get(),
                "break_end": self.v_break_end.get(),
            }
            
            # === AXIS BREAKS ===
            session_data["axis_breaks"] = {
                "y_breaks": [(s.get(), e.get()) for s, e in self.v_y_breaks],
                "x_breaks": [(s.get(), e.get()) for s, e in self.v_x_breaks],
            }
            
            # === PADDING ===
            session_data["padding"] = {
                "x_pad": self.v_x_pad.get(),
                "y_pad": self.v_y_pad.get(),
                "y_broken_offset": self.v_y_broken_offset.get(),
                "z_pad": self.v_z_pad.get(),
            }
            
            # === TICK SETTINGS ===
            session_data["tick_settings"] = {
                "x_maj": self.v_x_maj.get(),
                "x_min_div": self.v_x_min_div.get(),
                "x_tick_pad": self.v_x_tick_pad.get(),
                "y_maj": self.v_y_maj.get(),
                "y_min_div": self.v_y_min_div.get(),
                "y_tick_pad": self.v_y_tick_pad.get(),
                "y1_maj": self.v_y1_maj.get(),
                "y1_min_div": self.v_y1_min_div.get(),
                "y1_pad": self.v_y1_pad.get(),
                "y2_maj": self.v_y2_maj.get(),
                "y2_min_div": self.v_y2_min_div.get(),
                "y2_pad": self.v_y2_pad.get(),
                "z_maj": self.v_z_maj.get(),
                "z_min_div": self.v_z_min_div.get(),
                "z_tick_pad": self.v_z_tick_pad.get(),
            }
            
            # === FONT SETTINGS ===
            session_data["font_settings"] = {
                "font_family": self.v_font_fam.get(),
                "title_size": self.v_t_size.get(),
                "label_size": self.v_l_size.get(),
                "xtick_size": self.v_xtick_size.get(),
                "ytick_size": self.v_ytick_size.get(),
                "x_notation": self.v_x_not.get(),
                "y_notation": self.v_y_not.get(),
            }
            
            # === TICK APPEARANCE SETTINGS ===
            session_data["tick_appearance"] = {
                "tick_dir_x": self.v_tick_dir_x.get(),
                "tick_dir_y": self.v_tick_dir_y.get(),
                "tick_dir_y2": self.v_tick_dir_y2.get(),
                "tick_dir_z": self.v_tick_dir_z.get(),
                "minor_tick_dir_x": self.v_minor_tick_dir_x.get(),
                "minor_tick_dir_y": self.v_minor_tick_dir_y.get(),
                "minor_tick_dir_y2": self.v_minor_tick_dir_y2.get(),
                "minor_tick_dir_z": self.v_minor_tick_dir_z.get(),
                "major_tick_length": self.v_major_tick_length.get(),
                "minor_tick_length": self.v_minor_tick_length.get(),
            }

            # === TICK SIDE VISIBILITY ===
            session_data["tick_sides"] = {
                "x_tick_bottom": self.v_x_tick_bottom.get(),
                "x_tick_top": self.v_x_tick_top.get(),
                "y_tick_left": self.v_y_tick_left.get(),
                "y_tick_right": self.v_y_tick_right.get(),
            }

            # === GRID SETTINGS ===
            session_data["grid_settings"] = {
                "show_major_grid": self.show_major_grid.get(),
                "show_minor_grid": self.show_minor_grid.get(),
                "grid_alpha": self.v_grid_alpha.get(),
                "grid_linestyle": self.v_grid_linestyle.get(),
                "grid_linewidth": self.v_grid_linewidth.get(),
            }

            # === SECONDARY X-AXIS ===
            session_data["secondary_x_axis"] = {
                "enabled": self.enable_secondary_x.get(),
                "forward": self.v_sec_x_forward.get(),
                "inverse": self.v_sec_x_inverse.get(),
                "label": self.v_sec_x_label.get(),
                "tick_size": self.v_sec_x_tick_size.get(),
                "major_step": self.v_sec_x_maj.get(),
                "minor_divisions": self.v_sec_x_min_div.get(),
                "label_color": self.sec_x_label_color,
            }

            # === PLOT SETTINGS ===
            session_data["plot_settings"] = {
                "plot_type": self.plot_type.get(),
                "color_mode": self.v_color_mode.get(),
                "colormap": self.v_cmap_name.get(),
                "show_grid": self.show_grid.get(),
                "x_log": self.x_log.get(),
                "y_log": self.y_log.get(),
            }
            
            # === AXIS SELECTIONS ===
            y_idxs = self.y_listbox.curselection()
            y_columns = [self.y_listbox.get(i) for i in y_idxs]
            
            session_data["axis_selections"] = {
                "axis_ref_file": self.axis_ref_combo.get(),
                "x_column": self.x_combo.get(),
                "y_column": y_columns,
                "z_column": self.z_combo.get(),
                "y1_column": self.y1_combo.get(),
                "y2_column": self.y2_combo.get(),
                "merge_cols": self.merge_cols_var.get(),
                "use_ref_x": self.use_ref_x_var.get(),
            }
            
            # === UI STATE ===
            # Save selected datasets
            selected_indices = list(self.dataset_listbox.curselection())
            session_data["ui_state"] = {
                "selected_datasets": selected_indices,
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            # Count saved items for info message
            saved_items = [
                "Datasets", "Styles", "Legend Order", "Legend Settings",
                "Titles & Labels", "Data Transformation", "Axis Ranges",
                "Tick Settings", "Font Settings", "Plot Settings", "Axis Selections"
            ]
            
            messagebox.showinfo("Session Saved", 
                f"Session saved successfully to:\n{filepath}\n\n"
                f"Saved {len(self.datasets)} datasets\n"
                f"Saved settings: {', '.join(saved_items)}")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save session:\n{str(e)}")

    def open_dataset_window(self):
        """Open a separate window for managing datasets with better visibility."""
        if self.dataset_window is not None and self.dataset_window.winfo_exists():
            self.dataset_window.lift()
            return
        
        # Use dynamic sizing for the dataset manager
        w, h = self.get_dialog_size(0.40, 0.80, max_width=600, max_height=700, min_width=400, min_height=400)
        
        self.dataset_window = tk.Toplevel(self.root)
        self.dataset_window.title("Dataset Manager")
        self.dataset_window.geometry(f"{w}x{h}")
        self.dataset_window.transient(self.root)
        
        frame = ttk.Frame(self.dataset_window, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Load buttons at top
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text="Load Data File", command=self.load_files).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Unload Selected", command=self.unload_files).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Refresh", command=lambda: self.refresh_dataset_window_list()).pack(side='left', padx=2)
        
        # Main listbox with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        self.ds_window_listbox = tk.Listbox(list_frame, selectmode='extended', 
                                             yscrollcommand=sb.set, exportselection=False,
                                             font=('Consolas', 10))
        sb.config(command=self.ds_window_listbox.yview)
        self.ds_window_listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        
        # Bind selection event to sync with main listbox
        self.ds_window_listbox.bind('<<ListboxSelect>>', self.on_ds_window_selection_change)
        
        # Info label
        self.ds_info_label = ttk.Label(frame, text="", font=('Arial', 9))
        self.ds_info_label.pack(fill='x', pady=(10, 5))
        
        # Populate listbox
        self.refresh_dataset_window_list()
        
        # Handle window close
        self.dataset_window.protocol("WM_DELETE_WINDOW", self.on_ds_window_close)
    
    def refresh_dataset_window_list(self):
        """Refresh the dataset list in the separate window."""
        if self.dataset_window is None or not self.dataset_window.winfo_exists():
            return
        
        self.ds_window_listbox.delete(0, tk.END)
        for k in self.datasets.keys():
            df = self.datasets[k]
            cols = len(df.columns)
            rows = len(df)
            self.ds_window_listbox.insert(tk.END, f"{k}  ({rows} rows, {cols} cols)")
        
        # Sync selection with main listbox
        main_sel = list(self.dataset_listbox.curselection())
        self.ds_window_listbox.selection_clear(0, tk.END)
        for idx in main_sel:
            if idx < self.ds_window_listbox.size():
                self.ds_window_listbox.selection_set(idx)
        
        # Update info
        total_rows = sum(len(df) for df in self.datasets.values())
        self.ds_info_label.config(text=f"Total: {len(self.datasets)} datasets, {total_rows} rows")
    
    def on_ds_window_selection_change(self, event):
        """Sync selection from window listbox to main listbox."""
        sel_idxs = list(self.ds_window_listbox.curselection())
        self.dataset_listbox.selection_clear(0, tk.END)
        for idx in sel_idxs:
            if idx < self.dataset_listbox.size():
                self.dataset_listbox.selection_set(idx)
        self.update_plot()
    
    def on_ds_window_close(self):
        """Handle dataset window close."""
        if self.dataset_window:
            self.dataset_window.destroy()
        self.dataset_window = None

    def show_all_lines(self):
        """Show all hidden lines and reset visibility state."""
        self.hidden_legend_items.clear()
        self.update_plot()

    def _show_line_toggle_menu(self, screen_x, screen_y):
        """Create and show the line visibility toggle menu. Re-posts itself after each toggle."""
        all_keys = getattr(self, '_all_series_keys', [])
        if not all_keys:
            return
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        
        # Add "Show All Lines" option at top
        def show_all_and_repost():
            self.hidden_legend_items.clear()
            self.update_plot()
            self.root.after(10, lambda: self._show_line_toggle_menu(screen_x, screen_y))
        
        menu.add_command(label="Show All Lines", command=show_all_and_repost)
        
        # Add separator
        menu.add_separator()
        
        # Add ALL series with visibility toggle
        menu.add_command(label="Toggle Line Visibility:", state='disabled')
        for key in all_keys:
            # Get display name
            st = self.styles.get(key, {})
            leg = st.get('legend', '').strip()
            if leg:
                display_name = leg
            else:
                display_name = f"{key[0]}: {key[1]}"
            
            # Show checkmark prefix based on visibility
            is_visible = key not in self.hidden_legend_items
            prefix = "✓ " if is_visible else "✗ "
            
            # Create closure to capture key
            def make_toggle_callback(k):
                def toggle():
                    if k in self.hidden_legend_items:
                        self.hidden_legend_items.discard(k)
                    else:
                        self.hidden_legend_items.add(k)
                    self.update_plot()
                    # Re-post the menu after a short delay so it stays open
                    self.root.after(10, lambda: self._show_line_toggle_menu(screen_x, screen_y))
                return toggle
            menu.add_command(label=prefix + display_name, command=make_toggle_callback(key))
        
        # Show menu at given position
        menu.tk_popup(screen_x, screen_y)
    
    def _on_canvas_right_click(self, event):
        """Handle right-click on canvas to show context menu with all series toggle (works even with no legend)."""
        if event.button != 3:  # Only handle right-click
            return
        
        # Need at least one series to show the menu
        all_keys = getattr(self, '_all_series_keys', [])
        if not all_keys:
            return
        
        # Calculate screen position and delegate to menu builder
        screen_x = self.canvas.get_tk_widget().winfo_rootx() + int(event.x)
        screen_y = self.canvas.get_tk_widget().winfo_rooty() + int(event.y)
        self._show_line_toggle_menu(screen_x, screen_y)

    def on_legend_pick(self, event):
        """Handle click on legend to toggle line and legend entry visibility."""
        if event.artist is None:
            return
        
        # Find which legend entry was clicked
        legend = event.artist
        if not hasattr(legend, 'get_texts'):
            return
        
        # Get the clicked label index
        mouseevent = event.mouseevent
        if mouseevent is None:
            return
        
        # Handle right-click for context menu
        if mouseevent.button == 3:  # Right click
            self._show_legend_context_menu(mouseevent, legend)
            return
        
        # Handle left-click for toggle
        # Find clicked legend item
        for i, text in enumerate(legend.get_texts()):
            bbox = text.get_window_extent()
            if bbox.contains(mouseevent.x, mouseevent.y):
                # Toggle visibility by adding/removing from hidden_legend_items
                if i < len(self.current_lines) and hasattr(self, 'current_legend_keys') and i < len(self.current_legend_keys):
                    key = self.current_legend_keys[i]
                    
                    if key in self.hidden_legend_items:
                        # Show the line
                        self.hidden_legend_items.discard(key)
                    else:
                        # Hide the line
                        self.hidden_legend_items.add(key)
                    
                    # Re-render the plot to update both line and legend
                    self.update_plot()
                break
    
    def _show_legend_context_menu(self, mouseevent, legend):
        """Show context menu on right-click of legend — uses the same persistent toggle menu."""
        x = self.canvas.get_tk_widget().winfo_rootx() + int(mouseevent.x)
        y = self.canvas.get_tk_widget().winfo_rooty() + int(mouseevent.y)
        self._show_line_toggle_menu(x, y)
                
    def load_session(self):
        """Load a session from a JSON cache file."""
        # Determine where to look
        initial_dir = self.cache_folder if self.cache_folder else "."
        
        filepath = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[("JSON Cache", "*.json"), ("All files", "*.*")],
            title="Load Session Cache"
        )
        
        if not filepath:
            return
        
        # Update cache folder to the directory of the loaded file
        self.cache_folder = os.path.dirname(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Clear current data
            self.datasets = {}
            self.styles = {}
            
            # === RESTORE DATASETS ===
            for filename, df_data in session_data.get("datasets", {}).items():
                columns = df_data["columns"]
                data = df_data["data"]
                df = pl.DataFrame(data, schema=columns, orient="row")
                self.datasets[filename] = df
            
            # === RESTORE STYLES ===
            for str_key, style_val in session_data.get("styles", {}).items():
                parts = str_key.split("|||")
                if len(parts) == 2:
                    tuple_key = (parts[0], parts[1])
                    self.styles[tuple_key] = style_val
            
            # === RESTORE LEGEND ORDER ===
            self.legend_order = []
            for str_key in session_data.get("legend_order", []):
                parts = str_key.split("|||")
                if len(parts) == 2:
                    self.legend_order.append((parts[0], parts[1]))
            
            # === RESTORE LEGEND SETTINGS ===
            legend_settings = session_data.get("legend_settings", {})
            if legend_settings:
                self.legend_columns.set(legend_settings.get("columns", "1"))
                self.legend_position.set(legend_settings.get("position", "Best"))
                self.legend_draggable.set(legend_settings.get("draggable", True))
                self.show_legend.set(legend_settings.get("show_legend", True))
                self.v_leg_size.set(legend_settings.get("legend_size", "10"))
                self.v_legend.set(legend_settings.get("legend_csv", ""))
            
            # === RESTORE TITLES & LABELS ===
            titles_labels = session_data.get("titles_labels", {})
            if titles_labels:
                self.v_title.set(titles_labels.get("title", "My Plot"))
                self.v_xlabel.set(titles_labels.get("xlabel", ""))
                self.v_ylabel.set(titles_labels.get("ylabel", ""))
                self.v_y2label.set(titles_labels.get("y2label", ""))
                self.v_zlabel.set(titles_labels.get("zlabel", ""))
                self.title_color = titles_labels.get("title_color", "black")
                self.xlabel_color = titles_labels.get("xlabel_color", "black")
                self.ylabel_color = titles_labels.get("ylabel_color", "black")
                self.zlabel_color = titles_labels.get("zlabel_color", "black")
                self.xtick_color = titles_labels.get("xtick_color", "black")
                self.ytick_color = titles_labels.get("ytick_color", "black")
            
            # === RESTORE DATA TRANSFORMATION ===
            data_transformation = session_data.get("data_transformation", {})
            if data_transformation:
                self.v_x_div.set(data_transformation.get("x_div", "1"))
                self.v_y_div.set(data_transformation.get("y_div", "1"))
                self.v_y2_div.set(data_transformation.get("y2_div", "1"))
                self.v_z_div.set(data_transformation.get("z_div", "1"))
            
            # === RESTORE AXIS RANGES ===
            axis_ranges = session_data.get("axis_ranges", {})
            if axis_ranges:
                self.v_x_min.set(axis_ranges.get("x_min", ""))
                self.v_x_max.set(axis_ranges.get("x_max", ""))
                self.v_y_min.set(axis_ranges.get("y_min", ""))
                self.v_y_max.set(axis_ranges.get("y_max", ""))
                self.v_y2_min.set(axis_ranges.get("y2_min", ""))
                self.v_y2_max.set(axis_ranges.get("y2_max", ""))
                self.v_z_min.set(axis_ranges.get("z_min", ""))
                self.v_z_max.set(axis_ranges.get("z_max", ""))
                self.v_break_start.set(axis_ranges.get("break_start", ""))
                self.v_break_end.set(axis_ranges.get("break_end", ""))
            
            # === RESTORE AXIS BREAKS ===
            axis_breaks = session_data.get("axis_breaks", {})
            if axis_breaks:
                y_breaks = axis_breaks.get("y_breaks", [])
                for i, (s_var, e_var) in enumerate(self.v_y_breaks):
                    if i < len(y_breaks):
                        s_var.set(y_breaks[i][0] if y_breaks[i][0] else "")
                        e_var.set(y_breaks[i][1] if y_breaks[i][1] else "")
                x_breaks = axis_breaks.get("x_breaks", [])
                for i, (s_var, e_var) in enumerate(self.v_x_breaks):
                    if i < len(x_breaks):
                        s_var.set(x_breaks[i][0] if x_breaks[i][0] else "")
                        e_var.set(x_breaks[i][1] if x_breaks[i][1] else "")
            
            # === RESTORE PADDING ===
            padding = session_data.get("padding", {})
            if padding:
                self.v_x_pad.set(padding.get("x_pad", "4.0"))
                self.v_y_pad.set(padding.get("y_pad", "4.0"))
                self.v_y_broken_offset.set(padding.get("y_broken_offset", "-0.15"))
                self.v_z_pad.set(padding.get("z_pad", "10.0"))
            
            # === RESTORE TICK SETTINGS ===
            tick_settings = session_data.get("tick_settings", {})
            if tick_settings:
                self.v_x_maj.set(tick_settings.get("x_maj", ""))
                self.v_x_min_div.set(tick_settings.get("x_min_div", ""))
                self.v_x_tick_pad.set(tick_settings.get("x_tick_pad", "3.5"))
                self.v_y_maj.set(tick_settings.get("y_maj", ""))
                self.v_y_min_div.set(tick_settings.get("y_min_div", ""))
                self.v_y_tick_pad.set(tick_settings.get("y_tick_pad", "3.5"))
                self.v_y1_maj.set(tick_settings.get("y1_maj", ""))
                self.v_y1_min_div.set(tick_settings.get("y1_min_div", ""))
                self.v_y1_pad.set(tick_settings.get("y1_pad", "3.5"))
                self.v_y2_maj.set(tick_settings.get("y2_maj", ""))
                self.v_y2_min_div.set(tick_settings.get("y2_min_div", ""))
                self.v_y2_pad.set(tick_settings.get("y2_pad", "3.5"))
                self.v_z_maj.set(tick_settings.get("z_maj", ""))
                self.v_z_min_div.set(tick_settings.get("z_min_div", ""))
                self.v_z_tick_pad.set(tick_settings.get("z_tick_pad", "3.5"))
            
            # === RESTORE FONT SETTINGS ===
            font_settings = session_data.get("font_settings", {})
            if font_settings:
                self.v_font_fam.set(font_settings.get("font_family", "Arial"))
                self.v_t_size.set(font_settings.get("title_size", "14"))
                self.v_l_size.set(font_settings.get("label_size", "12"))
                self.v_xtick_size.set(font_settings.get("xtick_size", "10"))
                self.v_ytick_size.set(font_settings.get("ytick_size", "10"))
                self.v_x_not.set(font_settings.get("x_notation", "Scientific"))
                self.v_y_not.set(font_settings.get("y_notation", "Scientific"))
            
            # === RESTORE TICK APPEARANCE ===
            tick_appearance = session_data.get("tick_appearance", {})
            if tick_appearance:
                self.v_tick_dir_x.set(tick_appearance.get("tick_dir_x", "out"))
                self.v_tick_dir_y.set(tick_appearance.get("tick_dir_y", "out"))
                self.v_tick_dir_y2.set(tick_appearance.get("tick_dir_y2", "out"))
                self.v_tick_dir_z.set(tick_appearance.get("tick_dir_z", "out"))
                self.v_minor_tick_dir_x.set(tick_appearance.get("minor_tick_dir_x", "out"))
                self.v_minor_tick_dir_y.set(tick_appearance.get("minor_tick_dir_y", "out"))
                self.v_minor_tick_dir_y2.set(tick_appearance.get("minor_tick_dir_y2", "out"))
                self.v_minor_tick_dir_z.set(tick_appearance.get("minor_tick_dir_z", "out"))
                self.v_major_tick_length.set(tick_appearance.get("major_tick_length", "4.0"))
                self.v_minor_tick_length.set(tick_appearance.get("minor_tick_length", "2.0"))

            # === RESTORE TICK SIDE VISIBILITY ===
            tick_sides = session_data.get("tick_sides", {})
            if tick_sides:
                self.v_x_tick_bottom.set(tick_sides.get("x_tick_bottom", True))
                self.v_x_tick_top.set(tick_sides.get("x_tick_top", False))
                self.v_y_tick_left.set(tick_sides.get("y_tick_left", True))
                self.v_y_tick_right.set(tick_sides.get("y_tick_right", False))

            # === RESTORE GRID SETTINGS ===
            grid_settings = session_data.get("grid_settings", {})
            if grid_settings:
                self.show_major_grid.set(grid_settings.get("show_major_grid", True))
                self.show_minor_grid.set(grid_settings.get("show_minor_grid", False))
                self.v_grid_alpha.set(grid_settings.get("grid_alpha", "0.3"))
                self.v_grid_linestyle.set(grid_settings.get("grid_linestyle", "-"))
                self.v_grid_linewidth.set(grid_settings.get("grid_linewidth", "0.5"))

            # === RESTORE SECONDARY X-AXIS ===
            sec_x_settings = session_data.get("secondary_x_axis", {})
            if sec_x_settings:
                self.enable_secondary_x.set(sec_x_settings.get("enabled", False))
                self.v_sec_x_forward.set(sec_x_settings.get("forward", "x"))
                self.v_sec_x_inverse.set(sec_x_settings.get("inverse", "x"))
                self.v_sec_x_label.set(sec_x_settings.get("label", ""))
                self.v_sec_x_tick_size.set(sec_x_settings.get("tick_size", "10"))
                self.v_sec_x_maj.set(sec_x_settings.get("major_step", ""))
                self.v_sec_x_min_div.set(sec_x_settings.get("minor_divisions", ""))
                self.sec_x_label_color = sec_x_settings.get("label_color", "black")

            # === RESTORE PLOT SETTINGS ===
            plot_settings = session_data.get("plot_settings", {})
            if plot_settings:
                plot_type = plot_settings.get("plot_type", "Line")
                if plot_type in ["Line", "Scatter", "Broken Y-Axis", "Color Map", "Dual Y-Axis"]:
                    self.plot_type.set(plot_type)
                self.v_color_mode.set(plot_settings.get("color_mode", "Cycle"))
                self.v_cmap_name.set(plot_settings.get("colormap", "viridis"))
                self.show_grid.set(plot_settings.get("show_grid", True))
                self.x_log.set(plot_settings.get("x_log", False))
                self.y_log.set(plot_settings.get("y_log", False))
            
            # === RESTORE AXIS SELECTIONS ===
            axis_selections = session_data.get("axis_selections", {})
            if axis_selections:
                self.merge_cols_var.set(axis_selections.get("merge_cols", False))
                self.use_ref_x_var.set(axis_selections.get("use_ref_x", False))
                # Note: axis_ref_file, x_column, z_column, y1_column, y2_column 
                # will be restored after refresh_dataset_list populates the combos
            
            # Refresh UI to populate combos
            self.refresh_dataset_list(new_load=True)
            
            # === RESTORE AXIS SELECTIONS (after combos populated) ===
            if axis_selections:
                ref_file = axis_selections.get("axis_ref_file", "")
                if ref_file and ref_file in self.datasets:
                    self.axis_ref_combo.set(ref_file)
                    self.populate_column_selectors(None)
                
                x_col = axis_selections.get("x_column", "")
                if x_col and x_col in self.x_combo['values']:
                    self.x_combo.set(x_col)
                
                z_col = axis_selections.get("z_column", "")
                if z_col and z_col in self.z_combo['values']:
                    self.z_combo.set(z_col)
                
                # Restore Y listbox selections (for Line, Scatter, Broken Y-Axis, Color Map plots)
                y_columns = axis_selections.get("y_column", [])
                if y_columns:
                    self.y_listbox.selection_clear(0, tk.END)
                    for i in range(self.y_listbox.size()):
                        if self.y_listbox.get(i) in y_columns:
                            self.y_listbox.selection_set(i)
                
                y1_col = axis_selections.get("y1_column", "")
                if y1_col and y1_col in self.y1_combo['values']:
                    self.y1_combo.set(y1_col)
                
                y2_col = axis_selections.get("y2_column", "")
                if y2_col and y2_col in self.y2_combo['values']:
                    self.y2_combo.set(y2_col)
            
            # === RESTORE UI STATE ===
            ui_state = session_data.get("ui_state", {})
            if ui_state:
                selected_indices = ui_state.get("selected_datasets", [])
                self.dataset_listbox.selection_clear(0, tk.END)
                for idx in selected_indices:
                    if idx < self.dataset_listbox.size():
                        self.dataset_listbox.selection_set(idx)
            
            # Show info
            timestamp = session_data.get("timestamp", "Unknown")
            version = session_data.get("version", "1.0")
            
            restored_items = []
            if session_data.get("datasets"): restored_items.append("Datasets")
            if session_data.get("styles"): restored_items.append("Styles")
            if session_data.get("legend_order"): restored_items.append("Legend Order")
            if session_data.get("legend_settings"): restored_items.append("Legend Settings")
            if session_data.get("titles_labels"): restored_items.append("Titles & Labels")
            if session_data.get("data_transformation"): restored_items.append("Data Transformation")
            if session_data.get("axis_ranges"): restored_items.append("Axis Ranges")
            if session_data.get("tick_settings"): restored_items.append("Tick Settings")
            if session_data.get("font_settings"): restored_items.append("Font Settings")
            if session_data.get("plot_settings"): restored_items.append("Plot Settings")
            if session_data.get("axis_selections"): restored_items.append("Axis Selections")
            
            messagebox.showinfo("Session Loaded", 
                f"Session loaded successfully!\n\n"
                f"Version: {version}\n"
                f"Saved on: {timestamp}\n"
                f"Datasets: {len(self.datasets)}\n"
                f"Styles: {len(self.styles)}\n\n"
                f"Restored: {', '.join(restored_items)}")
            
            # Update plot with restored settings
            self.update_plot()
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load session:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = InteractivePlotter(root)
    root.mainloop()