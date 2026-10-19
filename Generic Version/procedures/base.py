"""
Base module for Generic Version procedures.

Contains common imports, instrument bindings, helper functions,
dynamic column generation, and the GenericProcedure base class with
centralized instrument reading that skips disconnected instruments.

Generic Version: Keithley SMUs (2450 x2, 2604B) + lock-ins
(SRS860 x2, SRS830 x3, MFLI x3) only — no magnet, no cryostat.
"""

import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import time, math, sys
import numpy as np
from scipy.constants import e
from scipy.constants import epsilon_0
from pymeasure.log import console_log
from pymeasure.display.Qt import QtWidgets, QtGui, QtCore
from pymeasure.display.windows.managed_dock_window import ManagedDockWindow

from pymeasure.experiment import Procedure, BooleanParameter
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter

import pyqtgraph as pg
pg.setConfigOption("useOpenGL", True)

import configuration as _cfg
from configuration import read_temperature


# ---------------- Connection helper ----------------

def _is_connected(inst):
    """True if instrument is a real connected instance (not None or 0)."""
    return inst not in (None, 0)


# ---------------- Instrument bindings ----------------

MFLI_1            = getattr(_cfg, "MFLI_1", 0)
MFLI_2            = getattr(_cfg, "MFLI_2", 0)
MFLI_3            = getattr(_cfg, "MFLI_3", 0)
SRS860_1          = getattr(_cfg, "SRS860_1", 0)
SRS860_2          = getattr(_cfg, "SRS860_2", 0)
SRS860_3          = getattr(_cfg, "SRS860_3", 0)
SRS860_4          = getattr(_cfg, "SRS860_4", 0)
SRS830_1          = getattr(_cfg, "SRS830_1", 0)
SRS830_2          = getattr(_cfg, "SRS830_2", 0)
SRS830_3          = getattr(_cfg, "SRS830_3", 0)
Dual_gate         = getattr(_cfg, "Dual_gate", 0)
Gate_1            = getattr(_cfg, "Gate_1", 0)
Gate_2            = getattr(_cfg, "Gate_2", 0)
YokoGS200_1       = getattr(_cfg, "YokoGS200_1", 0)
YokoGS200_2       = getattr(_cfg, "YokoGS200_2", 0)
Yoko7651_1        = getattr(_cfg, "Yoko7651_1", 0)
Yoko7651_2        = getattr(_cfg, "Yoko7651_2", 0)
K6221             = getattr(_cfg, "K6221", 0)

# RMS -> (peak) amplitude conversion for the Keithley 6221 waveform.
# The instrument's :SOUR:WAVE:AMPL is a PEAK value; the user works in RMS.
RMS_TO_PEAK = 1.4142

import os
save_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Generic Measurements")


# ---------------- Static column templates (backward compat + fallback) ----------------

BASE_DATA_COLUMNS = [
    'time(s)',
    'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
    'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
    'YokoGS200_1_voltage(V)', 'YokoGS200_2_voltage(V)',
    'Yoko7651_1_voltage(V)', 'Yoko7651_2_voltage(V)',
    'K6221_AC_amplitude_RMS(A)',
]

LOCKIN_VOLTAGE_COLUMNS = [
    'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
    'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
    'Lockin_Voltage_SRS830_3_X(V)', 'Lockin_Voltage_SRS830_3_Y(V)',
    'Lockin_Voltage_SRS860_1_X(V)', 'Lockin_Voltage_SRS860_1_Y(V)',
    'Lockin_Voltage_SRS860_2_X(V)', 'Lockin_Voltage_SRS860_2_Y(V)',
    'Lockin_Voltage_SRS860_3_X(V)', 'Lockin_Voltage_SRS860_3_Y(V)',
    'Lockin_Voltage_SRS860_4_X(V)', 'Lockin_Voltage_SRS860_4_Y(V)',
    'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
    'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
    'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
]

LOCKIN_CURRENT_COLUMNS = [
    'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
    'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
    'Lockin_Current_SRS830_3_X(A)', 'Lockin_Current_SRS830_3_Y(A)',
    'Lockin_Current_SRS860_1_X(A)', 'Lockin_Current_SRS860_1_Y(A)',
    'Lockin_Current_SRS860_2_X(A)', 'Lockin_Current_SRS860_2_Y(A)',
    'Lockin_Current_SRS860_3_X(A)', 'Lockin_Current_SRS860_3_Y(A)',
    'Lockin_Current_SRS860_4_X(A)', 'Lockin_Current_SRS860_4_Y(A)',
    'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
    'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
    'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
]

