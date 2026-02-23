import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import time
import os
import sys
import numpy as np
import matplotlib
import threading
import logging

# --- SETUP PATHS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

logging.basicConfig(level=logging.INFO)

try:
    # Attempt 1: Check if it is inside a folder named 'Instruments'
    from Instruments.keithley2450_with_add_ons import Keithley2450
except ImportError:
    try:
        # Attempt 2: Check if it is in the SAME folder as this script
        # (Notice we removed "Instruments." from the start)
        from Instruments.keithley2450_with_add_ons import Keithley2450
    except ImportError:
        print("\nCRITICAL ERROR: Could not import Keithley2450.")
        print("Make sure 'keithley2450_with_add_ons.py' is in the same folder or in an 'Instruments' subfolder.\n")
#from keithley2450_with_add_ons import Keithley2450

class IVMeasurementGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 IV Sweeper + Gate Monitor")
        self.root.geometry("700x750")  # Slightly wider for the extra buttons

        self.Gate = None
        self.Bias = None
        self.sequence_data = []

        # Track terminal states independently
        self.gate_front = True
        self.bias_front = True

        self.saved_params = {
            'gate_setup_curr': "1e-6", 'gate_setup_comp': "15e-9", 'gate_setup_nplc': "1",
            'gate_ramp_target': "0", 'gate_ramp_step': "0.1", 'gate_ramp_pause': "0.05",
            'seq_ramp_step': "0.1", 'seq_ramp_delay': "0.01", 'seq_dir': "",
            'bias_start': "0", 'bias_end': "1", 'bias_step': "0.1",
            'bias_delay': "0.01", 'bias_max_curr': "1e-6", 'save_dir': "",
            'loop_gate_start': "0", 'loop_gate_end': "1", 'loop_gate_pts': "5",
            'loop_gate_comp': "15e-9", 'loop_gate_nplc': "1",
            'loop_ramp_step': "0.1", 'loop_ramp_delay': "0.05"
        }

        # --- MENU ---
        menubar = tk.Menu(root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.popup_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menubar)

        # --- 1. CONNECTION ---
        conn_frame = ttk.LabelFrame(root, text="1. Instrument Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        # Configure grid columns to behave nicely
        conn_frame.columnconfigure(1, weight=1)  # The combobox column gets extra space

        # -- Gate Row (Row 0) --
        ttk.Label(conn_frame, text="Gate Inst:").grid(row=0, column=0, sticky="w", padx=5)
        self.gate_combo = ttk.Combobox(conn_frame, width=30)
        self.gate_combo.grid(row=0, column=1, sticky="ew", padx=5)

        self.btn_gate_term = tk.Button(conn_frame, text="Term: ???", bg="#e0e0e0", width=12,
                                       command=self.toggle_gate_term)
        self.btn_gate_term.grid(row=0, column=2, padx=5)

        tk.Button(conn_frame, text="RESET", bg="#ffcccb", fg="red", width=6, command=self.reset_gate).grid(row=0,
                                                                                                           column=3,
                                                                                                           padx=5)

        # -- Bias Row (Row 1) --
        ttk.Label(conn_frame, text="Bias Inst:").grid(row=1, column=0, sticky="w", padx=5)
        self.bias_combo = ttk.Combobox(conn_frame, width=30)
        self.bias_combo.grid(row=1, column=1, sticky="ew", padx=5)

        self.btn_bias_term = tk.Button(conn_frame, text="Term: ???", bg="#e0e0e0", width=12,
                                       command=self.toggle_bias_term)
        self.btn_bias_term.grid(row=1, column=2, padx=5)

        tk.Button(conn_frame, text="RESET", bg="#ffcccb", fg="red", width=6, command=self.reset_bias).grid(row=1,
                                                                                                           column=3,
                                                                                                           padx=5)

        # -- Common Buttons (Row 2) --
        # Align "Refresh" under the labels/comboboxes (Cols 0-1)
        ttk.Button(conn_frame, text="Refresh Lists", command=self.refresh_instruments).grid(row=2, column=0,
                                                                                            columnspan=2, sticky="ew",
                                                                                            padx=5, pady=10)

        # Align "Connect" under the buttons (Cols 2-3)
        ttk.Button(conn_frame, text="Connect All", command=self.connect_instruments).grid(row=2, column=2, columnspan=2,
                                                                                          sticky="ew", padx=5, pady=10)
        # --- 2. GATE CONTROL ---
        gate_frame = ttk.LabelFrame(root, text="2. Gate Control", padding=10)
        gate_frame.pack(fill="x", padx=10, pady=5)

        btn_frame = tk.Frame(gate_frame)
        btn_frame.pack(side="top", fill="x", pady=5)
        ttk.Button(btn_frame, text="Verify V/I", command=self.verify_gate_status).pack(side="left", fill="x",
                                                                                       expand=True, padx=2)
        ttk.Button(btn_frame, text="Setup Source", command=self.popup_setup_gate_source).pack(side="left", fill="x",
                                                                                              expand=True, padx=2)
        ttk.Button(btn_frame, text="Ramp Voltage (Monitor)", command=self.popup_ramp_gate).pack(side="left", fill="x",
                                                                                                expand=True, padx=2)

        self.btn_gate_toggle = tk.Button(gate_frame, text="Gate Output: UNKNOWN", bg="#e0e0e0",
                                         command=self.toggle_gate_output)
        self.btn_gate_toggle.pack(side="bottom", fill="x", expand=True, padx=5, pady=5)

        # --- 3. MEASUREMENT ---
        meas_frame = ttk.LabelFrame(root, text="3. Measurements", padding=10)
        meas_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(meas_frame, text="Run Single Sweep (WITH Gate Monitor)",
                   command=lambda: self.popup_sweep("single", True)).pack(fill="x", pady=2)
        ttk.Button(meas_frame, text="Run Single Sweep (NO Gate Info)",
                   command=lambda: self.popup_sweep("single", False)).pack(fill="x", pady=2)
        tk.Button(meas_frame, text="RUN MULTI-GATE LOOP", bg="lightblue",
                  command=lambda: self.popup_sweep("loop", True)).pack(fill="x", pady=5)

        # --- 4. SEQUENCER ---
        seq_frame = ttk.LabelFrame(root, text="4. Sequencer", padding=10)
        seq_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(seq_frame, text="Open Sequencer", bg="thistle", command=self.popup_sequencer).pack(fill="x")

        # --- LOG ---
        log_frame = ttk.LabelFrame(root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        self.refresh_instruments()

    # --- UTILS ---
    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def refresh_instruments(self):
        try:
            rm = pyvisa.ResourceManager()
            insts = list(rm.list_resources())
            self.gate_combo['values'] = insts
            self.bias_combo['values'] = insts

            # CHECK IF LIST HAS ITEMS
            if len(insts) > 0:
                self.log(f"Found {len(insts)} instrument(s).")
            else:
                self.log("No instruments found (List empty).")

        except Exception as e:
            self.log(f"Error searching: {e}")

    def connect_instruments(self):
        try:
            if self.gate_combo.get():
                self.Gate = Keithley2450(self.gate_combo.get())
                self.log(f"Connected Gate: {self.gate_combo.get()}")
                self.update_gate_visuals()  # Sync Output Status
                self.update_gate_term_visuals()  # Sync Terminal Status (NEW)

            if self.bias_combo.get():
                self.Bias = Keithley2450(self.bias_combo.get())
                self.log(f"Connected Bias: {self.bias_combo.get()}")
                self.update_bias_term_visuals()  # Sync Terminal Status (NEW)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def reset_gate(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        try:
            self.Gate.reset()
            self.log("Gate Instrument Reset (*RST).")
            # Re-sync visuals since reset might change terminals/output
            self.update_gate_visuals()
            self.update_gate_term_visuals()
        except Exception as e:
            self.log(f"Reset Error: {e}")

    def reset_bias(self):
        if not self.Bias: return messagebox.showerror("Error", "Bias not connected")
        try:
            self.Bias.reset()
            self.log("Bias Instrument Reset (*RST).")
            # Re-sync visuals
            self.update_bias_term_visuals()
        except Exception as e:
            self.log(f"Reset Error: {e}")
    # --- SEPARATE TERMINAL TOGGLES ---

    def toggle_gate_term(self):
        if not self.Gate: return
        try:
            # 1. Check actual state
            current = self.Gate.check_terminals()

            # 2. Flip State
            if "FRON" in current:
                self.Gate.use_rear_terminals()
            else:
                self.Gate.use_front_terminals()

            # 3. Wait a moment and Update UI
            time.sleep(0.2)
            self.update_gate_term_visuals()
        except Exception as e:
            self.log(f"Gate Term Error: {e}")

    def update_gate_term_visuals(self):
        if not self.Gate: return
        try:
            # Query instrument for truth
            state = self.Gate.check_terminals()

            if "FRON" in state:
                self.btn_gate_term.config(text="Term: FRONT", bg="#90ee90")  # Green
            else:
                self.btn_gate_term.config(text="Term: REAR", bg="orange")  # Orange
        except Exception as e:
            self.btn_gate_term.config(text="Term: ???", bg="grey")

    def toggle_bias_term(self):
        if not self.Bias: return
        try:
            current = self.Bias.check_terminals()

            if "FRON" in current:
                self.Bias.use_rear_terminals()
            else:
                self.Bias.use_front_terminals()

            time.sleep(0.2)
            self.update_bias_term_visuals()
        except Exception as e:
            self.log(f"Bias Term Error: {e}")

    def update_bias_term_visuals(self):
        if not self.Bias: return
        try:
            state = self.Bias.check_terminals()

            if "FRON" in state:
                self.btn_bias_term.config(text="Term: FRONT", bg="#90ee90")
            else:
                self.btn_bias_term.config(text="Term: REAR", bg="orange")
        except Exception as e:
            self.btn_bias_term.config(text="Term: ???", bg="grey")

    def apply_gate_term(self):
        # Update Button UI
        txt = "Term: FRONT" if self.gate_front else "Term: REAR"
        col = "#90ee90" if self.gate_front else "orange"
        self.btn_gate_term.config(text=txt, bg=col)

        # Update Instrument if connected
        if self.Gate:
            try:
                if self.gate_front:
                    self.Gate.use_front_terminals()
                else:
                    self.Gate.use_rear_terminals()
                self.log(f"Gate: Set to {txt}")
            except Exception as e:
                self.log(f"Gate Term Error: {e}")

    def apply_bias_term(self):
        # Update Button UI
        txt = "Term: FRONT" if self.bias_front else "Term: REAR"
        col = "#90ee90" if self.bias_front else "orange"
        self.btn_bias_term.config(text=txt, bg=col)

        # Update Instrument if connected
        if self.Bias:
            try:
                if self.bias_front:
                    self.Bias.use_front_terminals()
                else:
                    self.Bias.use_rear_terminals()
                self.log(f"Bias: Set to {txt}")
            except Exception as e:
                self.log(f"Bias Term Error: {e}")

    def toggle_gate_output(self):
        if not self.Gate: return
        try:
            if self.Gate.source_enabled:
                self.Gate.output_off()
            else:
                self.Gate.output_on()
            self.update_gate_visuals()
        except Exception as e:
            self.log(f"Gate Toggle Error: {e}")

    def update_gate_visuals(self):
        if not self.Gate: return
        time.sleep(0.1)
        try:
            if self.Gate.source_enabled:
                self.btn_gate_toggle.config(text="GATE ON (Click to OFF)", bg="#90ee90")
            else:
                self.btn_gate_toggle.config(text="GATE OFF (Click to ON)", bg="#ffcccb")
        except:
            pass

    def verify_gate_status(self):
        if not self.Gate: return
        try:
            v = self.Gate.measure__voltage()
            i = self.Gate.measure__current()
            self.log(f"CHECK > V: {v:.5f} V | I: {i:.5e} A")
        except Exception as e:
            self.log(str(e))

    # --- RAMP GATE WITH MONITOR (Thread-Safe Implementation) ---
    def popup_ramp_gate(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")

        win = tk.Toplevel(self.root)
        win.title("Ramp Gate with Monitor")
        win.geometry("300x400")

        # --- INPUTS ---
        tk.Label(win, text="Target V:").pack(pady=2)
        e_t = tk.Entry(win)
        e_t.insert(0, self.saved_params['gate_ramp_target'])
        e_t.pack()

        tk.Label(win, text="Step V:").pack(pady=2)
        e_s = tk.Entry(win)
        e_s.insert(0, self.saved_params['gate_ramp_step'])
        e_s.pack()

        tk.Label(win, text="Pause (s):").pack(pady=2)
        e_p = tk.Entry(win)
        e_p.insert(0, self.saved_params['gate_ramp_pause'])
        e_p.pack()

        # --- LIVE MONITOR DISPLAY ---
        # We use StringVars to allow thread-safe updates via set()
        self.mon_status = tk.StringVar(value="Ready")
        self.mon_val = tk.StringVar(value="V: --\nI: --")

        lbl_status = tk.Label(win, textvariable=self.mon_status, font=("Arial", 11, "bold"), fg="blue")
        lbl_status.pack(pady=10)

        lbl_val = tk.Label(win, textvariable=self.mon_val, font=("Consolas", 14), bg="#f0f0f0", width=20,
                           relief="sunken")
        lbl_val.pack(pady=5)

        # --- STOP LOGIC ---
        self.stop_ramp_flag = False

        def stop_now():
            self.stop_ramp_flag = True
            self.mon_status.set("STOPPING...")

        # Stop button starts disabled
        btn_stop = tk.Button(win, text="STOP RAMP", bg="red", fg="white", font=("bold"), command=stop_now,
                             state="disabled")
        btn_stop.pack(fill="x", padx=20, pady=10)

        # --- WORKER THREAD ---
        def run_thread():
            try:
                # 1. Capture Inputs (Main Thread)
                target = float(e_t.get())
                step = float(e_s.get())
                pause = float(e_p.get())

                # Save to memory
                self.saved_params.update(
                    {'gate_ramp_target': str(target), 'gate_ramp_step': str(step), 'gate_ramp_pause': str(pause)})

                # 2. Update UI for Start (Schedule on Main Thread)
                self.root.after(0, lambda: btn_stop.config(state="normal"))
                self.root.after(0, lambda: self.mon_status.set("Ramping..."))
                self.root.after(0, lambda: lbl_status.config(fg="blue"))

                self.stop_ramp_flag = False

                # 3. Define the Callback
                # This runs repeatedly inside the background thread
                def monitor_callback(v, i):
                    # Update the display variables SAFELY using after()
                    self.root.after(0, lambda: self.mon_val.set(f"V: {v:.5f} V\nI: {i:.5e} A"))

                    # Return True if the driver should abort
                    if self.stop_ramp_flag:
                        return True
                    return False

                # 4. Call the Driver
                # This blocks this thread until done or stopped
                self.Gate.voltage_ramping_with_monitor(target, step, pause, callback=monitor_callback)

                # 5. Finish UI Updates
                if self.stop_ramp_flag:
                    self.root.after(0, lambda: self.mon_status.set("Ramp Aborted"))
                    self.root.after(0, lambda: lbl_status.config(fg="red"))
                else:
                    self.root.after(0, lambda: self.mon_status.set("Ramp Done"))
                    self.root.after(0, lambda: lbl_status.config(fg="green"))

            except Exception as e:
                self.root.after(0, lambda: self.mon_status.set(f"Error: {e}"))
                self.root.after(0, lambda: lbl_status.config(fg="red"))
            finally:
                # Disable stop button
                self.root.after(0, lambda: btn_stop.config(state="disabled"))

        # Start the thread
        tk.Button(win, text="START RAMP",
                  command=lambda: threading.Thread(target=run_thread, daemon=True).start()).pack(pady=5)

    # --- SETUP GATE ---
    def popup_setup_gate_source(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        win = tk.Toplevel(self.root)
        win.title("Setup Gate")

        def entry_row(lbl, key, r):
            tk.Label(win, text=lbl).grid(row=r, column=0)
            e = tk.Entry(win)
            e.insert(0, self.saved_params[key])
            e.grid(row=r, column=1)
            return e

        e_c = entry_row("Limit (A):", 'gate_setup_curr', 0)
        e_comp = entry_row("Comp (A):", 'gate_setup_comp', 1)
        e_nplc = entry_row("NPLC:", 'gate_setup_nplc', 2)

        def apply():
            self.saved_params.update(
                {'gate_setup_curr': e_c.get(), 'gate_setup_comp': e_comp.get(), 'gate_setup_nplc': e_nplc.get()})
            try:
                self.Gate.configure_voltage_source(nplc=float(e_nplc.get()), current=float(e_c.get()),
                                                   compliance_current=float(e_comp.get()))
                self.Gate.output_on()
                self.update_gate_visuals()
                self.log("Gate configured & ON.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(win, text="Apply", command=apply).grid(row=3, columnspan=2, pady=5)

    # --- POPUP SWEEP ---
    def popup_sweep(self, mode, with_gate):
        if not self.Bias: return messagebox.showerror("Error", "Bias not connected")
        win = tk.Toplevel(self.root)
        win.title(f"{mode.upper()} SWEEP")

        r = 0
        entries = {}

        if mode == "loop":
            tk.Label(win, text="GATE LOOP", font="bold").grid(row=r, columnspan=2);
            r += 1
            tk.Label(win, text="Start/End/Pts:").grid(row=r, column=0)
            f = tk.Frame(win);
            f.grid(row=r, column=1)
            entries['gs'] = tk.Entry(f, width=5);
            entries['gs'].insert(0, self.saved_params['loop_gate_start']);
            entries['gs'].pack(side="left")
            entries['ge'] = tk.Entry(f, width=5);
            entries['ge'].insert(0, self.saved_params['loop_gate_end']);
            entries['ge'].pack(side="left")
            entries['gp'] = tk.Entry(f, width=5);
            entries['gp'].insert(0, self.saved_params['loop_gate_pts']);
            entries['gp'].pack(side="left")
            r += 1

            tk.Label(win, text="Comp/NPLC:").grid(row=r, column=0)
            f2 = tk.Frame(win);
            f2.grid(row=r, column=1)
            entries['gc'] = tk.Entry(f2, width=8);
            entries['gc'].insert(0, self.saved_params['loop_gate_comp']);
            entries['gc'].pack(side="left")
            entries['gn'] = tk.Entry(f2, width=5);
            entries['gn'].insert(0, self.saved_params['loop_gate_nplc']);
            entries['gn'].pack(side="left")
            r += 1

            tk.Label(win, text="Ramp Step/Delay:").grid(row=r, column=0)
            f3 = tk.Frame(win);
            f3.grid(row=r, column=1)
            entries['grs'] = tk.Entry(f3, width=8);
            entries['grs'].insert(0, self.saved_params['loop_ramp_step']);
            entries['grs'].pack(side="left")
            entries['grd'] = tk.Entry(f3, width=5);
            entries['grd'].insert(0, self.saved_params['loop_ramp_delay']);
            entries['grd'].pack(side="left")
            r += 1

        tk.Label(win, text="BIAS SWEEP", font="bold").grid(row=r, columnspan=2);
        r += 1

        def add_field(lbl, key):
            nonlocal r
            tk.Label(win, text=lbl).grid(row=r, column=0)
            e = tk.Entry(win)
            e.insert(0, self.saved_params[key])
            e.grid(row=r, column=1)
            r += 1
            return e

        entries['b1'] = add_field("Start (V):", 'bias_start')
        entries['b2'] = add_field("End (V):", 'bias_end')
        entries['bs'] = add_field("Step (V):", 'bias_step')
        entries['bd'] = add_field("Delay (s):", 'bias_delay')
        entries['bm'] = add_field("Max Curr (A):", 'bias_max_curr')

        tk.Label(win, text="Dir:").grid(row=r, column=0)
        entries['dir'] = tk.Entry(win)
        entries['dir'].insert(0, self.saved_params['save_dir'])
        entries['dir'].grid(row=r, column=1)
        tk.Button(win, text="...", command=lambda: (entries['dir'].delete(0, tk.END),
                                                    entries['dir'].insert(0, filedialog.askdirectory()))).grid(row=r,
                                                                                                               column=2)
        r += 1

        def run():
            # Update Memory
            self.saved_params.update({
                'bias_start': entries['b1'].get(), 'bias_end': entries['b2'].get(),
                'bias_step': entries['bs'].get(), 'bias_delay': entries['bd'].get(),
                'bias_max_curr': entries['bm'].get(), 'save_dir': entries['dir'].get()
            })

            params = {
                'bias1': float(entries['b1'].get()), 'bias2': float(entries['b2'].get()),
                'step': float(entries['bs'].get()), 'delay': float(entries['bd'].get()),
                'max_curr': float(entries['bm'].get()), 'dir': entries['dir'].get(),
                'mode': mode, 'with_gate': with_gate
            }

            if mode == "loop":
                self.saved_params.update({
                    'loop_gate_start': entries['gs'].get(), 'loop_gate_end': entries['ge'].get(),
                    'loop_gate_pts': entries['gp'].get(), 'loop_gate_comp': entries['gc'].get(),
                    'loop_ramp_step': entries['grs'].get(), 'loop_ramp_delay': entries['grd'].get()
                })
                params.update({
                    'gate_start': float(entries['gs'].get()), 'gate_end': float(entries['ge'].get()),
                    'gate_pts': int(entries['gp'].get()), 'gate_comp': float(entries['gc'].get()),
                    'gate_nplc': float(entries['gn'].get()), 'gate_ramp_step': float(entries['grs'].get()),
                    'gate_ramp_delay': float(entries['grd'].get())
                })

            win.destroy()
            threading.Thread(target=self.run_measurement_logic, args=(params,), daemon=True).start()

        tk.Button(win, text="RUN", command=run, bg="green", fg="white").grid(row=r, columnspan=3, pady=10)

    # --- MEASUREMENT LOGIC ---
    def run_measurement_logic(self, p):
        try:
            gate_vals = [None]
            if p['mode'] == "loop":
                gate_vals = np.linspace(p['gate_start'], p['gate_end'], p['gate_pts'])
                if self.Gate:
                    self.Gate.configure_voltage_source(nplc=p['gate_nplc'], current=1e-6,
                                                       compliance_current=p['gate_comp'])
                    self.Gate.output_on()
                    self.Gate.voltage_ramping(gate_vals[0], p['gate_ramp_step'], p['gate_ramp_delay'])

            for g_val in gate_vals:
                if p['mode'] == "loop":
                    self.log(f"Ramping Gate to {g_val:.4f}V...")
                    self.Gate.voltage_ramping(g_val, p['gate_ramp_step'], p['gate_ramp_delay'])
                    time.sleep(0.5)

                self.run_single_bias_sweep(p, gate_val_override=g_val)

            if p['mode'] == "loop" and self.Gate:
                self.Gate.voltage_ramping(0, p['gate_ramp_step'], p['gate_ramp_delay'])
                self.Gate.output_off()
                self.log("Loop Complete.")

        except Exception as e:
            self.log(f"Error in Logic: {e}")

    def run_single_bias_sweep(self, p, gate_val_override=None):
        try:
            # Configure Sweep
            self.Bias.create_hysteresis_voltage_sweep_config_list(
                Sp1=p['bias1'], Sp2=p['bias2'], step=abs(p['step']), curr_range=p['max_curr']
            )

            # Start Gate Monitor (if needed)
            stop_mon = threading.Event()
            gate_log = []

            def monitor():
                t0 = time.time()
                while not stop_mon.is_set():
                    try:
                        gate_log.append([time.time() - t0, self.Gate.measure__voltage(), self.Gate.measure__current()])
                        time.sleep(0.1)
                    except:
                        pass

            mon_thread = None
            if p['with_gate'] and self.Gate:
                mon_thread = threading.Thread(target=monitor)
                mon_thread.start()

            # Run Sweep
            raw_data = self.Bias.run_clist_sweep(p['delay'])

            # Stop Monitor
            if mon_thread:
                stop_mon.set()
                mon_thread.join()

            # Process Data
            data = [float(x) for x in raw_data.split(',')]
            curr = np.array(data[0::3])
            bias = np.array(data[1::3])

            # Save
            if not os.path.exists(p['dir']): os.makedirs(p['dir'])
            ts = int(time.time())

            g_lbl = "0"
            if gate_val_override is not None:
                g_lbl = f"{gate_val_override:.3f}"
            elif gate_log:
                g_lbl = f"{np.mean([x[1] for x in gate_log]):.3f}"

            name = f"VI_{ts}_G{g_lbl}V"
            path_csv = os.path.join(p['dir'], name + ".csv")

            np.savetxt(path_csv, np.vstack((bias, curr)).T, delimiter=",", header="Bias(V),Current(A)")
            if gate_log:
                np.savetxt(os.path.join(p['dir'], name + "_GateLog.csv"), gate_log, delimiter=",",
                           header="Time,GateV,GateI")

            # Plot
            self.root.after(0, self.popup_plot, bias, curr, name)
            self.log(f"Saved {name}")

        except Exception as e:
            self.log(f"Sweep Error: {e}")

    def popup_plot(self, x, y, title):
        try:
            win = tk.Toplevel(self.root)
            win.title(title)
            fig = Figure(figsize=(6, 4), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'o-')
            ax.set_xlabel("Bias (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(True)

            canvas = FigureCanvasTkAgg(fig, win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            NavigationToolbar2Tk(canvas, win).update()
        except:
            pass

    # --- SEQUENCER ---
    def popup_sequencer(self):
        self.log("Sequencer feature available in previous full version (omitted here for brevity).")

    def popup_help(self):
        messagebox.showinfo("Help",
                            "1. Connect Instruments.\n2. Use Terminals button to toggle Front/Rear.\n3. Ramp Monitor allows stopping mid-ramp.")


if __name__ == "__main__":
    root = tk.Tk()
    app = IVMeasurementGUI(root)
    root.mainloop()