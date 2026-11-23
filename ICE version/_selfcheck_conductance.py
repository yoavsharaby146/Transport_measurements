# ponytail: throwaway self-check for the unified dI/dV procedures (delete when done)
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import procedures.base as base
from procedures.base import _rebuild_all_columns, _rebuild_procedure_columns

base.read_temperature = lambda: [0.0, 0.0, 0.0, 0.0]


class FakeLockin:
    def __init__(self):
        self._dc = 0.0
        self._amp = 1e-3
    def snap(self, *a):
        return [1.0, 2.0]
    def read_demod(self):
        return [3.0, 4.0]
    @property
    def dc_offset(self):
        return self._dc
    @dc_offset.setter
    def dc_offset(self, v):
        self._dc = float(v)
    def set_dc_offset(self, v):
        self._dc = float(v)
    @property
    def sine_voltage(self):
        return self._amp
    @property
    def sine_amplitude(self):
        return self._amp
    @property
    def frequency(self):
        return 77.0


class FakeSMU:
    def __init__(self):
        self._v = 0.0
    def measure__voltage(self):
        return self._v
    def measure__current(self): return 0.0
    def is_output_on(self): return True
    def configure_voltage_source(self, **kw): pass
    def output_on(self): pass
    def ramp_voltage(self, v, *a):
        self._v = float(v)


base.magnet = None
base.Dual_gate = None
base.Gate_1 = FakeSMU()
base.Gate_2 = None
base.SRS860_1 = FakeLockin()
base.SRS860_2 = None
base.MFLI_1 = FakeLockin()
base.MFLI_2 = None
base.MFLI_3 = None
base.SRS830_1 = None
base.SRS830_2 = None
base.SRS830_3 = None
base.K6221 = None

import procedures.differential_conductance as dc_mod
dc_mod.read_temperature = lambda: [0.0, 0.0, 0.0, 0.0]

from procedures import (Differential_Conductance, Differential_Conductance_map,
                        PROCEDURES)

_rebuild_all_columns()

# dropdowns rebuilt to connected units
assert list(Differential_Conductance.exc_source.choices) == ['SRS860_1', 'MFLI_1']
assert list(Differential_Conductance.meas_lockin.choices) == ['SRS860_1', 'MFLI_1', 'SRS830_1'] or \
       list(Differential_Conductance.meas_lockin.choices) == ['SRS860_1', 'MFLI_1']  # SRS830_1 not connected
assert list(Differential_Conductance_map.smu.choices) == ['Gate_1']

for cls in (Differential_Conductance, Differential_Conductance_map):
    cols = cls.DATA_COLUMNS
    for c in ('DC_offset(V)', 'AC_voltage_RMS(V)',
              'Differential_Conductance_X(S)', 'Differential_Conductance_Y(S)',
              'Lockin_Current_SRS860_1_X(A)', 'MFLI_Lockin_1_Current_X(A)'):
        assert c in cols, (cls.__name__, c)


def _patch(p):
    p.should_stop = lambda: False
    p.emit = lambda *a, **k: None


# --- single sweep on SRS860 ---
p = Differential_Conductance()
p.exc_source = 'SRS860_1'
p.meas_lockin = 'SRS860_1'
p.use_srs860_1 = True
p.dc_offset_setpoint = 0.004
p.dc_offset_step = 2
p.acq_delay = 0
p.scan_mode = 'Sweep and Return'
p.startup()
_patch(p)
p.execute()
vals = p.getmeas(0.0)
assert len(vals) == len(p.DATA_COLUMNS), (len(vals), len(p.DATA_COLUMNS))
row = dict(zip(p.DATA_COLUMNS, vals))
assert row['Differential_Conductance_X(S)'] == 1.0 / 1e-3, row['Differential_Conductance_X(S)']
assert base.SRS860_1.dc_offset == 0.0  # Sweep and Return ends at the origin
print('unified dI/dV SRS860 sweep OK')

# same procedure, MFLI excitation: G uses MFLI read (3.0/1e-3)
p.exc_source = 'MFLI_1'
p.meas_lockin = 'MFLI_1'
p.use_MFLI_1 = True
p.dc_offset_setpoint = 0.0
p.execute()
row = dict(zip(p.DATA_COLUMNS, p.getmeas(0.0)))
assert row['Differential_Conductance_X(S)'] == 3.0 / 1e-3
print('unified dI/dV MFLI sweep OK')

# --- gate map ---
m = Differential_Conductance_map()
m.exc_source = 'SRS860_1'
m.meas_lockin = 'SRS860_1'
m.use_srs860_1 = True
m.gate_start, m.gate_end, m.gate_step = -0.01, 0.01, 5
m.gate_delay = 0
m.dc_start, m.dc_end = 0.0, 0.004
m.dc_offset_step = 2
m.acq_delay = 0
m.scan_mode = 'Snake'
m.startup()
_patch(m)
m.execute()
vals = m.getmeas(0.0)
assert len(vals) == len(m.DATA_COLUMNS), (len(vals), len(m.DATA_COLUMNS))
print('dI/dV gate map execute OK')

# registration + input coverage
assert 'Differential Conductance (unified)' in PROCEDURES
assert 'Differential Conductance Gate Map' in PROCEDURES
for name, spec in PROCEDURES.items():
    par_names = set(spec['cls']().parameter_objects().keys())
    for inp in spec['inputs']:
        assert inp in par_names, f"{name}: missing input parameter '{inp}'"
    for d in spec['displays']:
        assert d in spec['inputs'], f"{name}: display '{d}' not in inputs"

print('ALL_CHECKS_OK')
