"""
Instrument All-In-One Controller
================================

One GUI for the whole bench.

"Scan VISA Instruments" queries *IDN? on every VISA resource and opens a
model-appropriate panel per instrument. "Scan LabOne" connects to Zurich
Instruments devices (MFLI) through the LabOne data server (not VISA).

Auto-detected (VISA *IDN?):
  Keithley 2000         Multimeter
  Keithley 2182/2182A   Nanovoltmeter
  Keithley 2450 family  SourceMeter (2450/2460/2461/2470)
  Keithley 6221         AC/DC current source
  Keithley 2600 series  Dual-channel TSP SMU (2604B ...)
  SRS SR830 / SR860     Lock-in amplifiers
  Yokogawa GS200        DC source

Manual connect (no *IDN? or detection failed):
  Yokogawa 7651 (legacy protocol - never auto-detected), any model above

Via LabOne:
  Zurich Instruments MFLI lock-in

Run:
    python "Instrument control/InstrumentAllInOne_GUI.py"

Supersedes KeithleyAllInOne_GUI.py (which remains available).
Drivers come from ../Instruments/ and are used unmodified.
"""

import math
import os
import re
import sys
import time
import threading
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import numpy as np
import pyvisa
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

current_dir = os.path.dirname(os.path.abspath(__file__))
instruments_path = os.path.join(current_dir, '..')
sys.path.insert(0, instruments_path)  # front of path: beats stale local Instruments/

from Instruments.keithley2000_with_add_ons import Keithley2000
from Instruments.keithley2182_with_add_ons import Keithley2182
from Instruments.keithley2450_with_add_ons import Keithley2450
from Instruments.keithley2604B import Keithley2604B
from Instruments.keithley6221_with_add_ons import Keithley6221
from Instruments.SR830_with_add_ons import SR830
from Instruments.SR860_with_add_ons import SR860
from Instruments.yokogawags200_with_add_ons import YokogawaGS200
from Instruments.yokogawa7651_with_add_ons import Yokogawa7651

try:
    from Instruments.MFLI import MFLIController
except Exception:
    MFLIController = None  # zhinst / LabOne API not installed


# ============================================================
# Model detection
# ============================================================

KEITHLEY_2600_FAMILY = ('2600', '2601', '2602', '2603', '2604', '2605', '2606')
KEITHLEY_2450_FAMILY = ('2450', '2460', '2461', '2470')


def classify_instrument(idn):
    """Return a registry key for an *IDN? string, else None (not ours).

    'unknown' means: recognized vendor but unsupported model.
    """
    if not idn:
        return None
    parts = [p.strip() for p in idn.split(',')]
    vendor = parts[0].upper() if parts else ''
    model = parts[1].upper() if len(parts) > 1 else ''

    if 'KEITHLEY' in vendor:
        m = re.search(r'MODEL\s*([0-9]+[A-Z]*)', idn, re.IGNORECASE)
        digits = re.sub(r'\D', '', m.group(1)) if m else ''
        if digits in KEITHLEY_2600_FAMILY:
            return '2600'
        if digits in KEITHLEY_2450_FAMILY:
            # Same touchscreen SourceMeter SCPI family; 2450 driver covers them.
            return '2450'
        if digits in ('2000', '2182', '6221'):
            return digits
        return 'unknown'

    if 'STANFORD' in vendor or 'SRS' in vendor:
        if 'SR830' in model:
            return 'sr830'
        if 'SR860' in model:
            return 'sr860'
        return 'unknown'

    if 'YOKOGAWA' in vendor:
        # GS210 = newer firmware/revision of the GS200, same driver
        if 'GS200' in model or 'GS210' in model:
            return 'gs200'
        if '7651' in model:
            return 'yoko7651'
        return 'unknown'

    return None


DISPLAY_NAME = {
    '2000': 'Keithley 2000 Multimeter',
    '2182': 'Keithley 2182 Nanovoltmeter',
    '2450': 'Keithley 2450-family SourceMeter',
    '6221': 'Keithley 6221 Current Source',
    '2600': 'Keithley 2600-series SMU',
    'sr830': 'SRS SR830 Lock-in Amplifier',
    'sr860': 'SRS SR860 Lock-in Amplifier',
    'gs200': 'Yokogawa GS200 Source',
    'yoko7651': 'Yokogawa 7651 Source',
    'mfli': 'Zurich Instruments MFLI Lock-in',
}


class Utility:
    @staticmethod
    def format_eng(number, unit=''):
        try:
            val = float(number)
            if val == 0:
                return f'0 {unit}'
            exponent = int(math.floor(math.log10(abs(val))))
            eng = exponent - (exponent % 3)
            frac = val / (10 ** eng)
            prefixes = {-18: 'a', -15: 'f', -12: 'p', -9: 'n', -6: 'u', -3: 'm',
                        0: '', 3: 'k', 6: 'M', 9: 'G'}
            return f'{frac:.3g} {prefixes.get(eng, f"e{eng}")}{unit}'
        except Exception:
            return f'{number} {unit}'


# ============================================================
# Base panel: per-device lock + timestamped log + polling
# ============================================================

class KeithleyPanel(ttk.Frame):
    """Base class for one connected instrument tab."""

    def __init__(self, parent, inst, address):
        super().__init__(parent)
        self.inst = inst
        self.address = address
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self._build_log()
        self.build_ui()
        self.after(2000, self.poll)

    def _build_log(self):
        frame = ttk.LabelFrame(self, text='System Log')
        frame.pack(fill='x', padx=10, pady=5, side='bottom')
        self.console = scrolledtext.ScrolledText(frame, height=5, state='disabled',
                                                 font=('Consolas', 9))
        self.console.pack(fill='both', expand=True, padx=5, pady=5)

    def log_message(self, message):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.console.configure(state='normal')
        self.console.insert(tk.END, f'[{ts}] {message}\n')
        self.console.see(tk.END)
        self.console.configure(state='disabled')

    def build_ui(self):
        pass

    def poll(self):
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        try:
            if hasattr(self.inst, 'adapter'):
                self.inst.adapter.connection.close()
        except Exception:
            pass


# ============================================================
# Keithley 2000 - Multimeter
# ============================================================

K2000_READ = {
    'voltage': 'voltage', 'voltage ac': 'voltage',
    'current': 'current', 'current ac': 'current',
    'resistance': 'resistance', 'resistance 4W': 'resistance',
    'frequency': 'frequency', 'period': 'period',
    'temperature': 'temperature',
    'diode': 'voltage', 'continuity': 'resistance',
}


class Panel2000(KeithleyPanel):
    """Readout panel for the Keithley 2000 DMM."""

    def build_ui(self):
        cfg = ttk.LabelFrame(self, text='Measurement Configuration')
        cfg.pack(fill='x', padx=10, pady=10)

        ttk.Label(cfg, text='Mode:').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.mode_var = tk.StringVar(value='voltage')
        ttk.Combobox(cfg, textvariable=self.mode_var,
                     values=list(Keithley2000.MODES.keys()),
                     state='readonly', width=15).grid(row=0, column=1, padx=5, sticky='w')

        ttk.Label(cfg, text='NPLC:').grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.ent_nplc = ttk.Entry(cfg, width=8)
        self.ent_nplc.insert(0, '1')
        self.ent_nplc.grid(row=0, column=3, padx=5)

        ttk.Button(cfg, text='Apply', command=self.apply_config).grid(row=0, column=4, padx=5)
        ttk.Button(cfg, text='Auto Range', command=self.auto_range).grid(row=0, column=5, padx=5)

        read_frame = ttk.LabelFrame(self, text='Readout')
        read_frame.pack(fill='x', padx=10, pady=5)
        self.lbl_value = ttk.Label(read_frame, text='--', font=('Consolas', 18, 'bold'),
                                   foreground='blue')
        self.lbl_value.pack(side='left', padx=15, pady=8)
        self.btn_read = ttk.Button(read_frame, text='MEASURE', command=self.read_once)
        self.btn_read.pack(side='right', padx=10)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(read_frame, text='Auto refresh (2 s)',
                        variable=self.auto_var).pack(side='right', padx=10)

    def apply_config(self):
        mode = self.mode_var.get()
        try:
            nplc = float(self.ent_nplc.get())
            with self.lock:
                self.inst.mode = mode
                prop = mode.replace(' ', '_') + '_nplc'
                if hasattr(self.inst, prop):
                    setattr(self.inst, prop, nplc)
            self.log_message(f'Configured mode={mode}, NPLC={nplc}')
        except Exception as e:
            messagebox.showerror('Config Error', str(e))

    def auto_range(self):
        try:
            with self.lock:
                self.inst.auto_range(self.mode_var.get())
            self.log_message('Auto range set.')
        except Exception as e:
            self.log_message(f'Auto range error: {e}')

    def read_once(self):
        try:
            with self.lock:
                attr = K2000_READ.get(self.mode_var.get(), 'voltage')
                val = getattr(self.inst, attr)
            self.lbl_value.config(text=f'{val:.6g}')
            return val
        except Exception as e:
            self.lbl_value.config(text='Err')
            self.log_message(f'Read error: {e}')
            return None

    def poll(self):
        if self.auto_var.get():
            self.read_once()
        self.after(2000, self.poll)


# ============================================================
# Keithley 2182 - Nanovoltmeter
# ============================================================

class Panel2182(KeithleyPanel):
    """Voltage / temperature readout panel for the Keithley 2182."""

    def build_ui(self):
        cfg = ttk.LabelFrame(self, text='Channel Configuration')
        cfg.pack(fill='x', padx=10, pady=10)

        ttk.Label(cfg, text='Channel:').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.channel_var = tk.StringVar(value='1')
        ttk.Combobox(cfg, textvariable=self.channel_var, values=['1', '2'],
                     state='readonly', width=5).grid(row=0, column=1, padx=5)

        self.func_var = tk.StringVar(value='voltage')
        ttk.Label(cfg, text='Function:').grid(row=0, column=2, padx=5, pady=5, sticky='e')
        ttk.Combobox(cfg, textvariable=self.func_var, values=['voltage', 'temperature'],
                     state='readonly', width=12).grid(row=0, column=3, padx=5)

        ttk.Label(cfg, text='NPLC:').grid(row=0, column=4, padx=5, pady=5, sticky='e')
        self.ent_nplc = ttk.Entry(cfg, width=6)
        self.ent_nplc.insert(0, '5')
        self.ent_nplc.grid(row=0, column=5, padx=5)

        ttk.Label(cfg, text='Thermocouple:').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.tc_var = tk.StringVar(value='K')
        ttk.Combobox(cfg, textvariable=self.tc_var, values=list('BEJKNRST'),
                     state='readonly', width=5).grid(row=1, column=1, padx=5)

        ttk.Button(cfg, text='Apply', command=self.apply_config).grid(row=1, column=2, padx=5)

        read_frame = ttk.LabelFrame(self, text='Readout')
        read_frame.pack(fill='x', padx=10, pady=5)
        self.lbl_value = ttk.Label(read_frame, text='--', font=('Consolas', 18, 'bold'),
                                   foreground='blue')
        self.lbl_value.pack(side='left', padx=15, pady=8)
        self.btn_read = ttk.Button(read_frame, text='MEASURE', command=self.read_once)
        self.btn_read.pack(side='right', padx=10)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(read_frame, text='Auto refresh (2 s)',
                        variable=self.auto_var).pack(side='right', padx=10)
        ttk.Button(read_frame, text='Internal Temp',
                   command=self.read_internal_temp).pack(side='right', padx=10)

    def apply_config(self):
        ch = int(self.channel_var.get())
        func = self.func_var.get()
        nplc = float(self.ent_nplc.get())
        try:
            with self.lock:
                channel = self.inst.ch_1 if ch == 1 else self.inst.ch_2
                if func == 'voltage':
                    channel.setup_voltage(auto_range=True, nplc=nplc)
                else:
                    channel.setup_temperature(nplc=nplc)
                    self.inst.active_channel = ch
                    self.inst.thermocouple = self.tc_var.get()
            self.log_message(f'Configured channel {ch} for {func}, NPLC={nplc}')
        except Exception as e:
            messagebox.showerror('Config Error', str(e))

    def read_once(self):
        try:
            with self.lock:
                val = self.inst.voltage if self.func_var.get() == 'voltage' \
                    else self.inst.temperature
            unit = 'V' if self.func_var.get() == 'voltage' else 'C'
            self.lbl_value.config(text=f'{val:.6g} {unit}')
            return val
        except Exception as e:
            self.lbl_value.config(text='Err')
            self.log_message(f'Read error: {e}')
            return None

    def read_internal_temp(self):
        try:
            with self.lock:
                val = self.inst.internal_temperature
            self.log_message(f'Internal temperature: {val:.2f} C')
        except Exception as e:
            self.log_message(f'Internal temp error: {e}')

    def poll(self):
        if self.auto_var.get():
            self.read_once()
        self.after(2000, self.poll)


