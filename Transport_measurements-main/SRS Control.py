import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math
import sys
import os
import pyvisa

# --- IMPORT SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
instruments_path = os.path.join(current_dir, 'Instruments')
sys.path.append(instruments_path)

try:
    from SR830_with_add_ons import SR830
except ImportError:
    SR830 = None

# ==========================================
#      EXPLICIT SENSITIVITY MAPS
# ==========================================

# --- SR830 MAPS (Value -> SENS Index) ---
# 1V = Index 26. 2nV = Index 0.
SR830_VOLT_MAP = {
    1.0: 26, 0.5: 25, 0.2: 24, 0.1: 23, 0.05: 22, 0.02: 21, 0.01: 20,
    0.005: 19, 0.002: 18, 0.001: 17, 500e-6: 16, 200e-6: 15, 100e-6: 14,
    50e-6: 13, 20e-6: 12, 10e-6: 11, 5e-6: 10, 2e-6: 9, 1e-6: 8,
    500e-9: 7, 200e-9: 6, 100e-9: 5, 50e-9: 4, 20e-9: 3, 10e-9: 2,
    5e-9: 1, 2e-9: 0
}
# SR830 Current (Used only for GUI display, Index matches Voltage)
SR830_CURR_MAP = {
    1e-6: 26, 500e-9: 25, 200e-9: 24, 100e-9: 23, 50e-9: 22, 20e-9: 21, 10e-9: 20,
    5e-9: 19, 2e-9: 18, 1e-9: 17, 500e-12: 16, 200e-12: 15, 100e-12: 14,
    50e-12: 13, 20e-12: 12, 10e-12: 11, 5e-12: 10, 2e-12: 9, 1e-12: 8,
    500e-15: 7, 200e-15: 6, 100e-15: 5, 50e-15: 4, 20e-15: 3, 10e-15: 2,
    5e-15: 1, 2e-15: 0
}

# --- SR860 MAPS (Value -> SCAL Index) ---
# 1V = Index 0. 1nV = Index 27.
SR860_VOLT_MAP = {
    1.0: 0, 0.5: 1, 0.2: 2, 0.1: 3, 0.05: 4, 0.02: 5, 0.01: 6,
    0.005: 7, 0.002: 8, 0.001: 9, 500e-6: 10, 200e-6: 11, 100e-6: 12,
    50e-6: 13, 20e-6: 14, 10e-6: 15, 5e-6: 16, 2e-6: 17, 1e-6: 18,
    500e-9: 19, 200e-9: 20, 100e-9: 21, 50e-9: 22, 20e-9: 23, 10e-9: 24,
    5e-9: 25, 2e-9: 26, 1e-9: 27
}
# SR860 Current 1 uA Range (1uA = Index 0)
SR860_CURR_UA_MAP = {
    1e-6: 0, 500e-9: 1, 200e-9: 2, 100e-9: 3, 50e-9: 4, 20e-9: 5, 10e-9: 6,
    5e-9: 7, 2e-9: 8, 1e-9: 9, 500e-12: 10, 200e-12: 11, 100e-12: 12,
    50e-12: 13, 20e-12: 14, 10e-12: 15, 5e-12: 16, 2e-12: 17, 1e-12: 18,
    500e-15: 19, 200e-15: 20, 100e-15: 21, 50e-15: 22, 20e-15: 23, 10e-15: 24,
    5e-15: 25, 2e-15: 26, 1e-15: 27
}
# SR860 Current 10 nA Range (10nA = Index 0)
SR860_CURR_NA_MAP = {
    10e-9: 0, 5e-9: 1, 2e-9: 2, 1e-9: 3, 500e-12: 4, 200e-12: 5, 100e-12: 6,
    50e-12: 7, 20e-12: 8, 10e-12: 9, 5e-12: 10, 2e-12: 11, 1e-12: 12,
    500e-15: 13, 200e-15: 14, 100e-15: 15, 50e-15: 16, 20e-15: 17, 10e-15: 18,
    5e-15: 19, 2e-15: 20, 1e-15: 21, 500e-18: 22, 200e-18: 23, 100e-18: 24,
    50e-18: 25, 20e-18: 26, 10e-18: 27
}