MAGNET_COLUMNS = []  # Generic Version: no magnet


# ---------------- Dynamic column builders ----------------

def _build_smu_columns():
    """SMU columns for connected instruments only."""
    cols = []
    if _is_connected(Dual_gate):
        cols += ['SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)']
    if _is_connected(Gate_1):
        cols += ['Gate_1_voltage(V)', 'Gate_1_Leakage(A)']
    if _is_connected(Gate_2):
        cols += ['Gate_2_voltage(V)', 'Gate_2_Leakage(A)']
    # Yokogawas are source-only: single setpoint column each
    if _is_connected(YokoGS200_1):
        cols += ['YokoGS200_1_voltage(V)']
    if _is_connected(YokoGS200_2):
        cols += ['YokoGS200_2_voltage(V)']
    if _is_connected(Yoko7651_1):
        cols += ['Yoko7651_1_voltage(V)']
    if _is_connected(Yoko7651_2):
        cols += ['Yoko7651_2_voltage(V)']
    if _is_connected(K6221):
        cols += ['K6221_AC_amplitude_RMS(A)']
    return cols


def _build_lockin_columns(kind='voltage'):
    """Lock-in columns for connected instruments only.

    kind: 'voltage' or 'current'
    Column names match the original static lists exactly.
    """
    cols = []
    meas = kind.capitalize()  # 'Voltage' or 'Current'
    unit = '(V)' if kind == 'voltage' else '(A)'

    # Reading order must match _read_lockin_values()
    _lockin_specs = [
        (SRS830_1, 'SRS830_1', None),
        (SRS830_2, 'SRS830_2', None),
        (SRS830_3, 'SRS830_3', None),
        (SRS860_1, 'SRS860_1', None),
        (SRS860_2, 'SRS860_2', None),
        (SRS860_3, 'SRS860_3', None),
        (SRS860_4, 'SRS860_4', None),
        (MFLI_1,   None,       1),
        (MFLI_2,   None,       2),
        (MFLI_3,   None,       3),
    ]
    for inst, srs_name, mfli_num in _lockin_specs:
        if not _is_connected(inst):
            continue
        if srs_name:
            cols += [f'Lockin_{meas}_{srs_name}_X{unit}',
                     f'Lockin_{meas}_{srs_name}_Y{unit}']
        else:
            cols += [f'MFLI_Lockin_{mfli_num}_{meas}_X{unit}',
                     f'MFLI_Lockin_{mfli_num}_{meas}_Y{unit}']
    return cols


def _build_magnet_columns():
    return []  # Generic Version: no magnet


def _build_base_columns():
    """Fixed prefix + dynamic SMU columns."""
    return ['time(s)'] + _build_smu_columns()


def _rebuild_procedure_columns(cls):
    """Rebuild DATA_COLUMNS for a single GenericProcedure subclass."""
    mid = getattr(cls, '_MID_COLUMNS', [])
    kind = getattr(cls, '_LOCKIN_COL_TYPE', 'voltage')
    cls.DATA_COLUMNS = (
        _build_base_columns() + list(mid) +
        _build_lockin_columns(kind) + _build_magnet_columns()
    )
    # Optional hook: let subclasses refresh dynamic Parameters (e.g. the
    # R_aux procedure's aux_source choices) to connected instruments.
    rebuild_params = getattr(cls, '_rebuild_parameters', None)
    if callable(rebuild_params):
        rebuild_params()


