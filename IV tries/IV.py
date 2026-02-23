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

# --- FIX IMPORT PATH ---
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

# Import Keithley class
try:
    from Instruments.keithley2450_with_add_ons import Keithley2450
except ImportError:
    try:
        from Instruments.keithley2450_with_add_ons import Keithley2450
    except ImportError:
        print(f"\nCRITICAL ERROR: Could not import Keithley2450.")
        print("Please ensure 'Instruments' folder is in the parent directory.\n")
        time.sleep(10)


class IVMeasurementGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Keithley 2450 IV Sweeper + Sequencer")
        self.root.geometry("800x850")

        self.Gate = None
        self.Bias = None
        self.sequence_data = []

        # --- MEMORY FOR INPUT FIELDS ---
        # This dictionary stores the last used values
        self.saved_params = {
            # Gate Setup
            'gate_setup_curr': "1e-6",
            'gate_setup_comp': "15e-9",
            'gate_setup_nplc': "1",

            # Gate Ramp
            'gate_ramp_target': "0",
            'gate_ramp_step': "10",
            'gate_ramp_pause': "0.01",

            # Sequencer
            'seq_ramp_step': "10",
            'seq_ramp_delay': "0.01",
            'seq_dir': "",

            # Bias Sweep / Loop Common
            'bias_start': "1000",
            'bias_end': "-1000",
            'bias_step': "10",
            'bias_delay': "0.01",
            'bias_max_curr': "1e-6",
            'save_dir': "",

            # Loop Specific
            'loop_gate_start': "0",
            'loop_gate_end': "1",
            'loop_gate_pts': "5",
            'loop_gate_comp': "15e-9",
            'loop_gate_nplc': "1",
            'loop_ramp_step': "10",
            'loop_ramp_delay': "0.01"
        }

        # --- MENU BAR ---
        menubar = tk.Menu(root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide / Instructions", command=self.popup_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menubar)

        # --- GUI LAYOUT ---
        # 1. Connection
        conn_frame = ttk.LabelFrame(root, text="1. Instrument Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Gate Instrument:").grid(row=0, column=0, padx=5, sticky="w")
        self.gate_combo = ttk.Combobox(conn_frame, width=30)
        self.gate_combo.grid(row=0, column=1, padx=5)

        ttk.Label(conn_frame, text="Bias Instrument:").grid(row=1, column=0, padx=5, sticky="w")
        self.bias_combo = ttk.Combobox(conn_frame, width=30)
        self.bias_combo.grid(row=1, column=1, padx=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_instruments).grid(row=0, column=2, rowspan=2,
                                                                                      padx=10)
        ttk.Button(conn_frame, text="Connect", command=self.connect_instruments).grid(row=2, column=1, pady=10)

        # 2. Gate Control
        gate_frame = ttk.LabelFrame(root, text="2. Gate Control", padding=10)
        gate_frame.pack(fill="x", padx=10, pady=5)

        btn_frame = tk.Frame(gate_frame)
        btn_frame.pack(side="top", fill="x", pady=5)
        ttk.Button(btn_frame, text="Setup Voltage Source", command=self.popup_setup_gate_source).pack(side="left",
                                                                                                      fill="x",
                                                                                                      expand=True,
                                                                                                      padx=5)
        ttk.Button(btn_frame, text="Ramp Gate Voltage", command=self.popup_ramp_gate).pack(side="left", fill="x",
                                                                                           expand=True, padx=5)

        self.btn_gate_toggle = tk.Button(gate_frame, text="Gate Status: UNKNOWN", bg="#e0e0e0",
                                         command=self.toggle_gate_output)
        self.btn_gate_toggle.pack(side="bottom", fill="x", expand=True, padx=5, pady=5)

        # 3. Measurement
        meas_frame = ttk.LabelFrame(root, text="3. Manual & Loop Operations", padding=10)
        meas_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(meas_frame, text="Run Single Sweep (WITH Gate Info)",
                   command=lambda: self.popup_sweep(mode="single", with_gate=True)).pack(side="top", fill="x",
                                                                                         expand=True, padx=5, pady=2)
        ttk.Button(meas_frame, text="Run Single Sweep (NO Gate Info)",
                   command=lambda: self.popup_sweep(mode="single", with_gate=False)).pack(side="top", fill="x",
                                                                                          expand=True, padx=5, pady=2)

        ttk.Separator(meas_frame, orient="horizontal").pack(fill="x", pady=10)
        tk.Button(meas_frame, text="RUN MULTI-GATE IV LOOP", bg="lightblue", font=("Arial", 9, "bold"),
                  command=lambda: self.popup_sweep(mode="loop", with_gate=True)).pack(side="top", fill="x", expand=True,
                                                                                      padx=5, pady=5)

        # 4. Sequencer
        seq_frame = ttk.LabelFrame(root, text="4. Sequencer (Advanced)", padding=10)
        seq_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(seq_frame, text="OPEN SEQUENCER CONFIG", bg="thistle", font=("Arial", 9, "bold"),
                  command=self.popup_sequencer).pack(fill="x", expand=True)

        # 5. Log
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
            else:
                messagebox.showwarning("Warning", "Select a Bias instrument.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_gate_output(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        try:
            if self.Gate.source_enabled:
                self.Gate.output_off()
                self.log("Gate Output turned OFF.")
            else:
                self.Gate.output_on()
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

    # --- HELP POPUP ---
    def popup_help(self):
        win = tk.Toplevel(self.root)
        win.title("User Guide")
        win.geometry("600x700")

        text_area = tk.Text(win, wrap="word", font=("Arial", 10), padx=10, pady=10)
        text_area.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_area, command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        help_text = """
IV MEASUREMENT GUI - USER GUIDE

1. INSTRUMENT CONNECTION
------------------------
This section manages the communication with your Keithley instruments.

- Gate Instrument / Bias Instrument: 
  Dropdown lists showing all detected VISA resource addresses.
  (e.g., USB0::... or TCPIP::...)

- Refresh: 
  Scans the computer for connected instruments and updates the dropdowns.

- Connect: 
  Initializes the connection to the selected instruments.
  *Note:* You must select a Bias instrument to run any sweep.
  The Gate instrument is optional only for "Run Single Sweep (NO Gate Info)".

2. GATE CONTROL
------------------------
Direct manual control over the Gate Source Measure Unit (SMU).

- Setup Voltage Source: 
  Opens a popup to configure safety limits.
  * Current Limit: Max current the Gate can source/sink.
  * Compliance: Safety limit to protect the device.
  * NPLC: Integration time. Higher = slower, less noise.

- Ramp Gate Voltage: 
  Smoothly moves the gate voltage to a target value.
  * Target: Final Voltage.
  * Step: Voltage change per step (mV).
  * Pause: Wait time between steps (seconds).

- Gate Toggle Button: 
  A large colored button indicating status.
  * RED: Gate is OFF. Click to turn ON.
  * GREEN: Gate is ON. Click to turn OFF.

3. MEASUREMENT OPERATIONS
------------------------
Standard measurement modes.

- Run Single Sweep (WITH Gate Info):
  * Performs one IV sweep on the Bias instrument.
  * Reads the current voltage from the Gate instrument.
  * Saves Gate Voltage in the filename and file header.
  * Requires: Both instruments connected.

- Run Single Sweep (NO Gate Info):
  * Performs one IV sweep on the Bias instrument.
  * IGNORES the Gate instrument completely.
  * Useful for 2-terminal devices or when Gate is disconnected.

- RUN MULTI-GATE IV LOOP:
  * Automatically changes the Gate voltage in steps (Start -> End).
  * At each Gate step, it performs a full Bias IV sweep.
  * *Loop Settings:* You can control the Gate Ramping speed (Step/Delay) inside the popup.

4. SEQUENCER (ADVANCED)
------------------------
Allows running a custom list of measurements from a text file.

Global Settings (Popup):
- Gate Ramp Step (mV): Speed of gate voltage change between steps.
- Gate Ramp Delay (s): Pause between gate voltage steps.

File Format:
Create a .txt or .csv file. Each line is one measurement step.
Columns: Gate_V, Bias_Start, Bias_End, Bias_Step, Compliance

Example:
0.0, 0, 1000, 10, 1e-6
1.0, 0, 2000, 10, 1e-6
"""
        text_area.insert("1.0", help_text)
        text_area.config(state="disabled")

    # --- SEQUENCER LOGIC ---
    def popup_sequencer(self):
        if not self.Bias: return messagebox.showerror("Error", "Bias not connected")
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")

        win = tk.Toplevel(self.root)
        win.title("Sequencer Configuration")
        win.geometry("600x600")

        instr = "Format: Gate_V, Bias_Start_mV, Bias_End_mV, Step_mV, Compliance_A\n" \
                "Example: 1.0, 0, 1000, 10, 1e-6\n"
        tk.Label(win, text=instr, justify="left", bg="lightyellow", relief="solid").pack(pady=10, padx=10, fill="x")

        # 1. File Selection
        frame_file = tk.Frame(win)
        frame_file.pack(pady=5)
        lbl_status = tk.Label(frame_file, text="No file loaded", fg="red")

        def load_file():
            fn = filedialog.askopenfilename(
                filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")])
            if fn:
                try:
                    self.sequence_data = []
                    with open(fn, 'r') as f:
                        for line in f:
                            if line.strip() == "" or line.strip().startswith("#"): continue
                            parts = line.split(',')
                            if len(parts) < 5: continue
                            self.sequence_data.append({
                                'gate': float(parts[0]),
                                'bias_start': float(parts[1]),
                                'bias_end': float(parts[2]),
                                'step': float(parts[3]),
                                'comp': float(parts[4])
                            })
                    lbl_status.config(text=f"Loaded {len(self.sequence_data)} steps.", fg="green")
                    text_preview.delete(1.0, tk.END)
                    for i, s in enumerate(self.sequence_data):
                        text_preview.insert(tk.END,
                                            f"{i + 1}: Gate={s['gate']}V, Bias={s['bias_start']}->{s['bias_end']}mV\n")
                except Exception as e:
                    messagebox.showerror("Load Error", str(e))

        tk.Button(frame_file, text="Load Sequence File", command=load_file).pack(side="left", padx=5)
        lbl_status.pack(side="left", padx=5)

        text_preview = tk.Text(win, height=10, width=60)
        text_preview.pack(pady=5)

        # 2. Global Settings (Using stored values)
        frame_sets = ttk.LabelFrame(win, text="Global Sequence Settings", padding=5)
        frame_sets.pack(pady=5, fill="x", padx=10)

        tk.Label(frame_sets, text="Gate Ramp Step (mV):").grid(row=0, column=0, sticky="e")
        e_g_step = tk.Entry(frame_sets, width=10);
        e_g_step.insert(0, self.saved_params['seq_ramp_step']);
        e_g_step.grid(row=0, column=1)

        tk.Label(frame_sets, text="Gate Ramp Delay (s):").grid(row=0, column=2, sticky="e")
        e_g_delay = tk.Entry(frame_sets, width=10);
        e_g_delay.insert(0, self.saved_params['seq_ramp_delay']);
        e_g_delay.grid(row=0, column=3)

        tk.Label(frame_sets, text="Save Directory:").grid(row=1, column=0, sticky="e")
        e_dir = tk.Entry(frame_sets, width=30)
        e_dir.insert(0, self.saved_params['seq_dir'])
        e_dir.grid(row=1, column=1, columnspan=2)

        tk.Button(frame_sets, text="...",
                  command=lambda: (e_dir.delete(0, tk.END), e_dir.insert(0, filedialog.askdirectory()))).grid(row=1,
                                                                                                              column=3)

        def run_seq():
            if not self.sequence_data: return messagebox.showerror("Error", "No steps loaded")
            if not e_dir.get(): return messagebox.showerror("Error", "Select save dir")

            try:
                # Save input to memory
                self.saved_params['seq_ramp_step'] = e_g_step.get()
                self.saved_params['seq_ramp_delay'] = e_g_delay.get()
                self.saved_params['seq_dir'] = e_dir.get()

                # Capture Global Settings
                global_params = {
                    'save_dir': e_dir.get(),
                    'gate_ramp_step': float(e_g_step.get()),
                    'gate_ramp_delay': float(e_g_delay.get())
                }
                win.destroy()
                threading.Thread(target=self.run_sequencer_thread, args=(global_params,), daemon=True).start()
            except ValueError:
                messagebox.showerror("Error", "Check numeric inputs for ramp step/delay.")

        tk.Button(win, text="RUN SEQUENCE", bg="thistle", font=("Arial", 10, "bold"), command=run_seq).pack(pady=15,
                                                                                                            fill="x",
                                                                                                            padx=20)

    def run_sequencer_thread(self, global_params):
        self.log("Starting Sequencer...")
        try:
            self.Gate.configure_voltage_source(nplc=1, current=1e-6, compliance_current=15e-9)
            self.Gate.output_on()
            self.root.after(0, self.update_gate_visuals)

            save_dir = global_params['save_dir']
            ramp_step = global_params['gate_ramp_step']
            ramp_delay = global_params['gate_ramp_delay']

            for i, step in enumerate(self.sequence_data):
                self.log(f"--- Sequence Step {i + 1}/{len(self.sequence_data)} ---")

                # RAMP GATE with User Settings
                self.log(f"Ramping Gate to {step['gate']} V...")
                self.Gate.voltage_ramping(step['gate'], ramp_step, ramp_delay)
                time.sleep(0.5)

                p = {
                    'bias1': step['bias_start'],
                    'bias2': step['bias_end'],
                    'step': abs(step['step']),
                    'delay': 0.01,
                    'max_curr': step['comp'],
                    'dir': save_dir,
                    'with_gate': True
                }
                self.run_single_bias_sweep(p, gate_val_override=step['gate'])

            self.log("Sequence Finished. Resetting Gate to 0V.")
            self.Gate.voltage_ramping(0, ramp_step, ramp_delay)
            self.Gate.output_off()
            self.root.after(0, self.update_gate_visuals)

        except Exception as e:
            self.log(f"Sequence Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    # --- STANDARD POPUPS & RUNNER ---
    def popup_setup_gate_source(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        win = tk.Toplevel(self.root)
        win.title("Setup Gate")

        tk.Label(win, text="Current Limit (A):").grid(row=0, column=0)
        e_c = tk.Entry(win);
        e_c.insert(0, self.saved_params['gate_setup_curr']);
        e_c.grid(row=0, column=1)

        tk.Label(win, text="Compliance (A):").grid(row=1, column=0)
        e_comp = tk.Entry(win);
        e_comp.insert(0, self.saved_params['gate_setup_comp']);
        e_comp.grid(row=1, column=1)

        tk.Label(win, text="NPLC:").grid(row=2, column=0)
        e_nplc = tk.Entry(win);
        e_nplc.insert(0, self.saved_params['gate_setup_nplc']);
        e_nplc.grid(row=2, column=1)

        def apply():
            try:
                # Save
                self.saved_params['gate_setup_curr'] = e_c.get()
                self.saved_params['gate_setup_comp'] = e_comp.get()
                self.saved_params['gate_setup_nplc'] = e_nplc.get()

                self.Gate.configure_voltage_source(nplc=float(e_nplc.get()), current=float(e_c.get()),
                                                   compliance_current=float(e_comp.get()))
                self.Gate.output_on()
                self.log("Gate configured & ON.")
                self.update_gate_visuals()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Apply", command=apply).grid(row=3, columnspan=2, pady=10)

    def popup_ramp_gate(self):
        if not self.Gate: return messagebox.showerror("Error", "Gate not connected")
        win = tk.Toplevel(self.root)
        win.title("Ramp Gate")

        tk.Label(win, text="Target (V):").grid(row=0, column=0)
        e_t = tk.Entry(win);
        e_t.insert(0, self.saved_params['gate_ramp_target']);
        e_t.grid(row=0, column=1)

        tk.Label(win, text="Step (mV):").grid(row=1, column=0)
        e_s = tk.Entry(win);
        e_s.insert(0, self.saved_params['gate_ramp_step']);
        e_s.grid(row=1, column=1)

        tk.Label(win, text="Pause (s):").grid(row=2, column=0)
        e_p = tk.Entry(win);
        e_p.insert(0, self.saved_params['gate_ramp_pause']);
        e_p.grid(row=2, column=1)

        def run():
            try:
                # Save
                self.saved_params['gate_ramp_target'] = e_t.get()
                self.saved_params['gate_ramp_step'] = e_s.get()
                self.saved_params['gate_ramp_pause'] = e_p.get()

                t, s, p = float(e_t.get()), float(e_s.get()), float(e_p.get())
                threading.Thread(target=lambda: (self.log(f"Ramping to {t}V..."), self.Gate.voltage_ramping(t, s, p),
                                                 self.log("Ramp done.")), daemon=True).start()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Start", command=run).grid(row=3, columnspan=2, pady=10)

    def popup_sweep(self, mode="single", with_gate=True):
        if not self.Bias: return messagebox.showerror("Error", "Bias not connected")
        if with_gate and not self.Gate and mode != "single":
            return messagebox.showerror("Error", "Gate not connected")

        win = tk.Toplevel(self.root)
        title = "Hysteresis Sweep " + (
            "(WITH Gate)" if with_gate else "(NO Gate)") if mode == "single" else "Multi-Gate IV Loop"
        win.title(title)

        start_row = 0
        e_g_start, e_g_end, e_g_pts = None, None, None
        e_g_comp, e_g_nplc = None, None
        e_g_ramp_delay, e_g_ramp_step = None, None

        if mode == "loop":
            tk.Label(win, text="--- Gate Loop Settings ---", font=("Arial", 9, "bold")).grid(row=0, columnspan=2,
                                                                                             pady=5)

            tk.Label(win, text="Gate Start (V):").grid(row=1, column=0)
            e_g_start = tk.Entry(win);
            e_g_start.insert(0, self.saved_params['loop_gate_start']);
            e_g_start.grid(row=1, column=1)

            tk.Label(win, text="Gate End (V):").grid(row=2, column=0)
            e_g_end = tk.Entry(win);
            e_g_end.insert(0, self.saved_params['loop_gate_end']);
            e_g_end.grid(row=2, column=1)

            tk.Label(win, text="Num Points:").grid(row=3, column=0)
            e_g_pts = tk.Entry(win);
            e_g_pts.insert(0, self.saved_params['loop_gate_pts']);
            e_g_pts.grid(row=3, column=1)

            tk.Label(win, text="Gate Compliance (A):").grid(row=4, column=0)
            e_g_comp = tk.Entry(win);
            e_g_comp.insert(0, self.saved_params['loop_gate_comp']);
            e_g_comp.grid(row=4, column=1)

            tk.Label(win, text="Gate NPLC:").grid(row=5, column=0)
            e_g_nplc = tk.Entry(win);
            e_g_nplc.insert(0, self.saved_params['loop_gate_nplc']);
            e_g_nplc.grid(row=5, column=1)

            tk.Label(win, text="Ramp Step (mV):").grid(row=6, column=0)
            e_g_ramp_step = tk.Entry(win);
            e_g_ramp_step.insert(0, self.saved_params['loop_ramp_step']);
            e_g_ramp_step.grid(row=6, column=1)

            tk.Label(win, text="Ramp Delay (s):").grid(row=7, column=0)
            e_g_ramp_delay = tk.Entry(win);
            e_g_ramp_delay.insert(0, self.saved_params['loop_ramp_delay']);
            e_g_ramp_delay.grid(row=7, column=1)

            start_row = 8

        tk.Label(win, text="--- Bias Sweep Settings ---", font=("Arial", 9, "bold")).grid(row=start_row, columnspan=2,
                                                                                          pady=5)

        tk.Label(win, text="Bias 1 (mV) [Start]:").grid(row=start_row + 1, column=0)
        e_b1 = tk.Entry(win);
        e_b1.insert(0, self.saved_params['bias_start']);
        e_b1.grid(row=start_row + 1, column=1)

        tk.Label(win, text="Bias 2 (mV) [Turn]:").grid(row=start_row + 2, column=0)
        e_b2 = tk.Entry(win);
        e_b2.insert(0, self.saved_params['bias_end']);
        e_b2.grid(row=start_row + 2, column=1)

        tk.Label(win, text="Step (mV):").grid(row=start_row + 3, column=0)
        e_s = tk.Entry(win);
        e_s.insert(0, self.saved_params['bias_step']);
        e_s.grid(row=start_row + 3, column=1)

        tk.Label(win, text="Meas Delay (s):").grid(row=start_row + 4, column=0)
        e_d = tk.Entry(win);
        e_d.insert(0, self.saved_params['bias_delay']);
        e_d.grid(row=start_row + 4, column=1)

        tk.Label(win, text="Max Current (A):").grid(row=start_row + 5, column=0)
        e_m = tk.Entry(win);
        e_m.insert(0, self.saved_params['bias_max_curr']);
        e_m.grid(row=start_row + 5, column=1)

        tk.Label(win, text="Save Dir:").grid(row=start_row + 6, column=0)
        e_dir = tk.Entry(win);
        e_dir.insert(0, self.saved_params['save_dir']);
        e_dir.grid(row=start_row + 6, column=1)

        ttk.Button(win, text="...", width=3,
                   command=lambda: (e_dir.delete(0, tk.END), e_dir.insert(0, filedialog.askdirectory()))).grid(
            row=start_row + 6, column=2)

        def start():
            try:
                # Save Bias Settings
                self.saved_params['bias_start'] = e_b1.get()
                self.saved_params['bias_end'] = e_b2.get()
                self.saved_params['bias_step'] = e_s.get()
                self.saved_params['bias_delay'] = e_d.get()
                self.saved_params['bias_max_curr'] = e_m.get()
                self.saved_params['save_dir'] = e_dir.get()

                # Save Loop Settings
                if mode == "loop":
                    self.saved_params['loop_gate_start'] = e_g_start.get()
                    self.saved_params['loop_gate_end'] = e_g_end.get()
                    self.saved_params['loop_gate_pts'] = e_g_pts.get()
                    self.saved_params['loop_gate_comp'] = e_g_comp.get()
                    self.saved_params['loop_gate_nplc'] = e_g_nplc.get()
                    self.saved_params['loop_ramp_step'] = e_g_ramp_step.get()
                    self.saved_params['loop_ramp_delay'] = e_g_ramp_delay.get()

                p = {
                    'bias1': float(e_b1.get()), 'bias2': float(e_b2.get()),
                    'step': abs(float(e_s.get())), 'delay': float(e_d.get()),
                    'max_curr': float(e_m.get()), 'dir': e_dir.get(),
                    'mode': mode, 'with_gate': with_gate
                }
                if not p['dir']: return messagebox.showwarning("Warning", "Select save dir")

                if mode == "loop":
                    p['gate_start'] = float(e_g_start.get())
                    p['gate_end'] = float(e_g_end.get())
                    p['gate_pts'] = int(e_g_pts.get())
                    p['gate_comp'] = float(e_g_comp.get())
                    p['gate_nplc'] = float(e_g_nplc.get())
                    p['gate_ramp_step'] = float(e_g_ramp_step.get())
                    p['gate_ramp_delay'] = float(e_g_ramp_delay.get())

                win.destroy()
                threading.Thread(target=self.run_measurement_logic, args=(p,), daemon=True).start()
            except ValueError:
                messagebox.showerror("Error", "Check numeric inputs")

        btn_text = "RUN LOOP" if mode == "loop" else "RUN SWEEP"
        ttk.Button(win, text=btn_text, command=start).grid(row=start_row + 7, columnspan=3, pady=15)

    def run_measurement_logic(self, p):
        try:
            if p['mode'] == "loop":
                self.log("Initializing Multi-Gate Loop...")
                gate_values = np.linspace(p['gate_start'], p['gate_end'], p['gate_pts'])

                self.log("Configuring Gate...")
                self.Gate.configure_voltage_source(nplc=p['gate_nplc'], current=1e-6, compliance_current=p['gate_comp'])
                self.Gate.output_on()
                self.root.after(0, self.update_gate_visuals)

                self.log(f"Ramping Gate to Start: {p['gate_start']} V")
                self.Gate.voltage_ramping(p['gate_start'], p['gate_ramp_step'], p['gate_ramp_delay'])
            else:
                gate_values = [None]

            for i, gate_target in enumerate(gate_values):
                if p['mode'] == "loop":
                    self.log(f"--- Step {i + 1}/{len(gate_values)}: Gate = {gate_target:.4f} V ---")
                    self.Gate.voltage_ramping(gate_target, p['gate_ramp_step'], p['gate_ramp_delay'])
                    time.sleep(0.5)

                self.run_single_bias_sweep(p, gate_val_override=gate_target)

            if p['mode'] == "loop":
                self.log("Loop finished. Ramping Gate to 0V...")
                self.Gate.voltage_ramping(0, p['gate_ramp_step'], p['gate_ramp_delay'])
                self.Gate.output_off()
                self.root.after(0, self.update_gate_visuals)
                self.log("Gate OFF. Measurement Complete.")

        except Exception as e:
            self.log(f"Measurement Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def run_single_bias_sweep(self, p, gate_val_override=None):
        if p['bias1'] < 0:
            direction_pos_first = False
            pos_val = -p['bias1']
            neg_val = -p['bias2']
        else:
            direction_pos_first = True
            pos_val = p['bias1']
            neg_val = p['bias2']

        self.Bias.create_hysteresis_voltage_sweep_config_list(
            pos_val, neg_val, p['step'], p['max_curr'], direction_pos_first
        )

        real_gate_v = 0
        if p['with_gate']:
            if self.Gate:
                try:
                    real_gate_v = self.Gate.measure__voltage()
                except:
                    real_gate_v = gate_val_override if gate_val_override is not None else 0

        output = self.Bias.run_clist_sweep(delay=p['delay'])

        data = [float(x) for x in output.split(',')]
        curr, bias = np.array(data[0::3]), np.array(data[1::3])

        if not os.path.exists(p['dir']): os.makedirs(p['dir'])
        ts = int(time.time())
        gate_str = f"_Gate{real_gate_v:.3f}" if p['with_gate'] else ""
        name = f"VI{ts}{gate_str}_BiasFrom{p['bias1']}To{p['bias2']}"

        csv_path = os.path.join(p['dir'], name + ".csv")
        png_path = os.path.join(p['dir'], name + ".png")

        np.savetxt(csv_path, np.vstack((bias, curr, np.array(data[2::3]))).T, delimiter=',', header="Bias,Current,Time")

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