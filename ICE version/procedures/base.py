"""
Base module for ICE procedures.

Contains common imports, instrument bindings, helper functions,
dynamic column generation, and the ICEProcedure base class with
centralized instrument reading that skips disconnected instruments.
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

magnet            = getattr(_cfg, "magnet", 0)
MFLI_1            = getattr(_cfg, "MFLI_1", 0)
MFLI_2            = getattr(_cfg, "MFLI_2", 0)
MFLI_3            = getattr(_cfg, "MFLI_3", 0)
SRS860_1          = getattr(_cfg, "SRS860_1", 0)
SRS860_2          = getattr(_cfg, "SRS860_2", 0)
SRS830_1          = getattr(_cfg, "SRS830_1", 0)
SRS830_2          = getattr(_cfg, "SRS830_2", 0)
SRS830_3          = getattr(_cfg, "SRS830_3", 0)
Dual_gate         = getattr(_cfg, "Dual_gate", 0)
Gate_1            = getattr(_cfg, "Gate_1", 0)
Gate_2            = getattr(_cfg, "Gate_2", 0)

save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav"


# ---------------- Static column templates (backward compat + fallback) ----------------

BASE_DATA_COLUMNS = [
    'time(s)',
    '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
    'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
    'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
]

LOCKIN_VOLTAGE_COLUMNS = [
    'Lockin_Voltage_SRS860_1_X(V)', 'Lockin_Voltage_SRS860_1_Y(V)',
    'Lockin_Voltage_SRS860_2_X(V)', 'Lockin_Voltage_SRS860_2_Y(V)',
    'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
    'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
    'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
    'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
    'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
    'Lockin_Voltage_SRS830_3_X(V)', 'Lockin_Voltage_SRS830_3_Y(V)',
]

LOCKIN_CURRENT_COLUMNS = [
    'Lockin_Current_SRS860_1_X(A)', 'Lockin_Current_SRS860_1_Y(A)',
    'Lockin_Current_SRS860_2_X(A)', 'Lockin_Current_SRS860_2_Y(A)',
    'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
    'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
    'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
    'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
    'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
    'Lockin_Current_SRS830_3_X(A)', 'Lockin_Current_SRS830_3_Y(A)',
]

MAGNET_COLUMNS = ['field(T)']


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
        (SRS860_1, 'SRS860_1', None),
        (SRS860_2, 'SRS860_2', None),
        (MFLI_1,   None,       1),
        (MFLI_2,   None,       2),
        (MFLI_3,   None,       3),
        (SRS830_1, 'SRS830_1', None),
        (SRS830_2, 'SRS830_2', None),
        (SRS830_3, 'SRS830_3', None),
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
    return ['field(T)'] if _is_connected(magnet) else []


def _build_base_columns():
    """Fixed prefix + dynamic SMU columns."""
    return ['time(s)',
            '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)'
            ] + _build_smu_columns()


def _rebuild_procedure_columns(cls):
    """Rebuild DATA_COLUMNS for a single ICEProcedure subclass."""
    mid = getattr(cls, '_MID_COLUMNS', [])
    kind = getattr(cls, '_LOCKIN_COL_TYPE', 'voltage')
    cls.DATA_COLUMNS = (
        _build_base_columns() + list(mid) +
        _build_lockin_columns(kind) + _build_magnet_columns()
    )


def _rebuild_all_columns():
    """Rebuild module-level column lists and all ICEProcedure DATA_COLUMNS.

    Called from _rebind_instruments_from_configuration() after instruments
    are refreshed, so column lists reflect currently-connected hardware.
    """
    global BASE_DATA_COLUMNS, LOCKIN_VOLTAGE_COLUMNS, LOCKIN_CURRENT_COLUMNS, MAGNET_COLUMNS

    BASE_DATA_COLUMNS = _build_base_columns()
    LOCKIN_VOLTAGE_COLUMNS = _build_lockin_columns('voltage')
    LOCKIN_CURRENT_COLUMNS = _build_lockin_columns('current')
    MAGNET_COLUMNS = _build_magnet_columns()

    # Rebuild DATA_COLUMNS on every ICEProcedure subclass found in procedure modules
    for mod in sys.modules.values():
        if mod is None or not hasattr(mod, '__file__') or not mod.__file__:
            continue
        if 'procedures' not in getattr(mod, '__name__', ''):
            continue
        for attr_name in list(mod.__dict__):
            obj = mod.__dict__.get(attr_name)
            if (isinstance(obj, type) and issubclass(obj, ICEProcedure)
                    and obj is not ICEProcedure):
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


# ---------------- Input filtering for GUI ----------------

_INPUT_CONNECTION_MAP = {
    'use_magnet':     lambda c: _is_connected(getattr(c, 'magnet', 0)),
    'use_dual_gate':  lambda c: _is_connected(getattr(c, 'Dual_gate', 0)),
    'use_keithley_1': lambda c: _is_connected(getattr(c, 'Gate_1', 0)),
    'use_keithley_2': lambda c: _is_connected(getattr(c, 'Gate_2', 0)),
    'use_MFLI_1':     lambda c: _is_connected(getattr(c, 'MFLI_1', 0)),
    'use_MFLI_2':     lambda c: _is_connected(getattr(c, 'MFLI_2', 0)),
    'use_MFLI_3':     lambda c: _is_connected(getattr(c, 'MFLI_3', 0)),
    'use_srs860_1':   lambda c: _is_connected(getattr(c, 'SRS860_1', 0)),
    'use_srs860_2':   lambda c: _is_connected(getattr(c, 'SRS860_2', 0)),
    'use_srs830_1':   lambda c: _is_connected(getattr(c, 'SRS830_1', 0)),
    'use_srs830_2':   lambda c: _is_connected(getattr(c, 'SRS830_2', 0)),
    'use_srs830_3':   lambda c: _is_connected(getattr(c, 'SRS830_3', 0)),
}


def filter_inputs_by_connection(inputs, cfg):
    """Return inputs list with disconnected-instrument toggles removed."""
    skip = {name for name, check in _INPUT_CONNECTION_MAP.items() if not check(cfg)}
    return [i for i in inputs if i not in skip]


# ---------------- ICEProcedure base class ----------------

class ICEProcedure(Procedure):
    """Base class for ICE procedures.

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

    # --- Centralized metadata capture ---

    def _capture_metadata(self):
        """Record sine voltage + frequency for connected + enabled lock-ins."""
        if self.use_srs860_1 and _is_connected(SRS860_1):
            self.srs860_1_sine_voltage = SRS860_1.sine_voltage
            self.srs860_1_frequency = SRS860_1.frequency
        if self.use_srs860_2 and _is_connected(SRS860_2):
            self.srs860_2_sine_voltage = SRS860_2.sine_voltage
            self.srs860_2_frequency = SRS860_2.frequency
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
        return vals

    def _read_lockin_values(self):
        """Read connected lock-ins. NaN for connected-but-disabled, skip disconnected."""
        vals = []
        # Order must match _build_lockin_columns()
        if _is_connected(SRS860_1):
            vals += list(SRS860_1.snap("X", "Y")) if self.use_srs860_1 else [math.nan] * 2
        if _is_connected(SRS860_2):
            vals += list(SRS860_2.snap("X", "Y")) if self.use_srs860_2 else [math.nan] * 2
        if _is_connected(MFLI_1):
            vals += list(MFLI_1.read_demod()) if self.use_MFLI_1 else [math.nan] * 2
        if _is_connected(MFLI_2):
            vals += list(MFLI_2.read_demod()) if self.use_MFLI_2 else [math.nan] * 2
        if _is_connected(MFLI_3):
            vals += list(MFLI_3.read_demod()) if self.use_MFLI_3 else [math.nan] * 2
        if _is_connected(SRS830_1):
            vals += list(SRS830_1.snap("X", "Y")) if self.use_srs830_1 else [math.nan] * 2
        if _is_connected(SRS830_2):
            vals += list(SRS830_2.snap("X", "Y")) if self.use_srs830_2 else [math.nan] * 2
        if _is_connected(SRS830_3):
            vals += list(SRS830_3.snap("X", "Y")) if self.use_srs830_3 else [math.nan] * 2
        return vals

    def _read_magnet(self):
        """Read magnet field if connected. Returns [] if no magnet connected."""
        if not _is_connected(magnet):
            return []
        return [magnet.magnet_field_read_response() if self.use_magnet else math.nan]

    def _read_standard(self, t0, mid_extras=None):
        """Full reading: time+temp + SMUs + [mid_extras] + lockins + magnet.

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
        return vals

    # --- Shared SMU helpers ---

    def smu_choice(self, name):
        """Return the SMU object based on name selection."""
        if name == 'Gate_1': return Gate_1
        if name == 'Gate_2': return Gate_2
        if name == 'smua': return Dual_gate.smua
        if name == 'smub': return Dual_gate.smub
        log.error("SMU selection not supported")
        raise ValueError(f"Unknown SMU: {name}")

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
    global magnet, MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2
    magnet = _cfg.magnet
    MFLI_1 = _cfg.MFLI_1
    MFLI_2 = _cfg.MFLI_2
    MFLI_3 = _cfg.MFLI_3
    SRS860_1 = _cfg.SRS860_1
    SRS860_2 = _cfg.SRS860_2
    SRS830_1 = _cfg.SRS830_1
    SRS830_2 = _cfg.SRS830_2
    SRS830_3 = _cfg.SRS830_3
    Dual_gate = _cfg.Dual_gate
    Gate_1 = _cfg.Gate_1
    Gate_2 = _cfg.Gate_2

    # Update instrument refs in all procedure submodules that imported via from .base import *
    _inst_names = ['magnet', 'MFLI_1', 'MFLI_2', 'MFLI_3',
                   'SRS860_1', 'SRS860_2', 'SRS830_1', 'SRS830_2', 'SRS830_3',
                   'Dual_gate', 'Gate_1', 'Gate_2']
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