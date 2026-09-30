"""Offline check: dynamic columns + getmeas with fake instruments."""
import instruments_config as icfg
import Dilution_procedure_base as base
import Rt_procedure, RV_procedure, R_AUX_procedure, RH_procedure


class FakeLockin(object):
    def snap(self, *a):
        return (1.0, 2.0)


class FakeGate(object):
    def measure__voltage(self):
        return 0.1

    def measure__current(self):
        return 1e-9


class FakeDil(object):
    def get_temperature(self, thermometer_num):
        return 0.01

    def read_magnet(self):
        return (0.0, 0.0, 0.0)


RtCls = Rt_procedure.Resistance_time_measurement
AuxCls = R_AUX_procedure.Resistance_Aux_voltage_measurement

# nothing connected -> time only
assert RtCls.DATA_COLUMNS == ['time(s)'], RtCls.DATA_COLUMNS

# inject fakes, rebuild
icfg.SRS860_1 = FakeLockin()
icfg.SRS830_1 = FakeLockin()
icfg.SRS830_2 = FakeLockin()
icfg.Gate_1 = FakeGate()
icfg.Dilution = FakeDil()
base.rebuild_all()

expected = ['time(s)', 'Mixing_chanber(K)',
            'Gate_1_voltage(V)', 'Gate_1_Leakage(A)',
            'Lockin_Voltage_SRS860_1_X(V)', 'Lockin_Voltage_SRS860_1_Y(V)',
            'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
            'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
            'B_x (T)', 'B_y (T)', 'B_z (T)']
assert RtCls.DATA_COLUMNS == expected, RtCls.DATA_COLUMNS

# magnet temperature only on RH (magnet-field measurement)
RHCls = RH_procedure.Resistance_Magnet_field_measurement
rhcols = list(RHCls.DATA_COLUMNS)
assert 'Magnet Temperature(K)' not in RtCls.DATA_COLUMNS
assert rhcols[1:3] == ['Mixing_chanber(K)', 'Magnet Temperature(K)'], rhcols

# AUX mid column sits between SMU and lock-in columns
auxcols = list(AuxCls.DATA_COLUMNS)
assert auxcols[4] == 'Auxiliary_Voltage(V)', auxcols


def bind(p):
    p.Dilution = icfg.Dilution
    p.SRS860_1 = icfg.SRS860_1
    p.SRS860_2 = None
    p.SRS830_1 = icfg.SRS830_1
    p.SRS830_2 = icfg.SRS830_2
    p.SRS830_3 = None
    p.Gate_1 = icfg.Gate_1
    p.Gate_2 = None
    p.Dual_gate = None


p = RtCls()
bind(p)
vals = p.getmeas(0)
assert len(vals) == len(expected), (len(vals), len(expected))
assert vals[-3:] == [0.0, 0.0, 0.0]  # magnet columns last (RH relies on this)

ph = RHCls()
bind(ph)
vh = ph.getmeas(0)
assert len(vh) == len(rhcols), (len(vh), len(rhcols))

pa = AuxCls()
bind(pa)
setattr(pa.SRS860_1, 'dac1', 0.5)
va = pa.getmeas(0, 1)
assert len(va) == len(auxcols), (len(va), len(auxcols))
assert va[4] == 0.5

# RV smu_choice from base
pv = RV_procedure.Resistance_gate_voltage_measurement()
bind(pv)
assert pv.smu_choice('Gate_1') is pv.Gate_1

# magnet readout toggle: off -> no B columns, no B reads
icfg.MAGNET_ENABLED = False
base.rebuild_all()
assert RtCls.DATA_COLUMNS == expected[:-3], RtCls.DATA_COLUMNS
v2 = p.getmeas(0)
assert len(v2) == len(expected) - 3, len(v2)
icfg.MAGNET_ENABLED = True
base.rebuild_all()

print('columns self-check OK')