# ============================================================
# Keithley 6221 - AC/DC current source
# ============================================================

class Panel6221(KeithleyPanel):
    """DC source, ramp and waveform panel for the Keithley 6221."""

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        self.lbl_output = ttk.Label(top, text='OUTPUT: OFF', foreground='red',
                                    font=('Arial', 12, 'bold'))
        self.lbl_output.pack(side='left', padx=15)
        ttk.Button(top, text='Hard Reset', command=self.reset_instrument).pack(side='right', padx=5)

        nb = ttk.Notebook(self)
        nb.pack(fill='x', padx=10, pady=5)
        dc = ttk.Frame(nb); nb.add(dc, text='DC Source')
        ramp = ttk.Frame(nb); nb.add(ramp, text='Ramping')
        sweep = ttk.Frame(nb); nb.add(sweep, text='DC Sweep')
        wave = ttk.Frame(nb); nb.add(wave, text='Waveform')
        self._build_dc(dc)
        self._build_ramp(ramp)
        self._build_sweep(sweep)
        self._build_wave(wave)

    def _build_dc(self, parent):
        f = ttk.LabelFrame(parent, text='DC Current Source')
        f.pack(fill='x', padx=10, pady=10)

        ttk.Label(f, text='Source Current (A):').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.ent_level = ttk.Entry(f, width=15)
        self.ent_level.insert(0, '0.0')
        self.ent_level.grid(row=0, column=1, sticky='w')

        ttk.Label(f, text='Compliance (V):').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.ent_compliance = ttk.Entry(f, width=15)
        self.ent_compliance.insert(0, '10')
        self.ent_compliance.grid(row=1, column=1, sticky='w')

        ttk.Label(f, text='Source Range:').grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.range_var = tk.StringVar(value='Auto')
        ttk.Combobox(f, textvariable=self.range_var, width=12,
                     values=['Auto', '105e-3', '10e-3', '1e-3', '100e-6', '10e-6',
                             '1e-6']).grid(row=2, column=1, sticky='w')

        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, columnspan=3, pady=10)
        ttk.Button(bf, text='APPLY', command=self.apply_source).pack(side='left', padx=10)
        ttk.Button(bf, text='Toggle Output ON/OFF',
                   command=self.toggle_output).pack(side='left', padx=10)

    def _build_ramp(self, parent):
        f = ttk.LabelFrame(parent, text='Linear Ramp (software, abortable)')
        f.pack(fill='x', padx=10, pady=10)

        ttk.Label(f, text='Target (A):').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.ent_ramp_target = ttk.Entry(f, width=12)
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        ttk.Label(f, text='Step (A):').grid(row=0, column=2, padx=5, sticky='e')
        self.ent_ramp_step = ttk.Entry(f, width=12)
        self.ent_ramp_step.insert(0, '1e-6')
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        ttk.Label(f, text='Time/Step (s):').grid(row=0, column=4, padx=5, sticky='e')
        self.ent_ramp_time = ttk.Entry(f, width=10)
        self.ent_ramp_time.insert(0, '0.05')
        self.ent_ramp_time.grid(row=0, column=5, padx=5)

        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=6, pady=10)
        self.btn_start_ramp = ttk.Button(bf, text='Start Ramp', command=self.start_ramp)
        self.btn_start_ramp.pack(side='left', padx=10)
        self.btn_stop_ramp = ttk.Button(bf, text='ABORT', command=self.stop_ramp,
                                        state='disabled')
        self.btn_stop_ramp.pack(side='left', padx=10)
        self.lbl_ramp_status = ttk.Label(bf, text='--', font=('Consolas', 11, 'bold'))
        self.lbl_ramp_status.pack(side='left', padx=20)

    def _build_sweep(self, parent):
        f = ttk.LabelFrame(parent, text='DC Current Sweep (software, abortable)')
        f.pack(fill='x', padx=10, pady=10)

        for col, (label, attr, default, width) in enumerate([
                ('Start (A):', 'ent_sweep_start', '0', 12),
                ('Stop (A):', 'ent_sweep_stop', '1e-6', 12),
                ('Step (A):', 'ent_sweep_step', '1e-7', 12),
                ('Delay/Point (s):', 'ent_sweep_delay', '0.05', 10)]):
            ttk.Label(f, text=label).grid(row=0, column=col * 2, padx=5, pady=5, sticky='e')
            ent = ttk.Entry(f, width=width)
            ent.insert(0, default)
            ent.grid(row=0, column=col * 2 + 1, sticky='w')
            setattr(self, attr, ent)

        self.sweep_range_var = tk.StringVar(value='Auto')
        ttk.Label(f, text='Source Range:').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        ttk.Combobox(f, textvariable=self.sweep_range_var, width=12,
                     values=['Auto', '105e-3', '10e-3', '1e-3', '100e-6', '10e-6',
                             '1e-6']).grid(row=1, column=1, sticky='w')

        self.sweep_return_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text='Return to start after sweep',
                        variable=self.sweep_return_var).grid(
            row=2, column=0, columnspan=4, sticky='w', padx=5)

        bf = ttk.Frame(f)
        bf.grid(row=2, column=4, columnspan=5, pady=5)
        self.btn_start_sweep = ttk.Button(bf, text='Start Sweep', command=self.start_sweep)
        self.btn_start_sweep.pack(side='left', padx=10)
        self.btn_stop_sweep = ttk.Button(bf, text='ABORT', command=self.stop_sweep,
                                         state='disabled')
        self.btn_stop_sweep.pack(side='left', padx=10)
        self.lbl_sweep_status = ttk.Label(bf, text='--', font=('Consolas', 11, 'bold'))
        self.lbl_sweep_status.pack(side='left', padx=20)

        # Live plot: sourced current vs elapsed time
        self.fig_sweep, self.ax_sweep = plt.subplots(figsize=(6, 2.5), dpi=100)
        self.ax_sweep.set_title('DC Sweep')
        self.ax_sweep.set_xlabel('Time (s)')
        self.ax_sweep.set_ylabel('Current (A)')
        self.ax_sweep.grid(True)
        self.line_sweep, = self.ax_sweep.plot([], [], '.-', color='blue', linewidth=1)
        self.canvas_sweep = FigureCanvasTkAgg(self.fig_sweep, master=parent)
        self.canvas_sweep.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=5)

    def _build_wave(self, parent):
        f = ttk.LabelFrame(parent, text='Waveform Generator')
        f.pack(fill='x', padx=10, pady=10)

        ttk.Label(f, text='Function:').grid(row=0, column=0, padx=5, pady=3, sticky='e')
        self.wave_func_var = tk.StringVar(value='sine')
        ttk.Combobox(f, textvariable=self.wave_func_var, width=12,
                     values=['sine', 'ramp', 'square', 'arbitrary1', 'arbitrary2',
                             'arbitrary3', 'arbitrary4']).grid(row=0, column=1, sticky='w')
        ttk.Label(f, text='Frequency (Hz):').grid(row=1, column=0, padx=5, pady=3, sticky='e')
        self.ent_wf_freq = ttk.Entry(f, width=12); self.ent_wf_freq.insert(0, '1000')
        self.ent_wf_freq.grid(row=1, column=1, sticky='w')
        ttk.Label(f, text='Amplitude (A):').grid(row=2, column=0, padx=5, pady=3, sticky='e')
        self.ent_wf_ampl = ttk.Entry(f, width=12); self.ent_wf_ampl.insert(0, '1e-6')
        self.ent_wf_ampl.grid(row=2, column=1, sticky='w')
        ttk.Label(f, text='Offset (A):').grid(row=3, column=0, padx=5, pady=3, sticky='e')
        self.ent_wf_offs = ttk.Entry(f, width=12); self.ent_wf_offs.insert(0, '0')
        self.ent_wf_offs.grid(row=3, column=1, sticky='w')
        ttk.Label(f, text='Duty Cycle (%):').grid(row=4, column=0, padx=5, pady=3, sticky='e')
        self.ent_wf_duty = ttk.Entry(f, width=12); self.ent_wf_duty.insert(0, '50')
        self.ent_wf_duty.grid(row=4, column=1, sticky='w')

        bf = ttk.Frame(f)
        bf.grid(row=5, column=0, columnspan=3, pady=10)
        ttk.Button(bf, text='Set Waveform', command=self.apply_waveform).pack(side='left', padx=10)
        self.btn_wf_arm = ttk.Button(bf, text='ARM', command=self.wf_arm)
        self.btn_wf_arm.pack(side='left', padx=10)
        self.btn_wf_start = ttk.Button(bf, text='START', command=self.wf_start)
        self.btn_wf_start.pack(side='left', padx=10)
        self.btn_wf_abort = ttk.Button(bf, text='ABORT', command=self.wf_abort)
        self.btn_wf_abort.pack(side='left', padx=10)

    # --- DC source logic ---

    def apply_source(self):
        try:
            level = float(self.ent_level.get())
            comp = float(self.ent_compliance.get())
            with self.lock:
                self.inst.source_compliance = comp
                rng = self.range_var.get()
                if rng == 'Auto':
                    self.inst.source_auto_range = True
                else:
                    self.inst.source_range = float(rng)
                self.inst.source_current = level
            self.log_message(f'Applied: I={level}, Compliance={comp} V, Range={rng}')
        except ValueError:
            messagebox.showerror('Input Error', 'Please enter valid numbers')
        except Exception as e:
            messagebox.showerror('Instrument Error', str(e))

    def toggle_output(self):
        try:
            with self.lock:
                if self.inst.source_enabled:
                    self.inst.disable_source()
                else:
                    self.inst.enable_source()
        except Exception as e:
            self.log_message(f'Output toggle error: {e}')
        self._refresh_output()

    def _refresh_output(self):
        try:
            with self.lock:
                on = self.inst.source_enabled
            self.lbl_output.config(text=f'OUTPUT: {"ON" if on else "OFF"}',
                                   foreground='green' if on else 'red')
        except Exception:
            pass

    def reset_instrument(self):
        with self.lock:
            try:
                self.inst.reset()
                self.log_message('Instrument hard reset (output OFF).')
            except Exception as e:
                self.log_message(f'Reset error: {e}')
        self._refresh_output()

    # --- ramp logic ---

    def start_ramp(self):
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid ramp parameters')
            return
        self.log_message(f'Starting ramp -> {target} A...')
        self.stop_event.clear()
        self.btn_start_ramp.config(state='disabled')
        self.btn_stop_ramp.config(state='normal')
        threading.Thread(target=self._run_ramp_thread,
                         args=(target, step, time_step), daemon=True).start()

    def stop_ramp(self):
        self.stop_event.set()
        self.log_message('Ramp abort requested.')

    def _run_ramp_thread(self, target, step, time_step):
        try:
            with self.lock:
                self.inst.enable_source()
                start = float(self.inst.source_current)
            if step == 0:
                step = 1e-9
            points = int(abs(target - start) / abs(step)) + 1
            for val in np.linspace(start, target, points):
                if self.stop_event.is_set():
                    break
                with self.lock:
                    self.inst.source_current = val
                self.after(0, lambda v=val: self.lbl_ramp_status.config(text=f'{v:.4e} A'))
                time.sleep(time_step)
            with self.lock:
                self.inst.source_current = target
            self.log_message('Ramp aborted.' if self.stop_event.is_set()
                             else 'Ramp completed.')
        except Exception as e:
            self.log_message(f'Ramp error: {e}')
        finally:
            self.after(0, lambda: self.btn_stop_ramp.config(state='disabled'))
            self.after(0, lambda: self.btn_start_ramp.config(state='normal'))

    # --- DC sweep logic ---

    def start_sweep(self):
        try:
            start = float(self.ent_sweep_start.get())
            stop = float(self.ent_sweep_stop.get())
            step = float(self.ent_sweep_step.get())
            delay = float(self.ent_sweep_delay.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid sweep parameters')
            return
        if step <= 0:
            messagebox.showerror('Error', 'Step must be positive')
            return
        self.log_message(f'Starting DC sweep: {start} A -> {stop} A, step {step} A, '
                         f'range {self.sweep_range_var.get()}')
        self.stop_event.clear()
        self.btn_start_sweep.config(state='disabled')
        self.btn_stop_sweep.config(state='normal')
        self._sweep_x = []
        self._sweep_y = []
        self.ax_sweep.relim()
        self.ax_sweep.autoscale_view()
        threading.Thread(target=self._run_sweep_thread,
                         args=(start, stop, step, delay), daemon=True).start()

    def stop_sweep(self):
        self.stop_event.set()
        self.log_message('Sweep abort requested.')

    def _update_sweep_graph(self):
        self.line_sweep.set_data(self._sweep_x, self._sweep_y)
        if self._sweep_y:
            self.lbl_sweep_status.config(text=f'{self._sweep_y[-1]:.4e} A')
        self.ax_sweep.relim()
        self.ax_sweep.autoscale_view()
        self.canvas_sweep.draw()

    def _run_sweep_thread(self, start, stop, step, delay):
        try:
            with self.lock:
                rng = self.sweep_range_var.get()
                if rng == 'Auto':
                    self.inst.source_auto_range = True
                else:
                    # Fixed range: no relay switching mid-sweep, output stays continuous
                    self.inst.source_range = float(rng)
                self.inst.enable_source()
            values = np.arange(start, stop + (step / 2 if stop >= start else -step / 2),
                               step if stop >= start else -step)
            t0 = time.perf_counter()
            for val in values:
                if self.stop_event.is_set():
                    break
                with self.lock:
                    self.inst.source_current = float(val)
                self._sweep_x.append(time.perf_counter() - t0)
                self._sweep_y.append(float(val))
                self.after(0, self._update_sweep_graph)
                time.sleep(delay)
            if self.sweep_return_var.get() and not self.stop_event.is_set():
                with self.lock:
                    self.inst.source_current = start
            self.log_message('Sweep aborted.' if self.stop_event.is_set()
                             else f'Sweep complete ({len(self._sweep_y)} points).')
        except Exception as e:
            self.log_message(f'Sweep error: {e}')
        finally:
            self.after(0, lambda: self.btn_stop_sweep.config(state='disabled'))
            self.after(0, lambda: self.btn_start_sweep.config(state='normal'))

    # --- waveform logic ---

    def apply_waveform(self):
        try:
            with self.lock:
                self.inst.waveform_function = self.wave_func_var.get()
                self.inst.waveform_frequency = float(self.ent_wf_freq.get())
                self.inst.waveform_amplitude = float(self.ent_wf_ampl.get())
                self.inst.waveform_offset = float(self.ent_wf_offs.get())
                self.inst.waveform_dutycycle = float(self.ent_wf_duty.get())
            self.log_message('Waveform parameters set. Use ARM then START.')
        except Exception as e:
            messagebox.showerror('Waveform Error', str(e))

    def wf_arm(self):
        try:
            with self.lock:
                self.inst.waveform_arm()
            self.log_message('Waveform armed.')
        except Exception as e:
            self.log_message(f'Arm error: {e}')

    def wf_start(self):
        try:
            with self.lock:
                self.inst.enable_source()
                self.inst.waveform_start()
            self.log_message('Waveform started.')
        except Exception as e:
            self.log_message(f'Start error: {e}')
        self._refresh_output()

    def wf_abort(self):
        try:
            with self.lock:
                self.inst.waveform_abort()
                self.inst.disable_source()
            self.log_message('Waveform aborted and disarmed, output OFF.')
        except Exception as e:
            self.log_message(f'Abort error: {e}')
        self._refresh_output()

    def poll(self):
        self._refresh_output()
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        try:
            with self.lock:
                self.inst.waveform_abort()
                self.inst.disable_source()
        except Exception:
            pass
        plt.close(self.fig_sweep)
        super().cleanup()


# ============================================================
# Keithley 2450 - SourceMeter
# ============================================================

class Panel2450(KeithleyPanel):
    """Source/measure, ramp and system panel for the Keithley 2450."""

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        self.lbl_output = ttk.Label(top, text='OUTPUT: OFF', foreground='red',
                                    font=('Arial', 12, 'bold'))
        self.lbl_output.pack(side='left', padx=15)
        self.lbl_terminals = ttk.Label(top, text='TERMINALS: --', font=('Arial', 10))
        self.lbl_terminals.pack(side='left', padx=15)
        ttk.Button(top, text='Hard Reset', command=self.reset_instrument).pack(side='right', padx=5)

        nb = ttk.Notebook(self)
        nb.pack(fill='x', padx=10, pady=5)
        manual = ttk.Frame(nb); nb.add(manual, text='Manual Control')
        ramp = ttk.Frame(nb); nb.add(ramp, text='Ramping & Sweep')
        system = ttk.Frame(nb); nb.add(system, text='System Config')
        self._build_manual(manual)
        self._build_ramp(ramp)
        self._build_system(system)
        self._build_monitor()
        self._update_ui_labels()

    def _build_manual(self, parent):
        frame = ttk.LabelFrame(parent, text='Source & Measure Configuration')
        frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(frame, text='Source Mode:').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.source_mode_var = tk.StringVar(value='voltage')
        mf = ttk.Frame(frame)
        mf.grid(row=0, column=1, columnspan=2, sticky='w')
        ttk.Radiobutton(mf, text='Voltage', variable=self.source_mode_var, value='voltage',
                        command=self._update_ui_labels).pack(side='left')
        ttk.Radiobutton(mf, text='Current', variable=self.source_mode_var, value='current',
                        command=self._update_ui_labels).pack(side='left')

        ttk.Label(frame, text='Output Range:').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.out_range_var = tk.StringVar(value='Auto')
        self.cb_out_range = ttk.Combobox(frame, textvariable=self.out_range_var, width=15)
        self.cb_out_range.grid(row=1, column=1, padx=5, sticky='w')
        self.lbl_src_range_txt = ttk.Label(frame, text='(Source V Range)')
        self.lbl_src_range_txt.grid(row=1, column=2, sticky='w')

        ttk.Label(frame, text='Source Level:').grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.ent_level = ttk.Entry(frame, width=17)
        self.ent_level.insert(0, '0.0')
        self.ent_level.grid(row=2, column=1, padx=5, sticky='w')
        self.lbl_unit_level = ttk.Label(frame, text='V')
        self.lbl_unit_level.grid(row=2, column=2, sticky='w')

        ttk.Label(frame, text='Limit (Compliance):').grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.ent_limit = ttk.Entry(frame, width=17)
        self.ent_limit.insert(0, '0.01')
        self.ent_limit.grid(row=3, column=1, padx=5, sticky='w')
        self.lbl_unit_limit = ttk.Label(frame, text='A')
        self.lbl_unit_limit.grid(row=3, column=2, sticky='w')

        ttk.Label(frame, text='Measurement Range:').grid(row=4, column=0, padx=5, pady=5, sticky='e')
        self.meas_range_var = tk.StringVar(value='Auto')
        self.cb_meas_range = ttk.Combobox(frame, textvariable=self.meas_range_var, width=15)
        self.cb_meas_range.grid(row=4, column=1, padx=5, sticky='w')
        self.lbl_meas_range_txt = ttk.Label(frame, text='(Measure I Range)')
        self.lbl_meas_range_txt.grid(row=4, column=2, sticky='w')

        bf = ttk.Frame(frame)
        bf.grid(row=5, column=0, columnspan=4, pady=10)
        ttk.Button(bf, text='APPLY CONFIGURATION', command=self.apply_source).pack(side='left', padx=10)
        ttk.Button(bf, text='Toggle Output ON/OFF', command=self.toggle_output).pack(side='left', padx=10)

    def _build_ramp(self, parent):
        frame = ttk.LabelFrame(parent, text='Linear Sweep (Ramp)')
        frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(frame, text='Target Level:').grid(row=0, column=0, padx=5)
        self.ent_ramp_target = ttk.Entry(frame, width=10)
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        ttk.Label(frame, text='Step Size:').grid(row=0, column=2, padx=5)
        self.ent_ramp_step = ttk.Entry(frame, width=10)
        self.ent_ramp_step.insert(0, '0.1')
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        ttk.Label(frame, text='Time/Step (s):').grid(row=0, column=4, padx=5)
        self.ent_ramp_time = ttk.Entry(frame, width=10)
        self.ent_ramp_time.insert(0, '0.1')
        self.ent_ramp_time.grid(row=0, column=5, padx=5)

        self.btn_start_ramp = ttk.Button(frame, text='Start Ramp', command=self.start_ramp)
        self.btn_start_ramp.grid(row=1, column=1, pady=10)
        self.btn_stop_ramp = ttk.Button(frame, text='ABORT', command=self.stop_ramp,
                                        state='disabled')
        self.btn_stop_ramp.grid(row=1, column=3, pady=10)

    def _build_system(self, parent):
        frame_term = ttk.LabelFrame(parent, text='Terminals')
        frame_term.pack(fill='x', padx=10, pady=5)
        ttk.Button(frame_term, text='Use Front',
                   command=lambda: self.set_terminals('FRON')).pack(side='left', padx=5, pady=5)
        ttk.Button(frame_term, text='Use Rear',
                   command=lambda: self.set_terminals('REAR')).pack(side='left', padx=5, pady=5)

        frame_wire = ttk.LabelFrame(parent, text='Sensing Mode')
        frame_wire.pack(fill='x', padx=10, pady=5)
        self.wire_var = tk.IntVar(value=2)
        ttk.Radiobutton(frame_wire, text='2-Wire', variable=self.wire_var, value=2,
                        command=self.set_wiring).pack(side='left', padx=10)
        ttk.Radiobutton(frame_wire, text='4-Wire (Remote Sense)', variable=self.wire_var, value=4,
                        command=self.set_wiring).pack(side='left', padx=10)

    def _build_monitor(self):
        frame = ttk.Frame(self)
        frame.pack(fill='x', padx=10, pady=5)
        self.lbl_measure_title = ttk.Label(frame, text='Measured Current:', font=('Arial', 12))
        self.lbl_measure_title.pack(side='left', padx=5)
        self.lbl_measure_val = ttk.Label(frame, text='-- A', font=('Consolas', 16, 'bold'),
                                         foreground='blue')
        self.lbl_measure_val.pack(side='left', padx=5)
        ttk.Button(frame, text='MEASURE SINGLE POINT',
                   command=self.measure_single_point).pack(side='right', padx=10)

        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=100)
        self.ax.set_title('I-V Curve')
        self.ax.set_xlabel('Voltage (V)')
        self.ax.set_ylabel('Current (A)')
        self.ax.grid(True)
        self.line_iv, = self.ax.plot([], [], '.-', color='blue', linewidth=1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)

    def _update_ui_labels(self):
        mode = self.source_mode_var.get()
        if mode == 'voltage':
            self.lbl_unit_level.config(text='V')
            self.lbl_unit_limit.config(text='A')
            self.lbl_src_range_txt.config(text='(Source V Range)')
            self.lbl_meas_range_txt.config(text='(Measure I Range)')
            self.lbl_measure_title.config(text='Measured Current:')
            self.cb_out_range['values'] = ['Auto', '20e-3', '200e-3', '2', '20', '200']
            self.cb_meas_range['values'] = ['Auto', '1e-8', '1e-7', '1e-6', '10e-6',
                                            '100e-6', '1e-3', '10e-3', '100e-3', '1']
            self.lbl_measure_val.config(text='-- A')
        else:
            self.lbl_unit_level.config(text='A')
            self.lbl_unit_limit.config(text='V')
            self.lbl_src_range_txt.config(text='(Source I Range)')
            self.lbl_meas_range_txt.config(text='(Measure V Range)')
            self.lbl_measure_title.config(text='Measured Voltage:')
            self.cb_out_range['values'] = ['Auto', '1e-8', '1e-7', '1e-6', '10e-6',
                                            '100e-6', '1e-3', '10e-3', '100e-3', '1']
            self.cb_meas_range['values'] = ['Auto', '20e-3', '200e-3', '2', '20', '200']
            self.lbl_measure_val.config(text='-- V')

    def apply_source(self):
        try:
            val = float(self.ent_level.get())
            limit = float(self.ent_limit.get())
            mode = self.source_mode_var.get()
            meas_range_str = self.meas_range_var.get()
            auto_meas = (meas_range_str == 'Auto')

            with self.lock:
                if mode == 'voltage':
                    self.inst.apply_voltage(compliance_current=limit)
                    self.inst.source_voltage = val
                    if self.out_range_var.get() == 'Auto':
                        self.inst.auto_range_source()
                    else:
                        self.inst.source_voltage_range = float(self.out_range_var.get())
                    m_range = 1.05e-4 if auto_meas else float(meas_range_str)
                    self.inst.measure_current(nplc=1, current=m_range, auto_range=auto_meas)
                else:
                    self.inst.apply_current(compliance_voltage=limit)
                    self.inst.source_current = val
                    if self.out_range_var.get() == 'Auto':
                        self.inst.auto_range_source()
                    else:
                        self.inst.source_current_range = float(self.out_range_var.get())
                    m_range = 21.0 if auto_meas else float(meas_range_str)
                    self.inst.measure_voltage(nplc=1, voltage=m_range, auto_range=auto_meas)

            self.log_message(f'Applied: {mode.upper()} Src={val}, Lim={limit}')
        except ValueError:
            messagebox.showerror('Input Error', 'Please enter valid numbers')
        except Exception as e:
            messagebox.showerror('Instrument Error', str(e))

    def toggle_output(self):
        with self.lock:
            time.sleep(0.1)
            try:
                if self.inst.source_enabled:
                    self.inst.disable_source()
                    self.log_message('Output -> OFF')
                else:
                    self.inst.enable_source()
                    self.log_message('Output -> ON')
            except Exception as e:
                self.log_message(f'Toggle error: {e}')
                try:
                    self.inst.adapter.connection.clear()
                except Exception:
                    pass
        self._refresh_status()

    def measure_single_point(self):
        try:
            is_on = False
            with self.lock:
                try:
                    is_on = self.inst.source_enabled
                except Exception:
                    pass
            if not is_on:
                messagebox.showwarning('Measure', 'Please turn Output ON first.')
                return
            mode = self.source_mode_var.get()
            with self.lock:
                if mode == 'voltage':
                    src = self.inst.source_voltage
                    meas = self.inst.current
                    self.lbl_measure_val.config(text=f'Src: {src:.4f} V  |  Meas: {meas:.4e} A')
                else:
                    src = self.inst.source_current
                    meas = self.inst.voltage
                    self.lbl_measure_val.config(text=f'Src: {src:.4e} A  |  Meas: {meas:.4f} V')
        except Exception as e:
            self.log_message(f'Measure error: {e}')

    def set_terminals(self, term):
        with self.lock:
            try:
                if term == 'FRON':
                    self.inst.use_front_terminals()
                    self.log_message('Terminals -> Front')
                else:
                    self.inst.use_rear_terminals()
                    self.log_message('Terminals -> Rear')
            except Exception as e:
                self.log_message(f'Terminal error: {e}')

    def set_wiring(self):
        state = 'ON' if self.wire_var.get() == 4 else 'OFF'
        with self.lock:
            try:
                self.inst.write(f':SENS:VOLT:RSEN {state}')
                self.inst.write(f':SENS:RES:RSEN {state}')
                self.log_message(f'Sensing -> {self.wire_var.get()}-wire')
            except Exception as e:
                self.log_message(f'Wiring error: {e}')

    def reset_instrument(self):
        with self.lock:
            try:
                self.inst.reset()
                self.inst.apply_voltage()
                self.log_message('Instrument hard reset.')
            except Exception as e:
                self.log_message(f'Reset error: {e}')
        self._refresh_status()

    def start_ramp(self):
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid ramp parameters')
            return
        self.log_message(f'Starting ramp -> {target}...')
        self.stop_event.clear()
        self.btn_stop_ramp.config(state='normal')
        self.btn_start_ramp.config(state='disabled')
        self.data_x = []
        self.data_y = []
        self.ax.relim()
        self.ax.autoscale_view()
        threading.Thread(target=self._run_ramp_thread,
                         args=(target, step, time_step), daemon=True).start()

    def stop_ramp(self):
        self.stop_event.set()
        self.log_message('Ramp abort requested.')

    def _ramp_callback(self, meas_v, meas_i):
        if self.source_mode_var.get() == 'voltage':
            self.data_x.append(meas_v)
            self.data_y.append(meas_i)
        else:
            self.data_x.append(meas_i)
            self.data_y.append(meas_v)
        self.after(1, self._update_graph)
        return self.stop_event.is_set()

    def _update_graph(self):
        mode = self.source_mode_var.get()
        self.line_iv.set_data(self.data_x, self.data_y)
        if mode == 'voltage':
            self.ax.set_xlabel('Voltage (V)')
            self.ax.set_ylabel('Current (A)')
            self.ax.set_title('I-V Curve (Source: V)')
            if self.data_y:
                self.lbl_measure_val.config(text=f'{self.data_y[-1]:.4e} A')
        else:
            self.ax.set_xlabel('Current (A)')
            self.ax.set_ylabel('Voltage (V)')
            self.ax.set_title('V-I Curve (Source: I)')
            if self.data_y:
                self.lbl_measure_val.config(text=f'{self.data_y[-1]:.4f} V')
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def _run_ramp_thread(self, target, step, time_step):
        try:
            with self.lock:
                self.inst.enable_source()
            mode = self.source_mode_var.get()
            if mode == 'voltage':
                self.inst.voltage_ramping_with_monitor(target, step, time_step,
                                                       callback=self._ramp_callback)
            else:
                self.inst.current_ramping_with_monitor(target, step, time_step,
                                                       callback=self._ramp_callback)
            self.log_message('Ramp completed.' if not self.stop_event.is_set()
                             else 'Ramp aborted.')
        except Exception as e:
            self.log_message(f'Ramp error: {e}')
        finally:
            self.after(1, lambda: self.btn_stop_ramp.config(state='disabled'))
            self.after(1, lambda: self.btn_start_ramp.config(state='normal'))

    def _refresh_status(self):
        if self.lock.acquire(blocking=False):
            try:
                is_on = self.inst.source_enabled
                self.lbl_output.config(text=f'OUTPUT: {"ON" if is_on else "OFF"}',
                                       foreground='green' if is_on else 'red')
                raw_term = self.inst.check_terminals()
                term = raw_term.strip() if raw_term else '--'
                self.lbl_terminals.config(text=f'TERMINALS: {term}')
            except Exception:
                pass
            finally:
                self.lock.release()

    def poll(self):
        self._refresh_status()
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        try:
            with self.lock:
                self.inst.disable_source()
        except Exception:
            pass
        plt.close(self.fig)
        super().cleanup()