class SR860_Direct:
    def __init__(self, resource_name):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = 5000
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        self.inst.write("*CLS")

    def write(self, cmd):
        self.inst.write(cmd)

    def read(self):
        return self.inst.read()

    def query(self, cmd):
        return self.inst.query(cmd)

    def close(self):
        self.inst.close()

    TC_MAP = {
        1e-6: 0, 3e-6: 1, 10e-6: 2, 30e-6: 3, 100e-6: 4, 300e-6: 5,
        1e-3: 6, 3e-3: 7, 10e-3: 8, 30e-3: 9, 100e-3: 10, 300e-3: 11,
        1.0: 12, 3.0: 13, 10.0: 14, 30.0: 15, 100.0: 16, 300.0: 17,
        1000.0: 18, 3000.0: 19, 10000.0: 20, 30000.0: 21
    }
    SLOPE_MAP = {6: 0, 12: 1, 18: 2, 24: 3}
    RSRC_MAP = {'Internal': 0, 'External': 1, 'Dual': 2, 'Chop': 3}
    IRNG_MAP = {1.0: 0, 0.3: 1, 0.1: 2, 0.03: 3, 0.01: 4}
    ICPL_MAP = {'AC': 0, 'DC': 1}
    ILIN_MAP = {'Off': 0, 'Line': 1, '2xLine': 2, 'Both': 3}
    IGND_MAP = {'Float': 0, 'Ground': 1}

    # --- PROPERTIES ---
    @property
    def frequency(self):
        return float(self.query("FREQ?"))

    @frequency.setter
    def frequency(self, val):
        self.write(f"FREQ {val}")

    @property
    def phase(self):
        return float(self.query("PHAS?"))

    @phase.setter
    def phase(self, val):
        self.write(f"PHAS {val}")

    @property
    def sine_voltage(self):
        return float(self.query("SLVL?"))

    @sine_voltage.setter
    def sine_voltage(self, val):
        self.write(f"SLVL {val}")

    @property
    def sine_dc_level(self):
        return float(self.query("SOFF?"))

    @sine_dc_level.setter
    def sine_dc_level(self, val):
        self.write(f"SOFF {val}")

    @property
    def harmonic(self):
        return int(self.query("HARM?"))

    @harmonic.setter
    def harmonic(self, val):
        self.write(f"HARM {int(val)}")

    @property
    def sensitivity(self):
        return int(self.query("SCAL?"))

    @sensitivity.setter
    def sensitivity(self, val):
        self.write(f"SCAL {int(val)}")

    @property
    def time_constant(self):
        try:
            idx = int(self.query("OFLT?"))
            for v, i in self.TC_MAP.items():
                if i == idx: return v
            return 1.0
        except:
            return 1.0

    @time_constant.setter
    def time_constant(self, val):
        if val in self.TC_MAP: self.write(f"OFLT {self.TC_MAP[val]}")

    @property
    def filter_slope(self):
        try:
            idx = int(self.query("OFSL?"))
            for v, i in self.SLOPE_MAP.items():
                if i == idx: return v
            return 6
        except:
            return 6

    @filter_slope.setter
    def filter_slope(self, val):
        if val in self.SLOPE_MAP: self.write(f"OFSL {self.SLOPE_MAP[val]}")

    @property
    def reference_source(self):
        try:
            idx = int(self.query("RSRC?"))
            for k, i in self.RSRC_MAP.items():
                if i == idx: return k
            return 'Internal'
        except:
            return 'Internal'

    @reference_source.setter
    def reference_source(self, val):
        if val in self.RSRC_MAP: self.write(f"RSRC {self.RSRC_MAP[val]}")

    # --- INPUT COMMANDS ---
    @property
    def input_mode_index(self):
        try:
            return int(self.query("IVMD?"))
        except:
            return 0

    @input_mode_index.setter
    def input_mode_index(self, val):
        self.write(f"IVMD {int(val)}")

    @property
    def voltage_config_index(self):
        try:
            return int(self.query("ISRC?"))
        except:
            return 0

    @voltage_config_index.setter
    def voltage_config_index(self, val):
        self.write(f"ISRC {int(val)}")

    @property
    def current_config_index(self):
        try:
            return int(self.query("ICUR?"))
        except:
            return 0

    @current_config_index.setter
    def current_config_index(self, val):
        self.write(f"ICUR {int(val)}")

    @property
    def input_coupling(self):
        try:
            idx = int(self.query("ICPL?"))
            for k, i in self.ICPL_MAP.items():
                if i == idx: return k
            return 'AC'
        except:
            return 'AC'

    @input_coupling.setter
    def input_coupling(self, val):
        if val in self.ICPL_MAP: self.write(f"ICPL {self.ICPL_MAP[val]}")

    @property
    def input_range(self):
        try:
            idx = int(self.query("IRNG?"))
            for v, i in self.IRNG_MAP.items():
                if i == idx: return v
            return 1.0
        except:
            return 1.0

    @input_range.setter
    def input_range(self, val):
        if val in self.IRNG_MAP: self.write(f"IRNG {self.IRNG_MAP[val]}")

    @property
    def line_filter(self):
        try:
            idx = int(self.query("ILIN?"))
            for k, i in self.ILIN_MAP.items():
                if i == idx: return k
            return 'Off'
        except:
            return 'Off'

    @line_filter.setter
    def line_filter(self, val):
        if val in self.ILIN_MAP: self.write(f"ILIN {self.ILIN_MAP[val]}")

    @property
    def input_shield(self):
        try:
            idx = int(self.query("IGND?"))
            for k, i in self.IGND_MAP.items():
                if i == idx: return k
            return 'Float'
        except:
            return 'Float'

    @input_shield.setter
    def input_shield(self, val):
        if val in self.IGND_MAP: self.write(f"IGND {self.IGND_MAP[val]}")

    # --- AUXILIARY OUTPUT/INPUT COMMANDS ---
    def get_aux_out(self, channel):
        """Get auxiliary output voltage (channel 0-3)"""
        return float(self.query(f"AUXV? {channel}"))

    def set_aux_out(self, channel, value):
        """Set auxiliary output voltage (channel 0-3, range -10.5 to 10.5V)"""
        value = max(-10.5, min(10.5, value))  # Clamp to valid range
        self.write(f"AUXV {channel} ,{value:.4f}")

    def get_aux_in(self, channel):
        """Get auxiliary input voltage (channel 1-4)"""
        return float(self.query(f"OAUX? {channel}"))

    # Convenience properties for each channel
    @property
    def aux_out_1(self):
        return self.get_aux_out(0)
    @aux_out_1.setter
    def aux_out_1(self, val):
        self.set_aux_out(0, val)

    @property
    def aux_out_2(self):
        return self.get_aux_out(1)
    @aux_out_2.setter
    def aux_out_2(self, val):
        self.set_aux_out(1, val)

    @property
    def aux_out_3(self):
        return self.get_aux_out(2)
    @aux_out_3.setter
    def aux_out_3(self, val):
        self.set_aux_out(2, val)

    @property
    def aux_out_4(self):
        return self.get_aux_out(3)
    @aux_out_4.setter
    def aux_out_4(self, val):
        self.set_aux_out(3, val)

    @property
    def aux_in_1(self):
        return self.get_aux_in(0)

    @property
    def aux_in_2(self):
        return self.get_aux_in(1)

    @property
    def aux_in_3(self):
        return self.get_aux_in(2)

    @property
    def aux_in_4(self):
        return self.get_aux_in(3)


