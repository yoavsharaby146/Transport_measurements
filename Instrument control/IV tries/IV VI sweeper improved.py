import sys, os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa
import time
import threading
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, repo_root)  # front of path: resolves Instruments/ at repo root

try:
    from Instruments.keithley2450_with_add_ons import Keithley2450
    from Instruments.yokogawa7651_with_add_ons import Yokogawa7651
    from Instruments.yokogawags200_with_add_ons import YokogawaGS200
except ImportError as e:
    print("\nCRITICAL ERROR: Could not import instrument drivers.")
    print(f"{e}")
    print("Make sure 'Instruments/' exists at the repository root.\n")

# Yokogawa fixed voltage ranges (no auto-range command on either unit)
V_RANGES = [10e-3, 100e-3, 1, 10, 30]

GATE_KINDS = {
    "Keithley 2450": "keithley",
    "Yokogawa 7651": "yoko7651",
    "Yokogawa GS200": "gs200",
}


def pick_v_range(level):
    """Smallest fixed Yokogawa range that fits |level|."""
    for r in V_RANGES:
        if abs(level) <= r:
            return r
    return V_RANGES[-1]


class IVVISweeperImproved:
    def __init__(self, root):
        self.root = root
        self.root.title("IV/VI Sweeper - Bias (Keithley) + Optional Gate")

        self.bias_inst = None
        self.gate_inst = None
        self.gate_kind = None  # 'keithley' | 'yoko7651' | 'gs200'
        self.stop_event = threading.Event()

        self.saved_params = {
            # IV sweep (voltage source)
            'iv_sp1': "1000", 'iv_sp2': "-1000", 'iv_step': "10",
            'iv_delay': "0.01", 'iv_compliance': "1e-6",
            # VI sweep (current source)
            'vi_sp1': "1e-6", 'vi_sp2': "-1e-6", 'vi_step': "1e-7",
            'vi_delay': "0.01", 'vi_compliance': "1",
            # Bias source config
            'bias_nplc': "1",
            # Gate settings
            'gate_compliance': "1e-3", 'gate_nplc': "1",
            'gate_target': "0", 'gate_step': "10", 'gate_rate': "0.2",
            'gate_settle': "1",
            # Gate loop
            'gate_loop': False, 'gate_start': "-5", 'gate_end': "5", 'gate_loop_step': "1",
            'gate_loop_ramp_step': "10", 'gate_loop_ramp_delay': "0.05",
            'save_dir': "",
        }

        self._build_ui()
        self.refresh_instruments()

    # ============================ UI ============================

    def _build_ui(self):
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill="both", expand=True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # === 1. CONNECTION ===
        conn = ttk.LabelFrame(self.main_frame, text="1. Instrument Connection", padding=10)
        conn.pack(fill="x", pady=5)
        for c in range(6):
            conn.columnconfigure(c, weight=1)

        # Bias row (always Keithley)
        ttk.Label(conn, text="Bias (Keithley 2450):").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.bias_combo = ttk.Combobox(conn, width=32)
        self.bias_combo.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(conn, text="Connect", command=self.connect_bias, width=9).grid(row=0, column=2, padx=5)
        self.btn_bias_term = tk.Button(conn, text="Term: ---", bg="#e0e0e0", width=10,
                                       command=self.toggle_bias_terminals)
        self.btn_bias_term.grid(row=0, column=3, padx=5)
        self.btn_bias_out = tk.Button(conn, text="Out: ---", bg="#e0e0e0", width=9,
                                      command=self.toggle_bias_output)
        self.btn_bias_out.grid(row=0, column=4, padx=5)
        ttk.Button(conn, text="Reset", command=self.reset_bias, width=7).grid(row=0, column=5, padx=5)

        # Gate row (optional, selectable type)
        ttk.Label(conn, text="Gate (optional):").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        gate_row = ttk.Frame(conn)
        gate_row.grid(row=1, column=1, sticky="ew")
        self.gate_kind_combo = ttk.Combobox(gate_row, values=list(GATE_KINDS.keys()),
                                            state="readonly", width=16)
        self.gate_kind_combo.current(0)
        self.gate_kind_combo.pack(side="left")
        self.gate_combo = ttk.Combobox(gate_row, width=24)
        self.gate_combo.pack(side="left", padx=(5, 0), fill="x", expand=True)
        ttk.Button(conn, text="Connect", command=self.connect_gate, width=9).grid(row=1, column=2, padx=5)
        self.btn_gate_out = tk.Button(conn, text="Out: ---", bg="#e0e0e0", width=9,
                                      command=self.toggle_gate_output)
        self.btn_gate_out.grid(row=1, column=4, padx=5)
        ttk.Button(conn, text="Reset", command=self.reset_gate, width=7).grid(row=1, column=5, padx=5)

        btns = ttk.Frame(conn)
        btns.grid(row=2, column=0, columnspan=6, pady=5)
        ttk.Button(btns, text="Scan Instruments", command=self.refresh_instruments).pack(side="left", padx=10)
        ttk.Button(btns, text="Refresh Status", command=self.refresh_all_status).pack(side="left", padx=10)

        # === 2. GATE SOURCE CONFIG + RAMP ===
        gate = ttk.LabelFrame(self.main_frame, text="2. Gate Voltage Source & Ramping", padding=10)
        gate.pack(fill="x", pady=5)

        cfg = ttk.Frame(gate)
        cfg.pack(fill="x")
        ttk.Label(cfg, text="Compliance (A):").pack(side="left", padx=5)
        self.ent_gate_compliance = ttk.Entry(cfg, width=10)
        self.ent_gate_compliance.insert(0, self.saved_params['gate_compliance'])
        self.ent_gate_compliance.pack(side="left", padx=2)

        self.lbl_gate_nplc = ttk.Label(cfg, text="NPLC:")
        self.lbl_gate_nplc.pack(side="left", padx=(15, 0))
        self.ent_gate_nplc = ttk.Entry(cfg, width=6)
        self.ent_gate_nplc.insert(0, self.saved_params['gate_nplc'])
        self.ent_gate_nplc.pack(side="left", padx=2)

        ttk.Label(cfg, text="Target (V):").pack(side="left", padx=(15, 0))
        self.ent_gate_target = ttk.Entry(cfg, width=10)
        self.ent_gate_target.insert(0, self.saved_params['gate_target'])
        self.ent_gate_target.pack(side="left", padx=2)
        ttk.Label(cfg, text="Step (mV):").pack(side="left", padx=(15, 0))
        self.ent_gate_step = ttk.Entry(cfg, width=8)
        self.ent_gate_step.insert(0, self.saved_params['gate_step'])
        self.ent_gate_step.pack(side="left", padx=2)
        ttk.Label(cfg, text="Rate (V/s):").pack(side="left", padx=(15, 0))
        self.ent_gate_rate = ttk.Entry(cfg, width=8)
        self.ent_gate_rate.insert(0, self.saved_params['gate_rate'])
        self.ent_gate_rate.pack(side="left", padx=2)

        gate_btns = ttk.Frame(gate)
        gate_btns.pack(fill="x", pady=5)
        self.btn_gate_apply = ttk.Button(gate_btns, text="Configure Gate Source",
                                         command=self.apply_gate_config)
        self.btn_gate_apply.pack(side="left", padx=10)
        self.btn_gate_ramp = ttk.Button(gate_btns, text="Ramp Gate", command=self.start_gate_ramp)
        self.btn_gate_ramp.pack(side="left", padx=10)
        self.btn_gate_measure = ttk.Button(gate_btns, text="Measure Once", command=self.measure_gate_once)
        self.btn_gate_measure.pack(side="left", padx=10)
        self.lbl_gate_status = ttk.Label(gate_btns, text="Gate: --- V", font=("Consolas", 10))
        self.lbl_gate_status.pack(side="left", padx=20)

        # === 3. MEASUREMENT TYPE ===
        typ = ttk.LabelFrame(self.main_frame, text="3. Measurement Type", padding=10)
        typ.pack(fill="x", pady=5)
        self.sweep_type_var = tk.StringVar(value="iv")
        inner = ttk.Frame(typ)
        inner.pack()
        ttk.Radiobutton(inner, text="IV Sweep (Source Voltage, Measure Current)",
                        variable=self.sweep_type_var, value="iv",
                        command=self._update_ui_labels).pack(side="left", padx=20)
        ttk.Radiobutton(inner, text="VI Sweep (Source Current, Measure Voltage)",
                        variable=self.sweep_type_var, value="vi",
                        command=self._update_ui_labels).pack(side="left", padx=20)

        # === 4. BIAS SWEEP CONFIG ===
        cfgf = ttk.LabelFrame(self.main_frame, text="4. Bias Sweep Configuration", padding=10)
        cfgf.pack(fill="x", pady=5)
        for c in range(8):
            cfgf.columnconfigure(c, weight=1)

        ttk.Label(cfgf, text="Sp1:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.ent_sp1 = ttk.Entry(cfgf, width=13)
        self.ent_sp1.grid(row=0, column=1, padx=5, sticky="ew")
        self.lbl_sp1_unit = ttk.Label(cfgf, text="mV")
        self.lbl_sp1_unit.grid(row=0, column=2, sticky="w")

        ttk.Label(cfgf, text="Sp2:").grid(row=0, column=3, padx=5, pady=2, sticky="e")
        self.ent_sp2 = ttk.Entry(cfgf, width=13)
        self.ent_sp2.grid(row=0, column=4, padx=5, sticky="ew")
        self.lbl_sp2_unit = ttk.Label(cfgf, text="mV")
        self.lbl_sp2_unit.grid(row=0, column=5, sticky="w")

        ttk.Label(cfgf, text="Step:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.ent_step = ttk.Entry(cfgf, width=13)
        self.ent_step.grid(row=1, column=1, padx=5, sticky="ew")
        self.lbl_step_unit = ttk.Label(cfgf, text="mV")
        self.lbl_step_unit.grid(row=1, column=2, sticky="w")

        ttk.Label(cfgf, text="Delay (s):").grid(row=1, column=3, padx=5, pady=2, sticky="e")
        self.ent_delay = ttk.Entry(cfgf, width=13)
        self.ent_delay.grid(row=1, column=4, padx=5, sticky="ew")

        self.lbl_compliance = ttk.Label(cfgf, text="Compliance (A):")
        self.lbl_compliance.grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.ent_compliance = ttk.Entry(cfgf, width=13)
        self.ent_compliance.grid(row=2, column=1, padx=5, sticky="ew")

        ttk.Label(cfgf, text="Bias NPLC:").grid(row=2, column=3, padx=5, pady=2, sticky="e")
        self.ent_bias_nplc = ttk.Entry(cfgf, width=13)
        self.ent_bias_nplc.insert(0, self.saved_params['bias_nplc'])
        self.ent_bias_nplc.grid(row=2, column=4, padx=5, sticky="ew")

        # === 5. GATE LOOP CONFIG ===
        loop = ttk.LabelFrame(self.main_frame, text="5. Gate Sweep Loop (optional)", padding=10)
        loop.pack(fill="x", pady=5)
        self.gate_loop_var = tk.BooleanVar(value=False)
        self.chk_loop = ttk.Checkbutton(loop, text="Run bias sweep at multiple gate voltages",
                                        variable=self.gate_loop_var,
                                        command=self._toggle_loop_entries)
        self.chk_loop.pack(side="left", padx=10)
        lf = ttk.Frame(loop)
        lf.pack(side="left", padx=10)
        ttk.Label(lf, text="Start (V):").pack(side="left")
        self.ent_gate_start = ttk.Entry(lf, width=8)
        self.ent_gate_start.insert(0, self.saved_params['gate_start'])
        self.ent_gate_start.pack(side="left", padx=3)
        ttk.Label(lf, text="End (V):").pack(side="left")
        self.ent_gate_end = ttk.Entry(lf, width=8)
        self.ent_gate_end.insert(0, self.saved_params['gate_end'])
        self.ent_gate_end.pack(side="left", padx=3)
        ttk.Label(lf, text="Step (V):").pack(side="left")
        self.ent_gate_loop_step = ttk.Entry(lf, width=8)
        self.ent_gate_loop_step.insert(0, self.saved_params['gate_loop_step'])
        self.ent_gate_loop_step.pack(side="left", padx=3)
        ttk.Label(loop, text="Settle (s):").pack(side="left", padx=(20, 0))
        self.ent_gate_settle = ttk.Entry(loop, width=6)
        self.ent_gate_settle.insert(0, self.saved_params['gate_settle'])
        self.ent_gate_settle.pack(side="left", padx=3)

        # dedicated ramp parameters for gate movement inside the loop
        ttk.Label(loop, text="Ramp Step (mV):").pack(side="left", padx=(20, 0))
        self.ent_gate_loop_ramp_step = ttk.Entry(loop, width=7)
        self.ent_gate_loop_ramp_step.insert(0, self.saved_params['gate_loop_ramp_step'])
        self.ent_gate_loop_ramp_step.pack(side="left", padx=3)
        ttk.Label(loop, text="Ramp Delay (s):").pack(side="left", padx=(15, 0))
        self.ent_gate_loop_ramp_delay = ttk.Entry(loop, width=7)
        self.ent_gate_loop_ramp_delay.insert(0, self.saved_params['gate_loop_ramp_delay'])
        self.ent_gate_loop_ramp_delay.pack(side="left", padx=3)

        # === 6. SAVE + EXECUTION ===
        ex = ttk.LabelFrame(self.main_frame, text="6. Save & Execution", padding=10)
        ex.pack(fill="x", pady=5)
        row0 = ttk.Frame(ex)
        row0.pack(fill="x")
        ttk.Label(row0, text="Save Directory:").pack(side="left", padx=5)
        self.ent_dir = ttk.Entry(row0)
        self.ent_dir.insert(0, self.saved_params['save_dir'])
        self.ent_dir.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(row0, text="Browse...", command=self.browse_directory).pack(side="left", padx=5)

        row1 = ttk.Frame(ex)
        row1.pack(pady=5)
        self.btn_run = ttk.Button(row1, text="RUN SWEEP", command=self.start_sweep, width=15)
        self.btn_run.pack(side="left", padx=20)
        self.btn_abort = ttk.Button(row1, text="ABORT", command=self.abort_sweep, width=10,
                                    state="disabled")
        self.btn_abort.pack(side="left", padx=20)
        self.lbl_progress = ttk.Label(row1, text="Ready", font=("Arial", 10))
        self.lbl_progress.pack(side="left", padx=20)

        # === LOG ===
        logf = ttk.LabelFrame(self.main_frame, text="Log", padding=10)
        logf.pack(fill="both", expand=True, pady=5)
        self.log_text = tk.Text(logf, height=8, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        self._update_ui_labels()
        self._toggle_loop_entries()

    def _toggle_loop_entries(self):
        state = "normal" if self.gate_loop_var.get() else "disabled"
        for e in (self.ent_gate_start, self.ent_gate_end, self.ent_gate_loop_step,
                  self.ent_gate_settle, self.ent_gate_loop_ramp_step,
                  self.ent_gate_loop_ramp_delay):
            e.config(state=state)
        if self.gate_loop_var.get() and not self.gate_inst:
            self.log("Note: gate loop requires a connected gate instrument")

    def _update_ui_labels(self):
        st = self.sweep_type_var.get()
        if st == "iv":
            self.lbl_compliance.config(text="Compliance (A):")
            for l in (self.lbl_sp1_unit, self.lbl_sp2_unit, self.lbl_step_unit):
                l.config(text="mV")
            vals = ['iv_sp1', 'iv_sp2', 'iv_step', 'iv_delay', 'iv_compliance']
        else:
            self.lbl_compliance.config(text="Compliance (V):")
            for l in (self.lbl_sp1_unit, self.lbl_sp2_unit, self.lbl_step_unit):
                l.config(text="A")
            vals = ['vi_sp1', 'vi_sp2', 'vi_step', 'vi_delay', 'vi_compliance']
        entries = [self.ent_sp1, self.ent_sp2, self.ent_step, self.ent_delay, self.ent_compliance]
        for e, key in zip(entries, vals):
            e.delete(0, tk.END)
            e.insert(0, self.saved_params[key])

    def log(self, message):
        self.root.after(0, self._log_internal, message)

    def _log_internal(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _progress(self, text):
        self.root.after(0, lambda: self.lbl_progress.config(text=text))

    # ==================== CONNECTION ====================

    def refresh_instruments(self):
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
        addr = self.bias_combo.get()
        if not addr:
            messagebox.showerror("Error", "No bias address selected")
            return
        try:
            self.bias_inst = Keithley2450(addr)
            if hasattr(self.bias_inst, 'adapter'):
                self.bias_inst.adapter.connection.timeout = 10000
                self.bias_inst.adapter.connection.read_termination = '\n'
                self.bias_inst.adapter.connection.write_termination = '\n'
            self.log(f"Bias (Keithley 2450) connected: {addr}")
            self.update_bias_status()
        except Exception as e:
            self.bias_inst = None
            messagebox.showerror("Connection Error", f"Failed to connect bias:\n{e}")
            self.log(f"Bias connection failed: {e}")

    def connect_gate(self):
        addr = self.gate_combo.get()
        if not addr:
            messagebox.showerror("Error", "No gate address selected")
            return
        kind = GATE_KINDS[self.gate_kind_combo.get()]
        try:
            if kind == "keithley":
                inst = Keithley2450(addr)
                inst.adapter.connection.timeout = 10000
                inst.adapter.connection.read_termination = '\n'
                inst.adapter.connection.write_termination = '\n'
            elif kind == "yoko7651":
                inst = Yokogawa7651(addr)
                # legacy protocol: no termination overrides (matches working GUI)
                inst.adapter.connection.timeout = 10000
            else:  # gs200
                inst = YokogawaGS200(addr)
                inst.adapter.connection.timeout = 10000
                inst.adapter.connection.read_termination = '\n'
                inst.adapter.connection.write_termination = '\n'
                inst.adapter.connection.clear()
            self.gate_inst = inst
            self.gate_kind = kind
            self._apply_gate_ui_kind()
            self.log(f"Gate ({self.gate_kind_combo.get()}) connected: {addr}")
            self.update_gate_status()
        except Exception as e:
            self.gate_inst = None
            self.gate_kind = None
            messagebox.showerror("Connection Error", f"Failed to connect gate:\n{e}")
            self.log(f"Gate connection failed: {e}")

    def _apply_gate_ui_kind(self):
        """NPLC only applies to the Keithley gate."""
        state = "normal" if self.gate_kind == "keithley" else "disabled"
        self.ent_gate_nplc.config(state=state)
        self.lbl_gate_nplc.config(foreground="black" if self.gate_kind == "keithley" else "grey")

    def disconnect_bias(self):
        if self.bias_inst:
            # NOTE: output intentionally left in its current state —
            # closing the program does not mean the experiment is over.
            try:
                on = self.bias_inst.source_enabled
                self.log(f"Bias disconnected (output left {'ON' if on else 'OFF'})")
            except Exception:
                self.log("Bias disconnected")
            try:
                self.bias_inst.adapter.connection.close()
            except Exception:
                pass
            self.bias_inst = None

    def disconnect_gate(self):
        if self.gate_inst:
            # NOTE: output and level intentionally left untouched —
            # closing the program does not mean the experiment is over.
            level = self._gate_read_level()
            try:
                on = self._gate_output_on()
                v_str = f"{level:.4f} V" if level is not None else "unknown level"
                self.log(f"Gate disconnected (left at {v_str}, output "
                         f"{'ON' if on else 'OFF'})")
            except Exception:
                self.log("Gate disconnected")
            try:
                self.gate_inst.adapter.connection.close()
            except Exception:
                pass
            self.gate_inst = None
            self.gate_kind = None
        self.update_gate_status()

    def toggle_bias_terminals(self):
        if not self.bias_inst:
            return
        try:
            if "FRON" in self.bias_inst.check_terminals():
                self.bias_inst.use_rear_terminals()
            else:
                self.bias_inst.use_front_terminals()
            time.sleep(0.2)
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias terminal error: {e}")

    def toggle_bias_output(self):
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
        if not self.gate_inst:
            return
        try:
            on = self._gate_output_on()
            self._gate_enable(not on)
            self.log(f"Gate output {'OFF' if on else 'ON'}")
            time.sleep(0.1)
            self.update_gate_status()
        except Exception as e:
            self.log(f"Gate output error: {e}")

    def reset_bias(self):
        if not self.bias_inst:
            return
        try:
            self.bias_inst.reset()
            self.log("Bias reset")
            self.update_bias_status()
        except Exception as e:
            self.log(f"Bias reset error: {e}")

    def reset_gate(self):
        if not self.gate_inst:
            return
        try:
            if self.gate_kind == "keithley":
                self.gate_inst.reset()
            elif self.gate_kind == "yoko7651":
                self.gate_inst.write("RC;E")
                self.gate_inst.write("H0;E")
            else:
                self.gate_inst.reset()
                self.gate_inst.source_mode = "voltage"
            self.log("Gate reset")
            self.update_gate_status()
        except Exception as e:
            self.log(f"Gate reset error: {e}")

    def update_bias_status(self):
        if not self.bias_inst:
            self.btn_bias_term.config(text="Term: ---", bg="#e0e0e0")
            self.btn_bias_out.config(text="Out: ---", bg="#e0e0e0")
            return
        try:
            term = self.bias_inst.check_terminals()
            self.btn_bias_term.config(text="Term: FRONT" if "FRON" in term else "Term: REAR",
                                      bg="#90ee90" if "FRON" in term else "orange")
        except Exception:
            self.btn_bias_term.config(text="Term: ???", bg="grey")
        try:
            on = self.bias_inst.source_enabled
            self.btn_bias_out.config(text="Out: ON" if on else "Out: OFF",
                                     bg="#90ee90" if on else "#ffcccb")
        except Exception:
            self.btn_bias_out.config(text="Out: ???", bg="grey")

    def update_gate_status(self):
        if not self.gate_inst:
            self.btn_gate_out.config(text="Out: ---", bg="#e0e0e0")
            self.lbl_gate_status.config(text="Gate: --- V")
            return
        try:
            on = self._gate_output_on()
            self.btn_gate_out.config(text="Out: ON" if on else "Out: OFF",
                                     bg="#90ee90" if on else "#ffcccb")
        except Exception:
            self.btn_gate_out.config(text="Out: ???", bg="grey")

    def refresh_all_status(self):
        self.update_bias_status()
        self.update_gate_status()
        self.log("Status refreshed")

    # ==================== GATE UNIFORM API ====================

    def _gate_enable(self, on):
        if self.gate_kind == "keithley":
            self.gate_inst.enable_source() if on else self.gate_inst.disable_source()
        elif self.gate_kind == "yoko7651":
            self.gate_inst.enable_source() if on else self.gate_inst.disable_source()
        else:  # gs200
            self.gate_inst.source_enabled = bool(on)

    def _gate_output_on(self):
        return bool(self.gate_inst.source_enabled)

    def _gate_set_level(self, level):
        if self.gate_kind == "keithley":
            self.gate_inst.source_voltage = level
        elif self.gate_kind == "yoko7651":
            self.gate_inst.source_voltage = level
        else:  # gs200
            self.gate_inst.source_level = level

    def _gate_read_level(self):
        """Return current gate level (float) or None if readback fails."""
        try:
            if self.gate_kind == "gs200":
                return float(self.gate_inst.source_level)
            return float(self.gate_inst.source_voltage)
        except Exception:
            return None

    def _configure_gate_source(self, compliance, nplc, max_abs_v=None):
        """Configure the gate instrument as a voltage source."""
        if max_abs_v is None:
            # cover manual target and loop range
            cands = []
            try:
                cands.append(abs(float(self.ent_gate_target.get())))
            except ValueError:
                pass
            if self.gate_loop_var.get():
                try:
                    cands += [abs(float(self.ent_gate_start.get())),
                              abs(float(self.ent_gate_end.get()))]
                except ValueError:
                    pass
            max_abs_v = max(cands) if cands else 1.0

        if self.gate_kind == "keithley":
            self.gate_inst.configure_voltage_source(nplc=nplc, current=1e-6,
                                                    compliance_current=compliance)
        elif self.gate_kind == "yoko7651":
            self.gate_inst.apply_voltage(max_voltage=pick_v_range(max_abs_v),
                                         compliance_current=compliance)
        else:  # gs200
            self.gate_inst.source_mode = "voltage"
            self.gate_inst.source_range = pick_v_range(max_abs_v)
            self.gate_inst.current_limit = compliance
            self.gate_inst.source_level = 0
        self.log(f"Gate source configured (compliance={compliance} A"
                 + (f", NPLC={nplc}" if self.gate_kind == "keithley" else "") + ")")

    def _gate_ramp_params(self):
        """Parse step (mV) + rate (V/s) into (step_V, delay_s). Raises ValueError."""
        step_v = abs(float(self.ent_gate_step.get())) / 1000.0
        rate = float(self.ent_gate_rate.get())
        if rate <= 0:
            raise ValueError("Gate ramp rate must be > 0")
        if step_v <= 0:
            raise ValueError("Gate ramp step must be > 0")
        delay = step_v / rate
        return step_v, delay

    def apply_gate_config(self):
        if not self.gate_inst:
            messagebox.showerror("Error", "Gate not connected")
            return
        try:
            compliance = float(self.ent_gate_compliance.get())
            nplc = float(self.ent_gate_nplc.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid gate parameters")
            return
        try:
            self._configure_gate_source(compliance, nplc)
        except Exception as e:
            messagebox.showerror("Gate Config Error", str(e))
            self.log(f"Gate config error: {e}")

    def _ramp_gate_to(self, target, step_v, delay, quiet=False):
        """Slowly ramp gate to target. Aborts if stop_event set. Blocking."""
        inst, kind = self.gate_inst, self.gate_kind

        if kind == "keithley":
            def cb(v, i):
                self.root.after(0, lambda: self.lbl_gate_status.config(
                    text=f"Gate: {v:.4f} V | {i:.3e} A"))
                return self.stop_event.is_set()
            inst.voltage_ramping_with_monitor(target, step_v, delay, callback=cb)
        else:
            # Yokos: callback(elapsed, level)
            def cb(_elapsed, level):
                self.root.after(0, lambda: self.lbl_gate_status.config(
                    text=f"Gate: {level:.4f} V"))
                return self.stop_event.is_set()
            start = self._gate_read_level()
            if kind == "yoko7651":
                inst.ramping_with_monitor(target, step_v, delay, callback=cb,
                                          mode='voltage', start_level=start)
            else:
                inst.ramping_with_monitor(target, step_v, delay, callback=cb,
                                          start_level=start)
        if not quiet:
            self.log(f"Gate at {target} V")

    def measure_gate_once(self):
        if not self.gate_inst:
            messagebox.showerror("Error", "Gate not connected")
            return
        try:
            voltage = self._gate_read_level()
            current = None
            if self.gate_kind == "keithley":
                try:
                    current = float(self.gate_inst.ask(":MEAS:CURR?"))
                except Exception:
                    current = None
            v_str = f"{voltage:.4f}" if voltage is not None else "---"
            i_str = f" | {current:.3e} A" if current is not None else ""
            self.lbl_gate_status.config(text=f"Gate: {v_str} V{i_str}")
            self.log(f"Gate measurement: {v_str} V{i_str}")
        except Exception as e:
            self.log(f"Gate measurement error: {e}")
            messagebox.showerror("Measurement Error", f"Failed to measure gate:\n{e}")

    # ==================== MANUAL GATE RAMP ====================

    def start_gate_ramp(self):
        if not self.gate_inst:
            messagebox.showerror("Error", "Gate not connected")
            return
        try:
            target = float(self.ent_gate_target.get())
            step_v, delay = self._gate_ramp_params()
            compliance = float(self.ent_gate_compliance.get())
            nplc = float(self.ent_gate_nplc.get())
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid gate parameters: {e}")
            return

        self.saved_params.update({'gate_target': self.ent_gate_target.get(),
                                  'gate_step': self.ent_gate_step.get(),
                                  'gate_rate': self.ent_gate_rate.get(),
                                  'gate_compliance': self.ent_gate_compliance.get(),
                                  'gate_nplc': self.ent_gate_nplc.get()})

        try:
            self._configure_gate_source(compliance, nplc,
                                        max_abs_v=max(abs(target), 1e-3))
        except Exception as e:
            self.log(f"Gate config error: {e}")
            messagebox.showerror("Gate Config Error", str(e))
            return

        self.btn_gate_ramp.config(state="disabled")
        self.btn_abort.config(state="normal")
        self.btn_run.config(state="disabled")
        self.stop_event.clear()

        def worker():
            try:
                if not self._gate_output_on():
                    self._gate_set_level(self._gate_read_level() or 0.0)
                    self._gate_enable(True)
                self.log(f"Ramping gate to {target} V ...")
                self._ramp_gate_to(target, step_v, delay)
                self.log("Gate ramp complete" if not self.stop_event.is_set()
                         else "Gate ramp aborted")
            except Exception as e:
                self.log(f"Gate ramp error: {e}")
            finally:
                self.root.after(0, lambda: self.btn_gate_ramp.config(state="normal"))
                self.root.after(0, lambda: self.btn_abort.config(state="disabled"))
                self.root.after(0, lambda: self.btn_run.config(state="normal"))
                self.root.after(0, self.update_gate_status)

        threading.Thread(target=worker, daemon=True).start()

    # ==================== SWEEP EXECUTION ====================

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, directory)

    def start_sweep(self):
        if not self.bias_inst:
            messagebox.showerror("Error", "Bias instrument not connected (must be Keithley 2450)")
            return

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

        gate_list = [None]  # no gate stepping
        gate_step = gate_delay = gate_settle = gate_compliance = gate_nplc = None
        if self.gate_loop_var.get():
            if not self.gate_inst:
                messagebox.showerror("Error", "Gate loop selected but no gate instrument connected")
                return
            try:
                gs = float(self.ent_gate_start.get())
                ge = float(self.ent_gate_end.get())
                gst = abs(float(self.ent_gate_loop_step.get()))
                gate_step = abs(float(self.ent_gate_loop_ramp_step.get())) / 1000.0
                gate_delay = float(self.ent_gate_loop_ramp_delay.get())
                gate_settle = float(self.ent_gate_settle.get())
                gate_compliance = float(self.ent_gate_compliance.get())
                gate_nplc = float(self.ent_gate_nplc.get())
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid gate loop parameters: {e}")
                return
            if gst == 0 or gate_step == 0 or gate_delay < 0:
                messagebox.showerror("Error",
                                     "Gate loop step and ramp step must be non-zero; "
                                     "ramp delay must be >= 0")
                return
            sign = 1.0 if ge >= gs else -1.0
            gate_list = list(np.arange(gs, ge + sign * gst / 2.0, sign * gst))
            if not gate_list:
                messagebox.showerror("Error", "Gate loop produces no points")
                return

        sweep_type = self.sweep_type_var.get()
        if sweep_type == "iv":
            keys = ['iv_sp1', 'iv_sp2', 'iv_step', 'iv_delay', 'iv_compliance']
        else:
            keys = ['vi_sp1', 'vi_sp2', 'vi_step', 'vi_delay', 'vi_compliance']
        for key, ent in zip(keys, [self.ent_sp1, self.ent_sp2, self.ent_step,
                                   self.ent_delay, self.ent_compliance]):
            self.saved_params[key] = ent.get()
        self.saved_params['save_dir'] = save_dir

        self.btn_run.config(state="disabled")
        self.btn_abort.config(state="normal")
        self.btn_gate_ramp.config(state="disabled")
        self.stop_event.clear()

        params = {
            'sp1': sp1, 'sp2': sp2, 'step': step, 'delay': delay,
            'compliance': compliance, 'save_dir': save_dir, 'sweep_type': sweep_type,
            'gate_list': gate_list, 'gate_step': gate_step, 'gate_delay': gate_delay,
            'gate_settle': gate_settle, 'gate_compliance': gate_compliance,
            'gate_nplc': gate_nplc,
        }
        threading.Thread(target=self._run_sweep_thread, args=(params,), daemon=True).start()

    def abort_sweep(self):
        self.stop_event.set()
        self.log("Abort requested...")

    def _run_single_bias_sweep(self, p):
        """Configure + run one hysteresis sweep on the Keithley bias. Returns arrays."""
        if p['sweep_type'] == "iv":
            self.log(f"Bias sweep: 0 -> {p['sp1']} mV -> {p['sp2']} mV -> 0")
            self.bias_inst.create_hysteresis_voltage_sweep_config_list(
                Sp1=p['sp1'], Sp2=p['sp2'], step=p['step'],
                curr_range=p['compliance'])
            output = self.bias_inst.run_clist_sweep(delay=p['delay'], sweep_type='voltage')
        else:
            self.log(f"Bias sweep: 0 -> {p['sp1']} A -> {p['sp2']} A -> 0")
            self.bias_inst.create_hysteresis_current_sweep_config_list(
                Sp1=p['sp1'], Sp2=p['sp2'], step=p['step'],
                volt_range=p['compliance'])
            output = self.bias_inst.run_clist_sweep(delay=p['delay'], sweep_type='current')

        data = [float(x) for x in output.split(',')]
        measured = np.array(data[0::3])
        sourced = np.array(data[1::3])
        times = np.array(data[2::3])
        return measured, sourced, times

    def _run_sweep_thread(self, p):
        try:
            sweep_type = p['sweep_type']
            gate_list = p['gate_list']
            gate_loop = gate_list[0] is not None

            if gate_loop:
                self.log(f"Gate loop: {len(gate_list)} gate voltages "
                         f"({gate_list[0]} V .. {gate_list[-1]} V)")
                # configure gate, then slow ramp to the first gate value
                self._configure_gate_source(p['gate_compliance'], p['gate_nplc'],
                                            max_abs_v=max(abs(v) for v in gate_list))
                if not self._gate_output_on():
                    self._gate_set_level(0.0)
                    self._gate_enable(True)
                    time.sleep(0.2)
                self.log(f"Ramping gate slowly to initial {gate_list[0]} V ...")
                self._ramp_gate_to(gate_list[0], p['gate_step'], p['gate_delay'])
                if self.stop_event.is_set():
                    self.log("Aborted before first sweep")
                    return

            os.makedirs(p['save_dir'], exist_ok=True)

            for i, gv in enumerate(gate_list):
                if self.stop_event.is_set():
                    break

                if gate_loop and i > 0:
                    self.log(f"Ramping gate {gate_list[i - 1]} V -> {gv} V ...")
                    self._ramp_gate_to(gv, p['gate_step'], p['gate_delay'])
                    if self.stop_event.is_set():
                        break

                if gate_loop:
                    self._progress(f"Sweep {i + 1}/{len(gate_list)} @ Vg={gv} V")
                    time.sleep(p['gate_settle'])
                else:
                    self._progress("Running sweep...")

                measured, sourced, times = self._run_single_bias_sweep(p)

                ts = int(time.time())
                gate_str = f"_Gate_{gv:.3f}V" if gv is not None else ""
                if sweep_type == "iv":
                    name = f"IV_{ts}{gate_str}_Sp1_{p['sp1']}mV_Sp2_{p['sp2']}mV"
                    header, x, y = "Voltage(V),Current(A),Time(s)", sourced, measured
                else:
                    name = f"VI_{ts}{gate_str}_Sp1_{p['sp1']}A_Sp2_{p['sp2']}A"
                    header, x, y = "Current(A),Voltage(V),Time(s)", sourced, measured

                csv_path = os.path.join(p['save_dir'], name + ".csv")
                if gv is not None:
                    # gate voltage recorded as 4th column so each row is self-describing
                    header += ",GateVoltage(V)"
                    cols = np.vstack((x, y, times, np.full(x.size, gv)))
                else:
                    cols = np.vstack((x, y, times))
                np.savetxt(csv_path, cols.T, delimiter=',', header=header)
                self.log(f"Saved: {name}.csv")

            # always return gate to 0 V slowly after the measurement
            if gate_loop and self.gate_inst:
                if not self.stop_event.is_set():
                    self.log("Ramping gate back to 0 V ...")
                self.stop_event.clear()
                self._ramp_gate_to(0.0, p['gate_step'], p['gate_delay'])

            if self.stop_event.is_set():
                self.log("Sweep aborted")
                self._progress("Aborted")
            else:
                self._progress("Complete")
                self.log("Sweep complete!")

        except Exception as e:
            self.log(f"Sweep error: {e}")
            self._progress(f"Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Sweep Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, lambda: self.btn_abort.config(state="disabled"))
            self.root.after(0, lambda: self.btn_gate_ramp.config(state="normal"))

    def cleanup(self):
        self.stop_event.set()
        self.disconnect_bias()
        self.disconnect_gate()


def main():
    root = tk.Tk()
    root.geometry("950x800")
    app = IVVISweeperImproved(root)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()