def _rebuild_all_columns():
    """Rebuild module-level column lists and all GenericProcedure DATA_COLUMNS.

    Called from _rebind_instruments_from_configuration() after instruments
    are refreshed, so column lists reflect currently-connected hardware.
    """
    global BASE_DATA_COLUMNS, LOCKIN_VOLTAGE_COLUMNS, LOCKIN_CURRENT_COLUMNS, MAGNET_COLUMNS

    BASE_DATA_COLUMNS = _build_base_columns()
    LOCKIN_VOLTAGE_COLUMNS = _build_lockin_columns('voltage')
    LOCKIN_CURRENT_COLUMNS = _build_lockin_columns('current')
    MAGNET_COLUMNS = _build_magnet_columns()

    # Rebuild DATA_COLUMNS on every GenericProcedure subclass found in procedure modules
    for mod in sys.modules.values():
        if mod is None or not hasattr(mod, '__file__') or not mod.__file__:
            continue
        if 'procedures' not in getattr(mod, '__name__', ''):
            continue
        for attr_name in list(mod.__dict__):
            obj = mod.__dict__.get(attr_name)
            if (isinstance(obj, type) and issubclass(obj, GenericProcedure)
                    and obj is not GenericProcedure):
                _rebuild_procedure_columns(obj)

    # Propagate updated column-list globals to submodules that did from .base import *
    _col_names = ['BASE_DATA_COLUMNS', 'LOCKIN_VOLTAGE_COLUMNS',
                  'LOCKIN_CURRENT_COLUMNS', 'MAGNET_COLUMNS']
    for mod in sys.modules.values():
        if mod is None or not hasattr(mod, '__file__') or not mod.__file__:
            continue
        if 'procedures' not in getattr(mod, '__name__', ''):
            continue
        for name in _col_names:
            if name in mod.__dict__:
                mod.__dict__[name] = globals()[name]


# ---------------- Dynamic SMU dropdown builder ----------------

def _connected_smus():
    """Names of connected SMUs usable as sweep sources.

    Mapping (mirrors configuration.py):
        Gate_1 / Gate_2 — Keithley 2450 (also used for 2470) single SMUs
        smua / smub     — the two channels of the Keithley 2604B (Dual_gate);
                          offered only when the 2604B is connected
        YokoGS200_x / Yoko7651_x — Yokogawa voltage sources (via adapter)
    """
    names = []
    if _is_connected(Gate_1):
        names.append('Gate_1')
    if _is_connected(Gate_2):
        names.append('Gate_2')
    if _is_connected(Dual_gate):
        names += ['smua', 'smub']
    for yoko in ('YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2'):
        if _is_connected(globals()[yoko]):
            names.append(yoko)
    return names


def _make_smu_parameter(label='User defined SMU', default='Gate_1', **kwargs):
    """ListParameter offering only connected SMUs.

    Rebuilt after instruments are (re)bound via each procedure's
    _rebuild_parameters() classmethod (called from
    _rebuild_procedure_columns). Extra kwargs (group_by etc.) pass
    through to ListParameter.
    """
    choices = _connected_smus() or ['(none connected)']
    if default not in choices:
        default = choices[0]
    return ListParameter(label, choices=choices, default=default, **kwargs)


# ---------------- Input filtering for GUI ----------------

_INPUT_CONNECTION_MAP = {
    'use_dual_gate':  lambda c: _is_connected(getattr(c, 'Dual_gate', 0)),
    'use_keithley_1': lambda c: _is_connected(getattr(c, 'Gate_1', 0)),
    'use_keithley_2': lambda c: _is_connected(getattr(c, 'Gate_2', 0)),
    'use_yoko_gs200_1': lambda c: _is_connected(getattr(c, 'YokoGS200_1', 0)),
    'use_yoko_gs200_2': lambda c: _is_connected(getattr(c, 'YokoGS200_2', 0)),
    'use_yoko7651_1':   lambda c: _is_connected(getattr(c, 'Yoko7651_1', 0)),
    'use_yoko7651_2':   lambda c: _is_connected(getattr(c, 'Yoko7651_2', 0)),
    'use_k6221':        lambda c: _is_connected(getattr(c, 'K6221', 0)),
    'use_MFLI_1':     lambda c: _is_connected(getattr(c, 'MFLI_1', 0)),
    'use_MFLI_2':     lambda c: _is_connected(getattr(c, 'MFLI_2', 0)),
    'use_MFLI_3':     lambda c: _is_connected(getattr(c, 'MFLI_3', 0)),
    'use_srs860_1':   lambda c: _is_connected(getattr(c, 'SRS860_1', 0)),
    'use_srs860_2':   lambda c: _is_connected(getattr(c, 'SRS860_2', 0)),
    'use_srs860_3':   lambda c: _is_connected(getattr(c, 'SRS860_3', 0)),
    'use_srs860_4':   lambda c: _is_connected(getattr(c, 'SRS860_4', 0)),
    'use_srs830_1':   lambda c: _is_connected(getattr(c, 'SRS830_1', 0)),
    'use_srs830_2':   lambda c: _is_connected(getattr(c, 'SRS830_2', 0)),
    'use_srs830_3':   lambda c: _is_connected(getattr(c, 'SRS830_3', 0)),
}