# ============================================================
# Keithley 2600 series (2604B) - dual-channel TSP SMU
# ============================================================

class SMUChannelPanel(ttk.Frame):
    """UI for one SMU channel (smua or smub) of a 2600-series instrument."""

    def __init__(self, parent, device_panel, channel_name):
        super().__init__(parent)
        self.device = device_panel
        self.channel_name = channel_name  # 'smua' / 'smub'
        self.chan = None
        self.stop_event = threading.Event()
        self.data_x = []
        self.data_y = []
        self._build_ui()

    @property
    def lock(self):
        return self.device.lock

    def log(self, msg):
        self.device.log_message(f'[{self.channel_name.upper()}] {msg}')

    def attach(self, inst):
        self.chan = getattr(inst, self.channel_name)

    def set_output_label(self, on):
        self.lbl_output.config(text=f'OUTPUT: {"ON" if on else "OFF"}',
                               foreground='green' if on else 'red')

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        self.lbl_output = ttk.Label(top, text='OUTPUT: OFF', foreground='red',
                                    font=('Arial', 12, 'bold'))
        self.lbl_output.pack(side='left', padx=10)
        self.lbl_measure_val = ttk.Label(top, text='--', font=('Consolas', 13, 'bold'),
                                         foreground='blue')
        self.lbl_measure_val.pack(side='left', padx=20)
        ttk.Button(top, text='Toggle Output', command=self.toggle_output).pack(side='right', padx=5)
        ttk.Button(top, text='MEASURE', command=self.measure_once).pack(side='right', padx=5)

        f = ttk.LabelFrame(self, text='Source Configuration')
        f.pack(fill='x', padx=10, pady=5)

        ttk.Label(f, text='Source Mode:').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.source_mode_var = tk.StringVar(value='voltage')
        mf = ttk.Frame(f)
        mf.grid(row=0, column=1, columnspan=2, sticky='w')
        ttk.Radiobutton(mf, text='Voltage', variable=self.source_mode_var, value='voltage',
                        command=self._update_ui_labels).pack(side='left')
        ttk.Radiobutton(mf, text='Current', variable=self.source_mode_var, value='current',
                        command=self._update_ui_labels).pack(side='left')

        ttk.Label(f, text='Source Level:').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.ent_level = ttk.Entry(f, width=15)
        self.ent_level.insert(0, '0.0')
        self.ent_level.grid(row=1, column=1, padx=5, sticky='w')
        self.lbl_unit_level = ttk.Label(f, text='V')
        self.lbl_unit_level.grid(row=1, column=2, sticky='w')

        ttk.Label(f, text='Limit (Compliance):').grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.ent_limit = ttk.Entry(f, width=15)
        self.ent_limit.insert(0, '0.01')
        self.ent_limit.grid(row=2, column=1, padx=5, sticky='w')
        self.lbl_unit_limit = ttk.Label(f, text='A')
        self.lbl_unit_limit.grid(row=2, column=2, sticky='w')

        ttk.Button(f, text='APPLY CONFIGURATION',
                   command=self.apply_source).grid(row=3, column=0, columnspan=3, pady=10)

        rf = ttk.LabelFrame(self, text='Linear Ramp (abortable, live plot)')
        rf.pack(fill='x', padx=10, pady=5)
        ttk.Label(rf, text='Target:').grid(row=0, column=0, padx=5)
        self.ent_ramp_target = ttk.Entry(rf, width=10)
        self.ent_ramp_target.insert(0, '1.0')
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        ttk.Label(rf, text='Step Size:').grid(row=0, column=2, padx=5)
        self.ent_ramp_step = ttk.Entry(rf, width=10)
        self.ent_ramp_step.insert(0, '0.1')
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        ttk.Label(rf, text='Time/Step (s):').grid(row=0, column=4, padx=5)
        self.ent_ramp_time = ttk.Entry(rf, width=10)
        self.ent_ramp_time.insert(0, '0.1')
        self.ent_ramp_time.grid(row=0, column=5, padx=5)
        self.btn_start_ramp = ttk.Button(rf, text='Start Ramp', command=self.start_ramp)
        self.btn_start_ramp.grid(row=1, column=1, pady=10)
        self.btn_stop_ramp = ttk.Button(rf, text='ABORT', command=self.stop_ramp,
                                        state='disabled')
        self.btn_stop_ramp.grid(row=1, column=3, pady=10)

        self.fig, self.ax = plt.subplots(figsize=(5, 2.5), dpi=100)
        self.ax.set_title(f'I-V Curve ({self.channel_name.upper()})')
        self.ax.set_xlabel('Voltage (V)')
        self.ax.set_ylabel('Current (A)')
        self.ax.grid(True)
        self.line_iv, = self.ax.plot([], [], '.-', color='blue', linewidth=1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=5)

    def _update_ui_labels(self):
        if self.source_mode_var.get() == 'voltage':
            self.lbl_unit_level.config(text='V')
            self.lbl_unit_limit.config(text='A')
        else:
            self.lbl_unit_level.config(text='A')
            self.lbl_unit_limit.config(text='V')

    def apply_source(self):
        if not self.chan:
            return
        try:
            val = float(self.ent_level.get())
            limit = float(self.ent_limit.get())
            mode = self.source_mode_var.get()
            with self.lock:
                if mode == 'voltage':
                    self.chan.configure_voltage_source(voltage=val, current_limit=limit)
                else:
                    self.chan.configure_current_source(current=val, voltage_limit=limit)
            self.log(f'Applied: {mode.upper()} Src={val}, Lim={limit}')
        except ValueError:
            messagebox.showerror('Input Error', 'Please enter valid numbers')
        except Exception as e:
            messagebox.showerror('Instrument Error', str(e))

    def toggle_output(self):
        if not self.chan:
            return
        with self.lock:
            try:
                if self.chan.is_output_on():
                    self.chan.output_off()
                    self.log('Output -> OFF')
                else:
                    self.chan.output_on()
                    self.log('Output -> ON')
            except Exception as e:
                self.log(f'Toggle error: {e}')

    def measure_once(self):
        if not self.chan:
            return
        try:
            with self.lock:
                meas_v = self.chan.measure__voltage()
                meas_i = self.chan.measure__current()
            self.lbl_measure_val.config(
                text=f'{meas_v:.4f} V  |  {meas_i:.4e} A')
            self.log(f'Reading: {meas_v:.4f} V | {meas_i:.4e} A')
        except Exception as e:
            self.log(f'Measure error: {e}')

    def start_ramp(self):
        if not self.chan:
            return
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid ramp parameters')
            return
        self.log(f'Starting ramp -> {target}...')
        self.stop_event.clear()
        self.btn_stop_ramp.config(state='normal')
        self.btn_start_ramp.config(state='disabled')
        self.data_x = []
        self.data_y = []
        threading.Thread(target=self._run_ramp_thread,
                         args=(target, step, time_step), daemon=True).start()

    def stop_ramp(self):
        self.stop_event.set()
        self.log('Ramp abort requested.')

    def _run_ramp_thread(self, target, step, time_step):
        try:
            mode = self.source_mode_var.get()
            with self.lock:
                start_val = (self.chan.measure__voltage() if mode == 'voltage'
                             else self.chan.measure__current())
                self.chan.output_on()
            if step == 0:
                step = 1e-3
            num_steps = max(2, int(abs(target - start_val) / abs(step)) + 1)
            for val in np.linspace(start_val, target, num_steps):
                if self.stop_event.is_set():
                    break
                with self.lock:
                    if mode == 'voltage':
                        self.chan._w(f'source.levelv = {val}')
                    else:
                        self.chan._w(f'source.leveli = {val}')
                    time.sleep(time_step)
                    meas_v = self.chan.measure__voltage()
                    meas_i = self.chan.measure__current()
                if mode == 'voltage':
                    self.data_x.append(meas_v)
                    self.data_y.append(meas_i)
                else:
                    self.data_x.append(meas_i)
                    self.data_y.append(meas_v)
                self.after(1, self._update_graph)
            self.log('Ramp completed/stopped.')
        except Exception as e:
            self.log(f'Ramp error: {e}')
        finally:
            self.after(1, lambda: self.btn_stop_ramp.config(state='disabled'))
            self.after(1, lambda: self.btn_start_ramp.config(state='normal'))

    def _update_graph(self):
        mode = self.source_mode_var.get()
        self.line_iv.set_data(self.data_x, self.data_y)
        if mode == 'voltage':
            self.ax.set_xlabel('Voltage (V)')
            self.ax.set_ylabel('Current (A)')
        else:
            self.ax.set_xlabel('Current (A)')
            self.ax.set_ylabel('Voltage (V)')
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()


