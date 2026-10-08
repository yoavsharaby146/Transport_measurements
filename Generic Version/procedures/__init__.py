"""
Procedures package for Generic Version measurements.
Each procedure class is in its own module for easier maintenance.

Generic Version: Keithley SMUs + lock-ins only (no magnet, no cryostat).
"""

# Import base utilities
from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    GenericProcedure,
    MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2,
    YokoGS200_1, YokoGS200_2, Yoko7651_1, Yoko7651_2,
    read_temperature, _rebind_instruments_from_configuration,
    _as_cat_list, _proc_matches,
    filter_inputs_by_connection,
)

# Import procedure classes and their registration dicts
from .resistance_time import Resistance_time_measurement, proc_resistance_time
from .resistance_gate_sweep import Resistance_gate_sweep_measurement, proc_resistance_gate
from .resistance_two_gate_sweep import Resistance_two_gate_scan_sweep_measurement, proc_resistance_two_gate_sweep
from .resistance_two_gate_map import Resistance_two_gate_mapping_measurement, proc_resistance_two_gate_map

# Category colors
CATAGORIES = {
    "Time-based": "#BEE1F9",
    "Gate Sweep": "#BEF9C7",
    "2D Mapping": "#EABEF9",
}

# Build the PROCEDURES dictionary
PROCEDURES = {}
PROCEDURES.update(proc_resistance_time)
PROCEDURES.update(proc_resistance_gate)
PROCEDURES.update(proc_resistance_two_gate_sweep)
PROCEDURES.update(proc_resistance_two_gate_map)

# Export all
__all__ = [
    # Base utilities
    'log', 'time', 'math', 'np',
    'Procedure', 'BooleanParameter', 'IntegerParameter', 'FloatParameter', 'Parameter', 'Metadata', 'ListParameter',
    'GenericProcedure',
    'MFLI_1', 'MFLI_2', 'MFLI_3', 'SRS860_1', 'SRS860_2', 'SRS830_1', 'SRS830_2', 'SRS830_3', 'Dual_gate', 'Gate_1', 'Gate_2',
    'YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2',
    'read_temperature', '_rebind_instruments_from_configuration',
    '_as_cat_list', '_proc_matches',
    'filter_inputs_by_connection',
    # Procedure classes
    'Resistance_time_measurement',
    'Resistance_gate_sweep_measurement',
    'Resistance_two_gate_scan_sweep_measurement',
    'Resistance_two_gate_mapping_measurement',
    # Registration dicts
    'proc_resistance_time',
    'proc_resistance_gate',
    'proc_resistance_two_gate_sweep',
    'proc_resistance_two_gate_map',
    # Aggregates
    'CATAGORIES',
    'PROCEDURES',
]
