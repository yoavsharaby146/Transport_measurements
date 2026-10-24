import os
assert os.environ.get('QLMG_SIMULATE') == '1'
import time
import procedures
import configuration as cfg
import procedures.base as b
b._rebuild_all_columns()  # GUI does this at launch

# every instrument fake-connected
names = ['Gate_1','Gate_2','Dual_gate','YokoGS200_1','YokoGS200_2','Yoko7651_1',
         'Yoko7651_2','K6221','SRS860_1','SRS860_2','SRS860_3','SRS860_4',
         'SRS830_1','SRS830_2','SRS830_3','MFLI_1','MFLI_2','MFLI_3']
assert all(b._is_connected(getattr(cfg, n, 0)) for n in names)

# all procedures visible (requires gating passes)
hidden = [n for n, spec in procedures.PROCEDURES.items()
          if not spec.get('requires', lambda c: True)(cfg)]
assert not hidden, hidden
print('all', len(procedures.PROCEDURES), 'procedures visible in simulate mode')

# dropdowns full
from procedures.resistance_aux_sweep import _connected_aux_sources
print('smu choices:', len(b._connected_smus()), 'aux sources:',
      len(_connected_aux_sources()))

# fake behavior
f = cfg.K6221
f.source_current = 5e-6
assert float(f.source_current) == 5e-6, 'stored level not read back'
assert list(cfg.SRS830_1.snap('X','Y')) == [0.0, 0.0]
assert float(cfg.Dual_gate.smua.measure__voltage()) == 0.0
assert float(cfg.SRS860_1.sine_voltage) == 0.0

def _patch(p):
    p.should_stop = lambda: False
    p.emit = lambda *a, **k: None


# --- execute the 6221 dV/dI map (tiny ranges, no delays) ---
m = procedures.Differential_Resistance_6221_map()
m.gate_start, m.gate_end, m.gate_step = -0.01, 0.01, 5
m.gate_delay = 0
m.dc_start, m.dc_end = 0.0, 1e-7
m.step_size = 1e-8
m.acq_delay = 0
m.scan_mode = 'Snake'
m.startup()
_patch(m)
m.execute()
print('6221 map execute OK')

# --- execute the AUX dV/dI sweep (SRS830 fake) ---
a = procedures.Differential_Resistance_AUX()
a.aux_Target = 0.01
a.aux_step = 2
a.acq_delay = 0
a.scan_mode = 'Sweep to setpoint'
a.startup()
_patch(a)
a.execute()
print('AUX dV/dI execute OK, aux reads back', float(a._read_aux()))

# --- sequencer: dV/dI branch ---
s = procedures.RV_dV_dI_sequencer_measurement()
s.Type = 'dV/dI'
s.target_current = 1e-7
s.dc_step = 1e-8
s.acq_delay = 0
_patch(s)
s.execute()
print('sequencer dV/dI branch OK')

print('SIMULATE_TEST_OK')