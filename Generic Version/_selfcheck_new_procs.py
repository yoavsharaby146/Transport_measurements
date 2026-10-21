# ponytail: throwaway self-check — run after adding new Generic procedures
# Usage: python _selfcheck_new_procs.py  (delete when done)
import procedures
import procedures.base as b


class F:  # fake connected instrument
    pass


b.SRS830_1 = F()
b.Gate_1 = F()
b._rebuild_all_columns()

from procedures import (Differential_Resistance_AUX_map, Resistance_aux_gate_map,
                        RV_dV_dI_sequencer_measurement, RV_R_AUX_sequencer_measurement)

for c in (Differential_Resistance_AUX_map, Resistance_aux_gate_map,
          RV_dV_dI_sequencer_measurement, RV_R_AUX_sequencer_measurement):
    assert c.DATA_COLUMNS, c.__name__
    print(c.__name__, c.DATA_COLUMNS)

assert 'AUX_DC_offset(V)' in Differential_Resistance_AUX_map.DATA_COLUMNS
assert 'AUX_DC_offset(V)' in RV_dV_dI_sequencer_measurement.DATA_COLUMNS
assert 'Auxiliary_Voltage(V)' in Resistance_aux_gate_map.DATA_COLUMNS
assert 'Auxiliary_Voltage(V)' in RV_R_AUX_sequencer_measurement.DATA_COLUMNS
assert 'time(s)' in b.BASE_DATA_COLUMNS

# Parameter rebuild hooks
assert list(Differential_Resistance_AUX_map.aux_source.choices) == ['SRS830_1']
assert list(Resistance_aux_gate_map.smu.choices) == ['Gate_1']

# every proc dict input name must exist as a Parameter on its class
for name, spec in procedures.PROCEDURES.items():
    cls = spec['cls']
    par_names = set(cls().parameter_objects().keys())
    for inp in spec['inputs']:
        assert inp in par_names, f"{name}: missing input parameter '{inp}'"
    for d in spec['displays']:
        assert d in spec['inputs'], f"{name}: display '{d}' not in inputs"

print('ALL_CHECKS_OK')
