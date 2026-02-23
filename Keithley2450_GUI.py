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


class KeithleyControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 Master Controller")
        self.root.geometry("1200x900")

        self.inst = None
        self.stop_event = threading.Event()
        self.monitor_active = False

        # Thread Lock to prevent collisions
        self.lock = threading.Lock()

        # --- GUI Layout ---
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)

        self._build_connection_frame(top_frame)
        self._build_status_dashboard(top_frame)

        self._build_config_tabs()

        self._build_monitor_area()
        self._build_console_log()

        # Start minimal background poller
        self.root.after(2000, self._poll_instrument_status)

        # Auto-scan on startup
        self.scan_instruments()

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
        notebook = ttk.Notebook(self.root)
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
        frame = ttk.Frame(self.root)
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
        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100)
        self.ax.set_title("I-V Curve")
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel("Current (A)")
        self.ax.grid(True)

        self.line_iv, = self.ax.plot([], [], '.-', color='blue', linewidth=1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        self.data_x = []  # Source values
        self.data_y = []  # Measured values

    def _build_console_log(self):
        frame = ttk.LabelFrame(self.root, text="System Log")
        frame.pack(fill="x", padx=10, pady=5, side="bottom")
        self.console = scrolledtext.ScrolledText(frame, height=8, state='disabled', font=("Consolas", 9))
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
        self.log_message("Scanning for instruments...")
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
            self.visa_combo['values'] = live_resources
            if live_resources:
                self.visa_combo.current(0)
                self.log_message(f"Found {len(live_resources)} active instruments.")
            else:
                self.log_message("No active instruments found.")
        except Exception as e:
            self.log_message(f"Scan Error: {e}")

    def _update_ui_labels(self):
        """ Updates UI labels to reflect the current Source/Measure logic """
        mode = self.source_mode_var.get()
        if mode == "voltage":
            # SOURCE: Voltage, MEASURE: Current
            self.lbl_unit_level.config(text="V")
            self.lbl_unit_limit.config(text="A")
            self.lbl_src_range_txt.config(text="(Source V Range)")
            self.lbl_meas_range_txt.config(text="(Measure I Range)")
            self.lbl_measure_title.config(text="Measured Current:")

            self.cb_out_range['values'] = ["Auto", "20e-3","200e-3", "2", "20", "200"]  # V ranges
            self.cb_meas_range['values'] = ["Auto","1e-8","1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3",
                                            "1"]  # I ranges

            self.lbl_measure_val.config(text="-- A")

        else:
            # SOURCE: Current, MEASURE: Voltage
            self.lbl_unit_level.config(text="A")
            self.lbl_unit_limit.config(text="V")
            self.lbl_src_range_txt.config(text="(Source I Range)")
            self.lbl_meas_range_txt.config(text="(Measure V Range)")
            self.lbl_measure_title.config(text="Measured Voltage:")

            self.cb_out_range['values'] = ["Auto","1e-8","1e-7", "1e-6", "10e-6", "100e-6", "1e-3", "10e-3", "100e-3",
                                            "1"]  # I ranges
            self.cb_meas_range['values'] = ["Auto", "20e-3","200e-3", "2", "20", "200"]  # V ranges

            self.lbl_measure_val.config(text="-- V")

        if hasattr(self, 'source_mode_var'):
            self.root.update_idletasks()

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

    def reset_instrument(self):
        if not self.inst: return
        with self.lock:
            try:
                self.inst.reset()
                self.inst.apply_voltage()
                self.log_message("Instrument Hard Reset.")
            except Exception as e:
                self.log_message(f"Reset Error: {e}")

    def toggle_output(self):
        if not self.inst: return
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
        self.root.update_idletasks()

    def set_terminals(self, term):
        if not self.inst: return
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
        if not self.inst: return
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
        if not self.inst: return
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
        if not self.inst: return

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

        self.root.after(2000, self._poll_instrument_status)

    # --- Ramping Logic ---

    def start_ramp(self):
        if not self.inst: return

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

        self.root.after(1, self._update_graph)
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
            self.root.after(1, lambda: self.btn_stop_ramp.config(state="disabled"))
            self.root.after(1, lambda: self.btn_start_ramp.config(state="normal"))


if __name__ == "__main__":
    root = tk.Tk()
    app = KeithleyControllerApp(root)
    app._update_ui_labels()
    root.mainloop()