class Panel2600(KeithleyPanel):
    """Dual-SMU panel for Keithley 2600-series instruments (e.g. 2604B)."""

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        ttk.Label(top, text='Dual-channel SMU (TSP)', font=('Arial', 10)).pack(side='left', padx=10)
        ttk.Button(top, text='Hard Reset', command=self.reset_instrument).pack(side='right', padx=5)

        self.smu_notebook = ttk.Notebook(self)
        self.smu_notebook.pack(fill='both', expand=True, padx=10, pady=5)
        self.smua_ui = SMUChannelPanel(self.smu_notebook, self, 'smua')
        self.smu_notebook.add(self.smua_ui, text='SMU A')
        self.smub_ui = SMUChannelPanel(self.smu_notebook, self, 'smub')
        self.smu_notebook.add(self.smub_ui, text='SMU B')
        self.smua_ui.attach(self.inst)
        self.smub_ui.attach(self.inst)

    def reset_instrument(self):
        with self.lock:
            try:
                self.inst.reset()
                self.log_message('Instrument hard reset.')
            except Exception as e:
                self.log_message(f'Reset error: {e}')

    def poll(self):
        if self.inst and self.lock.acquire(blocking=False):
            try:
                self.smua_ui.set_output_label(self.inst.smua.is_output_on())
                self.smub_ui.set_output_label(self.inst.smub.is_output_on())
            except Exception:
                pass
            finally:
                self.lock.release()
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        self.smua_ui.stop_event.set()
        self.smub_ui.stop_event.set()
        for ui in (self.smua_ui, self.smub_ui):
            try:
                with self.lock:
                    ui.chan.output_off()
            except Exception:
                pass
            plt.close(ui.fig)
        try:
            self.inst.close()
        except Exception:
            pass


