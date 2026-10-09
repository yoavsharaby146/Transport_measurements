"""
Keithley All-In-One Controller
==============================

One GUI for every Keithley on the bench. Press "Scan for Keithleys" and the
program queries *IDN? on every VISA resource, then opens a model-appropriate
panel for each connected Keithley:

  Model 2000        Multimeter (V / I / R / T / freq readout)
  Model 2182/2182A  Nanovoltmeter (voltage / temperature, 2 channels)
  Model 2450        SourceMeter (source & measure, ramp, terminals)
  Model 6221        AC/DC current source (DC level, ramp, waveforms)
  2600 series       Dual-channel TSP SMU, e.g. 2604B (SMU A / SMU B)

Run:
    python "Instrument control/KeithleyAllInOne_GUI.py"

Written for the QLMG research instrument stack. Drivers come from
../Instruments/ and are used unmodified.
"""

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
sys.path.append(instruments_path)

from Instruments.keithley2000_with_add_ons import Keithley2000
from Instruments.keithley2182_with_add_ons import Keithley2182
from Instruments.keithley2450_with_add_ons import Keithley2450
from Instruments.keithley2604B import Keithley2604B
from Instruments.keithley6221_with_add_ons import Keithley6221


# ============================================================
# Model detection
# ============================================================

def classify_keithley(idn):
    """Return a registry key for a Keithley *IDN? string, else None."""
    if not idn or 'KEITHLEY' not in idn.upper():
        return None
    m = re.search(r'MODEL\s*([0-9]+[A-Z]*)', idn, re.IGNORECASE)
    model = m.group(1).upper() if m else ''
    digits = re.sub(r'\D', '', model)
    if digits in ('2600', '2601', '2602', '2603', '2604', '2605', '2606'):
        return '2600'
    if digits in ('2000', '2182', '2450', '6221'):
        return digits
    return 'unknown'


DISPLAY_NAME = {
    '2000': 'Keithley 2000 Multimeter',
    '2182': 'Keithley 2182 Nanovoltmeter',
    '2450': 'Keithley 2450 SourceMeter',
    '6221': 'Keithley 6221 Current Source',
    '2600': 'Keithley 2600-series SMU',
}


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
        wave = ttk.Frame(nb); nb.add(wave, text='Waveform')
        self._build_dc(dc)
        self._build_ramp(ramp)
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
# Main application
# ============================================================

DRIVERS = {
    '2000': Keithley2000,
    '2182': Keithley2182,
    '2450': Keithley2450,
    '6221': Keithley6221,
    '2600': Keithley2604B,
}

PANELS = {
    '2000': Panel2000,
    '2182': Panel2182,
    '2450': Panel2450,
    '6221': Panel6221,
    '2600': Panel2600,
}


class KeithleyAllInOneApp(tk.Tk):
    """Scans for Keithleys and hosts one tab per connected instrument."""

    def __init__(self):
        super().__init__()
        self.title('Keithley All-In-One Controller')
        self.geometry('1250x900')
        self.open_addresses = {}

        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=10, pady=5)
        self.btn_scan = ttk.Button(toolbar, text='Scan for Keithleys', command=self.start_scan)
        self.btn_scan.pack(side='left', padx=5)
        self.btn_close_tab = ttk.Button(toolbar, text='Close Current Tab',
                                        command=self.close_current_tab)
        self.btn_close_tab.pack(side='left', padx=5)
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

    # --- scanning ---

    def start_scan(self):
        self.btn_scan.config(state='disabled')
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        self._log_main('Scanning VISA resources...')
        found = []
        try:
            rm = pyvisa.ResourceManager()
            for addr in rm.list_resources():
                try:
                    res = rm.open_resource(addr, open_timeout=1500)
                    res.timeout = 1500
                    idn = res.query('*IDN?').strip()
                    res.close()
                except Exception:
                    continue
                key = classify_keithley(idn)
                if key == 'unknown':
                    self._log_main(f'{addr}: Keithley with unrecognized model ({idn}) - skipped')
                elif key:
                    found.append((addr, key))
                    self._log_main(f'{addr}: {DISPLAY_NAME[key]}')
                else:
                    self._log_main(f'{addr}: {idn.split(",")[0]} (not Keithley) - skipped')
        except Exception as e:
            self._log_main(f'Scan error: {e}')

        for addr, key in found:
            self.after(0, self.create_tab, addr, key)
        if not found:
            self._log_main('No Keithley instruments found.')
        self.after(0, lambda: self.btn_scan.config(state='normal'))

    def _log_main(self, msg):
        def append():
            ts = datetime.datetime.now().strftime('%H:%M:%S')
            self.main_log.config(state='normal')
            self.main_log.insert(tk.END, f'[{ts}] {msg}\n')
            self.main_log.see(tk.END)
            self.main_log.config(state='disabled')
        self.after(0, append)

    # --- tab management ---

    def create_tab(self, addr, key):
        if addr in self.open_addresses:
            self._log_main(f'{addr} already open - skipped')
            return
        try:
            inst = DRIVERS[key](addr)
            # Same connection tweaks the individual GUIs use
            if key != '2600' and hasattr(inst, 'adapter'):
                inst.adapter.connection.timeout = 10000
                if key != '2182':  # 2182 driver defaults to CR termination
                    inst.adapter.connection.read_termination = '\n'
                    inst.adapter.connection.write_termination = '\n'
        except Exception as e:
            messagebox.showerror('Connection Error', f'{DISPLAY_NAME[key]} at {addr} failed:\n{e}')
            return

        panel = PANELS[key](self.notebook, inst, addr)
        short = addr.split('::')[-1] if '::' in addr else addr
        self.notebook.add(panel, text=f'{key} - {short}')
        self.notebook.select(panel)
        self.open_addresses[addr] = panel
        panel.log_message(f'Connected: {DISPLAY_NAME[key]} at {addr}')
        self._log_main(f'Opened {DISPLAY_NAME[key]} at {addr}')
        self.lbl_status.config(text=f'Instruments: {len(self.open_addresses)}')

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
    app = KeithleyAllInOneApp()
    app.mainloop()


if __name__ == '__main__':
    main()