def filter_inputs_by_connection(inputs, cfg):
    """Return inputs list with disconnected-instrument toggles removed."""
    skip = {name for name, check in _INPUT_CONNECTION_MAP.items() if not check(cfg)}
    return [i for i in inputs if i not in skip]


# ---------------- Yokogawa SMU adapter ----------------

class YokoVoltageSourceAdapter:
    """Wraps a YokogawaGS200 or Yokogawa7651 with the Keithley-SMU interface
    used by the sweep procedures (is_output_on / configure_voltage_source /
    output_on / ramp_voltage / voltage_ramping / measure__*).

    Yokogawas are source-only in this setup: measure__voltage() returns the
    programmed level (not a real measurement) and measure__current() is NaN.
    Ramps are blocking software ramps (same timing semantics as the Keithleys).

    ponytail: fixed 10 V source range at configure time — set a different
    range on the instrument front panel if a sweep needs >10 V.
    """

    def __init__(self, inst):
        self._inst = inst
        self._is_gs200 = hasattr(inst, 'source_level')

    def is_output_on(self):
        return bool(self._inst.source_enabled)

    def output_on(self):
        if hasattr(self._inst, 'enable_source'):   # 7651
            self._inst.enable_source()
        else:                                      # GS200
            self._inst.source_enabled = True

    def output_off(self):
        if hasattr(self._inst, 'disable_source'):  # 7651
            self._inst.disable_source()
        else:                                      # GS200
            self._inst.source_enabled = False

    def configure_voltage_source(self, **kwargs):
        """Put the instrument in voltage mode. Keithley-specific kwargs
        (nplc/current/auto_range/compliance/voltage/current_limit) are
        ignored — the Yokogawa uses its own limits."""
        if self._is_gs200:
            self._inst.source_mode = 'voltage'
            self._inst.source_range = 10
            self._inst.current_limit = 1e-3
        else:
            self._inst.apply_voltage(10, 10e-3)

    def _set_level(self, v):
        if self._is_gs200:
            self._inst.source_level = float(v)
        else:
            self._inst.source_voltage = float(v)

    def measure__voltage(self):
        """Programmed level — Yokogawas have no measure readback here."""
        if self._is_gs200:
            return float(self._inst.source_level)
        return float(self._inst.source_voltage)

    def measure__current(self):
        return math.nan  # source-only: no current readback

    def ramp_voltage(self, target, steps=30, pause=20e-3):
        """Keithley semantics: go to target in `steps` discrete jumps."""
        current = self.measure__voltage()
        n = max(int(steps), 1)
        for v in np.linspace(current, target, n + 1)[1:]:
            self._set_level(v)
            time.sleep(pause)

    def voltage_ramping(self, target, step_size=1, pause=20e-3, callback=None):
        """Keithley semantics: step_size in mV."""
        current = self.measure__voltage()
        step = max(abs(step_size), 1e-6) / 1000.0
        step = step if target >= current else -step
        n = int(abs(target - current) / abs(step)) if step else 0
        for v in np.linspace(current, target, n + 1)[1:]:
            self._set_level(v)
            time.sleep(pause)
            if callback is not None:
                if callback(0.0, float(v)):
                    log.info("Ramp aborted by callback at level %g", v)
                    break


# ---------------- GenericProcedure base class ----------------