# ============================================================
# SRS SR830 / SR860 - Lock-in amplifiers
# ============================================================

class PanelSRS(KeithleyPanel):
    """Shared lock-in panel; subclasses set is_sr830."""

    is_sr830 = True

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=5, pady=5)
        model = 'SR830' if self.is_sr830 else 'SR860'
        ttk.Label(top, text=model, font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        ttk.Button(top, text='Refresh Settings',
                   command=self.refresh_settings).pack(side='left', padx=20)
        ttk.Button(top, text='Auto Phase', command=self._auto_phase).pack(side='left', padx=5)

        meas = ttk.LabelFrame(self, text='Measurements')
        meas.pack(fill='x', padx=5, pady=5)
        btn_frame = ttk.Frame(meas)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text='MEASURE SNAP',
                   command=self.measure_direct).pack(side='left', padx=5)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text='Auto-Update',
                        variable=self.auto_var).pack(side='left', padx=10)

        grid = ttk.Frame(meas)
        grid.pack(fill='x', padx=5, pady=5)
        self.vars_meas = {k: tk.StringVar(value='--') for k in ('X', 'Y', 'R', 'Theta')}
        for i, (label, var) in enumerate(self.vars_meas.items()):
            ttk.Label(grid, text=f'{label}:', font=('Arial', 14, 'bold')).grid(
                row=0, column=i * 2, padx=10)
            ttk.Label(grid, textvariable=var, font=('Arial', 14, 'bold'),
                      foreground='#0033cc').grid(row=0, column=i * 2 + 1, padx=10)

        self.controls = ttk.Frame(self)
        self.controls.pack(fill='both', expand=True, padx=5, pady=5)
        for c in range(3):
            self.controls.columnconfigure(c, weight=1)
        self.param_controls = []
        self._build_source_frame()
        self._build_input_frame()
        self._build_gain_frame()
        self._build_aux_section()
        threading.Thread(target=self.startup_sequence, daemon=True).start()

    def _build_source_frame(self):
        f = ttk.LabelFrame(self.controls, text='Source')
        f.grid(row=0, column=0, sticky='nsew', padx=2)
        self.add_combo(f, 'Ref Src', 'reference_source', self.inst.REFERENCE_SOURCES, 0)
        self.add_entry(f, 'Freq (Hz)', 'frequency', 1)
        self.add_entry(f, 'Phase (deg)', 'phase', 2)
        self.add_entry(f, 'Amp (V)', 'sine_voltage', 3)
        if self.is_sr830:
            self.add_entry(f, 'Harmonic', 'harmonic', 4, is_int=True)
        else:
            self.add_entry(f, 'DC Off (V)', 'dc_offset', 4)
            self.add_entry(f, 'Harmonic', 'harmonic', 5, is_int=True)

    def _build_input_frame(self):
        f = ttk.LabelFrame(self.controls, text='Input')
        f.grid(row=0, column=1, sticky='nsew', padx=2)
        self.add_combo(f, 'Config', 'input_config', self.inst.INPUT_CONFIGS, 0)
        self.add_combo(f, 'Shield', 'input_grounding', self.inst.INPUT_GROUNDINGS, 1)
        self.add_combo(f, 'Coupling', 'input_coupling', self.inst.INPUT_COUPLINGS, 2)
        self.add_combo(f, 'Filter', 'input_notch_config', self.inst.INPUT_NOTCH_CONFIGS, 3)

    def _build_gain_frame(self):
        f = ttk.LabelFrame(self.controls, text='Gain')
        f.grid(row=0, column=2, sticky='nsew', padx=2)
        self.add_combo(f, 'Sens', 'sensitivity', self.inst.SENSITIVITIES, 0, unit='V')
        self.add_combo(f, 'TC', 'time_constant', self.inst.TIME_CONSTANTS, 1, unit='s')
        self.add_combo(f, 'Slope', 'filter_slope', self.inst.FILTER_SLOPES, 2)
        if self.is_sr830:
            self.add_combo(f, 'Reserve', 'reserve', self.inst.RESERVE_VALUES, 3)

    def _build_aux_section(self):
        f = ttk.LabelFrame(self.controls, text='Auxiliary')
        f.grid(row=1, column=0, columnspan=3, sticky='nsew', padx=2, pady=5)
        self.vars_aux_out = {ch: tk.StringVar(value='0.000') for ch in range(1, 5)}
        self.vars_aux_in = {ch: tk.StringVar(value='--') for ch in range(1, 5)}
        for ch in range(1, 5):
            col = (ch - 1) * 2
            ttk.Label(f, text=f'Out {ch}:').grid(row=0, column=col, sticky='e', padx=2)
            ttk.Entry(f, textvariable=self.vars_aux_out[ch], width=8).grid(
                row=0, column=col + 1, padx=2)
            ttk.Button(f, text='Set', width=4,
                       command=lambda c=ch: self._set_aux(c)).grid(
                row=1, column=col, columnspan=2, pady=2)
            ttk.Label(f, text=f'In {ch}:').grid(row=0, column=8 + col, sticky='e', padx=2)
            ttk.Label(f, textvariable=self.vars_aux_in[ch], width=10,
                      foreground='#0066cc').grid(row=0, column=9 + col, sticky='w', padx=2)

    def _set_aux(self, ch):
        try:
            val = max(-10.5, min(10.5, float(self.vars_aux_out[ch].get())))
            with self.lock:
                setattr(self.inst, f'aux_out_{ch}', val)
                time.sleep(0.05)
                new = float(getattr(self.inst, f'aux_out_{ch}'))
            self.vars_aux_out[ch].set(f'{new:.4f}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    # --- generic control helpers ---

    def add_entry(self, parent, label, attr, row, is_int=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='e', padx=2)
        var = tk.StringVar(value='...')
        entry = ttk.Entry(parent, textvariable=var, width=10)
        entry.grid(row=row, column=1, padx=2)

        def set_val():
            try:
                val = int(var.get()) if is_int else float(var.get())
                with self.lock:
                    setattr(self.inst, attr, val)
                    time.sleep(0.1)
                    new = getattr(self.inst, attr)
                var.set(str(int(new) if is_int else new))
            except Exception as e:
                messagebox.showerror('Error', str(e))

        ttk.Button(parent, text='Set', command=set_val, width=4).grid(
            row=row, column=2, padx=2)
        entry.bind('<Return>', lambda e: set_val())
        self.param_controls.append({'type': 'entry', 'attr': attr, 'var': var})

    def add_combo(self, parent, label, attr, values, row, unit=''):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='e', padx=2)
        if values and isinstance(values[0], str):
            display = {v: v for v in values}
        else:
            display = {Utility.format_eng(v, unit): v for v in values}
        combo = ttk.Combobox(parent, values=list(display.keys()), state='readonly', width=12)
        combo.grid(row=row, column=1, padx=2)

        def on_select(e):
            try:
                with self.lock:
                    setattr(self.inst, attr, display[combo.get()])
            except Exception as ex:
                messagebox.showerror('Error', str(ex))

        combo.bind('<<ComboboxSelected>>', on_select)
        self.param_controls.append({'type': 'combo', 'attr': attr,
                                    'widget': combo, 'map': display})

    # --- readout / refresh ---

    def measure_direct(self):
        try:
            with self.lock:
                vals = self.inst.snap('X', 'Y', 'R', 'Theta')
                for ch in range(1, 5):
                    try:
                        v = getattr(self.inst, f'aux_in_{ch}')
                        self.vars_aux_in[ch].set(f'{v:.4f} V')
                    except Exception:
                        pass
            self.vars_meas['X'].set(Utility.format_eng(float(vals[0]), 'V'))
            self.vars_meas['Y'].set(Utility.format_eng(float(vals[1]), 'V'))
            self.vars_meas['R'].set(Utility.format_eng(float(vals[2]), 'V'))
            self.vars_meas['Theta'].set(f'{float(vals[3]):.2f} deg')
        except Exception:
            self.vars_meas['X'].set('Err')

    def _auto_phase(self):
        try:
            with self.lock:
                self.inst.auto_phase()
            self.log_message('Auto phase done.')
        except Exception as e:
            self.log_message(f'Auto phase error: {e}')

    def refresh_settings(self):
        threading.Thread(target=self.startup_sequence, daemon=True).start()

    def startup_sequence(self):
        for ctrl in self.param_controls:
            try:
                val = getattr(self.inst, ctrl['attr'])
                if ctrl['type'] == 'entry':
                    fmt = str(val)
                    self.after(0, lambda v=ctrl['var'], x=fmt: v.set(x))
                else:
                    match = val if isinstance(val, str) else None
                    if match is None:
                        best, diff = None, float('inf')
                        for k, v in ctrl['map'].items():
                            try:
                                dd = abs(v - val)
                                if dd < diff:
                                    diff, match = dd, k
                            except Exception:
                                pass
                    self.after(0, lambda w=ctrl['widget'], m=match: w.set(m))
                time.sleep(0.05)
            except Exception:
                pass
        try:
            outs = {ch: float(getattr(self.inst, f'aux_out_{ch}')) for ch in range(1, 5)}
            for ch, v in outs.items():
                self.after(0, lambda c=ch, x=v: self.vars_aux_out[c].set(f'{x:.4f}'))
        except Exception:
            pass

    def poll(self):
        if self.auto_var.get():
            self.measure_direct()
        self.after(1000, self.poll)


