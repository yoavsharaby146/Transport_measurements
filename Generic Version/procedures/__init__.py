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
    MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS860_3, SRS860_4, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2,
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
from .ac_current_sweep import AC_current_sweep_measurement, proc_ac_current_sweep
from .ac_dc_current_ramp import AC_DC_current_ramp_measurement, proc_ac_dc_ramp
from .resistance_aux_sweep import Resistance_aux_voltage_measurement, proc_resistance_aux
from .sequencer_rt_rv import Rt_RV_sequencer_measurement, proc_Rt_RV_sequencer

# Category colors
CATAGORIES = {
    "Time-based": "#BEE1F9",
    "Gate Sweep": "#BEF9C7",
    "2D Mapping": "#EABEF9",
    "AC Current Sweep": "#BEF9EC",
    "Aux Sweep": "#F9BEE1",
    "AC+DC": "#F9D3BE",
}

# Build the PROCEDURES dictionary
PROCEDURES = {}
PROCEDURES.update(proc_resistance_time)
PROCEDURES.update(proc_resistance_gate)
PROCEDURES.update(proc_resistance_two_gate_sweep)
PROCEDURES.update(proc_resistance_two_gate_map)
PROCEDURES.update(proc_ac_current_sweep)
PROCEDURES.update(proc_resistance_aux)
PROCEDURES.update(proc_Rt_RV_sequencer)
PROCEDURES.update(proc_ac_dc_ramp)

# Export all
__all__ = [
    # Base utilities
    'log', 'time', 'math', 'np',
    'Procedure', 'BooleanParameter', 'IntegerParameter', 'FloatParameter', 'Parameter', 'Metadata', 'ListParameter',
    'GenericProcedure',
    'MFLI_1', 'MFLI_2', 'MFLI_3', 'SRS860_1', 'SRS860_2', 'SRS860_3', 'SRS860_4', 'SRS830_1', 'SRS830_2', 'SRS830_3', 'Dual_gate', 'Gate_1', 'Gate_2',
    'YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2',
    'read_temperature', '_rebind_instruments_from_configuration',
    '_as_cat_list', '_proc_matches',
    'filter_inputs_by_connection',
    # Procedure classes
    'Resistance_time_measurement',
    'Resistance_gate_sweep_measurement',
    'Resistance_two_gate_scan_sweep_measurement',
    'Resistance_two_gate_mapping_measurement',
    'AC_current_sweep_measurement',
    'AC_DC_current_ramp_measurement',
    'Resistance_aux_voltage_measurement',
    'Rt_RV_sequencer_measurement',
    # Registration dicts
    'proc_resistance_time',
    'proc_resistance_gate',
    'proc_resistance_two_gate_sweep',
    'proc_resistance_two_gate_map',
    'proc_ac_current_sweep',
    'proc_ac_dc_ramp',
    'proc_resistance_aux',
    'proc_Rt_RV_sequencer',
    # Aggregates
    'CATAGORIES',
    'PROCEDURES',
]
