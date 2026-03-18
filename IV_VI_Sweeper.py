import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import time
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import threading

# Set backend
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Import Keithley driver
try:
    from Instruments.keithley2450_with_add_ons import Keithley2450
except ImportError:
    print("\nCRITICAL ERROR: Could not import Keithley2450.")
    print("Make sure 'Instruments/keithley2450_with_add_ons.py' exists.\n")


class IVVISweeperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 - IV/VI Sweeper with Gate")
        
        # Two instruments: Bias (sweep) and Gate
        self.bias_inst = None
        self.gate_inst = None
        self.stop_event = threading.Event()
        self.gate_stop_event = threading.Event()
        
        # Saved parameters for persistence
        self.saved_params = {
            # IV sweep (voltage source)
            'iv_sp1': "1000",
            'iv_sp2': "-1000", 
            'iv_step': "10",
            'iv_delay': "0.01",
            'iv_compliance': "1e-6",
            # VI sweep (current source)
            'vi_sp1': "1e-6",
            'vi_sp2': "-1e-6",
            'vi_step': "1e-7",
            'vi_delay': "0.01",
            'vi_compliance': "1",
            # Gate settings
            'gate_voltage': "0",
            'gate_step': "10",
            'gate_delay': "0.05",
            'gate_compliance': "1e-6",
            # Common
            'save_dir': "",
        }
        
        self._build_ui()
        self.refresh_instruments()
        
    def _build_ui(self):
        # Main container with grid configuration for resizing
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill="both", expand=True)
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # === 1. CONNECTION SECTION ===
        conn_frame = ttk.LabelFrame(self.main_frame, text="1. Instrument Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)
        
        # Bias instrument row
        ttk.Label(conn_frame, text="Bias Sweeper:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.bias_combo = ttk.Combobox(conn_frame, width=35)
        self.bias_combo.grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        self.btn_connect_bias = ttk.Button(conn_frame, text="Connect", command=self.connect_bias, width=10)
        self.btn_connect_bias.grid(row=0, column=3, padx=5, pady=2)
        
        # Bias status indicators
        self.btn_bias_term = tk.Button(conn_frame, text="Term: ---", bg="#e0e0e0", width=10,
                                        command=self.toggle_bias_terminals)
        self.btn_bias_term.grid(row=0, column=4, padx=5, pady=2)
        
        self.btn_bias_output = tk.Button(conn_frame, text="Out: ---", bg="#e0e0e0", width=10,
                                          command=self.toggle_bias_output)
        self.btn_bias_output.grid(row=0, column=5, padx=5, pady=2)
        
        # Gate instrument row
        ttk.Label(conn_frame, text="Gate Source:").grid(row=1, column=1, padx=5, pady=2, sticky="e")
        self.gate_combo = ttk.Combobox(conn_frame, width=35)
        self.gate_combo.grid(row=1, column=2, padx=5, pady=2, sticky="ew")
        self.btn_connect_gate = ttk.Button(conn_frame, text="Connect", command=self.connect_gate, width=10)
        self.btn_connect_gate.grid(row=1, column=3, padx=5, pady=2)
        
        # Gate status indicators
        self.btn_gate_term = tk.Button(conn_frame, text="Term: ---", bg="#e0e0e0", width=10,
                                        command=self.toggle_gate_terminals)
        self.btn_gate_term.grid(row=1, column=4, padx=5, pady=2)
        
        self.btn_gate_output = tk.Button(conn_frame, text="Out: ---", bg="#e0e0e0", width=10,
                                          command=self.toggle_gate_output)
        self.btn_gate_output.grid(row=1, column=5, padx=5, pady=2)
        
        # Common buttons
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.grid(row=2, column=0, columnspan=6, pady=5)
        
        self.btn_scan = ttk.Button(btn_frame, text="Scan Instruments", command=self.refresh_instruments)
        self.btn_scan.pack(side="left", padx=10)
        
        self.btn_reset_bias = ttk.Button(btn_frame, text="Reset Bias", command=self.reset_bias)
        self.btn_reset_bias.pack(side="left", padx=10)
        
        self.btn_reset_gate = ttk.Button(btn_frame, text="Reset Gate", command=self.reset_gate)
        self.btn_reset_gate.pack(side="left", padx=10)
        
        self.btn_refresh_status = ttk.Button(btn_frame, text="Refresh Status", command=self.refresh_all_status)
        self.btn_refresh_status.pack(side="left", padx=10)
        
        # === 2. GATE CONTROL SECTION ===
        gate_frame = ttk.LabelFrame(self.main_frame, text="2. Gate Voltage Control", padding=10)
        gate_frame.pack(fill="x", pady=5)
        
        # Gate voltage settings
        ttk.Label(gate_frame, text="Target (V):").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.ent_gate_voltage = ttk.Entry(gate_frame, width=12)
        self.ent_gate_voltage.insert(0, self.saved_params['gate_voltage'])
        self.ent_gate_voltage.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(gate_frame, text="Step (mV):").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        self.ent_gate_step = ttk.Entry(gate_frame, width=10)
        self.ent_gate_step.insert(0, self.saved_params['gate_step'])
        self.ent_gate_step.grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(gate_frame, text="Delay (s):").grid(row=0, column=4, padx=5, pady=2, sticky="e")
        self.ent_gate_delay = ttk.Entry(gate_frame, width=10)
        self.ent_gate_delay.insert(0, self.saved_params['gate_delay'])
        self.ent_gate_delay.grid(row=0, column=5, padx=5, pady=2)
        
        ttk.Label(gate_frame, text="Compliance (A):").grid(row=0, column=6, padx=5, pady=2, sticky="e")
        self.ent_gate_compliance = ttk.Entry(gate_frame, width=12)
        self.ent_gate_compliance.insert(0, self.saved_params['gate_compliance'])
        self.ent_gate_compliance.grid(row=0, column=7, padx=5, pady=2)
        
        # Gate control buttons
        gate_btn_frame = ttk.Frame(gate_frame)
        gate_btn_frame.grid(row=1, column=0, columnspan=8, pady=5)
        
        self.btn_gate_ramp = ttk.Button(gate_btn_frame, text="Ramp Gate Voltage", command=self.start_gate_ramp)
        self.btn_gate_ramp.pack(side="left", padx=10)
        
        self.btn_gate_abort = ttk.Button(gate_btn_frame, text="Abort Ramp", command=self.abort_gate_ramp, state="disabled")
        self.btn_gate_abort.pack(side="left", padx=10)
        
        self.btn_gate_measure = ttk.Button(gate_btn_frame, text="Measure Once", command=self.measure_gate_once)
        self.btn_gate_measure.pack(side="left", padx=10)
        
        # Gate monitor display
        self.lbl_gate_status = ttk.Label(gate_btn_frame, text="Gate: --- V | --- A", font=("Consolas", 10))
        self.lbl_gate_status.pack(side="left", padx=20)
        
        # === 3. MEASUREMENT TYPE SELECTION ===
        type_frame = ttk.LabelFrame(self.main_frame, text="3. Measurement Type", padding=10)
        type_frame.pack(fill="x", pady=5)
        
        self.sweep_type_var = tk.StringVar(value="iv")
        
        type_inner = ttk.Frame(type_frame)
        type_inner.pack()
        
        ttk.Radiobutton(type_inner, text="IV Sweep (Source Voltage → Measure Current)", 
                        variable=self.sweep_type_var, value="iv",
                        command=self._update_ui_labels).pack(side="left", padx=20)
        ttk.Radiobutton(type_inner, text="VI Sweep (Source Current → Measure Voltage)", 
                        variable=self.sweep_type_var, value="vi",
                        command=self._update_ui_labels).pack(side="left", padx=20)
        
        # === 4. SWEEP CONFIGURATION ===
        config_frame = ttk.LabelFrame(self.main_frame, text="4. Sweep Configuration", padding=10)
        config_frame.pack(fill="x", pady=5)
        
        # Grid configuration for resizing
        for i in range(8):
            config_frame.columnconfigure(i, weight=1)
        
        # Row 0: Sp1 and Sp2
        ttk.Label(config_frame, text="Sp1:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_sp1 = ttk.Entry(config_frame, width=15)
        self.ent_sp1.insert(0, self.saved_params['iv_sp1'])
        self.ent_sp1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(config_frame, text="Sp2:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.ent_sp2 = ttk.Entry(config_frame, width=15)
        self.ent_sp2.insert(0, self.saved_params['iv_sp2'])
        self.ent_sp2.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        # Row 1: Step and Delay
        ttk.Label(config_frame, text="Step:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ent_step = ttk.Entry(config_frame, width=15)
        self.ent_step.insert(0, self.saved_params['iv_step'])
        self.ent_step.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(config_frame, text="Delay (s):").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.ent_delay = ttk.Entry(config_frame, width=15)
        self.ent_delay.insert(0, self.saved_params['iv_delay'])
        self.ent_delay.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        
        # Row 2: Compliance
        self.lbl_compliance = ttk.Label(config_frame, text="Compliance (A):")
        self.lbl_compliance.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.ent_compliance = ttk.Entry(config_frame, width=15)
        self.ent_compliance.insert(0, self.saved_params['iv_compliance'])
        self.ent_compliance.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # Row 3: Save directory
        ttk.Label(config_frame, text="Save Directory:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.ent_dir = ttk.Entry(config_frame)
        self.ent_dir.insert(0, self.saved_params['save_dir'])
        self.ent_dir.grid(row=3, column=1, columnspan=5, padx=5, pady=5, sticky="ew")
        
        self.btn_browse = ttk.Button(config_frame, text="Browse...", command=self.browse_directory)
        self.btn_browse.grid(row=3, column=6, padx=5, pady=5)
        
        # Row 4: Include Gate Data checkbox
        self.include_gate_var = tk.BooleanVar(value=True)
        self.chk_include_gate = ttk.Checkbutton(config_frame, text="Include Gate Data in Filename/Title", 
                                                  variable=self.include_gate_var)
        self.chk_include_gate.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        
        # Unit labels (will be updated based on sweep type)
        self.lbl_sp1_unit = ttk.Label(config_frame, text="mV")
        self.lbl_sp1_unit.grid(row=0, column=1, sticky="e", padx=5)
        self.lbl_sp2_unit = ttk.Label(config_frame, text="mV")
        self.lbl_sp2_unit.grid(row=0, column=3, sticky="e", padx=5)
        self.lbl_step_unit = ttk.Label(config_frame, text="mV")
        self.lbl_step_unit.grid(row=1, column=1, sticky="e", padx=5)
        
        # === 5. EXECUTION ===
        exec_frame = ttk.LabelFrame(self.main_frame, text="5. Execution", padding=10)
        exec_frame.pack(fill="x", pady=5)
        
        btn_inner = ttk.Frame(exec_frame)
        btn_inner.pack(pady=5)
        
        self.btn_run = ttk.Button(btn_inner, text="RUN SWEEP", command=self.start_sweep, width=15)
        self.btn_run.pack(side="left", padx=20)
        
        self.btn_abort = ttk.Button(btn_inner, text="ABORT SWEEP", command=self.abort_sweep, width=12, state="disabled")
        self.btn_abort.pack(side="left", padx=20)
        
        # Progress label
        self.lbl_progress = ttk.Label(exec_frame, text="Ready", font=("Arial", 10))
        self.lbl_progress.pack(pady=5)
        
        # === 6. LOG ===
        log_frame = ttk.LabelFrame(self.main_frame, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=6, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        
        # Initialize UI labels
        self._update_ui_labels()
        
    def _update_ui_labels(self):
        """Update UI labels based on sweep type"""
        sweep_type = self.sweep_type_var.get()
        
        if sweep_type == "iv":
            # IV: Source Voltage, Measure Current
            self.lbl_compliance.config(text="Compliance (A):")
            self.lbl_sp1_unit.config(text="mV")
            self.lbl_sp2_unit.config(text="mV")
            self.lbl_step_unit.config(text="mV")
            
            # Update entry fields with saved IV params
            self.ent_sp1.delete(0, tk.END)
            self.ent_sp1.insert(0, self.saved_params['iv_sp1'])
            self.ent_sp2.delete(0, tk.END)
            self.ent_sp2.insert(0, self.saved_params['iv_sp2'])
            self.ent_step.delete(0, tk.END)
            self.ent_step.insert(0, self.saved_params['iv_step'])
            self.ent_delay.delete(0, tk.END)
            self.ent_delay.insert(0, self.saved_params['iv_delay'])
            self.ent_compliance.delete(0, tk.END)
            self.ent_compliance.insert(0, self.saved_params['iv_compliance'])
            
        else:
            # VI: Source Current, Measure Voltage
            self.lbl_compliance.config(text="Compliance (V):")
            self.lbl_sp1_unit.config(text="A")
            self.lbl_sp2_unit.config(text="A")
            self.lbl_step_unit.config(text="A")
            
            # Update entry fields with saved VI params
            self.ent_sp1.delete(0, tk.END)
            self.ent_sp1.insert(0, self.saved_params['vi_sp1'])
            self.ent_sp2.delete(0, tk.END)
            self.ent_sp2.insert(0, self.saved_params['vi_sp2'])
            self.ent_step.delete(0, tk.END)
            self.ent_step.insert(0, self.saved_params['vi_step'])
            self.ent_delay.delete(0, tk.END)
            self.ent_delay.insert(0, self.saved_params['vi_delay'])
            self.ent_compliance.delete(0, tk.END)
            self.ent_compliance.insert(0, self.saved_params['vi_compliance'])
    
    def log(self, message):
        """Thread-safe logging"""
        self.root.after(0, self._log_internal, message)
        
    def _log_internal(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
    # === INSTRUMENT MANAGEMENT ===
    
    def refresh_instruments(self):
        """Scan for available VISA resources"""
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
            self.bias_combo['values'] = resources
            self.gate_combo['values'] = resources
            if resources:
                self.log(f"Found {len(resources)} instrument(s)")
            else:
                self.log("No instruments found")
        except Exception as e:
            self.log(f"Scan error: {e}")
            
    def connect_bias(self):
        """Connect to Bias instrument"""
        addr = self.bias_combo.get()
        if not addr:
            messagebox.showerror("Error", "No Bias address selected")
            return
            
        try:
            self.bias_inst = Keithley2450(addr)
            if hasattr(self.bias_inst, 'adapter'):
                self.bias_inst.adapter.connection.timeout = 10000
                self.bias_inst.adapter.connection.read_termination = '\n'
                self.bias_inst.adapter.connection.write_termination = '\n'
            
            self.log(f"Bias connected: {addr}")
            self.update_bias_status()
            
        except Exception as e:
            self.bias_inst = None
            messagebox.showerror("Connection Error", f"Failed to connect Bias:\n{e}")
            self.log(f"Bias connection failed: {e}")
            
    def connect_gate(self):
        """Connect to Gate instrument"""
        addr = self.gate_combo.get()
        if not addr:
            messagebox.showerror("Error", "No Gate address selected")
            return
            
        try:
            self.gate_inst = Keithley2450(addr)
            if hasattr(self.gate_inst, 'adapter'):
                self.gate_inst.adapter.connection.timeout = 10000
                self.gate_inst.adapter.connection.read_termination = '\n'
                self.gate_inst.adapter.connection.write_termination = '\n'
            
            self.log(f"Gate connected: {addr}")
            self.update_gate_status()
            
        except Exception as e:
            self.gate_inst = None
            messagebox.showerror("Connection Error", f"Failed to connect Gate:\n{e}")
            self.log(f"Gate connection failed: {e}")
            
    def disconnect_bias(self):
        """Disconnect Bias instrument"""
        if self.bias_inst:
            try:
                self.bias_inst.disable_source()
                self.bias_inst.adapter.connection.close()
            except:
                pass
            self.bias_inst = None
            self.log("Bias disconnected")
            
    def disconnect_gate(self):
        """Disconnect Gate instrument"""
        if self.gate_inst:
            try:
                self.gate_inst.disable_source()
                self.gate_inst.adapter.connection.close()
            except:
                pass
            self.gate_inst = None
            self.log("Gate disconnected")
    
    # === STATUS INDICATORS ===
    
    def update_bias_status(self):
        """Update Bias status indicators"""
        if not self.bias_inst:
            self.btn_bias_term.config(text="Term: ---", bg="#e0e0e0")
            self.btn_bias_output.config(text="Out: ---", bg="#e0e0e0")
            return
            
        try:
            term = self.bias_inst.check_terminals()
            if "FRON" in term:
                self.btn_bias_term.config(text="Term: FRONT", bg="#90ee90")
            else:
                self.btn_bias_term.config(text="Term: REAR", bg="orange")
        except:
            self.btn_bias_term.config(text="Term: ???", bg="grey")
            
        try:
            if self.bias_inst.source_enabled:
                self.btn_bias_output.config(text="Out: ON", bg="#90ee90")
            else:
                self.btn_bias_output.config(text="Out: OFF", bg="#ffcccb")
        except:
            self.btn_bias_output.config(text="Out: ???", bg="grey")
            
    def update_gate_status(self):
        """Update Gate status indicators"""
        if not self.gate_inst:
            self.btn_gate_term.config(text="Term: ---", bg="#e0e0e0")
            self.btn_gate_output.config(text="Out: ---", bg="#e0e0e0")
            self.lbl_gate_status.config(text="Gate: --- V | --- A")
            return
            
        try:
            term = self.gate_inst.check_terminals()
            if "FRON" in term:
                self.btn_gate_term.config(text="Term: FRONT", bg="#90ee90")
            else:
                self.btn_gate_term.config(text="Term: REAR", bg="orange")
        except:
            self.btn_gate_term.config(text="Term: ???", bg="grey")
            
        try:
            if self.gate_inst.source_enabled:
                self.btn_gate_output.config(text="Out: ON", bg="#90ee90")
            else:
                self.btn_gate_output.config(text="Out: OFF", bg="#ffcccb")
        except:
            self.btn_gate_output.config(text="Out: ???", bg="grey")
            
    def toggle_bias_terminals(self):
        """Toggle Bias terminals"""
        if not self.bias_inst:
            return
        try:
            current = self.bias_inst.check_terminals()
            if "FRON" in current:
                self.bias_inst.use_rear_terminals()
            else:
                self.bias_inst.use_front_terminals()
            time.sleep(0.2)
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias terminal error: {e}")
            
    def toggle_gate_terminals(self):
        """Toggle Gate terminals"""
        if not self.gate_inst:
            return
        try:
            current = self.gate_inst.check_terminals()
            if "FRON" in current:
                self.gate_inst.use_rear_terminals()
            else:
                self.gate_inst.use_front_terminals()
            time.sleep(0.2)
            self.update_gate_status()
        except Exception as e:
            self.log(f"Gate terminal error: {e}")
            
    def toggle_bias_output(self):
        """Toggle Bias output"""
        if not self.bias_inst:
            return
        try:
            if self.bias_inst.source_enabled:
                self.bias_inst.disable_source()
                self.log("Bias output OFF")
            else:
                self.bias_inst.enable_source()
                self.log("Bias output ON")
            time.sleep(0.1)
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias output error: {e}")
            
    def toggle_gate_output(self):
        """Toggle Gate output"""
        if not self.gate_inst:
            return
        try:
            if self.gate_inst.source_enabled:
                self.gate_inst.disable_source()
                self.log("Gate output OFF")
            else:
                self.gate_inst.enable_source()
                self.log("Gate output ON")
            time.sleep(0.1)
            self.update_gate_status()
        except Exception as e:
            self.log(f"Gate output error: {e}")
            
    def reset_bias(self):
        """Reset Bias instrument"""
        if not self.bias_inst:
            return
        try:
            self.bias_inst.reset()
            self.log("Bias reset")
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias reset error: {e}")
            
    def reset_gate(self):
        """Reset Gate instrument"""
        if not self.gate_inst:
            return
        try:
            self.gate_inst.reset()
            self.log("Gate reset")
            self.update_gate_status()
        except Exception as e:
            self.log(f"Gate reset error: {e}")
    
    def refresh_all_status(self):
        """Refresh all status indicators for both instruments"""
        self.update_bias_status()
        self.update_gate_status()
        self.log("Status refreshed")
    
    def measure_gate_once(self):
        """Take a single measurement from the gate instrument"""
        if not self.gate_inst:
            messagebox.showerror("Error", "Gate not connected")
            return
        
        try:
            # Read voltage (source voltage setting)
            voltage = self.gate_inst.source_voltage
            
            # Read current using direct measurement query (same as ramping uses)
            try:
                current = float(self.gate_inst.ask(":MEAS:CURR?"))
            except:
                current = None
            
            # Handle None values
            voltage_str = f"{voltage:.4f}" if voltage is not None else "---"
            current_str = f"{current:.3e}" if current is not None else "---"
            
            # Update display
            self.lbl_gate_status.config(text=f"Gate: {voltage_str} V | {current_str} A")
            self.log(f"Gate measurement: {voltage_str} V | {current_str} A")
            
        except Exception as e:
            self.log(f"Gate measurement error: {e}")
            messagebox.showerror("Measurement Error", f"Failed to measure gate:\n{e}")
        
    # === GATE RAMPING ===
    
    def start_gate_ramp(self):
        """Start gate voltage ramp with monitoring"""
        if not self.gate_inst:
            messagebox.showerror("Error", "Gate not connected")
            return
            
        try:
            target = float(self.ent_gate_voltage.get())
            step = float(self.ent_gate_step.get()) / 1000  # Convert mV to V
            delay = float(self.ent_gate_delay.get())
            compliance = float(self.ent_gate_compliance.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid gate parameters")
            return
            
        # Save parameters
        self.saved_params['gate_voltage'] = self.ent_gate_voltage.get()
        self.saved_params['gate_step'] = self.ent_gate_step.get()
        self.saved_params['gate_delay'] = self.ent_gate_delay.get()
        self.saved_params['gate_compliance'] = self.ent_gate_compliance.get()
        
        # Configure gate as voltage source
        try:
            self.gate_inst.configure_voltage_source(nplc=1, current=1e-6, compliance_current=compliance)
        except Exception as e:
            self.log(f"Gate config error: {e}")
            return
            
        # Update UI
        self.btn_gate_ramp.config(state="disabled")
        self.btn_gate_abort.config(state="normal")
        self.gate_stop_event.clear()
        
        # Start ramp in background thread
        params = {
            'target': target,
            'step': step,
            'delay': delay
        }
        threading.Thread(target=self._run_gate_ramp_thread, args=(params,), daemon=True).start()
        
    def abort_gate_ramp(self):
        """Abort gate ramp"""
        self.gate_stop_event.set()
        self.log("Gate ramp abort requested...")
        
    def _run_gate_ramp_thread(self, params):
        """Background thread for gate ramping with monitoring"""
        try:
            target = params['target']
            step = params['step']
            delay = params['delay']
            
            self.log(f"Ramping gate to {target} V...")
            self.root.after(0, lambda: self.lbl_gate_status.config(text=f"Ramping to {target} V..."))
            
            # Enable output if not already on
            if not self.gate_inst.source_enabled:
                self.gate_inst.enable_source()
                self.root.after(0, self.update_gate_status)
            
            # Define callback for monitoring
            def ramp_callback(voltage, current):
                # Update display
                self.root.after(0, lambda v=voltage, i=current: 
                               self.lbl_gate_status.config(text=f"Gate: {v:.4f} V | {i:.3e} A"))
                
                # Check for abort
                return self.gate_stop_event.is_set()
            
            # Use the voltage ramping with monitor method
            self.gate_inst.voltage_ramping_with_monitor(target, step, delay, callback=ramp_callback)
            
            if self.gate_stop_event.is_set():
                self.log("Gate ramp aborted")
            else:
                self.log(f"Gate ramp complete: {target} V")
                
        except Exception as e:
            self.log(f"Gate ramp error: {e}")
            
        finally:
            self.root.after(0, lambda: self.btn_gate_ramp.config(state="normal"))
            self.root.after(0, lambda: self.btn_gate_abort.config(state="disabled"))
            self.root.after(0, self.update_gate_status)
            
    # === SWEEP EXECUTION ===
    
    def browse_directory(self):
        """Browse for save directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, directory)
            
    def start_sweep(self):
        """Start the sweep measurement"""
        if not self.bias_inst:
            messagebox.showerror("Error", "Bias instrument not connected")
            return
            
        # Get parameters
        try:
            sp1 = float(self.ent_sp1.get())
            sp2 = float(self.ent_sp2.get())
            step = abs(float(self.ent_step.get()))
            delay = float(self.ent_delay.get())
            compliance = float(self.ent_compliance.get())
            save_dir = self.ent_dir.get()
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric parameters")
            return
            
        if not save_dir:
            messagebox.showerror("Error", "Please select a save directory")
            return
            
        # Save parameters
        sweep_type = self.sweep_type_var.get()
        if sweep_type == "iv":
            self.saved_params['iv_sp1'] = self.ent_sp1.get()
            self.saved_params['iv_sp2'] = self.ent_sp2.get()
            self.saved_params['iv_step'] = self.ent_step.get()
            self.saved_params['iv_delay'] = self.ent_delay.get()
            self.saved_params['iv_compliance'] = self.ent_compliance.get()
        else:
            self.saved_params['vi_sp1'] = self.ent_sp1.get()
            self.saved_params['vi_sp2'] = self.ent_sp2.get()
            self.saved_params['vi_step'] = self.ent_step.get()
            self.saved_params['vi_delay'] = self.ent_delay.get()
            self.saved_params['vi_compliance'] = self.ent_compliance.get()
        self.saved_params['save_dir'] = save_dir
        
        # Get current gate voltage for filename
        gate_voltage = 0.0
        include_gate = self.include_gate_var.get()
        if include_gate and self.gate_inst:
            try:
                gate_voltage = self.gate_inst.source_voltage
            except:
                pass
            
        # Update UI
        self.btn_run.config(state="disabled")
        self.btn_abort.config(state="normal")
        self.stop_event.clear()
        
        # Start sweep in background thread
        params = {
            'sp1': sp1,
            'sp2': sp2,
            'step': step,
            'delay': delay,
            'compliance': compliance,
            'save_dir': save_dir,
            'sweep_type': sweep_type,
            'gate_voltage': gate_voltage,
            'include_gate': include_gate
        }
        
        threading.Thread(target=self._run_sweep_thread, args=(params,), daemon=True).start()
        
    def abort_sweep(self):
        """Abort the running sweep"""
        self.stop_event.set()
        self.log("Sweep abort requested...")
        
    def _run_sweep_thread(self, params):
        """Background thread for sweep execution"""
        try:
            sweep_type = params['sweep_type']
            gate_voltage = params['gate_voltage']
            include_gate = params['include_gate']
            
            # Format gate voltage for filename (only if include_gate is True)
            gate_str = f"_Gate_{gate_voltage:.3f}V" if include_gate and gate_voltage != 0 else ""
            
            if sweep_type == "iv":
                self.log(f"Starting IV Sweep: 0 → {params['sp1']} mV → {params['sp2']} mV → 0")
                self.root.after(0, lambda: self.lbl_progress.config(text="Configuring IV sweep..."))
                
                # Configure voltage sweep (values in mV)
                self.bias_inst.create_hysteresis_voltage_sweep_config_list(
                    Sp1=params['sp1'],
                    Sp2=params['sp2'],
                    step=params['step'],
                    curr_range=params['compliance']
                )
                
                self.root.after(0, lambda: self.lbl_progress.config(text="Running IV sweep..."))
                self.log("Running sweep...")
                
                # Run the sweep
                output = self.bias_inst.run_clist_sweep(delay=params['delay'], sweep_type='voltage')
                
            else:  # VI sweep
                self.log(f"Starting VI Sweep: 0 → {params['sp1']} A → {params['sp2']} A → 0")
                self.root.after(0, lambda: self.lbl_progress.config(text="Configuring VI sweep..."))
                
                # Configure current sweep (values in A)
                self.bias_inst.create_hysteresis_current_sweep_config_list(
                    Sp1=params['sp1'],
                    Sp2=params['sp2'],
                    step=params['step'],
                    volt_range=params['compliance']
                )
                
                self.root.after(0, lambda: self.lbl_progress.config(text="Running VI sweep..."))
                self.log("Running sweep...")
                
                # Run the sweep
                output = self.bias_inst.run_clist_sweep(delay=params['delay'], sweep_type='current')
            
            if self.stop_event.is_set():
                self.log("Sweep aborted")
                self.root.after(0, lambda: self.lbl_progress.config(text="Aborted"))
                return
                
            # Process data
            self.log("Processing data...")
            data = [float(x) for x in output.split(',')]
            measured = np.array(data[0::3])  # READ (measured value)
            sourced = np.array(data[1::3])   # SOUR (sourced value)
            times = np.array(data[2::3])     # REL (relative time)
            
            # Create save directory if needed
            if not os.path.exists(params['save_dir']):
                os.makedirs(params['save_dir'])
                
            # Generate filename with gate voltage (only if include_gate is True)
            ts = int(time.time())
            if sweep_type == "iv":
                name = f"IV_{ts}{gate_str}_Sp1_{params['sp1']}mV_Sp2_{params['sp2']}mV"
                csv_header = "Voltage(V),Current(A),Time(s)"
                x_label = "Voltage (V)"
                y_label = "Current (A)"
                x_data = sourced  # Voltage was sourced
                y_data = measured  # Current was measured
            else:
                name = f"VI_{ts}{gate_str}_Sp1_{params['sp1']}A_Sp2_{params['sp2']}A"
                csv_header = "Current(A),Voltage(V),Time(s)"
                x_label = "Current (A)"
                y_label = "Voltage (V)"
                x_data = sourced  # Current was sourced
                y_data = measured  # Voltage was measured
            
            # Add gate voltage to plot title (only if include_gate is True)
            if include_gate and gate_voltage != 0:
                plot_title = f"{name}\nGate: {gate_voltage:.4f} V"
            else:
                plot_title = name
            
            # Save CSV
            csv_path = os.path.join(params['save_dir'], name + ".csv")
            np.savetxt(csv_path, np.vstack((x_data, y_data, times)).T, delimiter=',', header=csv_header)
            self.log(f"Saved: {name}.csv")
            
            # Save PNG
            png_path = os.path.join(params['save_dir'], name + ".png")
            fig = plt.figure(figsize=(9, 5))
            plt.plot(x_data, y_data, 'o-', markersize=3)
            plt.xlabel(x_label)
            plt.ylabel(y_label)
            plt.title(plot_title)
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(png_path)
            plt.close(fig)
            self.log(f"Saved: {name}.png")
            
            # Show plot popup
            self.root.after(0, lambda: self._show_plot_popup(x_data, y_data, plot_title, x_label, y_label))
            
            self.root.after(0, lambda: self.lbl_progress.config(text="Complete"))
            self.log("Sweep complete!")
            
        except Exception as e:
            self.log(f"Sweep error: {e}")
            self.root.after(0, lambda: self.lbl_progress.config(text=f"Error: {e}"))
            messagebox.showerror("Sweep Error", str(e))
            
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, lambda: self.btn_abort.config(state="disabled"))
            
    def _show_plot_popup(self, x_data, y_data, title, x_label, y_label):
        """Show plot in a popup window"""
        try:
            win = tk.Toplevel(self.root)
            win.title(f"Plot: {title}")
            win.geometry("800x600")
            
            fig = Figure(figsize=(8, 5), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(x_data, y_data, 'o-', markersize=3)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            ax.set_title(title)
            ax.grid(True)
            
            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar
            NavigationToolbar2Tk(canvas, win).update()
            
        except Exception as e:
            self.log(f"Plot error: {e}")
            
    def cleanup(self):
        """Cleanup on exit"""
        self.stop_event.set()
        self.gate_stop_event.set()
        self.disconnect_bias()
        self.disconnect_gate()


def main():
    root = tk.Tk()
    root.geometry("850x750")
    app = IVVISweeperGUI(root)
    
    def on_closing():
        app.cleanup()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()