class PanelSR830(PanelSRS):
    is_sr830 = True


class PanelSR860(PanelSRS):
    is_sr830 = False


# ============================================================
# Yokogawa GS200 / 7651 - DC sources
# ============================================================

V_RANGES = [10e-3, 100e-3, 1, 10, 30]


class _PanelYoko(KeithleyPanel):
    """Shared Yokogawa source panel; subclasses set is_gs200."""

    is_gs200 = True

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        self.lbl_output = ttk.Label(top, text='OUTPUT: OFF', foreground='red',
                                    font=('Arial', 12, 'bold'))
        self.lbl_output.pack(side='left', padx=15)
        self.lbl_mode = ttk.Label(top, text='MODE: --', font=('Arial', 10))
        self.lbl_mode.pack(side='left', padx=15)
        ttk.Button(top, text='Hard Reset', command=self.reset_instrument).pack(side='right', padx=5)

        nb = ttk.Notebook(self)
        nb.pack(fill='x', padx=10, pady=5)
        manual = ttk.Frame(nb); nb.add(manual, text='Manual Control')
        ramp = ttk.Frame(nb); nb.add(ramp, text='Ramping')
        system = ttk.Frame(nb); nb.add(system, text='Safety')
        self._build_manual(manual)
        self._build_ramp(ramp)
        ttk.Button(system, text='SAFETY ZERO (Level 0 + Output OFF)',
                   command=self.safety_zero).pack(padx=10, pady=10, anchor='w')
        self._build_monitor()
        self._update_ui_labels()

    def _build_manual(self, parent):
        f = ttk.LabelFrame(parent, text='Source Configuration')
        f.pack(fill='x', padx=10, pady=10)

        ttk.Label(f, text='Source Mode:').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.source_mode_var = tk.StringVar(value='voltage')
        mf = ttk.Frame(f)
        mf.grid(row=0, column=1, columnspan=2, sticky='w')
        ttk.Radiobutton(mf, text='Voltage', variable=self.source_mode_var, value='voltage',
                        command=self._update_ui_labels).pack(side='left')
        ttk.Radiobutton(mf, text='Current', variable=self.source_mode_var, value='current',
                        command=self._update_ui_labels).pack(side='left')

        ttk.Label(f, text='Source Range:').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.out_range_var = tk.StringVar(value='Auto')
        self.cb_range = ttk.Combobox(f, textvariable=self.out_range_var, width=15)
        self.cb_range.grid(row=1, column=1, padx=5, sticky='w')

        ttk.Label(f, text='Source Level:').grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.ent_level = ttk.Entry(f, width=15)
        self.ent_level.insert(0, '0.0')
        self.ent_level.grid(row=2, column=1, padx=5, sticky='w')
        self.lbl_unit_level = ttk.Label(f, text='V')
        self.lbl_unit_level.grid(row=2, column=2, sticky='w')

        ttk.Label(f, text='Limit (Compliance):').grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.ent_limit = ttk.Entry(f, width=15)
        self.ent_limit.insert(0, '0.1')
        self.ent_limit.grid(row=3, column=1, padx=5, sticky='w')
        self.lbl_unit_limit = ttk.Label(f, text='A')
        self.lbl_unit_limit.grid(row=3, column=2, sticky='w')

        bf = ttk.Frame(f)
        bf.grid(row=4, column=0, columnspan=4, pady=10)
        ttk.Button(bf, text='APPLY', command=self.apply_source).pack(side='left', padx=10)
        ttk.Button(bf, text='Toggle Output', command=self.toggle_output).pack(side='left', padx=10)
        ttk.Button(bf, text='READ LEVEL', command=self.read_level).pack(side='left', padx=10)

    def _build_ramp(self, parent):
        f = ttk.LabelFrame(parent, text='Linear Sweep (Ramp)')
        f.pack(fill='x', padx=10, pady=10)

        ttk.Label(f, text='Target:').grid(row=0, column=0, padx=5, pady=5)
        self.ent_ramp_target = ttk.Entry(f, width=10)
        self.ent_ramp_target.grid(row=0, column=1, padx=5)
        ttk.Label(f, text='Step Size:').grid(row=0, column=2, padx=5)
        self.ent_ramp_step = ttk.Entry(f, width=10)
        self.ent_ramp_step.insert(0, '0.1')
        self.ent_ramp_step.grid(row=0, column=3, padx=5)
        ttk.Label(f, text='Time/Step (s):').grid(row=0, column=4, padx=5)
        self.ent_ramp_time = ttk.Entry(f, width=10)
        self.ent_ramp_time.insert(0, '0.1')
        self.ent_ramp_time.grid(row=0, column=5, padx=5)

        self.ramp_engine_var = tk.StringVar(value='software')
        ef = ttk.Frame(f)
        ef.grid(row=1, column=0, columnspan=4, pady=(10, 0), sticky='w')
        ttk.Radiobutton(ef, text='Software (abortable, plots level vs time)',
                        variable=self.ramp_engine_var, value='software').pack(side='left', padx=5)
        ttk.Radiobutton(ef, text='Built-in program (smooth)',
                        variable=self.ramp_engine_var, value='builtin').pack(side='left', padx=5)

        self.btn_start_ramp = ttk.Button(f, text='Start Ramp', command=self.start_ramp)
        self.btn_start_ramp.grid(row=2, column=1, pady=10)
        self.btn_stop_ramp = ttk.Button(f, text='ABORT', command=self.stop_ramp, state='disabled')
        self.btn_stop_ramp.grid(row=2, column=3, pady=10)

    def _build_monitor(self):
        frame = ttk.Frame(self)
        frame.pack(fill='x', padx=10, pady=5)
        self.lbl_level = ttk.Label(frame, text='--', font=('Consolas', 16, 'bold'),
                                   foreground='blue')
        self.lbl_level.pack(side='left', padx=15, pady=5)

        self.fig, self.ax = plt.subplots(figsize=(6, 2.5), dpi=100)
        self.ax.set_title('Level vs Time')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Level (V)')
        self.ax.grid(True)
        self.line_lvl, = self.ax.plot([], [], '.-', color='blue', linewidth=1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=5)

    # --- helpers ---

    def _ranges(self):
        if self.source_mode_var.get() == 'voltage':
            return V_RANGES
        return [1e-3, 10e-3, 100e-3, 200e-3] if self.is_gs200 else [1e-3, 10e-3, 100e-3]

    def _update_ui_labels(self):
        mode = self.source_mode_var.get()
        self.lbl_unit_level.config(text='V' if mode == 'voltage' else 'A')
        self.lbl_unit_limit.config(text='A' if mode == 'voltage' else 'V')
        self.cb_range['values'] = ['Auto'] + [str(r) for r in self._ranges()]

    def _pick_auto_range(self, level):
        for r in self._ranges():
            if abs(level) <= r:
                return r
        return self._ranges()[-1]

    def _set_level(self, level):
        if self.is_gs200:
            self.inst.source_level = level
        elif self.source_mode_var.get() == 'voltage':
            self.inst.source_voltage = level
        else:
            self.inst.source_current = level

    def _get_level(self):
        if self.is_gs200:
            return float(self.inst.source_level)
        if self.source_mode_var.get() == 'voltage':
            return float(self.inst.source_voltage)
        return float(self.inst.source_current)

    def _output_is_on(self):
        return bool(self.inst.source_enabled)

    def _output_set(self, on):
        if self.is_gs200:
            self.inst.source_enabled = on
        elif on:
            self.inst.enable_source()
        else:
            self.inst.disable_source()

    def apply_source(self):
        try:
            val = float(self.ent_level.get())
            limit = float(self.ent_limit.get())
            mode = self.source_mode_var.get()
            auto = self.out_range_var.get() == 'Auto'
            src_range = self._pick_auto_range(val) if auto else float(self.out_range_var.get())
            with self.lock:
                if self.is_gs200:
                    self.inst.source_mode = mode
                    self.inst.source_range = src_range
                    if mode == 'voltage':
                        self.inst.current_limit = limit
                    else:
                        self.inst.voltage_limit = limit
                    self.inst.source_level = val
                else:
                    if mode == 'voltage':
                        self.inst.apply_voltage(max_voltage=src_range, compliance_current=limit)
                    else:
                        self.inst.apply_current(max_current=src_range, compliance_voltage=limit)
                    if auto:
                        self.inst.set_level_auto_range(val)  # SA command
                    else:
                        self._set_level(val)
            self.log_message(f'Applied: {mode.upper()} Src={val}, Range={src_range}, Lim={limit}')
        except ValueError:
            messagebox.showerror('Input Error', 'Please enter valid numbers')
        except Exception as e:
            messagebox.showerror('Instrument Error', str(e))

    def read_level(self):
        try:
            with self.lock:
                mode = self.inst.source_mode
                level = self._get_level()
            unit = 'V' if mode == 'voltage' else 'A'
            self.lbl_level.config(text=f'{level:.4e} {unit}')
        except Exception as e:
            self.log_message(f'Read level error: {e}')

    def toggle_output(self):
        with self.lock:
            try:
                on = self._output_is_on()
                self._output_set(not on)
                self.log_message('Output -> ON' if not on else 'Output -> OFF')
            except Exception as e:
                self.log_message(f'Toggle error: {e}')
        self._refresh_status()

    def reset_instrument(self):
        with self.lock:
            try:
                if self.is_gs200:
                    self.inst.reset()
                    self.inst.source_mode = 'voltage'
                else:
                    self.inst.write('RC;E')  # setting init (manual 6.3 (6))
                    self.inst.write('H0;E')  # no header in output data
                self.log_message('Instrument reset.')
            except Exception as e:
                self.log_message(f'Reset error: {e}')

    def start_ramp(self):
        try:
            target = float(self.ent_ramp_target.get())
            step = float(self.ent_ramp_step.get())
            time_step = float(self.ent_ramp_time.get())
        except ValueError:
            messagebox.showerror('Error', 'Invalid ramp parameters')
            return
        engine = self.ramp_engine_var.get()
        self.log_message(f'Starting ramp ({engine}) -> {target}...')
        self.stop_event.clear()
        self.btn_start_ramp.config(state='disabled')
        self.btn_stop_ramp.config(state='normal' if engine == 'software' else 'disabled')
        self.data_x = []
        self.data_y = []
        self.ax.relim()
        self.ax.autoscale_view()
        threading.Thread(target=self._run_ramp_thread,
                         args=(target, step, time_step, engine), daemon=True).start()

    def stop_ramp(self):
        self.stop_event.set()
        # 7651 built-in program sweep can be halted mid-flight with RU0
        if not self.is_gs200 and self.inst and self.ramp_engine_var.get() == 'builtin':
            try:
                with self.lock:
                    self.inst.halt_program()
            except Exception:
                pass
        self.log_message('Ramp abort requested.')

    def _ramp_callback(self, elapsed, level):
        self.data_x.append(elapsed)
        self.data_y.append(level)
        self.after(1, self._update_graph)
        return self.stop_event.is_set()

    def _update_graph(self):
        unit = 'V' if self.source_mode_var.get() == 'voltage' else 'A'
        self.line_lvl.set_data(self.data_x, self.data_y)
        self.ax.set_ylabel(f'Level ({unit})')
        if self.data_y:
            self.lbl_level.config(text=f'{self.data_y[-1]:.4e} {unit}')
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def _run_ramp_thread(self, target, step, time_step, engine):
        try:
            with self.lock:
                self._output_set(True)
            if engine == 'software':
                # Both drivers share ramping_with_monitor(elapsed, level callback)
                self.inst.ramping_with_monitor(target, step, time_step,
                                               callback=self._ramp_callback)
                self.log_message('Ramp completed.' if not self.stop_event.is_set()
                                 else 'Ramp aborted.')
            else:
                with self.lock:
                    current = self._get_level()
                    n_steps = int(abs(target - current) / abs(step)) if step else 1
                    total_time = max(n_steps * time_step, 0.1)
                    self.inst.trigger_ramp_to_level(target, total_time)
                self.log_message(f'Built-in ramp started ({total_time:.2f}s).')
        except Exception as e:
            self.log_message(f'Ramp error: {e}')
        finally:
            self.after(0, lambda: self.btn_stop_ramp.config(state='disabled'))
            self.after(0, lambda: self.btn_start_ramp.config(state='normal'))

    def safety_zero(self):
        with self.lock:
            try:
                self._set_level(0)
                self._output_set(False)
                self.log_message('SAFETY ZERO: level 0, output OFF.')
            except Exception as e:
                self.log_message(f'Safety zero error: {e}')

    def _refresh_status(self):
        if self.inst and self.lock.acquire(blocking=False):
            try:
                on = self._output_is_on()
                self.lbl_output.config(text=f'OUTPUT: {"ON" if on else "OFF"}',
                                       foreground='green' if on else 'red')
                mode = self.inst.source_mode
                self.lbl_mode.config(text=f'MODE: {mode.upper()}')
            except Exception:
                pass
            finally:
                self.lock.release()

    def poll(self):
        self._refresh_status()
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        try:
            with self.lock:
                self._set_level(0)
                self._output_set(False)
        except Exception:
            pass
        plt.close(self.fig)
        super().cleanup()