class Utility:
    @staticmethod
    def format_eng(number, unit=""):
        try:
            val = float(number)
            if val == 0: return f"0 {unit}"
            exponent = int(math.floor(math.log10(abs(val))))
            eng_exponent = exponent - (exponent % 3)
            fraction = val / (10 ** eng_exponent)
            prefixes = {-18: "a", -15: "f", -12: "p", -9: "n", -6: "u", -3: "m", 0: "", 3: "k", 6: "M", 9: "G"}
            prefix = prefixes.get(eng_exponent, f"e{eng_exponent}")
            return f"{fraction:.3g} {prefix}{unit}"
        except:
            return f"{number} {unit}"


class InstrumentPanel(ttk.Frame):
    def __init__(self, parent, instrument_obj, remove_callback, name="Instrument"):
        super().__init__(parent)
        self.inst = instrument_obj
        self.remove_callback = remove_callback
        self.name = name
        self.stop_threads = False
        self.initialization_complete = False

        self.is_SR830 = (SR830 is not None and isinstance(self.inst, SR830))
        self.inst_cls = SR830 if self.is_SR830 else SR860_Direct

        self.active_sens_map = {}
        self.active_meas_unit = "V"

        self.auto_refresh = tk.BooleanVar(value=False)
        self.ctrl_vars = {}
        self.param_controls = []

        self.create_widgets()

        threading.Thread(target=self.startup_sequence, daemon=True).start()
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def create_widgets(self):
        # Top Bar
        top_frame = ttk.Frame(self)
        top_frame.pack(side="top", fill="x", padx=5, pady=5)
        ttk.Label(top_frame, text=f"Connected: {self.name}", font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(top_frame, text="⟳ Refresh Settings", command=self.refresh_settings).pack(side="left", padx=20)
        ttk.Button(top_frame, text="Disconnect", command=self.request_close).pack(side="right")

        # Measurement
        meas_frame = ttk.LabelFrame(self, text="Measurements")
        meas_frame.pack(side="top", fill="x", padx=5, pady=5)

        btn_frame = ttk.Frame(meas_frame)
        btn_frame.pack(side="top", fill="x", padx=5, pady=5)
        self.btn_measure = ttk.Button(btn_frame, text="MEASURE SNAP", command=self.measure_direct)
        self.btn_measure.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Checkbutton(btn_frame, text="Auto-Update", variable=self.auto_refresh).pack(side="left", padx=10)

        grid_frame = ttk.Frame(meas_frame)
        grid_frame.pack(side="top", fill="x", padx=5, pady=5)
        self.vars_meas = {
            "X": tk.StringVar(value="--"), "Y": tk.StringVar(value="--"),
            "R": tk.StringVar(value="--"), "Theta": tk.StringVar(value="--")
        }
        for i, (label, var) in enumerate(self.vars_meas.items()):
            ttk.Label(grid_frame, text=f"{label}:", font=('Arial', 14, 'bold')).grid(row=0, column=i * 2, padx=10)
            ttk.Label(grid_frame, textvariable=var, font=('Arial', 14, 'bold'), foreground="#0033cc").grid(row=0,
                                                                                                           column=i * 2 + 1,
                                                                                                           padx=10)

        self.controls_frame = ttk.Frame(self)
        self.controls_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        if self.is_SR830:
            self.build_sr830_layout(self.controls_frame)
        else:
            self.build_sr860_layout(self.controls_frame)

    # --- AUXILIARY SECTION (Shared) ---
    def build_auxiliary_section(self, parent, row):
        """Build auxiliary output/input controls. Returns the frame."""
        aux_frame = ttk.LabelFrame(parent, text="Auxiliary")
        aux_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=2, pady=5)
        
        # Configure columns for even spacing
        for i in range(8):
            aux_frame.columnconfigure(i, weight=1)

        # Variables for auxiliary inputs (read-only display)
        self.vars_aux_in = {
            1: tk.StringVar(value="--"),
            2: tk.StringVar(value="--"),
            3: tk.StringVar(value="--"),
            4: tk.StringVar(value="--")
        }
        
        # Variables for auxiliary outputs
        self.vars_aux_out = {
            1: tk.StringVar(value="0.000"),
            2: tk.StringVar(value="0.000"),
            3: tk.StringVar(value="0.000"),
            4: tk.StringVar(value="0.000")
        }

        # Header row
        ttk.Label(aux_frame, text="Outputs", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=4, pady=2)
        ttk.Label(aux_frame, text="Inputs (Read)", font=('Arial', 9, 'bold')).grid(row=0, column=4, columnspan=4, pady=2)

        # Store set handlers for reuse
        self._aux_set_handlers = {}

        # Row 1: Aux 1 and 2
        for ch in [1, 2]:
            col_offset = (ch - 1) * 2
            # Output control
            ttk.Label(aux_frame, text=f"Out {ch}:").grid(row=1, column=col_offset, sticky="e", padx=2)
            entry = ttk.Entry(aux_frame, textvariable=self.vars_aux_out[ch], width=8)
            entry.grid(row=1, column=col_offset + 1, padx=2)
            
            def make_set_handler(channel):
                def set_aux():
                    try:
                        val = float(self.vars_aux_out[channel].get())
                        val = max(-10.5, min(10.5, val))  # Clamp to valid range
                        if self.is_SR830:
                            setattr(self.inst, f'aux_out_{channel}', val)
                        else:
                            self.inst.set_aux_out(channel-1, val)
                        time.sleep(0.05)
                        # Read back
                        if self.is_SR830:
                            new_val = getattr(self.inst, f'aux_out_{channel}')
                        else:
                            new_val = self.inst.get_aux_out(channel-1)
                        self.vars_aux_out[channel].set(f"{new_val:.4f}")
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                return set_aux
            
            self._aux_set_handlers[ch] = make_set_handler(ch)
            btn = ttk.Button(aux_frame, text="Set", command=self._aux_set_handlers[ch], width=4)
            btn.grid(row=2, column=col_offset, columnspan=2, pady=2)
            
            # Input display
            ttk.Label(aux_frame, text=f"In {ch}:").grid(row=1, column=4 + col_offset, sticky="e", padx=2)
            lbl = ttk.Label(aux_frame, textvariable=self.vars_aux_in[ch], width=10, 
                           font=('Arial', 10), foreground="#0066cc")
            lbl.grid(row=1, column=5 + col_offset, padx=2, sticky="w")

        # Row 2: Aux 3 and 4
        for ch in [3, 4]:
            col_offset = (ch - 3) * 2
            # Output control
            ttk.Label(aux_frame, text=f"Out {ch}:").grid(row=3, column=col_offset, sticky="e", padx=2)
            entry = ttk.Entry(aux_frame, textvariable=self.vars_aux_out[ch], width=8)
            entry.grid(row=3, column=col_offset + 1, padx=2)
            
            self._aux_set_handlers[ch] = make_set_handler(ch)
            btn = ttk.Button(aux_frame, text="Set", command=self._aux_set_handlers[ch], width=4)
            btn.grid(row=4, column=col_offset, columnspan=2, pady=2)
            
            # Input display
            ttk.Label(aux_frame, text=f"In {ch}:").grid(row=3, column=4 + col_offset, sticky="e", padx=2)
            lbl = ttk.Label(aux_frame, textvariable=self.vars_aux_in[ch], width=10,
                           font=('Arial', 10), foreground="#0066cc")
            lbl.grid(row=3, column=5 + col_offset, padx=2, sticky="w")

        return aux_frame

    def read_aux_inputs(self):
        """Read all auxiliary inputs and update display (SR830 only)"""
        if not self.is_SR830:
            return  # Skip for SR860 to improve performance
        try:
            for ch in [1, 2, 3, 4]:
                val = getattr(self.inst, f'aux_in_{ch}')
                self.vars_aux_in[ch].set(f"{val:.4f} V")
        except:
            pass

    def load_aux_outputs(self):
        """Load current auxiliary output values into the entry fields"""
        try:
            for ch in [1, 2, 3, 4]:
                if self.is_SR830:
                    val = getattr(self.inst, f'aux_out_{ch}')
                else:
                    val = self.inst.get_aux_out(ch-1)
                self.vars_aux_out[ch].set(f"{val:.4f}")
        except:
            pass

    def build_sr860_layout(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)

        f1 = ttk.LabelFrame(parent, text="Source")
        f1.grid(row=0, column=0, sticky="nsew", padx=2)
        self.add_combo(f1, "Ref Src", "reference_source", list(SR860_Direct.RSRC_MAP.keys()), 0)
        self.add_entry(f1, "Freq (Hz)", "frequency", 1)
        self.add_entry(f1, "Phase (deg)", "phase", 2)
        self.add_entry(f1, "Amp (V)", "sine_voltage", 3)
        self.add_entry(f1, "DC Off (V)", "sine_dc_level", 4)
        self.add_entry(f1, "Harmonic", "harmonic", 5, is_int=True)

        f2 = ttk.LabelFrame(parent, text="Input Setup")
        f2.grid(row=0, column=1, sticky="nsew", padx=2)
        ttk.Label(f2, text="Input Mode").grid(row=0, column=0, sticky="e", padx=2)
        self.combo_mode = ttk.Combobox(f2, values=["Voltage", "Current"], state="readonly", width=12)
        self.combo_mode.grid(row=0, column=1, padx=2)
        self.combo_mode.bind("<<ComboboxSelected>>", self.on_sr860_mode_change)

        ttk.Label(f2, text="Configuration").grid(row=1, column=0, sticky="e", padx=2)
        self.combo_cfg = ttk.Combobox(f2, state="readonly", width=12)
        self.combo_cfg.grid(row=1, column=1, padx=2)
        self.combo_cfg.bind("<<ComboboxSelected>>", self.on_sr860_cfg_change)

        self.add_combo(f2, "Range", "input_range", list(SR860_Direct.IRNG_MAP.keys()), 2, unit="V")
        self.add_combo(f2, "Coupling", "input_coupling", list(SR860_Direct.ICPL_MAP.keys()), 3)
        self.add_combo(f2, "Filter", "line_filter", list(SR860_Direct.ILIN_MAP.keys()), 4)
        self.add_combo(f2, "Shield", "input_shield", list(SR860_Direct.IGND_MAP.keys()), 5)

        f3 = ttk.LabelFrame(parent, text="Gain & Time")
        f3.grid(row=0, column=2, sticky="nsew", padx=2)
        self.active_sens_map = SR860_VOLT_MAP
        self.add_combo(f3, "Sensitivity", "sensitivity", [], 0, unit="V")
        self.add_combo(f3, "Time Const", "time_constant", list(SR860_Direct.TC_MAP.keys()), 1, unit="s")
        self.add_combo(f3, "Slope (dB)", "filter_slope", list(SR860_Direct.SLOPE_MAP.keys()), 2)

        # Add auxiliary section in row 1
        self.build_auxiliary_section(parent, 1)

    def on_sr860_mode_change(self, event):
        mode = self.combo_mode.get()
        if mode == "Voltage":
            setattr(self.inst, 'input_mode_index', 0)
            self.combo_cfg['values'] = ["A", "A-B"]
            self.combo_cfg.current(0)
            setattr(self.inst, 'voltage_config_index', 0)
        else:
            setattr(self.inst, 'input_mode_index', 1)
            self.combo_cfg['values'] = ["1 µA", "10 nA"]
            self.combo_cfg.current(0)
            setattr(self.inst, 'current_config_index', 0)
        self.update_sensitivity_list()

    def on_sr860_cfg_change(self, event):
        mode = self.combo_mode.get()
        cfg = self.combo_cfg.get()
        if mode == "Voltage":
            idx = 1 if cfg == "A-B" else 0
            setattr(self.inst, 'voltage_config_index', idx)
        else:
            idx = 1 if cfg == "10 nA" else 0
            setattr(self.inst, 'current_config_index', idx)
        self.update_sensitivity_list()

    def update_sr860_ui_from_inst(self):
        try:
            mode_idx = self.inst.input_mode_index
            if mode_idx == 0:
                self.combo_mode.set("Voltage")
                self.combo_cfg['values'] = ["A", "A-B"]
                v_cfg = self.inst.voltage_config_index
                self.combo_cfg.set("A-B" if v_cfg == 1 else "A")
            else:
                self.combo_mode.set("Current")
                self.combo_cfg['values'] = ["1 µA", "10 nA"]
                c_cfg = self.inst.current_config_index
                self.combo_cfg.set("10 nA" if c_cfg == 1 else "1 µA")
        except:
            pass

    # --- SR830 LAYOUT ---
    def build_sr830_layout(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)
        
        f1 = ttk.LabelFrame(parent, text="Source")
        f1.grid(row=0, column=0, sticky="nsew", padx=2)
        self.add_combo(f1, "Ref Src", "reference_source", self.inst.REFERENCE_SOURCES, 0)
        self.add_entry(f1, "Freq (Hz)", "frequency", 1)
        self.add_entry(f1, "Phase", "phase", 2)
        self.add_entry(f1, "Amp (V)", "sine_voltage", 3)
        self.add_entry(f1, "Harmonic", "harmonic", 4, is_int=True)

        f2 = ttk.LabelFrame(parent, text="Input")
        f2.grid(row=0, column=1, sticky="nsew", padx=2)
        self.add_combo(f2, "Config", "input_config", self.inst.INPUT_CONFIGS, 0)
        self.add_combo(f2, "Shield", "input_grounding", self.inst.INPUT_GROUNDINGS, 1)
        self.add_combo(f2, "Coupling", "input_coupling", self.inst.INPUT_COUPLINGS, 2)
        self.add_combo(f2, "Filter", "input_notch_config", self.inst.INPUT_NOTCH_CONFIGS, 3)

        f3 = ttk.LabelFrame(parent, text="Gain")
        f3.grid(row=0, column=2, sticky="nsew", padx=2)
        self.active_sens_map = SR830_VOLT_MAP
        self.add_combo(f3, "Sens", "sensitivity", [], 0, unit="V")
        self.add_combo(f3, "TC", "time_constant", self.inst.TIME_CONSTANTS, 1, unit="s")
        self.add_combo(f3, "Slope", "filter_slope", self.inst.FILTER_SLOPES, 2)
        self.add_combo(f3, "Reserve", "reserve", self.inst.RESERVE_VALUES, 3)

        # Add auxiliary section in row 1
        self.build_auxiliary_section(parent, 1)

    # --- HELPERS ---
    def add_entry(self, parent, label, attr, row, is_int=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=2)
        var = tk.StringVar(value="...")
        self.ctrl_vars[attr] = var
        entry = ttk.Entry(parent, textvariable=var, width=8)
        entry.grid(row=row, column=1, padx=2)

        def set_val():
            try:
                val = int(var.get()) if is_int else float(var.get())
                setattr(self.inst, attr, val)
                time.sleep(0.1)
                new_val = getattr(self.inst, attr)
                var.set(str(int(new_val) if is_int else new_val))
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(parent, text="Set", command=set_val, width=4).grid(row=row, column=2, padx=2)
        entry.bind('<Return>', lambda e: set_val())
        self.param_controls.append({'type': 'entry', 'attr': attr, 'var': var, 'is_int': is_int})

    def add_combo(self, parent, label, attr, values, row, unit=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=2)

        display_map = {}
        if attr != "sensitivity":
            if values and isinstance(values[0], str):
                display_map = {v: v for v in values}
            else:
                display_map = {Utility.format_eng(v, unit): v for v in values}

        combo = ttk.Combobox(parent, values=list(display_map.keys()), state="readonly", width=12)
        combo.grid(row=row, column=1, padx=2)
        self.ctrl_vars[attr] = tk.StringVar()

        def on_select(e):
            try:
                if attr == "sensitivity":
                    # Look up INDEX in active map by Display String
                    key = combo.get()
                    raw_val = None
                    for k_val, idx in self.active_sens_map.items():
                        if Utility.format_eng(k_val, self.active_meas_unit) == key:
                            raw_val = idx
                            break

                    if raw_val is not None:
                        # For SR830, we must force sending Index.
                        if self.is_SR830 and hasattr(self.inst, 'adapter'):
                            self.inst.adapter.connection.write(f"SENS {raw_val}")
                        else:
                            # SR860 uses SCAL, SR830 uses SENS (if no adapter)
                            cmd = "SENS" if self.is_SR830 else "SCAL"
                            self.inst.write(f"{cmd} {raw_val}")
                else:
                    if combo.get() not in display_map: return
                    val = display_map[combo.get()]
                    setattr(self.inst, attr, val)

                if attr in ["input_config", "voltage_input_mode"]:
                    self.update_sensitivity_list()
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        combo.bind("<<ComboboxSelected>>", on_select)
        self.param_controls.append({'type': 'combo', 'attr': attr, 'widget': combo, 'map': display_map, 'unit': unit})

    # --- SENSITIVITY LOGIC ---
    def update_sensitivity_list(self):
        new_map = {}
        unit = "V"

        if self.is_SR830:
            is_curr = False
            for ctrl in self.param_controls:
                if ctrl['attr'] == 'input_config':
                    if "I" in ctrl['widget'].get(): is_curr = True

            if is_curr:
                new_map = SR830_CURR_MAP
                unit = "A"
            else:
                new_map = SR830_VOLT_MAP
                unit = "V"
        else:
            mode = self.combo_mode.get()
            if mode == "Voltage":
                new_map = SR860_VOLT_MAP
                unit = "V"
            else:
                unit = "A"
                cfg = self.combo_cfg.get()
                if "10 nA" in cfg:
                    new_map = SR860_CURR_NA_MAP
                else:
                    new_map = SR860_CURR_UA_MAP

        self.active_sens_map = new_map
        self.active_meas_unit = unit

        for ctrl in self.param_controls:
            if ctrl['attr'] == 'sensitivity':
                display_keys = [Utility.format_eng(k, unit) for k in new_map.keys()]
                ctrl['widget']['values'] = display_keys

                # RE-SELECT Correct Value
                # The SR830 driver might return a Float (Volts) OR an Int (Index)
                # The SR860 driver returns an Int (Index)
                try:
                    raw_read = getattr(self.inst, 'sensitivity')
                    target_idx = -1

                    # TYPE DETECTION
                    if isinstance(raw_read, float):
                        # It is a Voltage Value (e.g. 0.01). Find corresponding Index.
                        # We use SR830_VOLT_MAP because it maps Volts -> Index.
                        # Find closest key in SR830_VOLT_MAP to this float
                        closest_v = min(SR830_VOLT_MAP.keys(), key=lambda k: abs(k - raw_read))
                        target_idx = SR830_VOLT_MAP[closest_v]
                    else:
                        # It is likely an Integer Index (e.g. 20)
                        # OR it's a string "20"
                        target_idx = int(float(raw_read))

                    # Now find which Key in our NEW MAP maps to this Index
                    found_val = None
                    for k, idx in new_map.items():
                        if idx == target_idx:
                            found_val = k
                            break

                    if found_val is not None:
                        ctrl['widget'].set(Utility.format_eng(found_val, unit))
                except:
                    pass

    def measure_direct(self):
        try:
            unit = self.active_meas_unit
            if self.is_SR830:
                self.inst.adapter.connection.write("*CLS")
                self.inst.write("SNAP? 1,2,3,4")
                response = self.inst.read()
                parts = response.strip().split(',')
                if len(parts) >= 4:
                    self.vars_meas["X"].set(Utility.format_eng(float(parts[0]), unit))
                    self.vars_meas["Y"].set(Utility.format_eng(float(parts[1]), unit))
                    self.vars_meas["R"].set(Utility.format_eng(float(parts[2]), unit))
                    self.vars_meas["Theta"].set(f"{float(parts[3]):.2f} °")
            else:
                self.inst.write("*CLS")
                val_x = float(self.inst.query("OUTP? 0"))
                val_y = float(self.inst.query("OUTP? 1"))
                val_r = float(self.inst.query("OUTP? 2"))
                val_t = float(self.inst.query("OUTP? 3"))
                self.vars_meas["X"].set(Utility.format_eng(val_x, unit))
                self.vars_meas["Y"].set(Utility.format_eng(val_y, unit))
                self.vars_meas["R"].set(Utility.format_eng(val_r, unit))
                self.vars_meas["Theta"].set(f"{val_t:.2f} °")
            
            # Also read auxiliary inputs
            self.read_aux_inputs()
        except:
            self.vars_meas["X"].set("Err")

    def refresh_settings(self):
        threading.Thread(target=self.startup_sequence, daemon=True).start()

    def startup_sequence(self):
        time.sleep(0.1)
        if not self.is_SR830:
            self.after(0, self.update_sr860_ui_from_inst)
        time.sleep(0.1)
        self.after(0, self.update_sensitivity_list)
        time.sleep(0.2)

        for ctrl in self.param_controls:
            if self.stop_threads: break
            try:
                val = getattr(self.inst, ctrl['attr'])
                if ctrl['type'] == 'entry':
                    fmt_val = str(int(val) if ctrl['is_int'] else val)
                    self.after(0, lambda v=ctrl['var'], x=fmt_val: v.set(x))
                elif ctrl['type'] == 'combo':
                    if ctrl['attr'] == 'sensitivity': continue  # Handled by update

                    d_map = ctrl['map']
                    match = "Err"
                    if isinstance(val, str):
                        match = val
                    else:
                        min_diff = float('inf')
                        for k, v in d_map.items():
                            try:
                                diff = abs(v - val)
                                if diff < min_diff:
                                    min_diff = diff
                                    match = k
                            except:
                                pass
                    self.after(0, lambda w=ctrl['widget'], m=match: w.set(m))
                time.sleep(0.02)
            except:
                pass
        
        # Load auxiliary values
        time.sleep(0.1)
        self.after(0, self.load_aux_outputs)
        self.after(0, self.read_aux_inputs)
        
        self.initialization_complete = True

    def monitor_loop(self):
        while not self.stop_threads:
            if self.initialization_complete and self.auto_refresh.get():
                self.measure_direct()
                time.sleep(0.5)
            else:
                time.sleep(0.2)

    def request_close(self):
        self.stop_threads = True
        try:
            if hasattr(self.inst, 'close'):
                self.inst.close()
            elif hasattr(self.inst, 'adapter'):
                self.inst.adapter.close()
        except:
            pass
        self.remove_callback(self)


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SRS Lock-in Controller")
        self.geometry("1000x650")

        c_frame = ttk.LabelFrame(self, text="Connection")
        c_frame.pack(fill="x", padx=10, pady=5)

        self.addr_combo = ttk.Combobox(c_frame, width=25)
        self.addr_combo.pack(side="left", padx=5)
        ttk.Button(c_frame, text="Refresh", command=self.scan_ports).pack(side="left")

        self.model_combo = ttk.Combobox(c_frame, values=["SR830", "SR860"], state="readonly", width=10)
        self.model_combo.current(0)
        self.model_combo.pack(side="left", padx=15)

        ttk.Button(c_frame, text="CONNECT", command=self.connect).pack(side="left", padx=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=5)

        self.scan_ports()

    def scan_ports(self):
        try:
            rm = pyvisa.ResourceManager()
            ports = list(rm.list_resources())
            self.addr_combo['values'] = ports if ports else ["No VISA devices found"]
            if ports:
                self.addr_combo.current(0)
        except:
            self.addr_combo['values'] = ["VISA Error"]

    def connect(self):
        addr = self.addr_combo.get()
        model = self.model_combo.get()
        if "found" in addr or "Error" in addr:
            return
        try:
            if model == "SR830":
                if SR830 is None:
                    raise Exception("SR830 Driver missing")
                inst = SR830(addr)
            else:
                inst = SR860_Direct(addr)
            tab = InstrumentPanel(self.notebook, inst, self.close_tab, name=f"{model} ({addr})")
            self.notebook.add(tab, text=f"{model}")
            self.notebook.select(tab)
        except Exception as e:
            messagebox.showerror("Connection Failed", str(e))

    def close_tab(self, tab):
        self.notebook.forget(tab)
        tab.destroy()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
