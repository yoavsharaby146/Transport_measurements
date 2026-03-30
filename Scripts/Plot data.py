import matplotlib

matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import polars as pl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import numpy as np
from scipy.interpolate import griddata
import sys
import json
import os
from datetime import datetime

# Import colormaps for the gradient feature
from matplotlib import cm


class InteractivePlotter:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive CSV Plotter (Fixed & Enhanced)")

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

        # --- COLOR SETTINGS (NEW) ---
        self.v_color_mode = tk.StringVar(value="Cycle")  # "Cycle" or "Gradient"
        self.v_cmap_name = tk.StringVar(value="viridis")
        self.available_cmaps = [
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
        self.v_break_start = tk.StringVar()
        self.v_break_end = tk.StringVar()

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
        self.legend_draggable = tk.BooleanVar(value=True)
        self.legend_position = tk.StringVar(value="Best")

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

        # --- CACHE SETTINGS ---
        self.cache_folder = None  # User-selected folder for cache files
        
        # --- LEGEND ORDER ---
        self.legend_order = []  # List of (filename, column) tuples in desired order - persists across selections
        
        # --- LINE VISIBILITY STATE ---
        self.line_visibility = {}  # (filename, column) -> bool for toggling lines via legend
        self.current_lines = []  # Store current plot lines for legend toggle
        
        # --- DATASET WINDOW ---
        self.dataset_window = None

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
        canvas_scroll.bind_all("<MouseWheel>", lambda e: canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        plot_frame = ttk.Frame(main_container)
        main_container.add(plot_frame)

        # === Control Panel ===
        row = 0
        ttk.Label(control_frame, text="DATA FILES", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=4,
                                                                                     sticky='w', pady=(0, 5))
        row += 1
        ttk.Button(control_frame, text="Load CSV File(s)", command=self.load_files).grid(row=row, column=0,
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

        # --- NEW: Color Controls (Gradient Feature) ---
        ttk.Label(control_frame, text="Color Mode:").grid(row=row, column=0, sticky='w')
        c_mode = ttk.Combobox(control_frame, textvariable=self.v_color_mode, values=["Cycle", "Gradient"],
                              state='readonly', width=10)
        c_mode.grid(row=row, column=1, sticky='ew', padx=2)
        c_mode.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

        c_map = ttk.Combobox(control_frame, textvariable=self.v_cmap_name, values=self.available_cmaps,
                             state='readonly', width=12)
        c_map.grid(row=row, column=2, columnspan=2, sticky='ew', padx=2)
        c_map.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        row += 1
        # --------------------------------------------

        ttk.Button(control_frame, text="Configure Styles", command=self.open_style_dialog).grid(row=row, column=0,
                                                                                                columnspan=4,
                                                                                                sticky='ew', pady=5)
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

        # --- CLEANED BUTTONS (Removed 'Chinese' characters) ---
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
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)

        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.ax.text(0.5, 0.5, 'Load CSV file(s) to begin', ha='center', va='center', fontsize=16, color='gray')
        self.ax.set_xticks([]);
        self.ax.set_yticks([])
        self.canvas.draw()

    # --- DIALOG BUILDERS (FIXED FONTS) ---

    def open_ranges_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Ranges & Data Transformation")
        d.geometry("450x700")
        d.transient(self.root)
        frame = ttk.Frame(d, padding=10)
        frame.pack(fill='both', expand=True)

        # FIX: Changed font='bold' to font=('Arial', 10, 'bold')
        ttk.Label(frame, text="Data Transformation (Divide by)", font=('Arial', 10, 'bold')).pack(pady=5)

        def add_entry(txt, var):
            f = ttk.Frame(frame)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=15).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')

        add_entry("Divide X:", self.v_x_div)
        add_entry("Divide Y:", self.v_y_div)
        add_entry("Divide Y2:", self.v_y2_div)
        add_entry("Divide Z:", self.v_z_div)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Axis Ranges", font=('Arial', 10, 'bold')).pack(pady=5)

        add_entry("X Min:", self.v_x_min)
        add_entry("X Max:", self.v_x_max)
        add_entry("Y Min:", self.v_y_min)
        add_entry("Y Max:", self.v_y_max)
        add_entry("Z Min (Color):", self.v_z_min)
        add_entry("Z Max (Color):", self.v_z_max)

        ttk.Label(frame, text="Broken Axis:", foreground="blue").pack(pady=(5, 0))
        add_entry("Break Start:", self.v_break_start)
        add_entry("Break End:", self.v_break_end)
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        add_entry("Y2 Min:", self.v_y2_min)
        add_entry("Y2 Max:", self.v_y2_max)

        ttk.Button(frame, text="Reset Ranges", command=self.reset_ranges).pack(pady=10)
        ttk.Button(frame, text="Update Plot", command=self.update_plot).pack(pady=5)

    def open_labels_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Labels, Titles & Colors")
        d.geometry("450x850")
        d.transient(self.root)
        frame = ttk.Frame(d, padding=10)
        frame.pack(fill='both', expand=True)

        def add_entry(txt, var):
            f = ttk.Frame(frame)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=15).pack(side='left')
            ttk.Entry(f, textvariable=var).pack(side='right', expand=True, fill='x')

        # FIX: Font bug
        ttk.Label(frame, text="Text Content", font=('Arial', 10, 'bold')).pack(pady=5)
        add_entry("Plot Title:", self.v_title)
        add_entry("X Label:", self.v_xlabel)
        add_entry("Y Label:", self.v_ylabel)
        add_entry("Y2 Label:", self.v_y2label)
        add_entry("Z Label (Color):", self.v_zlabel)
        add_entry("Legend (csv):", self.v_legend)
        ttk.Checkbutton(frame, text="Show Legend", variable=self.show_legend).pack(pady=2)
        ttk.Checkbutton(frame, text="Show Grid", variable=self.show_grid).pack(pady=2)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Label Spacing (Padding)", font=('Arial', 10, 'bold')).pack(pady=5)
        add_entry("X Pad:", self.v_x_pad)
        add_entry("Y Pad:", self.v_y_pad)
        add_entry("Y Broken Offset:", self.v_y_broken_offset)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Label Colors", font=('Arial', 10, 'bold')).pack(pady=5)

        def choose_col(attr, btn):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                setattr(self, attr, c)
                btn.config(bg=c)
                d.lift()

        def add_col(txt, attr, default):
            f = ttk.Frame(frame)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt, width=15).pack(side='left')
            b = tk.Button(f, text=" ", bg=default, width=10)
            b.config(command=lambda: choose_col(attr, b))
            b.pack(side='right')

        add_col("Title Color:", "title_color", self.title_color)
        add_col("X Label Color:", "xlabel_color", self.xlabel_color)
        add_col("Y Label Color:", "ylabel_color", self.ylabel_color)
        add_col("Z Label Color:", "zlabel_color", self.zlabel_color)
        add_col("X Tick Color:", "xtick_color", self.xtick_color)
        add_col("Y Tick Color:", "ytick_color", self.ytick_color)
        
        # --- LEGEND SETTINGS ---
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Legend Settings", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Legend columns
        col_frame = ttk.Frame(frame)
        col_frame.pack(fill='x', pady=2)
        ttk.Label(col_frame, text="Legend Columns:", width=15).pack(side='left')
        col_combo = ttk.Combobox(col_frame, textvariable=self.legend_columns, 
                                  values=["1", "2", "3", "4", "5", "6", "7", "8"], width=10, state='readonly')
        col_combo.pack(side='right')
        
        # Legend position
        pos_frame = ttk.Frame(frame)
        pos_frame.pack(fill='x', pady=2)
        ttk.Label(pos_frame, text="Position:", width=15).pack(side='left')
        pos_combo = ttk.Combobox(pos_frame, textvariable=self.legend_position,
                                  values=["Best", "Upper Right", "Upper Left", "Lower Right", "Lower Left",
                                          "Center Left", "Center Right", "Lower Center", "Upper Center", "Center",
                                          "Outside Right", "Outside Bottom"],
                                  width=18, state='readonly')
        pos_combo.pack(side='right')
        
        # Draggable checkbox
        ttk.Checkbutton(frame, text="Draggable Legend (click & drag to reposition)", 
                        variable=self.legend_draggable).pack(pady=5)
        
        ttk.Button(frame, text="Update Plot", command=self.update_plot).pack(pady=10)

    def open_ticks_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Ticks & Fonts")
        d.geometry("450x550")
        d.transient(self.root)
        frame = ttk.Frame(d, padding=10)
        frame.pack(fill='both', expand=True)

        # FIX: Font bug
        ttk.Label(frame, text="Tick Control", font=('Arial', 10, 'bold')).pack(pady=5)

        gf = ttk.Frame(frame)
        gf.pack(fill='x')
        # FIX: Font bug in grid headers
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

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Notation", font=('Arial', 10, 'bold')).pack(pady=5)
        f_not = ttk.Frame(frame)
        f_not.pack(fill='x')
        ttk.Label(f_not, text="X Notation:").pack(side='left')
        xn = ttk.Combobox(f_not, textvariable=self.v_x_not, values=["Scientific", "Plain", "Engineering"], width=15,
                          state='readonly')
        xn.pack(side='left', padx=5)
        ttk.Label(f_not, text="Y Notation:").pack(side='left')
        yn = ttk.Combobox(f_not, textvariable=self.v_y_not, values=["Scientific", "Plain", "Engineering"], width=15,
                          state='readonly')
        yn.pack(side='left', padx=5)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame, text="Font Settings", font=('Arial', 10, 'bold')).pack(pady=5)
        f_fam = ttk.Frame(frame)
        f_fam.pack(fill='x', pady=2)
        ttk.Label(f_fam, text="Font Family:").pack(side='left')
        ttk.Combobox(f_fam, textvariable=self.v_font_fam,
                     values=["Arial", "Times New Roman", "Courier New", "Calibri", "DejaVu Sans"], width=25).pack(
            side='right')

        def add_sz(txt, var):
            f = ttk.Frame(frame)
            f.pack(fill='x', pady=2)
            ttk.Label(f, text=txt).pack(side='left')
            ttk.Entry(f, textvariable=var, width=10).pack(side='right')

        add_sz("Title Size:", self.v_t_size)
        add_sz("Axis Label Size:", self.v_l_size)
        add_sz("Legend Size:", self.v_leg_size)
        add_sz("X Tick Size:", self.v_xtick_size)
        add_sz("Y Tick Size:", self.v_ytick_size)
        ttk.Button(frame, text="Update Plot", command=self.update_plot).pack(pady=10)

    # --- MAIN LOGIC ---
    def load_files(self):
        filenames = filedialog.askopenfilenames(title="Select CSV file(s)",
                                                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filenames: return
        for filepath in filenames:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                header_line = 0
                for i, line in enumerate(lines[:50]):
                    if 'time(s)' in line.lower(): header_line = i; break
                
                # Count how many trailing lines to skip (metadata, comments, empty lines)
                skip_footer = 0
                header_cols = len(lines[header_line].split(','))
                
                # Check from the end of file for problematic lines
                for i in range(len(lines) - 1, header_line, -1):
                    line = lines[i].strip()
                    # Skip empty lines
                    if not line:
                        skip_footer += 1
                        continue
                    # Skip comment/metadata lines starting with ; or #
                    if line.startswith(';') or line.startswith('#'):
                        skip_footer += 1
                        continue
                    # Skip lines with different column count
                    line_cols = len(line.split(','))
                    if line_cols != header_cols:
                        skip_footer += 1
                        continue
                    # Found a valid data line, stop checking
                    break
                
                # Read CSV, skipping footer if metadata detected
                # Use truncate_ragged_lines=True to handle inconsistent column counts
                # Use ignore_errors=True to skip rows with parsing issues
                if skip_footer > 0:
                    # Read all data except trailing problematic lines
                    df = pl.read_csv(
                        filepath, 
                        skip_rows=header_line, 
                        n_rows=len(lines) - header_line - skip_footer,
                        truncate_ragged_lines=True,
                        ignore_errors=True
                    )
                else:
                    df = pl.read_csv(
                        filepath, 
                        skip_rows=header_line,
                        truncate_ragged_lines=True,
                        ignore_errors=True
                    )
                
                filename = filepath.split('/')[-1]
                self.datasets[filename] = df
            except Exception as e:
                messagebox.showerror("Error", str(e))
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

        d = tk.Toplevel(self.root);
        d.title("Style Config");
        d.geometry("700x400");
        d.transient(self.root)
        cv = tk.Canvas(d);
        sb = ttk.Scrollbar(d, orient="vertical", command=cv.yview)
        fr = ttk.Frame(cv);
        fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=fr, anchor="nw");
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True);
        sb.pack(side="right", fill="y")

        ttk.Label(fr, text="Series").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(fr, text="Color").grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(fr, text="Width").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(fr, text="Type").grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(fr, text="Legend").grid(row=0, column=4, padx=5, pady=5)
        r = 1

        def pick_c(btn, k):
            c = colorchooser.askcolor(parent=d)[1]
            if c:
                if k not in self.styles: self.styles[k] = {}
                self.styles[k]['color'] = c;
                btn.config(bg=c);
                d.lift()

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

        for fk, yc in pairs_to_style:
            k = (fk, yc);
            st = self.styles.get(k, {})
            c = st.get('color', '#d3d3d3')
            w = st.get('width', 2.0);
            ls = st.get('linestyle', '-')
            ttk.Label(fr, text=f"{fk}\n{yc}").grid(row=r, column=0, padx=5, sticky='w')
            btn = tk.Button(fr, text=" ", bg=c, width=5)
            btn.config(command=lambda b=btn, k=k: pick_c(b, k))
            btn.grid(row=r, column=1)
            wv = tk.StringVar(value=str(w))
            wv.trace("w", lambda n, i, m, v=wv, k=k: up_w(v.get(), k))
            ttk.Entry(fr, textvariable=wv, width=6).grid(row=r, column=2)
            lsb = ttk.Combobox(fr, values=['-', '--', '-.', ':', 'None'], width=5, state='readonly')
            lsb.set(ls);
            lsb.bind("<<ComboboxSelected>>", lambda e, b=lsb, k=k: up_ls(b.get(), k))
            lsb.grid(row=r, column=3);
            # Legend entry field
            leg_val = tk.StringVar(value=st.get('legend', ''))
            leg_entry = ttk.Entry(fr, textvariable=leg_val, width=15)
            leg_entry.grid(row=r, column=4, padx=5)
            leg_val.trace("w", lambda n, i, m, v=leg_val, k=k: up_leg(v, k))
            r += 1
        ttk.Button(d, text="Apply", command=lambda: [self.update_plot(), d.destroy()]).pack(pady=10)

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
        
        # Create dialog
        d = tk.Toplevel(self.root)
        d.title("Legend Order")
        d.geometry("400x450")
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
        
        # Apply/Cancel buttons
        bottom_frame = ttk.Frame(frame)
        bottom_frame.pack(fill='x', pady=(10, 0))
        
        def apply_order():
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
            d.destroy()
        
        def apply_and_keep():
            # Merge current_order with existing legend_order
            new_order = []
            added_keys = set()
            
            # First, preserve items from existing legend_order that aren't in current selection
            for key in self.legend_order:
                if key not in pairs_to_order:
                    new_order.append(key)
                    added_keys.add(key)
            
            # Then, add items from current_order
            for key in current_order:
                if key not in added_keys:
                    new_order.append(key)
                    added_keys.add(key)
            
            self.legend_order = new_order
            self.update_plot()
        
        ttk.Button(bottom_frame, text="Apply", command=apply_order).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(bottom_frame, text="Apply & Keep Open", command=apply_and_keep).pack(side='left', expand=True, fill='x', padx=2)
        ttk.Button(bottom_frame, text="Cancel", command=d.destroy).pack(side='left', expand=True, fill='x', padx=2)

    def update_plot(self):
        sel_ds = self.get_selected_datasets()
        if not sel_ds or self.current_dataset_key is None: return
        self.fig.clear()

        def val(var, default=None, type_fn=float):
            try:
                return type_fn(var.get())
            except:
                return default

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

                    for ax_t in target_axes:
                        if "Scatter" in ptype:
                            ln = ax_t.scatter(X_plot, Y_plot, label=lbl, color=c, s=w, alpha=0.6)
                        else:
                            ln, = ax_t.plot(X_plot, Y_plot, label=lbl, color=c, linewidth=w, linestyle=ls)
                        if ax_t == target_axes[0]:
                            lines.append(ln);
                            labels.append(lbl)
                            if ptype == "Dual Y-Axis": ax_t.tick_params(axis='y', labelcolor=c)
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
                                    cmap='seismic', vmin=z_min_val, vmax=z_max_val)
                self.ax.set_ylabel(self.v_ylabel.get() or ycols[0], fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color)
                cbar = self.fig.colorbar(im, ax=self.ax)
                cbar.set_label(self.v_zlabel.get() or self.z_combo.get(), fontsize=l_sz, labelpad=z_lab_pad,
                               fontname=font, color=self.zlabel_color)
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

            for ax_curr in axes_list:
                if not self.x_log.get():
                    apply_format(ax_curr, 'x', self.v_x_not.get())
                    if x_maj: ax_curr.xaxis.set_major_locator(ticker.MultipleLocator(x_maj))
                    if x_min > 1: ax_curr.xaxis.set_minor_locator(ticker.AutoMinorLocator(x_min))
                ax_curr.tick_params(axis='x', labelsize=xt_sz, pad=x_pad_val, labelcolor=self.xtick_color)

                if ptype != "Dual Y-Axis":
                    ax_curr.tick_params(axis='y', labelsize=yt_sz, pad=y_pad_val, labelcolor=self.ytick_color)
                    if not self.y_log.get() and ptype != "Color Map":
                        apply_format(ax_curr, 'y', self.v_y_not.get())
                        if y_maj: ax_curr.yaxis.set_major_locator(ticker.MultipleLocator(y_maj))
                        if y_min > 1: ax_curr.yaxis.set_minor_locator(ticker.AutoMinorLocator(y_min))

            target_ax = axes_list[-1] if ptype == "Broken Y-Axis" else self.ax
            if self.x_log.get() and ptype != "Color Map":
                target_ax.set_xscale('log')
                if ptype == "Broken Y-Axis": axes_list[0].set_xscale('log')

            target_ax.set_xlabel(self.v_xlabel.get() or xcol, fontsize=l_sz, labelpad=x_lab_pad, fontname=font,
                                 color=self.xlabel_color)
            (axes_list[0] if ptype == "Broken Y-Axis" else self.ax).set_title(self.v_title.get(), fontsize=t_sz,
                                                                              fontweight='bold', fontname=font,
                                                                              color=self.title_color)

            if val(self.v_x_min): target_ax.set_xlim(left=val(self.v_x_min))
            if val(self.v_x_max): target_ax.set_xlim(right=val(self.v_x_max))
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
            elif ptype == "Dual Y-Axis":
                # Set Y1 (left axis) label
                y1_label = self.v_ylabel.get() or (ycols[0] if ycols else "Y1")
                self.ax.set_ylabel(y1_label, fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color)
                # Set Y2 (right axis) label
                y2_label = self.v_y2label.get() or (ycols[1] if len(ycols) > 1 else "Y2")
                axes_list[1].set_ylabel(y2_label, fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                        color=self.ylabel_color)
                # Set Y1 axis range
                if val(self.v_y_min): self.ax.set_ylim(bottom=val(self.v_y_min))
                if val(self.v_y_max): self.ax.set_ylim(top=val(self.v_y_max))
                # Set Y2 axis range
                if val(self.v_y2_min): axes_list[1].set_ylim(bottom=val(self.v_y2_min))
                if val(self.v_y2_max): axes_list[1].set_ylim(top=val(self.v_y2_max))
            elif ptype != "Color Map":
                self.ax.set_ylabel(self.v_ylabel.get() or "Values", fontsize=l_sz, labelpad=y_lab_pad, fontname=font,
                                   color=self.ylabel_color)
                if val(self.v_y_min): self.ax.set_ylim(bottom=val(self.v_y_min))
                if val(self.v_y_max): self.ax.set_ylim(top=val(self.v_y_max))

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
                
                # Make legend draggable if enabled
                if self.legend_draggable.get():
                    legend.set_draggable(True)
                
                # Connect pick event for legend toggle (click on legend to hide/show lines)
                self.canvas.mpl_connect('pick_event', self.on_legend_pick)
                legend.set_picker(10)  # Set pick radius for legend

            if self.show_grid.get():
                for a in axes_list: a.grid(True, alpha=0.3)

            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            print(f"Error plotting: {e}")
            messagebox.showerror("Plot Error", str(e))

    def reset_ranges(self):
        for v in [self.v_x_min, self.v_x_max, self.v_y_min, self.v_y_max, self.v_y2_min, self.v_y2_max, self.v_z_min,
                  self.v_z_max, self.v_break_start, self.v_break_end]:
            v.set("")
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
                "version": "2.0",  # Version for future compatibility
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
            session_data["axis_selections"] = {
                "axis_ref_file": self.axis_ref_combo.get(),
                "x_column": self.x_combo.get(),
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
        
        self.dataset_window = tk.Toplevel(self.root)
        self.dataset_window.title("Dataset Manager")
        self.dataset_window.geometry("500x600")
        self.dataset_window.transient(self.root)
        
        frame = ttk.Frame(self.dataset_window, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Load buttons at top
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text="Load CSV File(s)", command=self.load_files).pack(side='left', padx=2)
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

    def on_legend_pick(self, event):
        """Handle click on legend to toggle line visibility."""
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
        
        # Find clicked legend item
        for i, text in enumerate(legend.get_texts()):
            bbox = text.get_window_extent()
            if bbox.contains(mouseevent.x, mouseevent.y):
                # Toggle visibility of corresponding line
                if i < len(self.current_lines):
                    line = self.current_lines[i]
                    visible = line.get_visible()
                    line.set_visible(not visible)
                    
                    # Fade/unfade legend text
                    if visible:
                        text.set_alpha(0.3)
                    else:
                        text.set_alpha(1.0)
                    
                    self.canvas.draw()
                break

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