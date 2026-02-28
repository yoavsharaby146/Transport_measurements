"""
Procedures package for Dilution measurements.

This package contains all measurement procedures organized by type.
"""

from .base import (
    log, save_dir, dilution, MFLI_1, MFLI_2, MFLI_3,
    SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    _rebind_instruments_from_configuration, _as_cat_list, _proc_matches,
    BASE_DATA_COLUMNS, LOCKIN_VOLTAGE_COLUMNS, MAGNET_COLUMNS
)

# Import all procedures
from .resistance_time import Resistance_time_measurement, proc_resistance_time
from .resistance_gate_sweep import Resistance_gate_sweep_measurement, proc_resistance_gate
from .resistance_magnet_sweep import Resistance_magnet_sweep_measurement, proc_resistance_magnet
from .resistance_two_gate_sweep import Resistance_two_gate_scan_sweep_measurement, proc_resistance_two_gate_sweep
from .resistance_carrier_density import Resistance_carrier_density_farward_backward_measurement, proc_resistance_carrier_density
from .resistance_two_gate_map import Resistance_two_gate_mapping_measurement, proc_resistance_two_gate_map
from .resistance_magnet_gate_map import Resistance_magnet_and_gate_mapping_measurement, proc_resistance_magnet_gate_map
from .resistance_magnet_2gate_map import Resistance_magnet_and_2gate_mapping_measurement, proc_resistance_magnet_2gate_map
from .differential_conductance_srs860 import Differential_conductance_SRS860, proc_differential_conductance_SRS860
from .differential_conductance_zurich import Differential_conductance_Zurich, proc_differential_conductance_Zurich
from .differential_conductance_zurich_gated import Differential_conductance_Zurich_gated, proc_differential_conductance_Zurich_gate
from .differential_resistance_zurich import Differential_Resistance_Zurich, proc_differential_resistance_Zurich
from .differential_resistance_gate_map import Differential_Resistance_Gate_map_Zurich, proc_differential_resistance_gate_map_zurich
from .differential_resistance_aux_map import Differential_Resistance_AUX_map_gate_sweep_Zurich, proc_differential_resistance_aux_map_gate_zurich
from .sequencer_rt_rv_rh import Rt_RV_RH_sequencer_measurement, proc_Rt_RV_RH_sequencer
from .sequencer_rv_dvdi import RV_dV_dI_sequencer_measurement, proc_RV_dV_dI_sequencer

# Build PROCEDURES dictionary
PROCEDURES = {}
PROCEDURES.update(proc_resistance_time)
PROCEDURES.update(proc_resistance_gate)
PROCEDURES.update(proc_resistance_magnet)
PROCEDURES.update(proc_resistance_two_gate_sweep)
PROCEDURES.update(proc_resistance_carrier_density)
PROCEDURES.update(proc_resistance_two_gate_map)
PROCEDURES.update(proc_resistance_magnet_gate_map)
PROCEDURES.update(proc_resistance_magnet_2gate_map)
PROCEDURES.update(proc_differential_conductance_SRS860)
PROCEDURES.update(proc_differential_conductance_Zurich)
PROCEDURES.update(proc_differential_conductance_Zurich_gate)
PROCEDURES.update(proc_differential_resistance_Zurich)
PROCEDURES.update(proc_differential_resistance_gate_map_zurich)
PROCEDURES.update(proc_differential_resistance_aux_map_gate_zurich)
PROCEDURES.update(proc_Rt_RV_RH_sequencer)
PROCEDURES.update(proc_RV_dV_dI_sequencer)

# Categories for the launcher
CATAGORIES = {
    "Time-based": "#BEE1F9",
    "Gate Sweep": "#BEF9C7",
    "Magnetic Field": "#F6F9BE",
    "2D Mapping": "#EABEF9",
    "Tunneling junction": "#F9BEC2",
    "Differential Resistance": "#F9E3BE",
    "Keithley 2450": "#FCBBD5"
}

__all__ = [
    'PROCEDURES', 'CATAGORIES',
    'Resistance_time_measurement', 'proc_resistance_time',
    'Resistance_gate_sweep_measurement', 'proc_resistance_gate',
    'Resistance_magnet_sweep_measurement', 'proc_resistance_magnet',
    'Resistance_two_gate_scan_sweep_measurement', 'proc_resistance_two_gate_sweep',
    'Resistance_carrier_density_farward_backward_measurement', 'proc_resistance_carrier_density',
    'Resistance_two_gate_mapping_measurement', 'proc_resistance_two_gate_map',
    'Resistance_magnet_and_gate_mapping_measurement', 'proc_resistance_magnet_gate_map',
    'Resistance_magnet_and_2gate_mapping_measurement', 'proc_resistance_magnet_2gate_map',
    'Differential_conductance_SRS860', 'proc_differential_conductance_SRS860',
    'Differential_conductance_Zurich', 'proc_differential_conductance_Zurich',
    'Differential_conductance_Zurich_gated', 'proc_differential_conductance_Zurich_gate',
    'Differential_Resistance_Zurich', 'proc_differential_resistance_Zurich',
    'Differential_Resistance_Gate_map_Zurich', 'proc_differential_resistance_gate_map_zurich',
    'Differential_Resistance_AUX_map_gate_sweep_Zurich', 'proc_differential_resistance_aux_map_gate_zurich',
    'Rt_RV_RH_sequencer_measurement', 'proc_Rt_RV_RH_sequencer',
    'RV_dV_dI_sequencer_measurement', 'proc_RV_dV_dI_sequencer',
]