class PanelGS200(_PanelYoko):
    is_gs200 = True


class Panel7651(_PanelYoko):
    is_gs200 = False

    


# ============================================================
# Zurich Instruments MFLI - via LabOne data server (not VISA)
# ============================================================

class PanelMFLI(KeithleyPanel):
    """MFLI lock-in panel driven through the LabOne data server."""

    def build_ui(self):
        cfg = ttk.LabelFrame(self, text='Output Signal')
        cfg.pack(fill='x', padx=10, pady=10)

        ttk.Label(cfg, text='Frequency (Hz):').grid(row=0, column=0, padx=5, pady=3, sticky='e')
        self.ent_freq = ttk.Entry(cfg, width=12); self.ent_freq.insert(0, '1000')
        self.ent_freq.grid(row=0, column=1, sticky='w')
        ttk.Label(cfg, text='Amplitude (Vrms):').grid(row=1, column=0, padx=5, pady=3, sticky='e')
        self.ent_ampl = ttk.Entry(cfg, width=12); self.ent_ampl.insert(0, '0.1')
        self.ent_ampl.grid(row=1, column=1, sticky='w')
        ttk.Label(cfg, text='DC Offset (V):').grid(row=2, column=0, padx=5, pady=3, sticky='e')
        self.ent_offset = ttk.Entry(cfg, width=12); self.ent_offset.insert(0, '0')
        self.ent_offset.grid(row=2, column=1, sticky='w')
        ttk.Label(cfg, text='Time Const (s):').grid(row=3, column=0, padx=5, pady=3, sticky='e')
        self.ent_tc = ttk.Entry(cfg, width=12); self.ent_tc.insert(0, '0.1')
        self.ent_tc.grid(row=3, column=1, sticky='w')

        bf = ttk.Frame(cfg)
        bf.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(bf, text='APPLY', command=self.apply_settings).pack(side='left', padx=10)
        self.btn_output = ttk.Button(bf, text='Output: ?', command=self.toggle_output)
        self.btn_output.pack(side='left', padx=10)

        meas = ttk.LabelFrame(self, text='Demodulator Readout')
        meas.pack(fill='x', padx=10, pady=5)
        self.lbl_xy = ttk.Label(meas, text='X: --   Y: --   R: --',
                                font=('Consolas', 14, 'bold'), foreground='blue')
        self.lbl_xy.pack(side='left', padx=15, pady=8)
        self.btn_read = ttk.Button(meas, text='READ X/Y', command=self.read_demod)
        self.btn_read.pack(side='right', padx=10)
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(meas, text='Auto refresh (2 s)',
                        variable=self.auto_var).pack(side='right', padx=10)

        self._output_on = False

    def apply_settings(self):
        try:
            with self.lock:
                self.inst.frequency = float(self.ent_freq.get())
                self.inst.sine_amplitude = float(self.ent_ampl.get())
                self.inst.dc_offset = float(self.ent_offset.get())
                self.inst.timeconstant = float(self.ent_tc.get())
            self.log_message('Output signal settings applied.')
        except Exception as e:
            messagebox.showerror('MFLI Error', str(e))

    def toggle_output(self):
        try:
            with self.lock:
                self._output_on = not self._output_on
                self.inst.turn_voltage(self._output_on)
            self.btn_output.config(
                text=f'Output: {"ON" if self._output_on else "OFF"}')
            self.log_message(f'Output -> {"ON" if self._output_on else "OFF"}')
        except Exception as e:
            self.log_message(f'Output toggle error: {e}')

    def read_demod(self):
        try:
            with self.lock:
                xy = self.inst.read_demod()
            x, y = float(xy[0]), float(xy[1])
            r = float(np.hypot(x, y))
            self.lbl_xy.config(text=f'X: {x:.4e}   Y: {y:.4e}   R: {r:.4e}')
        except Exception as e:
            self.lbl_xy.config(text='X: Err   Y: Err   R: Err')
            self.log_message(f'Read error: {e}')

    def poll(self):
        if self.auto_var.get():
            self.read_demod()
        self.after(2000, self.poll)

    def cleanup(self):
        self.stop_event.set()
        try:
            with self.lock:
                self.inst.turn_voltage(False)
        except Exception:
            pass