class GenericProcedure(Procedure):
    """Base class for Generic Version procedures.

    Centralizes instrument reading logic so that only connected
    instruments produce data columns and readings.  Disconnected
    instruments are skipped entirely (no NaN padding, no column).

    Subclasses configure behaviour via class attributes:
        _MID_COLUMNS      list of extra column names inserted between
                          SMU and lock-in sections (default [])
        _LOCKIN_COL_TYPE  'voltage' or 'current' (default 'voltage')

    DATA_COLUMNS is rebuilt dynamically by _rebuild_all_columns()
    after instruments are (re)connected.
    """

    _MID_COLUMNS = []
    _LOCKIN_COL_TYPE = 'voltage'
    DATA_COLUMNS = []  # rebuilt at startup by _rebuild_all_columns()

    # --- Shared metadata (inherited by all subclasses) ---
    srs860_1_sine_voltage = Metadata("SRS860_1 sine voltage", default=math.nan)
    srs860_1_frequency   = Metadata("SRS860_1 frequency (Hz)", default=math.nan)
    srs860_2_sine_voltage = Metadata("SRS860_2 sine voltage", default=math.nan)
    srs860_2_frequency   = Metadata("SRS860_2 frequency (Hz)", default=math.nan)
    srs860_3_sine_voltage = Metadata("SRS860_3 sine voltage", default=math.nan)
    srs860_3_frequency   = Metadata("SRS860_3 frequency (Hz)", default=math.nan)
    srs860_4_sine_voltage = Metadata("SRS860_4 sine voltage", default=math.nan)
    srs860_4_frequency   = Metadata("SRS860_4 frequency (Hz)", default=math.nan)
    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency   = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency   = Metadata("SRS830_2 frequency (Hz)", default=math.nan)
    srs830_3_sine_voltage = Metadata("SRS830_3 sine voltage", default=math.nan)
    srs830_3_frequency   = Metadata("SRS830_3 frequency (Hz)", default=math.nan)
    MFLI_1_sine_voltage  = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency     = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_2_sine_voltage  = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency     = Metadata("MFLI_2 frequency (Hz)", default=math.nan)
    MFLI_3_sine_voltage  = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency     = Metadata("MFLI_3 frequency (Hz)", default=math.nan)
    k6221_frequency      = Metadata("K6221 frequency (Hz)", default=math.nan)
    k6221_amplitude_RMS  = Metadata("K6221 amplitude RMS (A)", default=math.nan)

    # --- Centralized metadata capture ---

    def _capture_metadata(self):
        """Record sine voltage + frequency for connected + enabled lock-ins."""
        if self.use_srs860_1 and _is_connected(SRS860_1):
            self.srs860_1_sine_voltage = SRS860_1.sine_voltage
            self.srs860_1_frequency = SRS860_1.frequency
        if self.use_srs860_2 and _is_connected(SRS860_2):
            self.srs860_2_sine_voltage = SRS860_2.sine_voltage
            self.srs860_2_frequency = SRS860_2.frequency
        if self.use_srs860_3 and _is_connected(SRS860_3):
            self.srs860_3_sine_voltage = SRS860_3.sine_voltage
            self.srs860_3_frequency = SRS860_3.frequency
        if self.use_srs860_4 and _is_connected(SRS860_4):
            self.srs860_4_sine_voltage = SRS860_4.sine_voltage
            self.srs860_4_frequency = SRS860_4.frequency
        if self.use_MFLI_1 and _is_connected(MFLI_1):
            self.MFLI_1_sine_voltage = MFLI_1.sine_amplitude
            self.MFLI_1_frequency = MFLI_1.frequency
        if self.use_MFLI_2 and _is_connected(MFLI_2):
            self.MFLI_2_sine_voltage = MFLI_2.sine_amplitude
            self.MFLI_2_frequency = MFLI_2.frequency
        if self.use_MFLI_3 and _is_connected(MFLI_3):
            self.MFLI_3_sine_voltage = MFLI_3.sine_amplitude
            self.MFLI_3_frequency = MFLI_3.frequency
        if self.use_srs830_1 and _is_connected(SRS830_1):
            self.srs830_1_sine_voltage = SRS830_1.sine_voltage
            self.srs830_1_frequency = SRS830_1.frequency
        if self.use_srs830_2 and _is_connected(SRS830_2):
            self.srs830_2_sine_voltage = SRS830_2.sine_voltage
            self.srs830_2_frequency = SRS830_2.frequency
        if self.use_srs830_3 and _is_connected(SRS830_3):
            self.srs830_3_sine_voltage = SRS830_3.sine_voltage
            self.srs830_3_frequency = SRS830_3.frequency
        if self.use_k6221 and _is_connected(K6221):
            self.k6221_frequency = K6221.waveform_frequency
            self.k6221_amplitude_RMS = K6221.waveform_amplitude / RMS_TO_PEAK

    # --- Centralized instrument readers ---

    def _read_smu_values(self):
        """Read connected SMUs. NaN for connected-but-disabled, skip disconnected."""
        vals = []
        if _is_connected(Dual_gate):
            if self.use_dual_gate:
                vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                         Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
            else:
                vals += [math.nan] * 4
        if _is_connected(Gate_1):
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        if _is_connected(Gate_2):
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2
        # Yokogawas are source-only: read back the programmed level
        if _is_connected(YokoGS200_1):
            vals += [YokoGS200_1.source_level] if self.use_yoko_gs200_1 else [math.nan]
        if _is_connected(YokoGS200_2):
            vals += [YokoGS200_2.source_level] if self.use_yoko_gs200_2 else [math.nan]
        if _is_connected(Yoko7651_1):
            vals += [Yoko7651_1.source_voltage] if self.use_yoko7651_1 else [math.nan]
        if _is_connected(Yoko7651_2):
            vals += [Yoko7651_2.source_voltage] if self.use_yoko7651_2 else [math.nan]
        if _is_connected(K6221):
            # read back peak amplitude, convert to RMS for the CSV
            vals += [K6221.waveform_amplitude / RMS_TO_PEAK] if self.use_k6221 else [math.nan]
        return vals

    # --- Lock-in read with retry (transient VISA timeouts) ---

    def _read_lockin_with_retry(self, reader, name, attempts=5, delay=0.5):
        """Call reader() retrying transient communication errors (e.g. VISA
        VI_ERROR_TMO on SR860/SR830 USB reads). Returns list of values on
        success, NaN pair if the instrument stays unreadable so a long
        measurement is not killed by one hiccup."""
        for i in range(attempts):
            try:
                return list(reader())
            except Exception as e:
                log.warning("%s read failed (attempt %d/%d): %s", name, i + 1, attempts, e)
                time.sleep(delay)
        log.error("%s unreadable after %d attempts - recording NaN", name, attempts)
        return [math.nan] * 2

    def _read_lockin_values(self):
        """Read connected lock-ins. NaN for connected-but-disabled, skip disconnected."""
        vals = []
        # Order must match _build_lockin_columns(): SRS830 group, SRS860 group, MFLI
        if _is_connected(SRS830_1):
            vals += self._read_lockin_with_retry(lambda: SRS830_1.snap("X", "Y"), "SRS830_1") \
                if self.use_srs830_1 else [math.nan] * 2
        if _is_connected(SRS830_2):
            vals += self._read_lockin_with_retry(lambda: SRS830_2.snap("X", "Y"), "SRS830_2") \
                if self.use_srs830_2 else [math.nan] * 2
        if _is_connected(SRS830_3):
            vals += self._read_lockin_with_retry(lambda: SRS830_3.snap("X", "Y"), "SRS830_3") \
                if self.use_srs830_3 else [math.nan] * 2
        if _is_connected(SRS860_1):
            vals += self._read_lockin_with_retry(lambda: SRS860_1.snap("X", "Y"), "SRS860_1") \
                if self.use_srs860_1 else [math.nan] * 2
        if _is_connected(SRS860_2):
            vals += self._read_lockin_with_retry(lambda: SRS860_2.snap("X", "Y"), "SRS860_2") \
                if self.use_srs860_2 else [math.nan] * 2
        if _is_connected(SRS860_3):
            vals += self._read_lockin_with_retry(lambda: SRS860_3.snap("X", "Y"), "SRS860_3") \
                if self.use_srs860_3 else [math.nan] * 2
        if _is_connected(SRS860_4):
            vals += self._read_lockin_with_retry(lambda: SRS860_4.snap("X", "Y"), "SRS860_4") \
                if self.use_srs860_4 else [math.nan] * 2
        if _is_connected(MFLI_1):
            vals += self._read_lockin_with_retry(lambda: MFLI_1.read_demod(), "MFLI_1") \
                if self.use_MFLI_1 else [math.nan] * 2
        if _is_connected(MFLI_2):
            vals += self._read_lockin_with_retry(lambda: MFLI_2.read_demod(), "MFLI_2") \
                if self.use_MFLI_2 else [math.nan] * 2
        if _is_connected(MFLI_3):
            vals += self._read_lockin_with_retry(lambda: MFLI_3.read_demod(), "MFLI_3") \
                if self.use_MFLI_3 else [math.nan] * 2
        return vals

    def _read_magnet(self):
        """Generic Version: no magnet — always empty."""
        return []

    def _read_standard(self, t0, mid_extras=None):
        """Full reading: time + SMUs + [mid_extras] + lockins.

        Args:
            t0: start time for elapsed calculation
            mid_extras: optional list of extra values (e.g. AUX/DC offset)
                        inserted between SMU and lock-in readings
        """
        vals = [time.time() - t0] + list(read_temperature())
        vals += self._read_smu_values()
        if mid_extras is not None:
            vals += mid_extras
        vals += self._read_lockin_values()
        vals += self._read_magnet()
        if len(vals) != len(self.DATA_COLUMNS):
            raise RuntimeError(
                f"Column misalignment: {len(vals)} values but "
                f"{len(self.DATA_COLUMNS)} columns. Your deployed files are "
                f"out of sync - copy ALL files of the Generic Version folder "
                f"from the repository (columns and readers must be the same "
                f"revision).")
        return vals

    # --- Shared SMU helpers ---

    def smu_choice(self, name):
        """Return the SMU object based on name selection."""
        yokos = ('YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2')
        if name not in ('Gate_1', 'Gate_2', 'smua', 'smub') + yokos:
            log.error("SMU selection not supported")
            raise ValueError(f"Unknown SMU: {name}")
        if name in ('smua', 'smub'):
            inst = getattr(Dual_gate, name, 0) if _is_connected(Dual_gate) else 0
        else:
            inst = globals().get(name, 0)
        if not _is_connected(inst):
            raise ValueError(f"{name} selected as SMU but is not connected "
                             f"(check the pre-launch dialog)")
        if name in yokos:
            return YokoVoltageSourceAdapter(inst)
        return inst

    def smu_output(self, Gate, name):
        """Enable SMU output with appropriate configuration."""
        if not Gate.is_output_on():
            log.info(f"{name} output was OFF. Turning it ON.")
            if name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        """Generate a linspace from start to end with step in milli-units."""
        step = abs(step_units / 1000.0)
        if step == 0:
            step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)


