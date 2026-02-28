"""
Base module for Dilution procedures.

Contains common imports, instrument bindings, and helper functions.
"""

import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import time, math
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

# Import configuration
import configuration_Dilution as _cfg
#from configuration_Dilution import read_temperature

# Safe bindings (fall back to 0 if the attribute doesn't exist)
dilution = getattr(_cfg, "dilution", 0)
MFLI_1 = getattr(_cfg, "MFLI_1", 0)
MFLI_2 = getattr(_cfg, "MFLI_2", 0)
MFLI_3 = getattr(_cfg, "MFLI_3", 0)
SRS860 = getattr(_cfg, "SRS860", 0)
SRS830_1 = getattr(_cfg, "SRS830_1", 0)
SRS830_2 = getattr(_cfg, "SRS830_2", 0)
Dual_gate = getattr(_cfg, "Dual_gate", 0)
Gate_1 = getattr(_cfg, "Gate_1", 0)
Gate_2 = getattr(_cfg, "Gate_2", 0)

save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav"


def _rebind_instruments_from_configuration():
    """Refresh module-level instrument globals after configuration reload."""
    global dilution, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2
    dilution = _cfg.dilution
    MFLI_1 = _cfg.MFLI_1
    MFLI_2 = _cfg.MFLI_2
    MFLI_3 = _cfg.MFLI_3
    SRS860 = _cfg.SRS860
    SRS830_1 = _cfg.SRS830_1
    SRS830_2 = _cfg.SRS830_2
    Dual_gate = _cfg.Dual_gate
    Gate_1 = _cfg.Gate_1
    Gate_2 = _cfg.Gate_2


def _as_cat_list(cat_value):
    """Convert category value to list of strings."""
    if cat_value is None:
        return []
    if isinstance(cat_value, (list, tuple, set)):
        return [str(c) for c in cat_value]
    return [str(cat_value)]


def _proc_matches(proc_dict, selected_names):
    """AND logic: a procedure must include ALL selected categories to match."""
    if not selected_names:  # no filter => match all
        return True
    proc_cats = set(_as_cat_list(proc_dict.get('category')))
    return set(selected_names).issubset(proc_cats)


# Common DATA_COLUMNS templates
BASE_DATA_COLUMNS = [
    'time(s)',
    'Mixing_chanber(K)',
    'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
    'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
]

LOCKIN_VOLTAGE_COLUMNS = [
    'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
    'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
    'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
    'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
    'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
    'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
]

LOCKIN_CURRENT_COLUMNS = [
    'Lockin_Current_SRS860_X(A)', 'Lockin_Current_SRS860_Y(A)',
    'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
    'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
    'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
    'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
    'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
]

MAGNET_COLUMNS = ['B_x (T)', 'B_y (T)', 'B_z (T)']