"""
Procedures package for ICE measurements.
Each procedure class is in its own module for easier maintenance.
"""

# Import base utilities
from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    ICEProcedure,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2,
    YokoGS200_1, YokoGS200_2, Yoko7651_1, Yoko7651_2, K6221,
    read_temperature, _rebind_instruments_from_configuration,
    _as_cat_list, _proc_matches,
    filter_inputs_by_connection,
)

# Import procedure classes and their registration dicts
from .resistance_time import Resistance_time_measurement, proc_resistance_time
from .resistance_temperature import Resistance_temperature_measurement, proc_resistance_temperature
from .resistance_gate_sweep import Resistance_gate_sweep_measurement, proc_resistance_gate
from .resistance_magnet_sweep import Resistance_magnet_sweep_measurement, proc_resistance_magnet
from .resistance_two_gate_sweep import Resistance_two_gate_scan_sweep_measurement, proc_resistance_two_gate_sweep
from .resistance_two_gate_map import Resistance_two_gate_mapping_measurement, proc_resistance_two_gate_map
from .resistance_magnet_gate_map import Resistance_magnet_and_gate_mapping_measurement, proc_resistance_magnet_gate_map
from .resistance_magnet_2gate_map import Resistance_magnet_and_2gate_mapping_measurement, proc_resistance_magnet_2gate_map
from .differential_conductance import Differential_Conductance, proc_differential_conductance
from .differential_conductance_map import Differential_Conductance_map, proc_differential_conductance_map
# Superseded by the unified Differential_Conductance procedure (any connected
# SRS860 / MFLI as excitation): the old differential_conductance_srs860.py /
# differential_conductance_zurich.py modules were removed.
# Superseded by the unified AUX procedure (any connected lock-in as source):
# the old differential_resistance_srs860.py / differential_resistance_zurich.py
# modules were removed; use Differential_Resistance_AUX instead.
from .differential_resistance_aux import Differential_Resistance_AUX, proc_differential_resistance_AUX
from .differential_resistance_aux_map import Differential_Resistance_AUX_map, proc_differential_resistance_AUX_map
from .sequencer_rt_rv_rh import Rt_RV_RH_sequencer_measurement, proc_Rt_RV_RH_sequencer
from .sequencer_rv_dvdi import RV_dV_dI_sequencer_measurement, proc_RV_dV_dI_sequencer
from .ac_current_sweep import AC_current_sweep_measurement, proc_ac_current_sweep

# Category colors
CATAGORIES = {
    "Time-based": "#BEE1F9",
    "Temperature": "#F9DABE",
    "Gate Sweep": "#BEF9C7",
    "Magnetic Field": "#F6F9BE",
    "2D Mapping": "#EABEF9",
    "Tunneling junction": "#F9BEC2",
    "Differential Resistance": "#F9E3BE",
    "AC Current Sweep": "#BEF9EC",
}

# Build the PROCEDURES dictionary
PROCEDURES = {}
PROCEDURES.update(proc_resistance_time)
PROCEDURES.update(proc_resistance_temperature)
PROCEDURES.update(proc_resistance_gate)
PROCEDURES.update(proc_resistance_magnet)
PROCEDURES.update(proc_resistance_two_gate_sweep)
PROCEDURES.update(proc_resistance_two_gate_map)
PROCEDURES.update(proc_resistance_magnet_gate_map)
PROCEDURES.update(proc_resistance_magnet_2gate_map)
PROCEDURES.update(proc_differential_conductance)
PROCEDURES.update(proc_differential_conductance_map)
PROCEDURES.update(proc_differential_resistance_AUX)
PROCEDURES.update(proc_differential_resistance_AUX_map)
PROCEDURES.update(proc_Rt_RV_RH_sequencer)
PROCEDURES.update(proc_RV_dV_dI_sequencer)
PROCEDURES.update(proc_ac_current_sweep)

# Export all
__all__ = [
    # Base utilities
    'log', 'time', 'math', 'np',
    'Procedure', 'BooleanParameter', 'IntegerParameter', 'FloatParameter', 'Parameter', 'Metadata', 'ListParameter',
    'ICEProcedure',
    'magnet', 'MFLI_1', 'MFLI_2', 'MFLI_3', 'SRS860_1', 'SRS860_2', 'SRS830_1', 'SRS830_2', 'SRS830_3', 'Dual_gate', 'Gate_1', 'Gate_2',
    'YokoGS200_1', 'YokoGS200_2', 'Yoko7651_1', 'Yoko7651_2', 'K6221',
    'read_temperature', '_rebind_instruments_from_configuration',
    '_as_cat_list', '_proc_matches',
    'filter_inputs_by_connection',
    # Procedure classes
    'Resistance_time_measurement',
    'Resistance_temperature_measurement',
    'Resistance_gate_sweep_measurement',
    'Resistance_magnet_sweep_measurement',
    'Resistance_two_gate_scan_sweep_measurement',
    'Resistance_two_gate_mapping_measurement',
    'Resistance_magnet_and_gate_mapping_measurement',
    'Resistance_magnet_and_2gate_mapping_measurement',
    'Differential_Conductance',
    'Differential_Conductance_map',
    'Differential_Resistance_AUX',
    'Differential_Resistance_AUX_map',
    'Rt_RV_RH_sequencer_measurement',
    'RV_dV_dI_sequencer_measurement',
    'AC_current_sweep_measurement',
    # Registration dicts
    'proc_resistance_time',
    'proc_resistance_temperature',
    'proc_resistance_gate',
    'proc_resistance_magnet',
    'proc_resistance_two_gate_sweep',
    'proc_resistance_two_gate_map',
    'proc_resistance_magnet_gate_map',
    'proc_resistance_magnet_2gate_map',
    'proc_differential_conductance',
    'proc_differential_conductance_map',
    'proc_differential_resistance_AUX',
    'proc_differential_resistance_AUX_map',
    'proc_Rt_RV_RH_sequencer',
    'proc_RV_dV_dI_sequencer',
    'proc_ac_current_sweep',
    # Aggregates
    'CATAGORIES',
    'PROCEDURES',
]
