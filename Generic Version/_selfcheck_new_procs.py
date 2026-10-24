# ponytail: throwaway self-check — run after adding new Generic procedures
# Usage: python _selfcheck_new_procs.py  (delete when done)
import procedures
import procedures.base as b


class F:  # fake connected instrument
    pass


b.SRS830_1 = F()
b.Gate_1 = F()
b._rebuild_all_columns()

from procedures import (Differential_Resistance_6221, Differential_Resistance_AUX,
                        Differential_Resistance_6221_map, Resistance_aux_gate_map,
                        RV_dV_dI_sequencer_measurement, RV_R_AUX_sequencer_measurement)

for c in (Differential_Resistance_6221_map, Resistance_aux_gate_map,
          RV_dV_dI_sequencer_measurement, RV_R_AUX_sequencer_measurement):
    assert c.DATA_COLUMNS, c.__name__
    print(c.__name__, c.DATA_COLUMNS)

# 6221 dV/dI family sweeps DC current on the K6221
assert 'DC_current(A)' in Differential_Resistance_6221_map.DATA_COLUMNS
assert 'DC_current(A)' in RV_dV_dI_sequencer_measurement.DATA_COLUMNS
# AUX family sweeps a lock-in AUX voltage
assert 'AUX_DC_offset(V)' in Differential_Resistance_AUX.DATA_COLUMNS
assert 'Auxiliary_Voltage(V)' in Resistance_aux_gate_map.DATA_COLUMNS
assert 'Auxiliary_Voltage(V)' in RV_R_AUX_sequencer_measurement.DATA_COLUMNS
assert 'time(s)' in b.BASE_DATA_COLUMNS

# Parameter rebuild hooks
assert list(Resistance_aux_gate_map.aux_source.choices) == ['SRS830_1']
assert list(Resistance_aux_gate_map.smu.choices) == ['Gate_1']

# 6221 dV/dI family: no AUX params, no AC setup, no compliance param
# (compliance / current range are set manually on the instrument)
for c in (Differential_Resistance_6221, Differential_Resistance_6221_map,
          RV_dV_dI_sequencer_measurement):
    params = set(c().parameter_objects().keys())
    for absent in ('ac_source', 'aux_source', 'aux_signal', 'dc_compliance'):
        assert absent not in params, (c.__name__, absent)
# AUX dV/dI: no K6221 AC setup either
aux_params = set(Differential_Resistance_AUX().parameter_objects().keys())
for absent in ('ac_source', 'ac_running', 'waveform', 'frequency',
               'ac_current', 'ac_compliance'):
    assert absent not in aux_params, absent

# every proc dict input name must exist as a Parameter on its class
for name, spec in procedures.PROCEDURES.items():
    cls = spec['cls']
    par_names = set(cls().parameter_objects().keys())
    for inp in spec['inputs']:
        assert inp in par_names, f"{name}: missing input parameter '{inp}'"
    for d in spec['displays']:
        assert d in spec['inputs'], f"{name}: display '{d}' not in inputs"

print('ALL_CHECKS_OK')