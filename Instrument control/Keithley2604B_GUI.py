import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import datetime
import pyvisa
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import numpy as np

# Import your 2604B driver
from Instruments.keithley2604B import Keithley2604B


class SMUChannelUI:
    """Encapsulates the UI and control logic for a single SMU channel (A or B)"""
    
    def __init__(self, parent_notebook, channel_name, main_app, device_tab):
        self.main_app = main_app
        self.device_tab = device_tab  # Parent device tab (holds the lock and inst)
        self.channel_name = channel_name.lower() # "smua" or "smub"
        self.channel_obj = None # Will point to inst.smua or inst.smub
        
        self.stop_event = threading.Event()
        self.monitor_active = False
        
        # Data for graph
        self.data_x = []
        self.data_y = []
        
        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text=channel_name.upper())
        
        self._build_ui()
        
    def _build_ui(self):
        # Top status area for this specific SMU
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_output = ttk.Label(status_frame, text="OUTPUT: OFF", foreground="red", font=("Arial", 12, "bold"))
        self.lbl_output.pack(side="left", padx=5)
        
        # Split into Left (Controls) and Right (Monitor)
        content_frame = ttk.Frame(self.frame)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side="left", fill="y", padx=(0, 5))
        
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self._build_config_tabs(left_panel)
        self._build_monitor_area(right_panel)
        
    def _build_config_tabs(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        
        self.tab_manual = ttk.Frame(notebook)
        notebook.add(self.tab_manual, text="Manual Control")
        self._build_manual_control(self.tab_manual)
        
        self.tab_ramp = ttk.Frame(notebook)
        notebook.add(self.tab_ramp, text="Ramping & Sweep")
        self._build_ramping_control(self.tab_ramp)
        
    def _build_manual_control(self, parent):
        frame = ttk.LabelFrame(parent, text="Source & Measure Configuration")
        frame.pack(fill="x", padx=10, pady=10)
        
        # Row 0: Mode
        ttk.Label(frame, text="Source Mode:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.source_mode_var = tk.StringVar(value="voltage")
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(mode_frame, text="Voltage", variable=self.source_mode_var, value="voltage",
                        command=self._update_ui_labels).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Current", variable=self.source_mode_var, value="current",
                        command=self._update_ui_labels).pack(side="left")
        
        # Row 1: Output Range
        ttk.Label(frame, text="Output Range:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.out_range_var = tk.StringVar(value="Auto")
        self.cb_out_range = ttk.Combobox(frame, textvariable=self.out_range_var, width=15)
        self.cb_out_range.grid(row=1, column=1, padx=5, sticky="w")
        self.lbl_src_range_txt = ttk.Label(frame, text="(Source V Range)")
        self.lbl_src_range_txt.grid(row=1, column=2, sticky="w")
        
        # Row 2: Source Level
        ttk.Label(frame, text="Output Source Level:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.ent_level = ttk.Entry(frame, width=17)
        self.ent_level.insert(0, "0.0")
        self.ent_level.grid(row=2, column=1, padx=5, sticky="w")
        self.lbl_unit_level = ttk.Label(frame, text="V")
        self.lbl_unit_level.grid(row=2, column=2, sticky="w")
        
        # Row 3: Compliance
        ttk.Label(frame, text="Limit (Compliance):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.ent_limit = ttk.Entry(frame, width=17)
        self.ent_limit.insert(0, "0.01")
        self.ent_limit.grid(row=3, column=1, padx=5, sticky="w")
        self.lbl_unit_limit = ttk.Label(frame, text="A")
        self.lbl_unit_limit.grid(row=3, column=2, sticky="w")
        
        # Row 4: Measure Range
        ttk.Label(frame, text="Measurement Range:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.meas_range_var = tk.StringVar(value="Auto")
        self.cb_meas_range = ttk.Combobox(frame, textvariable=self.meas_range_var, width=15)
        self.cb_meas_range.grid(row=4, column=1, padx=5, sticky="w")
        self.lbl_meas_range_txt = ttk.Label(frame, text="(Measure I Range)")
        self.lbl_meas_range_txt.grid(row=4, column=2, sticky="w")
        
        # Row 5: Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=4, pady=15)
        
        self.btn_apply = ttk.Button(btn_frame, text="APPLY CONFIGURATION", command=self.apply_source, state="disabled")
        self.btn_apply.pack(side="left", padx=10)
        
        self.btn_output_toggle = ttk.Button(btn_frame, text="Toggle Output ON/OFF", command=self.toggle_output, state="disabled")
        self.btn_output_toggle.pack(side="left", padx=10)

    def _build_ramping_control(self, parent):
        frame = ttk.LabelFrame(parent, text="Linear Sweep (Ramp)")
        frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(frame, text="Target Level:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_ramp_target = ttk.Entry(frame, width=10)
        self.ent_ramp_target.insert(0, "1.0")
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        
        ttk.Label(frame, text="Step Size:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.ent_ramp_step = ttk.Entry(frame, width=10)
        self.ent_ramp_step.insert(0, "0.1")
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        
        ttk.Label(frame, text="Time/Step (s):").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.ent_ramp_time = ttk.Entry(frame, width=10)
        self.ent_ramp_time.insert(0, "0.1")
        self.ent_ramp_time.grid(row=0, column=5, padx=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=6, pady=10)
        
        self.btn_start_ramp = ttk.Button(btn_frame, text="Start Ramp", command=self.start_ramp, state="disabled")
        self.btn_start_ramp.pack(side="left", padx=5)
        
        self.btn_stop_ramp = ttk.Button(btn_frame, text="ABORT", command=self.stop_ramp, state="disabled")
        self.btn_stop_ramp.pack(side="left", padx=5)

    def _build_monitor_area(self, parent):
        frame = ttk.LabelFrame(parent, text="Monitor & Graph")
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        top_bar = ttk.Frame(frame)
        top_bar.pack(fill="x", padx=5, pady=5)
        
        self.lbl_measure_title = ttk.Label(top_bar, text="Measured Current:", font=("Arial", 11))
        self.lbl_measure_title.pack(side="left", padx=5)
        
        self.lbl_measure_val = ttk.Label(top_bar, text="-- A", font=("Consolas", 14, "bold"), foreground="blue")
        self.lbl_measure_val.pack(side="left", padx=15)
        
        self.btn_measure_now = ttk.Button(top_bar, text="MEASURE SINGLE POINT", command=self.measure_single_point, state="disabled")
        self.btn_measure_now.pack(side="right", padx=5)
        
        # Graph
        self.fig, self.ax = plt.subplots(figsize=(5, 3), dpi=100)
        self.ax.set_title(f"I-V Curve ({self.channel_name.upper()})")
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel("Current (A)")
        self.ax.grid(True)
        
        self.line_iv, = self.ax.plot([], [], '.-', color='blue', linewidth=1)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    def _update_ui_labels(self):
        """Updates UI labels to reflect the current Source/Measure logic"""
        mode = self.source_mode_var.get()
        if mode == "voltage":
            # SOURCE: Voltage, MEASURE: Current
            self.lbl_unit_level.config(text="V")
            self.lbl_unit_limit.config(text="A")
            self.lbl_src_range_txt.config(text="(Source V Range)")
            self.lbl_meas_range_txt.config(text="(Measure I Range)")
            self.lbl_measure_title.config(text="Measured Current:")
            
            self.cb_out_range['values'] = ["Auto", "20e-3", "200e-3", "2", "20", "200"]  # V ranges
            self.cb_meas_range['values'] = ["Auto", "1e-8", "1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3", "1"]  # I ranges
            
            self.lbl_measure_val.config(text="-- A")
            
        else:
            # SOURCE: Current, MEASURE: Voltage
            self.lbl_unit_level.config(text="A")
            self.lbl_unit_limit.config(text="V")
            self.lbl_src_range_txt.config(text="(Source I Range)")
            self.lbl_meas_range_txt.config(text="(Measure V Range)")
            self.lbl_measure_title.config(text="Measured Voltage:")
            
            self.cb_out_range['values'] = ["Auto", "1e-8", "1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3", "1"]  # I ranges
            self.cb_meas_range['values'] = ["Auto", "20e-3", "200e-3", "2", "20", "200"]  # V ranges
            
            self.lbl_measure_val.config(text="-- V")

    def connect_channel(self, inst):
        """Called by parent DeviceTab when instrument connects"""
        self.channel_obj = inst.smua if self.channel_name == "smua" else inst.smub
        
        for btn in [self.btn_apply, self.btn_output_toggle, self.btn_start_ramp, self.btn_measure_now]:
            btn.config(state="normal")
        self._update_ui_labels()

    def disconnect_channel(self):
        if self.channel_obj:
            try:
                with self.device_tab.lock:
                    self.channel_obj.output_off()
            except:
                pass
        self.channel_obj = None
        for btn in [self.btn_apply, self.btn_output_toggle, self.btn_start_ramp, self.btn_measure_now]:
            btn.config(state="disabled")
        self.lbl_output.config(text="OUTPUT: OFF", foreground="red")

    def apply_source(self):
        if not self.channel_obj:
            return
        try:
            val = float(self.ent_level.get())
            limit = float(self.ent_limit.get())
            mode = self.source_mode_var.get()
            meas_range_str = self.meas_range_var.get()
            auto_meas = (meas_range_str == "Auto")
            
            with self.device_tab.lock:
                if mode == "voltage":
                    # 1. Configure Source Voltage
                    self.channel_obj.configure_voltage_source(voltage=val, current_limit=limit)
                    
                    # Apply output range
                    if self.out_range_var.get() == "Auto":
                        # Use auto range - set to a reasonable default or let instrument auto-range
                        pass
                    else:
                        out_range = float(self.out_range_var.get())
                        self.channel_obj._w(f"source.rangev = {out_range}")
                    
                    # 2. Configure MEASURE CURRENT range
                    if auto_meas:
                        # Auto range - let instrument handle it
                        pass
                    else:
                        m_range = float(meas_range_str)
                        self.channel_obj._w(f"measure.rangei = {m_range}")
                    
                else:  # mode == "current"
                    # 1. Configure Source Current
                    self.channel_obj.configure_current_source(current=val, voltage_limit=limit)
                    
                    # Apply output range
                    if self.out_range_var.get() == "Auto":
                        pass
                    else:
                        out_range = float(self.out_range_var.get())
                        self.channel_obj._w(f"source.rangei = {out_range}")
                    
                    # 2. Configure MEASURE VOLTAGE range
                    if auto_meas:
                        pass
                    else:
                        m_range = float(meas_range_str)
                        self.channel_obj._w(f"measure.rangev = {m_range}")
                    
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Applied: {mode.upper()} Src={val}, Lim={limit}")
            
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numbers")
        except Exception as e:
            messagebox.showerror("Instrument Error", f"Command Failed:\n{str(e)}")
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Config Error: {e}")

    def toggle_output(self):
        if not self.channel_obj:
            return
        with self.device_tab.lock:
            time.sleep(0.1)
            try:
                is_on = self.channel_obj.is_output_on()
                if is_on:
                    self.channel_obj.output_off()
                    self.device_tab.log_message(f"[{self.channel_name.upper()}] Output -> OFF")
                else:
                    self.channel_obj.output_on()
                    self.device_tab.log_message(f"[{self.channel_name.upper()}] Output -> ON")
            except Exception as e:
                self.device_tab.log_message(f"[{self.channel_name.upper()}] Toggle Error: {e}")
                try:
                    # Try to clear any instrument errors
                    pass
                except:
                    pass

    def measure_single_point(self):
        if not self.channel_obj:
            return
        
        # 1. Safety Check: Is Output ON?
        is_on = False
        with self.device_tab.lock:
            try:
                is_on = self.channel_obj.is_output_on()
            except:
                pass
        
        if not is_on:
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Cannot measure: Output is OFF")
            messagebox.showwarning("Measure", f"Please turn {self.channel_name.upper()} Output ON first.")
            return
        
        try:
            mode = self.source_mode_var.get()
            
            with self.device_tab.lock:
                if mode == "voltage":
                    # --- MODE: Sourcing VOLTAGE, Measuring CURRENT ---
                    
                    # 1. Ask instrument what Voltage it is outputting
                    real_source_val = self.channel_obj.measure__voltage()
                    
                    # 2. Ask instrument what Current it is reading
                    measured_val = self.channel_obj.measure__current()
                    
                    # 3. Update the Display Label
                    self.lbl_measure_title.config(text=f"Status: [Source V] -> [Measure I]")
                    self.lbl_measure_val.config(text=f"Src: {real_source_val:.4f} V  |  Meas: {measured_val:.4e} A")
                    self.device_tab.log_message(f"[{self.channel_name.upper()}] Reading: {real_source_val:.4f} V -> {measured_val:.4e} A")
                    
                else:
                    # --- MODE: Sourcing CURRENT, Measuring VOLTAGE ---
                    
                    # 1. Ask instrument what Current it is outputting
                    real_source_val = self.channel_obj.measure__current()
                    
                    # 2. Ask instrument what Voltage it is reading
                    measured_val = self.channel_obj.measure__voltage()
                    
                    # 3. Update the Display Label
                    self.lbl_measure_title.config(text=f"Status: [Source I] -> [Measure V]")
                    self.lbl_measure_val.config(text=f"Src: {real_source_val:.4e} A  |  Meas: {measured_val:.4f} V")
                    self.device_tab.log_message(f"[{self.channel_name.upper()}] Reading: {real_source_val:.4e} A -> {measured_val:.4f} V")
                    
        except Exception as e:
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Measure Error: {e}")

    def start_ramp(self):
        if not self.channel_obj:
            return
        
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid Ramp Parameters")
            return
        
        self.device_tab.log_message(f"[{self.channel_name.upper()}] Starting Ramp -> {target}...")
        self.stop_event.clear()
        self.btn_stop_ramp.config(state="normal")
        self.btn_start_ramp.config(state="disabled")
        
        self.data_x = []
        self.data_y = []
        self.monitor_active = True
        
        self.ax.relim()
        self.ax.autoscale_view()
        
        mode = self.source_mode_var.get()
        
        # We run the ramp loop in a separate thread so we can plot data dynamically
        t = threading.Thread(target=self._run_custom_ramp_thread, args=(mode, target, step, time_step))
        t.start()

    def stop_ramp(self):
        self.stop_event.set()
        self.device_tab.log_message(f"[{self.channel_name.upper()}] Ramp Abort Requested.")

    def _run_custom_ramp_thread(self, mode, target, step, time_step):
        try:
            with self.device_tab.lock:
                if mode == "voltage":
                    start_val = self.channel_obj.measure__voltage()
                else:
                    start_val = self.channel_obj.measure__current()
                
                self.channel_obj.output_on()
            
            # Calculate number of steps based on step size
            total_diff = abs(target - start_val)
            num_steps = max(2, int(total_diff / step) + 1)
            
            for val in np.linspace(start_val, target, num_steps):
                if self.stop_event.is_set():
                    break
                    
                with self.device_tab.lock:
                    if mode == "voltage":
                        self.channel_obj._w(f"source.levelv = {val}")
                        time.sleep(time_step)
                        meas_v = self.channel_obj.measure__voltage()
                        meas_i = self.channel_obj.measure__current()
                    else:
                        self.channel_obj._w(f"source.leveli = {val}")
                        time.sleep(time_step)
                        meas_v = self.channel_obj.measure__voltage()
                        meas_i = self.channel_obj.measure__current()
                
                # Update Graph Data Arrays
                if mode == "voltage":
                    self.data_x.append(meas_v)
                    self.data_y.append(meas_i)
                else:
                    self.data_x.append(meas_i)
                    self.data_y.append(meas_v)
                
                self.frame.after(1, self._update_graph)
                
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Ramp Completed/Stopped.")
        except Exception as e:
            self.device_tab.log_message(f"[{self.channel_name.upper()}] Ramp Error: {e}")
        finally:
            self.monitor_active = False
            self.frame.after(1, lambda: self.btn_stop_ramp.config(state="disabled"))
            self.frame.after(1, lambda: self.btn_start_ramp.config(state="normal"))

    def _update_graph(self):
        mode = self.source_mode_var.get()
        
        self.line_iv.set_data(self.data_x, self.data_y)
        
        if mode == "voltage":
            self.ax.set_xlabel("Voltage (V)")
            self.ax.set_ylabel("Current (A)")
            self.ax.set_title(f"I-V Curve ({self.channel_name.upper()}, Source: V)")
            if self.data_y:
                self.lbl_measure_val.config(text=f"{self.data_y[-1]:.4e} A")
        else:
            self.ax.set_xlabel("Current (A)")
            self.ax.set_ylabel("Voltage (V)")
            self.ax.set_title(f"V-I Curve ({self.channel_name.upper()}, Source: I)")
            if self.data_y:
                self.lbl_measure_val.config(text=f"{self.data_y[-1]:.4f} V")
                
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()


class DeviceTab:
    """Encapsulates connection and both SMU channels for a single 2604B device"""
    
    def __init__(self, parent_notebook, device_name, main_app):
        self.main_app = main_app
        self.device_name = device_name
        self.inst = None
        
        # Lock for thread-safe VISA operations to this instrument
        self.lock = threading.Lock()
        
        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text=device_name)
        
        self._build_ui()
        self.frame.after(2000, self._poll_instrument_status)
        
    def _build_ui(self):
        # Top frame for connection
        top_frame = ttk.LabelFrame(self.frame, text="Instrument Connection")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(top_frame, text="VISA Address:").pack(side="left", padx=5)
        self.visa_combo = ttk.Combobox(top_frame, width=35, state="readonly")
        self.visa_combo.pack(side="left", padx=5)
        
        self.btn_scan = ttk.Button(top_frame, text="Scan", command=self.scan_instruments)
        self.btn_scan.pack(side="left", padx=5)
        
        self.btn_connect = ttk.Button(top_frame, text="Connect", command=self.connect_instrument)
        self.btn_connect.pack(side="left", padx=5)
        
        self.btn_reset = ttk.Button(top_frame, text="Hard Reset", command=self.reset_instrument, state="disabled")
        self.btn_reset.pack(side="left", padx=5)
        
        # Middle Notebook for SMU A and SMU B
        self.smu_notebook = ttk.Notebook(self.frame)
        self.smu_notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.smua_ui = SMUChannelUI(self.smu_notebook, "smua", self.main_app, self)
        self.smub_ui = SMUChannelUI(self.smu_notebook, "smub", self.main_app, self)
        
        # Bottom Console Log
        log_frame = ttk.LabelFrame(self.frame, text="System Log")
        log_frame.pack(fill="x", padx=10, pady=5, side="bottom")
        self.console = scrolledtext.ScrolledText(log_frame, height=5, state='disabled', font=("Consolas", 9))
        self.console.pack(fill="both", expand=True, padx=5, pady=5)
        
    def log_message(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        self.console.configure(state='normal')
        self.console.insert(tk.END, full_msg)
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        
    def scan_instruments(self):
        self.log_message("Scanning for instruments...")
        resources = self.main_app.scan_all_instruments()
        self.update_available_resources(resources)
            
    def update_available_resources(self, resources):
        current = self.visa_combo.get()
        self.visa_combo['values'] = resources
        if current not in resources and resources:
            self.visa_combo.current(0)
            
    def connect_instrument(self):
        addr = self.visa_combo.get()
        if not addr:
            self.log_message("No address selected.")
            return
        
        self.log_message(f"Connecting to {addr}...")
        try:
            with self.lock:
                self.inst = Keithley2604B(addr)
                idn = self.inst.get_idn()
            
            self.btn_reset.config(state="normal")
            self.log_message(f"Connected: {idn}")
            
            # Hook up individual channel tabs
            self.smua_ui.connect_channel(self.inst)
            self.smub_ui.connect_channel(self.inst)
            
        except Exception as e:
            self.inst = None
            messagebox.showerror("Connection Error", f"Failed:\n{str(e)}")
            self.log_message(f"Connection Failed: {str(e)}")

    def disconnect_instrument(self):
        """Disconnect from the current instrument"""
        if self.inst:
            self.smua_ui.disconnect_channel()
            self.smub_ui.disconnect_channel()
            try:
                with self.lock:
                    self.inst.close()
            except:
                pass
            self.inst = None
        self.btn_reset.config(state="disabled")
        self.log_message("Disconnected.")
        
    def reset_instrument(self):
        if not self.inst:
            return
        with self.lock:
            try:
                self.inst.reset()
                self.log_message("Instrument Hard Reset.")
                # Reset UI states as SMUs are turned off by reset
                self.smua_ui.disconnect_channel()
                self.smub_ui.disconnect_channel()
                # Re-establish connections internally
                self.smua_ui.connect_channel(self.inst)
                self.smub_ui.connect_channel(self.inst)
            except Exception as e:
                self.log_message(f"Reset Error: {e}")

    def _poll_instrument_status(self):
        if self.inst:
            if self.lock.acquire(blocking=False):
                try:
                    # Poll SMU A
                    on_a = self.inst.smua.is_output_on()
                    self.smua_ui.lbl_output.config(text=f"OUTPUT: {'ON' if on_a else 'OFF'}", 
                                                   foreground="green" if on_a else "red")
                    # Poll SMU B
                    on_b = self.inst.smub.is_output_on()
                    self.smub_ui.lbl_output.config(text=f"OUTPUT: {'ON' if on_b else 'OFF'}", 
                                                   foreground="green" if on_b else "red")
                except Exception:
                    pass
                finally:
                    self.lock.release()
                    
        self.frame.after(2000, self._poll_instrument_status)

    def cleanup(self):
        self.smua_ui.stop_event.set()
        self.smub_ui.stop_event.set()
        self.disconnect_instrument()
        plt.close(self.smua_ui.fig)
        plt.close(self.smub_ui.fig)


class Keithley2604BApp:
    """Main application managing multiple device connections"""
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2604B Dual-SMU Controller")
        self.root.geometry("1300x950")
        
        self.device_tabs = []
        self.device_counter = 0
        self.cached_resources = []
        
        self._build_main_ui()
        self.scan_all_instruments()
        self.add_device_tab()
        
    def _build_main_ui(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=10, pady=5)
        
        self.btn_add_device = ttk.Button(toolbar, text="+ Add Device Tab", command=self.add_device_tab)
        self.btn_add_device.pack(side="left", padx=5)
        
        self.btn_remove_device = ttk.Button(toolbar, text="- Remove Current Tab", command=self.remove_current_tab)
        self.btn_remove_device.pack(side="left", padx=5)
        
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        
        self.btn_scan_all = ttk.Button(toolbar, text="Scan All Instruments", command=self.scan_all_instruments)
        self.btn_scan_all.pack(side="left", padx=5)
        
        self.lbl_device_count = ttk.Label(toolbar, text="Devices: 0", font=("Arial", 10))
        self.lbl_device_count.pack(side="right", padx=10)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
    def add_device_tab(self):
        self.device_counter += 1
        device_name = f"2604B Device {self.device_counter}"
        
        device_tab = DeviceTab(self.notebook, device_name, self)
        self.device_tabs.append(device_tab)
        
        if self.cached_resources:
            device_tab.update_available_resources(self.cached_resources)
            
        self._update_device_count()
        self.notebook.select(device_tab.frame)
        
    def remove_current_tab(self):
        if len(self.device_tabs) <= 1:
            messagebox.showwarning("Warning", "Cannot remove the last device tab.")
            return
            
        current_idx = self.notebook.index(self.notebook.select())
        device_tab = self.device_tabs[current_idx]
        
        if device_tab.inst:
            if not messagebox.askyesno("Confirm", f"Disconnect and remove {device_tab.device_name}?"):
                return
                
        device_tab.cleanup()
        self.device_tabs.remove(device_tab)
        self.notebook.forget(current_idx)
        self._update_device_count()
        
    def scan_all_instruments(self):
        print("Scanning for instruments...")
        try:
            rm = pyvisa.ResourceManager()
            raw_resources = rm.list_resources()
            live_resources = []
            for r in raw_resources:
                try:
                    inst = rm.open_resource(r, open_timeout=100)
                    inst.close()
                    live_resources.append(r)
                except:
                    pass
            self.cached_resources = live_resources
            
            for device_tab in self.device_tabs:
                device_tab.update_available_resources(live_resources)
            print(f"Found {len(live_resources)} active instruments.")
            return live_resources
        except Exception as e:
            print(f"Scan Error: {e}")
            return []
            
    def _update_device_count(self):
        self.lbl_device_count.config(text=f"Devices: {len(self.device_tabs)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = Keithley2604BApp(root)
    root.mainloop()