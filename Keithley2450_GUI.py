import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import datetime
import pyvisa
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time

# Import your driver
from Instruments.keithley2450_with_add_ons import Keithley2450


class DeviceTab:
    """Encapsulates all controls and state for a single Keithley 2450 device"""
    
    def __init__(self, parent_notebook, device_name, main_app):
        self.main_app = main_app
        self.device_name = device_name
        self.inst = None
        self.stop_event = threading.Event()
        self.monitor_active = False
        self.lock = threading.Lock()
        
        # Data for graph
        self.data_x = []
        self.data_y = []
        
        # Create the main frame for this device tab
        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text=device_name)
        
        self._build_ui()
        
    def _build_ui(self):
        # Top frame for connection and status
        top_frame = ttk.Frame(self.frame)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        self._build_connection_frame(top_frame)
        self._build_status_dashboard(top_frame)
        
        self._build_config_tabs()
        self._build_monitor_area()
        self._build_console_log()
        
        # Start background poller for this device
        self.frame.after(2000, self._poll_instrument_status)
        
    def _build_connection_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Connection")
        frame.pack(fill="x", pady=5)
        
        ttk.Label(frame, text="VISA Address:").pack(side="left", padx=5)
        self.visa_combo = ttk.Combobox(frame, width=40, state="readonly")
        self.visa_combo.pack(side="left", padx=5)
        
        self.btn_scan = ttk.Button(frame, text="Scan", command=self.scan_instruments)
        self.btn_scan.pack(side="left", padx=5)
        
        self.btn_connect = ttk.Button(frame, text="Connect", command=self.connect_instrument)
        self.btn_connect.pack(side="left", padx=5)
        
        self.btn_reset = ttk.Button(frame, text="Hard Reset", command=self.reset_instrument, state="disabled")
        self.btn_reset.pack(side="left", padx=5)
        
    def _build_status_dashboard(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=5)
        
        self.lbl_output = ttk.Label(frame, text="OUTPUT: OFF", foreground="red", font=("Arial", 12, "bold"))
        self.lbl_output.pack(side="left", padx=20)
        
        self.lbl_terminals = ttk.Label(frame, text="TERMINALS: --", font=("Arial", 10))
        self.lbl_terminals.pack(side="left", padx=20)
        
    def _build_config_tabs(self):
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill="x", padx=10, pady=5)
        
        self.tab_manual = ttk.Frame(notebook)
        notebook.add(self.tab_manual, text="Manual Control")
        self._build_manual_control(self.tab_manual)
        
        self.tab_ramp = ttk.Frame(notebook)
        notebook.add(self.tab_ramp, text="Ramping & Sweep")
        self._build_ramping_control(self.tab_ramp)
        
        self.tab_sys = ttk.Frame(notebook)
        notebook.add(self.tab_sys, text="System Config")
        self._build_system_control(self.tab_sys)
        
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
        
        self.btn_output_toggle = ttk.Button(btn_frame, text="Toggle Output ON/OFF", command=self.toggle_output,
                                            state="disabled")
        self.btn_output_toggle.pack(side="left", padx=10)
        
    def _build_ramping_control(self, parent):
        frame = ttk.LabelFrame(parent, text="Linear Sweep (Ramp)")
        frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(frame, text="Target Level:").grid(row=0, column=0, padx=5)
        self.ent_ramp_target = ttk.Entry(frame, width=10)
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        
        ttk.Label(frame, text="Step Size:").grid(row=0, column=2, padx=5)
        self.ent_ramp_step = ttk.Entry(frame, width=10)
        self.ent_ramp_step.insert(0, "0.1")
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        
        ttk.Label(frame, text="Time/Step (s):").grid(row=0, column=4, padx=5)
        self.ent_ramp_time = ttk.Entry(frame, width=10)
        self.ent_ramp_time.insert(0, "0.1")
        self.ent_ramp_time.grid(row=0, column=5, padx=5)
        
        self.btn_start_ramp = ttk.Button(frame, text="Start Ramp", command=self.start_ramp, state="disabled")
        self.btn_start_ramp.grid(row=1, column=1, pady=10)
        
        self.btn_stop_ramp = ttk.Button(frame, text="ABORT", command=self.stop_ramp, state="disabled")
        self.btn_stop_ramp.grid(row=1, column=3, pady=10)
        
    def _build_system_control(self, parent):
        # Terminals
        frame_term = ttk.LabelFrame(parent, text="Terminals")
        frame_term.pack(fill="x", padx=10, pady=5)
        
        self.btn_front = ttk.Button(frame_term, text="Use Front", command=lambda: self.set_terminals("FRON"),
                                    state="disabled")
        self.btn_front.pack(side="left", padx=5, pady=5)
        
        self.btn_rear = ttk.Button(frame_term, text="Use Rear", command=lambda: self.set_terminals("REAR"),
                                   state="disabled")
        self.btn_rear.pack(side="left", padx=5, pady=5)
        
        # Wiring
        frame_wire = ttk.LabelFrame(parent, text="Sensing Mode")
        frame_wire.pack(fill="x", padx=10, pady=5)
        
        self.wire_var = tk.IntVar(value=2)
        ttk.Radiobutton(frame_wire, text="2-Wire", variable=self.wire_var, value=2, command=self.set_wiring).pack(
            side="left", padx=10)
        ttk.Radiobutton(frame_wire, text="4-Wire (Remote Sense)", variable=self.wire_var, value=4,
                        command=self.set_wiring).pack(side="left", padx=10)
        
    def _build_monitor_area(self):
        # Frame container
        frame = ttk.Frame(self.frame)
        frame.pack(fill="x", padx=10, pady=5)
        
        # Main Measurement Label
        self.lbl_measure_title = ttk.Label(frame, text="Measured Current:", font=("Arial", 12))
        self.lbl_measure_title.pack(side="left", padx=5)
        
        self.lbl_measure_val = ttk.Label(frame, text="-- A", font=("Consolas", 16, "bold"), foreground="blue")
        self.lbl_measure_val.pack(side="left", padx=5)
        
        self.btn_measure_now = ttk.Button(frame, text="MEASURE SINGLE POINT", command=self.measure_single_point,
                                          state="disabled")
        self.btn_measure_now.pack(side="right", padx=10)
        
        # --- GRAPH SETUP ---
        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=100)
        self.ax.set_title("I-V Curve")
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel("Current (A)")
        self.ax.grid(True)
        
        self.line_iv, = self.ax.plot([], [], '.-', color='blue', linewidth=1)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
    def _build_console_log(self):
        frame = ttk.LabelFrame(self.frame, text="System Log")
        frame.pack(fill="x", padx=10, pady=5, side="bottom")
        self.console = scrolledtext.ScrolledText(frame, height=6, state='disabled', font=("Consolas", 9))
        self.console.pack(fill="both", expand=True, padx=5, pady=5)
        
    def log_message(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        self.console.configure(state='normal')
        self.console.insert(tk.END, full_msg)
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        
    # --- Logic ---
    
    def scan_instruments(self):
        """Scan for available instruments - uses shared resources from main app"""
        self.log_message("Scanning for instruments...")
        resources = self.main_app.scan_all_instruments()
        self.visa_combo['values'] = resources
        if resources:
            self.visa_combo.current(0)
            self.log_message(f"Found {len(resources)} active instruments.")
        else:
            self.log_message("No active instruments found.")
            
    def update_available_resources(self, resources):
        """Update the combo box with new resources"""
        current = self.visa_combo.get()
        self.visa_combo['values'] = resources
        if current not in resources and resources:
            self.visa_combo.current(0)
        
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
            self.cb_meas_range['values'] = ["Auto", "1e-8", "1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3",
                                            "1"]  # I ranges
            
            self.lbl_measure_val.config(text="-- A")
            
        else:
            # SOURCE: Current, MEASURE: Voltage
            self.lbl_unit_level.config(text="A")
            self.lbl_unit_limit.config(text="V")
            self.lbl_src_range_txt.config(text="(Source I Range)")
            self.lbl_meas_range_txt.config(text="(Measure V Range)")
            self.lbl_measure_title.config(text="Measured Voltage:")
            
            self.cb_out_range['values'] = ["Auto", "1e-8", "1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3",
                                            "1"]  # I ranges
            self.cb_meas_range['values'] = ["Auto", "20e-3", "200e-3", "2", "20", "200"]  # V ranges
            
            self.lbl_measure_val.config(text="-- V")
            
    def connect_instrument(self):
        addr = self.visa_combo.get()
        if not addr:
            self.log_message("No address selected.")
            return
        
        self.log_message(f"Connecting to {addr}...")
        try:
            with self.lock:
                self.inst = Keithley2450(addr)
                if hasattr(self.inst, 'adapter'):
                    self.inst.adapter.connection.timeout = 10000
                    self.inst.adapter.connection.read_termination = '\n'
                    self.inst.adapter.connection.write_termination = '\n'
                    self.inst.adapter.connection.clear()
            
            for btn in [self.btn_reset, self.btn_apply, self.btn_output_toggle,
                        self.btn_start_ramp, self.btn_front, self.btn_rear, self.btn_measure_now]:
                btn.config(state="normal")
            
            self.log_message(f"Connected to {self.inst.name}")
            self._update_ui_labels()
            self.update_status_indicators()
            
        except Exception as e:
            self.inst = None
            messagebox.showerror("Connection Error", f"Failed:\n{str(e)}")
            self.log_message(f"Connection Failed: {str(e)}")
            
    def disconnect_instrument(self):
        """Disconnect from the current instrument"""
        if self.inst:
            try:
                with self.lock:
                    self.inst.disable_source()
                    self.inst.adapter.connection.close()
            except:
                pass
            self.inst = None
            
        for btn in [self.btn_reset, self.btn_apply, self.btn_output_toggle,
                    self.btn_start_ramp, self.btn_front, self.btn_rear, self.btn_measure_now]:
            btn.config(state="disabled")
            
        self.log_message("Disconnected.")
        self.lbl_output.config(text="OUTPUT: OFF", foreground="red")
        self.lbl_terminals.config(text="TERMINALS: --")
        
    def reset_instrument(self):
        if not self.inst:
            return
        with self.lock:
            try:
                self.inst.reset()
                self.inst.apply_voltage()
                self.log_message("Instrument Hard Reset.")
            except Exception as e:
                self.log_message(f"Reset Error: {e}")
                
    def toggle_output(self):
        if not self.inst:
            return
        with self.lock:
            time.sleep(0.1)
            try:
                if self.inst.source_enabled:
                    self.inst.disable_source()
                    self.log_message("Output -> OFF")
                else:
                    self.inst.enable_source()
                    self.log_message("Output -> ON")
            except Exception as e:
                self.log_message(f"Toggle Error: {e}")
                try:
                    self.inst.adapter.connection.clear()
                except:
                    pass
                    
        self.update_status_indicators()
        
    def update_status_indicators(self):
        pass  # Status is updated by poller
        
    def set_terminals(self, term):
        if not self.inst:
            return
        with self.lock:
            try:
                if term == "FRON":
                    self.inst.use_front_terminals()
                    self.log_message("Cmd: Terminals -> Front")
                else:
                    self.inst.use_rear_terminals()
                    self.log_message("Cmd: Terminals -> Rear")
            except Exception as e:
                self.log_message(f"Terminal Error: {e}")
                
    def set_wiring(self):
        if not self.inst:
            return
        with self.lock:
            try:
                # Get mode: 2 or 4
                mode = self.wire_var.get()
                
                # Convert to SCPI State: 4-wire -> "ON", 2-wire -> "OFF"
                state = "ON" if mode == 4 else "OFF"
                
                # 1. Enable for VOLTAGE (Crucial for Source V / Measure V remote sense)
                self.inst.write(f":SENS:VOLT:RSEN {state}")
                
                # 2. Enable for RESISTANCE (Matches your original driver logic)
                self.inst.write(f":SENS:RES:RSEN {state}")
                
                self.log_message(f"Cmd: Sensing -> {mode}-Wire (Set Volt & Res)")
            except Exception as e:
                self.log_message(f"Wiring Error: {e}")
                
    def apply_source(self):
        if not self.inst:
            return
        try:
            val = float(self.ent_level.get())
            limit = float(self.ent_limit.get())
            mode = self.source_mode_var.get()
            meas_range_str = self.meas_range_var.get()
            auto_meas = (meas_range_str == "Auto")
            
            with self.lock:
                if mode == "voltage":
                    # 1. Apply Source Voltage
                    self.inst.apply_voltage(compliance_current=limit)
                    self.inst.source_voltage = val
                    
                    if self.out_range_var.get() == "Auto":
                        self.inst.auto_range_source()
                    else:
                        self.inst.source_voltage_range = float(self.out_range_var.get())
                    
                    # 2. Configure MEASURE CURRENT
                    if auto_meas:
                        m_range = 1.05e-4  # Dummy value (ignored by auto_range=True)
                    else:
                        m_range = float(meas_range_str)
                    
                    self.inst.measure_current(nplc=1, current=m_range, auto_range=auto_meas)
                    
                else:  # mode == current
                    # 1. Apply Source Current
                    self.inst.apply_current(compliance_voltage=limit)
                    self.inst.source_current = val
                    
                    if self.out_range_var.get() == "Auto":
                        self.inst.auto_range_source()
                    else:
                        self.inst.source_current_range = float(self.out_range_var.get())
                    
                    # 2. Configure MEASURE VOLTAGE
                    if auto_meas:
                        m_range = 21.0  # Dummy value
                    else:
                        m_range = float(meas_range_str)
                    
                    self.inst.measure_voltage(nplc=1, voltage=m_range, auto_range=auto_meas)
                    
            self.log_message(f"Applied: {mode.upper()} Src={val}, Lim={limit}")
            self.update_status_indicators()
            
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numbers")
        except Exception as e:
            messagebox.showerror("Instrument Error", f"Command Failed:\n{str(e)}")
            
    def measure_single_point(self):
        if not self.inst:
            return
        
        # 1. Safety Check: Is Output ON?
        is_on = False
        with self.lock:
            try:
                is_on = self.inst.source_enabled
            except:
                pass
        
        if not is_on:
            self.log_message("Cannot measure: Output is OFF")
            messagebox.showwarning("Measure", "Please turn Output ON first.")
            return
        
        try:
            mode = self.source_mode_var.get()
            
            with self.lock:
                if mode == "voltage":
                    # --- MODE: Sourcing VOLTAGE, Measuring CURRENT ---
                    
                    # 1. Ask instrument what Voltage it is outputting
                    real_source_val = self.inst.source_voltage
                    
                    # 2. Ask instrument what Current it is reading
                    measured_val = self.inst.current
                    
                    # 3. Update the Display Label
                    self.lbl_measure_title.config(text="Status: [Source V] -> [Measure I]")
                    self.lbl_measure_val.config(text=f"Src: {real_source_val:.4f} V  |  Meas: {measured_val:.4e} A")
                    self.log_message(f"Reading: {real_source_val:.4f} V -> {measured_val:.4e} A")
                    
                else:
                    # --- MODE: Sourcing CURRENT, Measuring VOLTAGE ---
                    
                    # 1. Ask instrument what Current it is outputting
                    real_source_val = self.inst.source_current
                    
                    # 2. Ask instrument what Voltage it is reading
                    measured_val = self.inst.voltage
                    
                    # 3. Update the Display Label
                    self.lbl_measure_title.config(text="Status: [Source I] -> [Measure V]")
                    self.lbl_measure_val.config(text=f"Src: {real_source_val:.4e} A  |  Meas: {measured_val:.4f} V")
                    self.log_message(f"Reading: {real_source_val:.4e} A -> {measured_val:.4f} V")
                    
        except Exception as e:
            self.log_message(f"Measure Error: {e}")
            
    def _poll_instrument_status(self):
        if self.inst:
            if self.lock.acquire(blocking=False):
                try:
                    is_on = self.inst.source_enabled
                    self.lbl_output.config(text=f"OUTPUT: {'ON' if is_on else 'OFF'}",
                                           foreground="green" if is_on else "red")
                    
                    raw_term = self.inst.check_terminals()
                    term = raw_term.strip() if raw_term else "--"
                    self.lbl_terminals.config(text=f"TERMINALS: {term}")
                except Exception:
                    pass
                finally:
                    self.lock.release()
                    
        self.frame.after(2000, self._poll_instrument_status)
        
    # --- Ramping Logic ---
    
    def start_ramp(self):
        if not self.inst:
            return
        
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid Ramp Parameters")
            return
        
        self.log_message(f"Starting Ramp -> {target}...")
        self.stop_event.clear()
        self.btn_stop_ramp.config(state="normal")
        self.btn_start_ramp.config(state="disabled")
        
        self.data_x = []
        self.data_y = []
        self.monitor_active = True
        
        self.ax.relim()
        self.ax.autoscale_view()
        
        t = threading.Thread(target=self._run_ramp_thread, args=(target, step, time_step))
        t.start()
        
    def stop_ramp(self):
        self.stop_event.set()
        self.log_message("Ramp Abort Requested.")
        
    def _ramp_callback(self, meas_v, meas_i):
        mode = self.source_mode_var.get()
        if mode == "voltage":
            # X = Voltage (Source), Y = Current (Measure)
            self.data_x.append(meas_v)
            self.data_y.append(meas_i)
        else:
            # X = Current (Source), Y = Voltage (Measure)
            self.data_x.append(meas_i)
            self.data_y.append(meas_v)
            
        self.frame.after(1, self._update_graph)
        return self.stop_event.is_set()
    
    def _update_graph(self):
        mode = self.source_mode_var.get()
        
        self.line_iv.set_data(self.data_x, self.data_y)
        
        if mode == "voltage":
            self.ax.set_xlabel("Voltage (V)")
            self.ax.set_ylabel("Current (A)")
            self.ax.set_title("I-V Curve (Source: V)")
            if self.data_y:
                self.lbl_measure_val.config(text=f"{self.data_y[-1]:.4e} A")
        else:
            self.ax.set_xlabel("Current (A)")
            self.ax.set_ylabel("Voltage (V)")
            self.ax.set_title("V-I Curve (Source: I)")
            if self.data_y:
                self.lbl_measure_val.config(text=f"{self.data_y[-1]:.4f} V")
                
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()
        
    def _run_ramp_thread(self, target, step, time_step):
        try:
            with self.lock:
                self.inst.enable_source()
                
            self.inst.voltage_ramping_with_monitor(target, step, time_step, callback=self._ramp_callback)
            self.log_message("Ramp Completed.")
        except Exception as e:
            self.log_message(f"Ramp Error: {e}")
        finally:
            self.monitor_active = False
            self.frame.after(1, lambda: self.btn_stop_ramp.config(state="disabled"))
            self.frame.after(1, lambda: self.btn_start_ramp.config(state="normal"))
            
    def cleanup(self):
        """Clean up resources when tab is closed"""
        self.stop_event.set()
        self.disconnect_instrument()
        plt.close(self.fig)


class KeithleyControllerApp:
    """Main application that manages multiple device tabs"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 Master Controller - Multi-Device")
        self.root.geometry("1300x950")
        
        self.device_tabs = []
        self.device_counter = 0
        self.cached_resources = []
        
        # --- Main UI ---
        self._build_main_ui()
        
        # Auto-scan on startup
        self.scan_all_instruments()
        
        # Add first device tab
        self.add_device_tab()
        
    def _build_main_ui(self):
        # Top toolbar for managing devices
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
        
        # Notebook for device tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
    def add_device_tab(self):
        """Add a new device tab"""
        self.device_counter += 1
        device_name = f"Device {self.device_counter}"
        
        device_tab = DeviceTab(self.notebook, device_name, self)
        self.device_tabs.append(device_tab)
        
        # Update the combo box with cached resources
        if self.cached_resources:
            device_tab.update_available_resources(self.cached_resources)
            
        self._update_device_count()
        self.notebook.select(device_tab.frame)
        
    def remove_current_tab(self):
        """Remove the currently selected device tab"""
        if len(self.device_tabs) <= 1:
            messagebox.showwarning("Warning", "Cannot remove the last device tab.")
            return
            
        current_idx = self.notebook.index(self.notebook.select())
        device_tab = self.device_tabs[current_idx]
        
        # Confirm disconnect if connected
        if device_tab.inst:
            if not messagebox.askyesno("Confirm", f"Disconnect and remove {device_tab.device_name}?"):
                return
                
        # Cleanup and remove
        device_tab.cleanup()
        self.device_tabs.remove(device_tab)
        self.notebook.forget(current_idx)
        self._update_device_count()
        
    def scan_all_instruments(self):
        """Scan for all available VISA resources"""
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
            
            # Update all device tabs
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
    app = KeithleyControllerApp(root)
    root.mainloop()