# ---------------- Category helpers ----------------

def _as_cat_list(cat_value):
    if cat_value is None:
        return []
    if isinstance(cat_value, (list, tuple, set)):
        return [str(c) for c in cat_value]
    return [str(cat_value)]


def _proc_matches(proc_dict, selected_names):
    """AND logic: a procedure must include ALL selected categories to match."""
    if not selected_names:
        return True
    proc_cats = set(_as_cat_list(proc_dict.get('category')))
    return set(selected_names).issubset(proc_cats)


# ---------------- Instrument rebinding ----------------

def _rebind_instruments_from_configuration():
    """Refresh module-level instrument globals after configuration reload."""
    global MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS860_3, SRS860_4, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2, YokoGS200_1, YokoGS200_2, Yoko7651_1, Yoko7651_2, K6221
    MFLI_1 = _cfg.MFLI_1
    MFLI_2 = _cfg.MFLI_2
    MFLI_3 = _cfg.MFLI_3
    SRS860_1 = _cfg.SRS860_1
    SRS860_2 = _cfg.SRS860_2
    SRS860_3 = getattr(_cfg, "SRS860_3", 0)
    SRS860_4 = getattr(_cfg, "SRS860_4", 0)
    SRS830_1 = _cfg.SRS830_1
    SRS830_2 = _cfg.SRS830_2
    SRS830_3 = _cfg.SRS830_3
    Dual_gate = _cfg.Dual_gate
    Gate_1 = _cfg.Gate_1
    Gate_2 = _cfg.Gate_2
    YokoGS200_1 = getattr(_cfg, "YokoGS200_1", 0)
    YokoGS200_2 = getattr(_cfg, "YokoGS200_2", 0)
    Yoko7651_1 = getattr(_cfg, "Yoko7651_1", 0)
    Yoko7651_2 = getattr(_cfg, "Yoko7651_2", 0)
    K6221 = getattr(_cfg, "K6221", 0)

    # Update instrument refs in all procedure submodules that imported via from .base import *
    _inst_names = ['MFLI_1', 'MFLI_2', 'MFLI_3',
                   'SRS860_1', 'SRS860_2', 'SRS860_3', 'SRS860_4', 'SRS830_1', 'SRS830_2', 'SRS830_3',
                   'Dual_gate', 'Gate_1', 'Gate_2',
                   'YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2', 'K6221']
    for mod in sys.modules.values():
        if mod is None or not hasattr(mod, '__file__') or not mod.__file__:
            continue
        if 'procedures' not in getattr(mod, '__name__', ''):
            continue
        for name in _inst_names:
            if name in mod.__dict__:
                mod.__dict__[name] = globals()[name]

    # Rebuild dynamic column lists and all procedure DATA_COLUMNS
    _rebuild_all_columns()