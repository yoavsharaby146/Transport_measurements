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
        self.root.title("Keithley 2450 - IV/VI Sweeper")
        
        self.inst = None
        self.stop_event = threading.Event()
        
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
        
        # Row 0: VISA Address
        conn_inner = ttk.Frame(conn_frame)
        conn_inner.pack(fill="x")
        
        ttk.Label(conn_inner, text="VISA Address:").pack(side="left", padx=5)
        self.visa_combo = ttk.Combobox(conn_inner, width=40)
        self.visa_combo.pack(side="left", padx=5, fill="x", expand=True)
        
        self.btn_scan = ttk.Button(conn_inner, text="Scan", command=self.refresh_instruments, width=8)
        self.btn_scan.pack(side="left", padx=5)
        
        self.btn_connect = ttk.Button(conn_inner, text="Connect", command=self.connect_instrument, width=10)
        self.btn_connect.pack(side="left", padx=5)
        
        # Row 1: Status indicators
        status_frame = ttk.Frame(conn_frame)
        status_frame.pack(fill="x", pady=5)
        
        self.btn_terminals = tk.Button(status_frame, text="Term: ---", bg="#e0e0e0", width=12,
                                       command=self.toggle_terminals)
        self.btn_terminals.pack(side="left", padx=10)
        
        self.btn_output = tk.Button(status_frame, text="Output: ---", bg="#e0e0e0", width=14,
                                    command=self.toggle_output)
        self.btn_output.pack(side="left", padx=10)
        
        self.btn_reset = ttk.Button(status_frame, text="Hard Reset", command=self.reset_instrument, width=10)
        self.btn_reset.pack(side="left", padx=10)
        
        self.btn_status = ttk.Button(status_frame, text="Refresh Status", command=self.update_status_indicators, width=12)
        self.btn_status.pack(side="left", padx=10)
        
        # === 2. MEASUREMENT TYPE SELECTION ===
        type_frame = ttk.LabelFrame(self.main_frame, text="2. Measurement Type", padding=10)
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
        
        # === 3. SWEEP CONFIGURATION ===
        config_frame = ttk.LabelFrame(self.main_frame, text="3. Sweep Configuration", padding=10)
        config_frame.pack(fill="x", pady=5)
        
        # Grid configuration for resizing
        for i in range(4):
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
        self.ent_dir.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        self.btn_browse = ttk.Button(config_frame, text="Browse...", command=self.browse_directory)
        self.btn_browse.grid(row=3, column=3, padx=5, pady=5)
        
        # Unit labels (will be updated based on sweep type)
        self.lbl_sp1_unit = ttk.Label(config_frame, text="mV")
        self.lbl_sp1_unit.grid(row=0, column=1, sticky="e", padx=5)
        self.lbl_sp2_unit = ttk.Label(config_frame, text="mV")
        self.lbl_sp2_unit.grid(row=0, column=3, sticky="e", padx=5)
        self.lbl_step_unit = ttk.Label(config_frame, text="mV")
        self.lbl_step_unit.grid(row=1, column=1, sticky="e", padx=5)
        
        # === 4. EXECUTION ===
        exec_frame = ttk.LabelFrame(self.main_frame, text="4. Execution", padding=10)
        exec_frame.pack(fill="x", pady=5)
        
        btn_inner = ttk.Frame(exec_frame)
        btn_inner.pack(pady=5)
        
        self.btn_run = ttk.Button(btn_inner, text="RUN SWEEP", command=self.start_sweep, width=15)
        self.btn_run.pack(side="left", padx=20)
        
        self.btn_abort = ttk.Button(btn_inner, text="ABORT", command=self.abort_sweep, width=10, state="disabled")
        self.btn_abort.pack(side="left", padx=20)
        
        # Progress label
        self.lbl_progress = ttk.Label(exec_frame, text="Ready", font=("Arial", 10))
        self.lbl_progress.pack(pady=5)
        
        # === 5. LOG ===
        log_frame = ttk.LabelFrame(self.main_frame, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
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
        
    def refresh_instruments(self):
        """Scan for available VISA resources"""
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
            self.visa_combo['values'] = resources
            if resources:
                self.log(f"Found {len(resources)} instrument(s)")
            else:
                self.log("No instruments found")
        except Exception as e:
            self.log(f"Scan error: {e}")
            
    def connect_instrument(self):
        """Connect to selected instrument"""
        addr = self.visa_combo.get()
        if not addr:
            messagebox.showerror("Error", "No address selected")
            return
            
        try:
            self.inst = Keithley2450(addr)
            if hasattr(self.inst, 'adapter'):
                self.inst.adapter.connection.timeout = 10000
                self.inst.adapter.connection.read_termination = '\n'
                self.inst.adapter.connection.write_termination = '\n'
            
            self.log(f"Connected to: {addr}")
            self.update_status_indicators()
            
        except Exception as e:
            self.inst = None
            messagebox.showerror("Connection Error", f"Failed to connect:\n{e}")
            self.log(f"Connection failed: {e}")
            
    def disconnect_instrument(self):
        """Disconnect from instrument"""
        if self.inst:
            try:
                self.inst.disable_source()
                self.inst.adapter.connection.close()
            except:
                pass
            self.inst = None
            self.log("Disconnected")
            
    def toggle_terminals(self):
        """Toggle between front and rear terminals"""
        if not self.inst:
            return
        try:
            current = self.inst.check_terminals()
            if "FRON" in current:
                self.inst.use_rear_terminals()
            else:
                self.inst.use_front_terminals()
            time.sleep(0.2)
            self.update_status_indicators()
        except Exception as e:
            self.log(f"Terminal toggle error: {e}")
            
    def toggle_output(self):
        """Toggle output on/off"""
        if not self.inst:
            return
        try:
            if self.inst.source_enabled:
                self.inst.disable_source()
                self.log("Output OFF")
            else:
                self.inst.enable_source()
                self.log("Output ON")
            time.sleep(0.1)
            self.update_status_indicators()
        except Exception as e:
            self.log(f"Output toggle error: {e}")
            
    def update_status_indicators(self):
        """Update terminal and output status indicators"""
        if not self.inst:
            self.btn_terminals.config(text="Term: ---", bg="#e0e0e0")
            self.btn_output.config(text="Output: ---", bg="#e0e0e0")
            return
            
        try:
            # Check terminals
            term = self.inst.check_terminals()
            if "FRON" in term:
                self.btn_terminals.config(text="Term: FRONT", bg="#90ee90")
            else:
                self.btn_terminals.config(text="Term: REAR", bg="orange")
        except:
            self.btn_terminals.config(text="Term: ???", bg="grey")
            
        try:
            # Check output
            if self.inst.source_enabled:
                self.btn_output.config(text="Output: ON", bg="#90ee90")
            else:
                self.btn_output.config(text="Output: OFF", bg="#ffcccb")
        except:
            self.btn_output.config(text="Output: ???", bg="grey")
            
    def reset_instrument(self):
        """Hard reset the instrument"""
        if not self.inst:
            return
        try:
            self.inst.reset()
            self.log("Instrument reset")
            self.update_status_indicators()
        except Exception as e:
            self.log(f"Reset error: {e}")
            
    def browse_directory(self):
        """Browse for save directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, directory)
            
    def start_sweep(self):
        """Start the sweep measurement"""
        if not self.inst:
            messagebox.showerror("Error", "Not connected to instrument")
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
            'sweep_type': sweep_type
        }
        
        threading.Thread(target=self._run_sweep_thread, args=(params,), daemon=True).start()
        
    def abort_sweep(self):
        """Abort the running sweep"""
        self.stop_event.set()
        self.log("Abort requested...")
        
    def _run_sweep_thread(self, params):
        """Background thread for sweep execution"""
        try:
            sweep_type = params['sweep_type']
            
            if sweep_type == "iv":
                self.log(f"Starting IV Sweep: 0 → {params['sp1']} mV → {params['sp2']} mV → 0")
                self.root.after(0, lambda: self.lbl_progress.config(text="Configuring IV sweep..."))
                
                # Configure voltage sweep (values in mV)
                self.inst.create_hysteresis_voltage_sweep_config_list(
                    Sp1=params['sp1'],
                    Sp2=params['sp2'],
                    step=params['step'],
                    curr_range=params['compliance']
                )
                
                self.root.after(0, lambda: self.lbl_progress.config(text="Running IV sweep..."))
                self.log("Running sweep...")
                
                # Run the sweep
                output = self.inst.run_clist_sweep(delay=params['delay'], sweep_type='voltage')
                
            else:  # VI sweep
                self.log(f"Starting VI Sweep: 0 → {params['sp1']} A → {params['sp2']} A → 0")
                self.root.after(0, lambda: self.lbl_progress.config(text="Configuring VI sweep..."))
                
                # Configure current sweep (values in A)
                self.inst.create_hysteresis_current_sweep_config_list(
                    Sp1=params['sp1'],
                    Sp2=params['sp2'],
                    step=params['step'],
                    volt_range=params['compliance']
                )
                
                self.root.after(0, lambda: self.lbl_progress.config(text="Running VI sweep..."))
                self.log("Running sweep...")
                
                # Run the sweep
                output = self.inst.run_clist_sweep(delay=params['delay'], sweep_type='current')
            
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
                
            # Generate filename
            ts = int(time.time())
            if sweep_type == "iv":
                name = f"IV_{ts}_Sp1_{params['sp1']}mV_Sp2_{params['sp2']}mV"
                csv_header = "Voltage(V),Current(A),Time(s)"
                x_label = "Voltage (V)"
                y_label = "Current (A)"
                x_data = sourced  # Voltage was sourced
                y_data = measured  # Current was measured
            else:
                name = f"VI_{ts}_Sp1_{params['sp1']}A_Sp2_{params['sp2']}A"
                csv_header = "Current(A),Voltage(V),Time(s)"
                x_label = "Current (A)"
                y_label = "Voltage (V)"
                x_data = sourced  # Current was sourced
                y_data = measured  # Voltage was measured
            
            # Save CSV
            csv_path = os.path.join(params['save_dir'], name + ".csv")
            np.savetxt(csv_path, np.vstack((x_data, y_data, times)).T, delimiter=',', header=csv_header)
            self.log(f"Saved: {name}.csv")
            
##            # Save PNG
##            png_path = os.path.join(params['save_dir'], name + ".png")
##            fig = plt.figure(figsize=(9, 5))
##            plt.plot(x_data, y_data, 'o-', markersize=3)
##            plt.xlabel(x_label)
##            plt.ylabel(y_label)
##            plt.title(name)
##            plt.grid(True)
##            plt.tight_layout()
##            plt.savefig(png_path)
##            plt.close(fig)
##            self.log(f"Saved: {name}.png")
            
            # Show plot popup
            #self.root.after(0, lambda: self._show_plot_popup(x_data, y_data, name, x_label, y_label))
            
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
        self.disconnect_instrument()


def main():
    root = tk.Tk()
    root.geometry("700x650")
    app = IVVISweeperGUI(root)
    
    def on_closing():
        app.cleanup()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
