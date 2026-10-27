"""Offline self-check for AMI430.py - run with real hardware disconnected."""
from AMI430 import AMI430


class Fake:
    def __init__(self, replies):
        self.replies = dict(replies)
        self.sent = []

    def write(self, c):
        self.sent.append(c)

    def query(self, c):
        return self.replies[c]


class T(AMI430):
    def __init__(self):
        self.instrument = Fake({
            'FIELD:MEAS?': '-1.234E-03',
            'FIELD:TAR?': 'FIELD:TAR 1.500E+00',
            'RAMPSTATE?': '8',
            'CONF:FIELD:UNITS?': 'TESLA',
            'CONF:RAMP:RATE:FIELD?': 'CONF:RAMP:RATE:FIELD 1.000000E-02,1',
            'PS:EN?': 'PS:EN 1',
            'PERS:SW?': 'PERS:SW 0',
            'CURR:MEAS?': '1.000E+01',
            'VOLT:MEAS?': '2.500E-01',
            '*OPC?': '1',
        })


t = T()
assert abs(t.magnet_field - (-1.234e-3)) < 1e-12
assert t.target_field == 1.5
assert t.ramp_state == 'AT TARGET'
assert t.ramp_state_code == 8
assert t.is_ramping is False
assert t.ramp_rate == 1e-2
assert t.ps_heater is True
assert t.is_persistent is False
assert t.magnet_current == 10.0
assert t.magnet_voltage == 0.25
assert t.field_units == 'TESLA'
t.target_field = 2.0
assert 'FIELD:TAR 2.0' in t.instrument.sent
t.ramp()
assert 'FIELD:RAMP' in t.instrument.sent
t.pause()
assert 'FIELD:PAUSE' in t.instrument.sent
t.zero_field()
assert 'FIELD:ZERO' in t.instrument.sent
print('mock tests OK')
