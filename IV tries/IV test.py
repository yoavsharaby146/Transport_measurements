import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import time
import os
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import threading
import logging

# --- 1. SETUP PATHS & IMPORTS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Set backend to TkAgg
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Set up logging
logging.basicConfig(level=logging.INFO)

# Try to import the Keithley class
try:
    from Instruments.keithley2450_with_add_ons import Keithley2450
except ImportError:
    try:
        from Instruments.keithley2450_with_add_ons import Keithley2450
    except ImportError:
        print(f"\nCRITICAL ERROR: Could not import Keithley2450.")
        print("Please ensure 'Instruments/keithley2450_with_add_ons.py' exists.\n")


class IVMeasurementGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 IV Sweeper + Gate Monitor")
        self.root.geometry("850x900")

        self.Gate = None
        self.Bias = None
        self.sequence_data = []

        # --- MEMORY FOR INPUT FIELDS ---
        self.saved_params = {
            'gate_setup_curr': "1e-6", 'gate_setup_comp': "15e-9", 'gate_setup_nplc': "1",
            'gate_ramp_target': "0", 'gate_ramp_step': "10", 'gate_ramp_pause': "0.01",
            'seq_ramp_step': "10", 'seq_ramp_delay': "0.01", 'seq_dir': "",
            'bias_start': "1000", 'bias_end': "-1000", 'bias_step': "10",
            'bias_delay': "0.01", 'bias_max_curr': "1e-6", 'save_dir': "",
            'loop_gate_start': "0", 'loop_gate_end': "1", 'loop_gate_pts': "5",
            'loop_gate_comp': "15e-9", 'loop_gate_nplc': "1",
            'loop_ramp_step': "10", 'loop_ramp_delay': "0.01"
        }

        # --- MENU BAR ---
        menubar = tk.Menu(root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.popup_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menubar)

        # --- GUI SECTION 1: CONNECTION ---
        conn_frame = ttk.LabelFrame(root, text="1. Instrument Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(conn_frame, text="Gate Instrument:").grid(row=0, column=0, padx=5, sticky="w")
        self.gate_combo = ttk.Combobox(conn_frame, width=30);
        self.gate_combo.grid(row=0, column=1, padx=5)
        ttk.Label(conn_frame, text="Bias Instrument:").grid(row=1, column=0, padx=5, sticky="w")
        self.bias_combo = ttk.Combobox(conn_frame, width=30);
        self.bias_combo.grid(row=1, column=1, padx=5)
        ttk.Button(conn_frame, text="Refresh List", command=self.refresh_instruments).grid(row=0, column=2, rowspan=2,
                                                                                           padx=10)
        ttk.Button(conn_frame, text="Connect All", command=self.connect_instruments).grid(row=2, column=1, pady=10)

        # --- GUI SECTION 2: GATE CONTROL ---
        gate_frame = ttk.LabelFrame(root, text="2. Gate Control", padding=10)
        gate_frame.pack(fill="x", padx=10, pady=5)
        btn_frame = tk.Frame(gate_frame);
        btn_frame.pack(side="top", fill="x", pady=5)
        ttk.Button(btn_frame, text="Verify V/I", command=self.verify_gate_status).pack(side="left", fill="x",
                                                                                       expand=True, padx=5)
        ttk.Button(btn_frame, text="Setup Source", command=self.popup_setup_gate_source).pack(side="left", fill="x",
                                                                                              expand=True, padx=5)
        ttk.Button(btn_frame, text="Ramp Voltage", command=self.popup_ramp_gate).pack(side="left", fill="x",
                                                                                      expand=True, padx=5)
        self.btn_gate_toggle = tk.Button(gate_frame, text="Gate Status: UNKNOWN", bg="#e0e0e0",
                                         command=self.toggle_gate_output)
        self.btn_gate_toggle.pack(side="bottom", fill="x", expand=True, padx=5, pady=5)

        # --- GUI SECTION 3: MEASUREMENT ---
        meas_frame = ttk.LabelFrame(root, text="3. Manual & Loop Operations", padding=10)
        meas_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(meas_frame, text="Run Single Sweep (WITH Gate Monitor)",
                   command=lambda: self.popup_sweep(mode="single", with_gate=True)).pack(side="top", fill="x",
                                                                                         expand=True, padx=5, pady=2)
        ttk.Button(meas_frame, text="Run Single Sweep (NO Gate Info)",
                   command=lambda: self.popup_sweep(mode="single", with_gate=False)).pack(side="top", fill="x",
                                                                                          expand=True, padx=5, pady=2)
        ttk.Separator(meas_frame, orient="horizontal").pack(fill="x", pady=10)
        tk.Button(meas_frame, text="RUN MULTI-GATE IV LOOP", bg="lightblue", font=("Arial", 9, "bold"),
                  command=lambda: self.popup_sweep(mode="loop", with_gate=True)).pack(side="top", fill="x", expand=True,
                                                                                      padx=5, pady=5)

        # --- GUI SECTION 4: SEQUENCER ---
        seq_frame = ttk.LabelFrame(root, text="4. Sequencer (Advanced)", padding=10)
        seq_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(seq_frame, text="OPEN SEQUENCER CONFIG", bg="thistle", font=("Arial", 9, "bold"),
                  command=self.popup_sequencer).pack(fill="x", expand=True)

        # --- GUI SECTION 5: LOG ---
        log_frame = ttk.LabelFrame(root, text="Status Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        self.refresh_instruments()

    # --- HELPERS ---
    def log(self, message):
        self.root.after(0, self._log_internal, message)

    def _log_internal(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def refresh_instruments(self):
        try:
            rm = pyvisa.ResourceManager()
            self.gate_combo['values'] = list(rm.list_resources())
            self.bias_combo['values'] = list(rm.list_resources())
            self.log("Instruments found.")
        except Exception:
            self.log("No instruments found.")

    def connect_instruments(self):
        try:
            if self.gate_combo.get():
                self.Gate = Keithley2450(self.gate_combo.get())
                self.log(f"Connected to Gate: {self.gate_combo.get()}")
                self.update_gate_visuals()
            if self.bias_combo.get():
                self.Bias = Keithley2450(self.bias_combo.get())
                self.log(f"Connected to Bias: {self.bias_combo.get()}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_gate_output(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        try:
            if self.Gate.source_enabled:
                self.Gate.output_off();
                self.log("Gate Output turned OFF.")
            else:
                self.Gate.output_on();
                self.log("Gate Output turned ON.")
            self.update_gate_visuals()
        except Exception as e:
            self.log(f"Error toggling gate: {e}")

    def update_gate_visuals(self):
        if not self.Gate: return
        try:
            time.sleep(0.1)
            if self.Gate.source_enabled:
                self.btn_gate_toggle.config(text="GATE IS ON (Click to OFF)", bg="#90ee90", fg="black")
            else:
                self.btn_gate_toggle.config(text="GATE IS OFF (Click to ON)", bg="#ffcccb", fg="black")
        except:
            self.btn_gate_toggle.config(text="Gate Status: Unknown", bg="grey")

    # --- NEW TABBED HELP WINDOW ---
    def popup_help(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("User Guide")
        help_win.geometry("700x500")

        notebook = ttk.Notebook(help_win)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        def add_tab(title, content_text):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            scrollbar = ttk.Scrollbar(frame)
            scrollbar.pack(side='right', fill='y')
            text_area = tk.Text(frame, wrap='word', font=("Consolas", 10), yscrollcommand=scrollbar.set, padx=10,
                                pady=10)
            text_area.pack(fill='both', expand=True)
            text_area.insert('end', content_text)
            text_area.config(state='disabled')
            scrollbar.config(command=text_area.yview)

        txt_conn = """
1. INSTRUMENT CONNECTION
------------------------
- Gate Instrument / Bias Instrument: 
  Dropdown lists showing all detected VISA resource addresses.

- Connect: 
  Initializes the connection. 
  *Note:* Bias instrument is REQUIRED. Gate instrument is OPTIONAL for Sequencer or Single (No Gate) sweeps.
"""
        txt_gate = """
2. GATE CONTROL
---------------
- Verify V/I:
  Instantly measures and prints the current Gate Voltage and Current.

- Setup Voltage Source: 
  Configure Current Limit, Compliance, and NPLC.

- Ramp Voltage: 
  Smoothly moves the gate voltage to a target value.
"""
        txt_meas = """
3. MEASUREMENT OPERATIONS
-------------------------
- Run Single Sweep (WITH Gate Monitor):
  * Performs one IV sweep on the Bias instrument.
  * Monitors Gate instrument in background (if connected).
  * Saves _GateLog.csv file.

- Run Single Sweep (NO Gate Info):
  * Performs one IV sweep on the Bias instrument.
  * IGNORES the Gate instrument completely.

- RUN MULTI-GATE IV LOOP:
  * Automatically changes the Gate voltage in steps.
  * Requires Gate instrument to be connected.
"""
        txt_seq = """
4. SEQUENCER (ADVANCED)
-----------------------
Executes a list of measurements defined in a text file.

**NOTE: Gate Instrument is OPTIONAL here.**
If Gate is connected, it will ramp voltage.
If Gate is NOT connected, it ignores the Gate column and runs Bias sweeps only.

FILE FORMAT:
Comma-separated values (CSV). Order is strictly:
Gate_V, Bias_Start_mV, Bias_End_mV, Bias_Step_mV, Compliance_A

Example:
0.0, 0, 1000, 10, 1e-6
"""
        add_tab("Connection", txt_conn)
        add_tab("Gate Control", txt_gate)
        add_tab("Measurements", txt_meas)
        add_tab("Sequencer", txt_seq)

    # --- OTHER FEATURES ---
    def verify_gate_status(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        threading.Thread(target=self._verify_gate_thread, daemon=True).start()

    def _verify_gate_thread(self):
        try:
            v = self.Gate.measure__voltage()
            i = self.Gate.measure__current()
            self.log(f"GATE CHECK > Voltage: {v:.5f} V | Current: {i:.5e} A")
        except Exception as e:
            self.log(f"Error checking gate: {e}")

    def popup_sequencer(self):
        # Allow opening if Bias is present (Gate is now optional)
        if not self.Bias: return messagebox.showerror("Error", "Connect Bias instrument first.")

        win = tk.Toplevel(self.root);
        win.title("Sequencer");
        win.geometry("600x600")

        tk.Label(win, text="Format: Gate_V, Bias_Start, Bias_End, Step, Comp", bg="lightyellow").pack(pady=5, fill="x")

        frame_file = tk.Frame(win);
        frame_file.pack(pady=5)
        lbl_status = tk.Label(frame_file, text="No file", fg="red")

        def load_file():
            fn = filedialog.askopenfilename()
            if fn:
                try:
                    self.sequence_data = []
                    with open(fn, 'r') as f:
                        for line in f:
                            if line.strip().startswith("#") or not line.strip(): continue
                            p = line.split(',')
                            if len(p) < 5: continue
                            self.sequence_data.append(
                                {'gate': float(p[0]), 'bias_start': float(p[1]), 'bias_end': float(p[2]),
                                 'step': float(p[3]), 'comp': float(p[4])})
                    lbl_status.config(text=f"Loaded {len(self.sequence_data)} steps", fg="green")
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        tk.Button(frame_file, text="Load File", command=load_file).pack(side="left")
        lbl_status.pack(side="left", padx=5)

        f_set = ttk.LabelFrame(win, text="Settings");
        f_set.pack(fill="x", padx=10)
        e_gs = tk.Entry(f_set, width=10);
        e_gs.insert(0, self.saved_params['seq_ramp_step']);
        e_gs.pack(side="left")
        e_gd = tk.Entry(f_set, width=10);
        e_gd.insert(0, self.saved_params['seq_ramp_delay']);
        e_gd.pack(side="left")
        e_dir = tk.Entry(f_set, width=20);
        e_dir.insert(0, self.saved_params['seq_dir']);
        e_dir.pack(side="left")
        tk.Button(f_set, text="...",
                  command=lambda: (e_dir.delete(0, tk.END), e_dir.insert(0, filedialog.askdirectory()))).pack(
            side="left")

        def run():
            self.saved_params.update(
                {'seq_ramp_step': e_gs.get(), 'seq_ramp_delay': e_gd.get(), 'seq_dir': e_dir.get()})
            gp = {'save_dir': e_dir.get(), 'gate_ramp_step': float(e_gs.get()), 'gate_ramp_delay': float(e_gd.get())}
            win.destroy()
            threading.Thread(target=self.run_sequencer_thread, args=(gp,), daemon=True).start()

        tk.Button(win, text="RUN", command=run).pack(pady=10)

    def run_sequencer_thread(self, gp):
        self.log("Starting Sequencer...")
        try:
            # OPTIONAL GATE CONFIG
            if self.Gate:
                self.Gate.configure_voltage_source(nplc=1, current=1e-6, compliance_current=15e-9)
                self.Gate.output_on()
            else:
                self.log("No Gate detected. Running Bias Sequence only.")

            for i, step in enumerate(self.sequence_data):
                # OPTIONAL GATE RAMP
                if self.Gate:
                    self.log(f"Step {i + 1}: Ramping Gate to {step['gate']}V")
                    self.Gate.voltage_ramping(step['gate'], gp['gate_ramp_step'], gp['gate_ramp_delay'])
                else:
                    self.log(f"Step {i + 1}: Gate Ignored.")

                # Check if we should enable the monitor (only if Gate exists)
                gate_exists = (self.Gate is not None)

                p = {
                    'bias1': step['bias_start'],
                    'bias2': step['bias_end'],
                    'step': abs(step['step']),
                    'delay': 0.01,
                    'max_curr': step['comp'],
                    'dir': gp['save_dir'],
                    'with_gate': gate_exists,
                    'mode': 'single'
                }

                self.run_single_bias_sweep(p, gate_val_override=step['gate'])

            # OPTIONAL SHUTDOWN
            if self.Gate:
                self.Gate.voltage_ramping(0, gp['gate_ramp_step'], gp['gate_ramp_delay'])
                self.Gate.output_off()

            self.log("Sequencer Done.")
        except Exception as e:
            self.log(f"Seq Error: {e}")

    def popup_setup_gate_source(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        win = tk.Toplevel(self.root);
        win.title("Setup Gate")
        tk.Label(win, text="Limit (A):").grid(row=0, column=0);
        e_c = tk.Entry(win);
        e_c.insert(0, self.saved_params['gate_setup_curr']);
        e_c.grid(row=0, column=1)
        tk.Label(win, text="Comp (A):").grid(row=1, column=0);
        e_comp = tk.Entry(win);
        e_comp.insert(0, self.saved_params['gate_setup_comp']);
        e_comp.grid(row=1, column=1)
        tk.Label(win, text="NPLC:").grid(row=2, column=0);
        e_nplc = tk.Entry(win);
        e_nplc.insert(0, self.saved_params['gate_setup_nplc']);
        e_nplc.grid(row=2, column=1)

        def apply():
            self.saved_params.update(
                {'gate_setup_curr': e_c.get(), 'gate_setup_comp': e_comp.get(), 'gate_setup_nplc': e_nplc.get()})
            self.Gate.configure_voltage_source(nplc=float(e_nplc.get()), current=float(e_c.get()),
                                               compliance_current=float(e_comp.get()))
            self.Gate.output_on();
            self.update_gate_visuals();
            win.destroy()

        tk.Button(win, text="Apply", command=apply).grid(row=3, columnspan=2)

    def popup_ramp_gate(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        win = tk.Toplevel(self.root);
        win.title("Ramp Gate")
        tk.Label(win, text="Target (V):").grid(row=0, column=0);
        e_t = tk.Entry(win);
        e_t.insert(0, self.saved_params['gate_ramp_target']);
        e_t.grid(row=0, column=1)
        tk.Label(win, text="Step (mV):").grid(row=1, column=0);
        e_s = tk.Entry(win);
        e_s.insert(0, self.saved_params['gate_ramp_step']);
        e_s.grid(row=1, column=1)
        tk.Label(win, text="Pause (s):").grid(row=2, column=0);
        e_p = tk.Entry(win);
        e_p.insert(0, self.saved_params['gate_ramp_pause']);
        e_p.grid(row=2, column=1)

        def run():
            self.saved_params.update(
                {'gate_ramp_target': e_t.get(), 'gate_ramp_step': e_s.get(), 'gate_ramp_pause': e_p.get()})
            threading.Thread(
                target=lambda: self.Gate.voltage_ramping(float(e_t.get()), float(e_s.get()), float(e_p.get())),
                daemon=True).start()
            win.destroy()

        tk.Button(win, text="Run", command=run).grid(row=3, columnspan=2)

    def popup_sweep(self, mode="single", with_gate=True):
        if not self.Bias: return messagebox.showerror("Error", "Bias not connected")
        win = tk.Toplevel(self.root);
        win.title(f"{mode.upper()} SWEEP")

        row_idx = 0
        e_g_start, e_g_end, e_g_pts, e_g_comp, e_g_nplc, e_g_rs, e_g_rd = None, None, None, None, None, None, None

        if mode == "loop":
            tk.Label(win, text="GATE LOOP", font=("bold")).grid(row=0, columnspan=2)
            tk.Label(win, text="Start(V)/End(V)/Pts:").grid(row=1, column=0)
            e_g_start = tk.Entry(win, width=5);
            e_g_start.insert(0, self.saved_params['loop_gate_start']);
            e_g_start.grid(row=1, column=1, sticky="w")
            e_g_end = tk.Entry(win, width=5);
            e_g_end.insert(0, self.saved_params['loop_gate_end']);
            e_g_end.grid(row=1, column=1)
            e_g_pts = tk.Entry(win, width=5);
            e_g_pts.insert(0, self.saved_params['loop_gate_pts']);
            e_g_pts.grid(row=1, column=1, sticky="e")
            tk.Label(win, text="Comp/NPLC:").grid(row=2, column=0)
            e_g_comp = tk.Entry(win, width=10);
            e_g_comp.insert(0, self.saved_params['loop_gate_comp']);
            e_g_comp.grid(row=2, column=1, sticky="w")
            e_g_nplc = tk.Entry(win, width=10);
            e_g_nplc.insert(0, self.saved_params['loop_gate_nplc']);
            e_g_nplc.grid(row=2, column=1, sticky="e")
            tk.Label(win, text="Ramp Step/Delay:").grid(row=3, column=0)
            e_g_rs = tk.Entry(win, width=10);
            e_g_rs.insert(0, self.saved_params['loop_ramp_step']);
            e_g_rs.grid(row=3, column=1, sticky="w")
            e_g_rd = tk.Entry(win, width=10);
            e_g_rd.insert(0, self.saved_params['loop_ramp_delay']);
            e_g_rd.grid(row=3, column=1, sticky="e")
            row_idx = 4

        tk.Label(win, text="BIAS SWEEP", font=("bold")).grid(row=row_idx, columnspan=2)
        tk.Label(win, text="Start (mV):").grid(row=row_idx + 1, column=0);
        e_b1 = tk.Entry(win);
        e_b1.insert(0, self.saved_params['bias_start']);
        e_b1.grid(row=row_idx + 1, column=1)
        tk.Label(win, text="End (mV):").grid(row=row_idx + 2, column=0);
        e_b2 = tk.Entry(win);
        e_b2.insert(0, self.saved_params['bias_end']);
        e_b2.grid(row=row_idx + 2, column=1)
        tk.Label(win, text="Step (mV):").grid(row=row_idx + 3, column=0);
        e_s = tk.Entry(win);
        e_s.insert(0, self.saved_params['bias_step']);
        e_s.grid(row=row_idx + 3, column=1)
        tk.Label(win, text="Delay (s):").grid(row=row_idx + 4, column=0);
        e_d = tk.Entry(win);
        e_d.insert(0, self.saved_params['bias_delay']);
        e_d.grid(row=row_idx + 4, column=1)
        tk.Label(win, text="Max Curr (A):").grid(row=row_idx + 5, column=0);
        e_m = tk.Entry(win);
        e_m.insert(0, self.saved_params['bias_max_curr']);
        e_m.grid(row=row_idx + 5, column=1)
        tk.Label(win, text="Dir:").grid(row=row_idx + 6, column=0);
        e_dir = tk.Entry(win);
        e_dir.insert(0, self.saved_params['save_dir']);
        e_dir.grid(row=row_idx + 6, column=1)
        tk.Button(win, text="...",
                  command=lambda: (e_dir.delete(0, tk.END), e_dir.insert(0, filedialog.askdirectory()))).grid(
            row=row_idx + 6, column=2)

        def start():
            self.saved_params.update(
                {'bias_start': e_b1.get(), 'bias_end': e_b2.get(), 'bias_step': e_s.get(), 'bias_delay': e_d.get(),
                 'bias_max_curr': e_m.get(), 'save_dir': e_dir.get()})
            p = {'bias1': float(e_b1.get()), 'bias2': float(e_b2.get()), 'step': float(e_s.get()),
                 'delay': float(e_d.get()), 'max_curr': float(e_m.get()), 'dir': e_dir.get(), 'mode': mode,
                 'with_gate': with_gate}
            if mode == "loop":
                self.saved_params.update(
                    {'loop_gate_start': e_g_start.get(), 'loop_gate_end': e_g_end.get(), 'loop_gate_pts': e_g_pts.get(),
                     'loop_gate_comp': e_g_comp.get(), 'loop_gate_nplc': e_g_nplc.get()})
                p.update({'gate_start': float(e_g_start.get()), 'gate_end': float(e_g_end.get()),
                          'gate_pts': int(e_g_pts.get()), 'gate_comp': float(e_g_comp.get()),
                          'gate_nplc': float(e_g_nplc.get()), 'gate_ramp_step': float(e_g_rs.get()),
                          'gate_ramp_delay': float(e_g_rd.get())})
            win.destroy()
            threading.Thread(target=self.run_measurement_logic, args=(p,), daemon=True).start()

        tk.Button(win, text="RUN", command=start).grid(row=row_idx + 7, columnspan=3, pady=10)

    def run_measurement_logic(self, p):
        try:
            gate_vals = [None]
            if p['mode'] == "loop":
                gate_vals = np.linspace(p['gate_start'], p['gate_end'], p['gate_pts'])
                self.Gate.configure_voltage_source(nplc=p['gate_nplc'], current=1e-6, compliance_current=p['gate_comp'])
                self.Gate.output_on()
                self.Gate.voltage_ramping(p['gate_start'], p['gate_ramp_step'], p['gate_ramp_delay'])

            for g_val in gate_vals:
                if p['mode'] == "loop":
                    self.log(f"Loop Step: Gate {g_val:.4f}V")
                    self.Gate.voltage_ramping(g_val, p['gate_ramp_step'], p['gate_ramp_delay'])
                    time.sleep(0.5)
                self.run_single_bias_sweep(p, gate_val_override=g_val)

            if p['mode'] == "loop":
                self.Gate.voltage_ramping(0, p['gate_ramp_step'], p['gate_ramp_delay'])
                self.Gate.output_off()
                self.log("Loop Complete.")
        except Exception as e:
            self.log(f"Err: {e}")

    def run_single_bias_sweep(self, p, gate_val_override=None):
        # Clean inputs to prevent precision errors
        b1_cleaned = round(p['bias1'], 6)
        b2_cleaned = round(p['bias2'], 6)
        step_cleaned = abs(round(p['step'], 6))

        # --- UPDATED DRIVER CALL ---
        # Passing Signed values directly so the driver handles 0->Sp1->Sp2->0
        self.Bias.create_hysteresis_voltage_sweep_config_list(
            Sp1=b1_cleaned,
            Sp2=b2_cleaned,
            step=step_cleaned,
            curr_range=p['max_curr']
        )

        # Monitor Thread
        stop_gate_monitor = threading.Event()
        gate_data_log = []

        def monitor_gate_task():
            start_t = time.time()
            while not stop_gate_monitor.is_set():
                try:
                    gv = self.Gate.measure__voltage()
                    gi = self.Gate.measure__current()
                    gate_data_log.append([time.time() - start_t, gv, gi])
                    time.sleep(0.1)
                except:
                    pass

        monitor_thread = None
        # CHECK: Only run monitor if requested AND Gate is present
        if p.get('with_gate', False) and self.Gate:
            monitor_thread = threading.Thread(target=monitor_gate_task)
            monitor_thread.start()

        # Run Sweep
        output = self.Bias.run_clist_sweep(delay=p['delay'])

        # Stop Monitor
        if monitor_thread:
            stop_gate_monitor.set()
            monitor_thread.join()

        # Process
        data = [float(x) for x in output.split(',')]
        curr, bias = np.array(data[0::3]), np.array(data[1::3])

        if not os.path.exists(p['dir']): os.makedirs(p['dir'])
        ts = int(time.time())

        gate_lbl = "0"
        if p.get('with_gate', False) and self.Gate:
            if gate_data_log:
                avg_gate = np.mean([row[1] for row in gate_data_log])
                gate_lbl = f"{avg_gate:.3f}"
            elif gate_val_override is not None:
                gate_lbl = f"{gate_val_override:.3f}"

        name = f"VI{ts}_Gate{gate_lbl}_BiasFrom{p['bias1']}To{p['bias2']}"
        csv_path = os.path.join(p['dir'], name + ".csv")
        gate_log_path = os.path.join(p['dir'], name + "_GateLog.csv")
        png_path = os.path.join(p['dir'], name + ".png")

        np.savetxt(csv_path, np.vstack((bias, curr, np.array(data[2::3]))).T, delimiter=',', header="Bias,Current,Time")

        if gate_data_log:
            np.savetxt(gate_log_path, np.array(gate_data_log), delimiter=',', header="Time_Rel,Gate_V,Gate_I")
            self.log(f"Saved Gate Log: {name}_GateLog.csv")

        # Plot
        fig = plt.figure(figsize=(9, 5))
        plt.plot(bias, curr)
        plt.title(name);
        plt.xlabel("Bias (V)");
        plt.ylabel("Current (A)");
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close(fig)

        self.log(f"Saved: {name}")
        self.root.after(0, self.create_plot_popup, bias, curr, name)

    def create_plot_popup(self, x, y, title):
        try:
            win = tk.Toplevel(self.root)
            win.title(f"Plot: {title}")
            fig = Figure(figsize=(9, 5), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(x, y, '-o', markersize=3)
            ax.set_title(title);
            ax.set_xlabel("Bias (V)");
            ax.set_ylabel("Current (A)");
            ax.grid(True)
            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
            NavigationToolbar2Tk(canvas, win).update()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = IVMeasurementGUI(root)
    root.mainloop()