# ============================================================
# Main application
# ============================================================

VISA_DRIVERS = {
    '2000': Keithley2000,
    '2182': Keithley2182,
    '2450': Keithley2450,
    '6221': Keithley6221,
    '2600': Keithley2604B,
    'sr830': SR830,
    'sr860': SR860,
    'gs200': YokogawaGS200,
    'yoko7651': Yokogawa7651,
}

VISA_PANELS = {
    '2000': Panel2000,
    '2182': Panel2182,
    '2450': Panel2450,
    '6221': Panel6221,
    '2600': Panel2600,
    'sr830': PanelSR830,
    'sr860': PanelSR860,
    'gs200': PanelGS200,
    'yoko7651': Panel7651,
}

# Order shown in the manual-connect model dropdown (no mfli: not VISA)
MANUAL_MODELS = ['2450', '2000', '2182', '6221', '2600',
                 'sr830', 'sr860', 'gs200', 'yoko7651']


def _tweak_connection(inst, key):
    """Per-model VISA connection tweaks, same as the individual GUIs use."""
    if not hasattr(inst, 'adapter'):
        return
    conn = inst.adapter.connection
    conn.timeout = 10000
    if key in ('2182', 'yoko7651'):
        return  # 2182: CR termination default; 7651: legacy protocol, no terminations
    conn.read_termination = '\n'
    conn.write_termination = '\n'
    if key == 'gs200':
        try:
            conn.clear()
        except Exception:
            pass


class InstrumentAllInOneApp(tk.Tk):
    """Scans VISA + LabOne and hosts one tab per connected instrument."""

    def __init__(self):
        super().__init__()
        self.title('Instrument All-In-One Controller')
        self.geometry('1250x900')
        self.open_addresses = {}

        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=10, pady=5)
        self.btn_scan = ttk.Button(toolbar, text='Scan VISA Instruments',
                                   command=self.start_scan)
        self.btn_scan.pack(side='left', padx=5)
        self.btn_labone = ttk.Button(toolbar, text='Scan LabOne (MFLI)',
                                     command=self.scan_labone)
        self.btn_labone.pack(side='left', padx=5)
        self.btn_close_tab = ttk.Button(toolbar, text='Close Current Tab',
                                        command=self.close_current_tab)
        self.btn_close_tab.pack(side='left', padx=5)

        # --- Manual connection (for instruments auto-detection misses) ---
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        ttk.Label(toolbar, text='Manual:').pack(side='left', padx=5)
        self.addr_combo = ttk.Combobox(toolbar, width=30)
        self.addr_combo.pack(side='left', padx=5)
        ttk.Label(toolbar, text='Model:').pack(side='left', padx=5)
        self.model_var = tk.StringVar(value='2450')
        ttk.Combobox(toolbar, textvariable=self.model_var,
                     values=MANUAL_MODELS, state='readonly',
                     width=8).pack(side='left', padx=5)
        self.btn_manual = ttk.Button(toolbar, text='Connect Manually',
                                     command=self.manual_connect)
        self.btn_manual.pack(side='left', padx=5)

        self.lbl_status = ttk.Label(toolbar, text='', font=('Arial', 10))
        self.lbl_status.pack(side='right', padx=10)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        log_frame = ttk.LabelFrame(self, text='Scan Log')
        log_frame.pack(fill='x', padx=10, pady=5)
        self.main_log = scrolledtext.ScrolledText(log_frame, height=6, state='disabled',
                                                  font=('Consolas', 9))
        self.main_log.pack(fill='both', expand=True, padx=5, pady=5)

        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.start_scan()

    # --- VISA scanning ---

    def start_scan(self):
        self.btn_scan.config(state='disabled')
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        self._log_main('Scanning VISA resources...')
        found = []
        scanned = []
        try:
            rm = pyvisa.ResourceManager()
            for addr in rm.list_resources():
                scanned.append(addr)
                try:
                    res = rm.open_resource(addr, open_timeout=2000)
                    res.timeout = 2000
                    idn = res.query('*IDN?').strip()
                    res.close()
                except Exception:
                    self._log_main(f'{addr}: no *IDN? answer - use Manual connect')
                    continue
                key = classify_instrument(idn)
                if key == 'unknown':
                    self._log_main(f'{addr}: unrecognized model ({idn}) - skipped')
                elif key:
                    found.append((addr, key))
                    self._log_main(f'{addr}: {DISPLAY_NAME[key]}')
                else:
                    self._log_main(f'{addr}: {idn.split(",")[0]} (unsupported vendor) - skipped')
        except Exception as e:
            self._log_main(f'Scan error: {e}')

        for addr, key in found:
            self.after(0, self.create_tab, addr, key)
        if not found:
            self._log_main('No supported instruments found. Use Manual connect if needed.')
        self.after(0, self._update_addr_combo, scanned)
        self.after(0, lambda: self.btn_scan.config(state='normal'))

    def _log_main(self, msg):
        def append():
            ts = datetime.datetime.now().strftime('%H:%M:%S')
            self.main_log.config(state='normal')
            self.main_log.insert(tk.END, f'[{ts}] {msg}\n')
            self.main_log.see(tk.END)
            self.main_log.config(state='disabled')
        self.after(0, append)

    # --- LabOne scanning (MFLI) ---

    def scan_labone(self):
        if MFLIController is None:
            messagebox.showerror('LabOne Missing',
                                 'zhinst package not installed. Install the LabOne API:\n'
                                 'pip install zhinst')
            return
        dlg = tk.Toplevel(self)
        dlg.title('Connect MFLI via LabOne')
        dlg.grab_set()
        fields = [('Host', 'localhost'), ('Port', '8004'), ('Device', 'MFLI1')]
        entries = {}
        for i, (label, default) in enumerate(fields):
            ttk.Label(dlg, text=f'{label}:').grid(row=i, column=0, padx=5, pady=5, sticky='e')
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=20).grid(row=i, column=1, padx=5)
            entries[label.lower()] = var

        def do_connect():
            host = entries['host'].get().strip()
            port = int(entries['port'].get())
            device = entries['device'].get().strip()
            dlg.destroy()
            threading.Thread(target=self._labone_thread,
                             args=(host, port, device), daemon=True).start()

        ttk.Button(dlg, text='Connect', command=do_connect).grid(
            row=3, column=0, columnspan=2, pady=10)

    def _labone_thread(self, host, port, device):
        self._log_main(f'Connecting LabOne {host}:{port} device {device}...')
        try:
            inst = MFLIController(host=host, port=port, device=device)
            freq = inst.frequency  # verify the device answers
            self.after(0, self._add_mfli_tab, inst, host, port, device, freq)
        except Exception as e:
            self._log_main(f'LabOne connection failed: {e}')

    def _add_mfli_tab(self, inst, host, port, device, freq):
        addr = f'labone://{host}:{port}/{device}'
        if addr in self.open_addresses:
            self._log_main(f'{addr} already open - skipped')
            return
        panel = PanelMFLI(self.notebook, inst, addr)
        self.notebook.add(panel, text=f'MFLI - {device}')
        self.notebook.select(panel)
        self.open_addresses[addr] = panel
        panel.log_message(f'Connected via LabOne ({host}:{port}), frequency={freq:g} Hz')
        self._log_main(f'Opened MFLI {device} at {host}:{port}')
        self.lbl_status.config(text=f'Instruments: {len(self.open_addresses)}')

    # --- tab management ---

    def create_tab(self, addr, key):
        if addr in self.open_addresses:
            self._log_main(f'{addr} already open - skipped')
            return
        try:
            inst = VISA_DRIVERS[key](addr)
            _tweak_connection(inst, key)
        except Exception as e:
            messagebox.showerror('Connection Error',
                                 f'{DISPLAY_NAME[key]} at {addr} failed:\n{e}')
            return

        panel = VISA_PANELS[key](self.notebook, inst, addr)
        short = addr.split('::')[-1] if '::' in addr else addr
        self.notebook.add(panel, text=f'{key} - {short}')
        self.notebook.select(panel)
        self.open_addresses[addr] = panel
        panel.log_message(f'Connected: {DISPLAY_NAME[key]} at {addr}')
        self._log_main(f'Opened {DISPLAY_NAME[key]} at {addr}')
        self.lbl_status.config(text=f'Instruments: {len(self.open_addresses)}')

    def manual_connect(self):
        # Connect to a user-specified address and model, bypassing auto-detection.
        addr = self.addr_combo.get().strip()
        if not addr:
            messagebox.showerror('Error', 'Enter or select a VISA address first.')
            return
        self.create_tab(addr, self.model_var.get())

    def _update_addr_combo(self, resources):
        # Fill the manual-address combobox with everything the scan saw.
        current = self.addr_combo.get()
        self.addr_combo['values'] = list(resources)
        if not current and resources:
            self.addr_combo.current(0)

    def close_current_tab(self):
        if not self.notebook.tabs():
            return
        tab_id = self.notebook.select()
        panel = self.nametowidget(tab_id)
        if not isinstance(panel, KeithleyPanel):
            return
        if not messagebox.askyesno('Confirm', f'Disconnect {panel.address}?'):
            return
        panel.cleanup()
        self.notebook.forget(tab_id)
        self.open_addresses.pop(panel.address, None)
        self.lbl_status.config(text=f'Instruments: {len(self.open_addresses)}')
        self._log_main(f'Closed {panel.address}')

    def on_close(self):
        for tab_id in self.notebook.tabs():
            panel = self.nametowidget(tab_id)
            if isinstance(panel, KeithleyPanel):
                try:
                    panel.cleanup()
                except Exception:
                    pass
        self.destroy()


def main():
    app = InstrumentAllInOneApp()
    app.mainloop()


if __name__ == '__main__':
    main()

