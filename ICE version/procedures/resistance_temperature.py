"""
Resistance vs temperature-control measurement procedure.

Measures resistance over time while (optionally) driving the on-screen
LabVIEW temperature control (temperature_control.py in the ICE version
root): sets Set Point, Ramp Rate and Heater Range at startup, and logs
the LabVIEW set point, actual panel temperature and heater range with
every data point.

Note: in coords (OCR) mode each LabVIEW read takes ~0.5 s, so keep
acq_delay >= 1 s. UIA mode is much faster.
"""

from .base import *
from . import base

import os
import sys

# temperature_control.py lives in the ICE version root (parent of procedures/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import temperature_control as tctrl


class Resistance_temperature_measurement(ICEProcedure):

    # Extra columns inserted between the SMU and lock-in sections
    _MID_COLUMNS = ['LabVIEW_SetPoint(K)', 'LabVIEW_Temp(K)', 'LabVIEW_Heater']

    Title = Parameter('Rt measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    change_temperature = BooleanParameter('Change temperature (LabVIEW)',
                                          default=False)
    target_temp = FloatParameter('Target Temperature (K)', default=300,
                                 group_by='change_temperature')
    ramp_rate = FloatParameter('Ramp Rate (K/min)', default=5,
                               group_by='change_temperature')
    heater_range = ListParameter('Heater Range',
                                 choices=['off', 'low', 'medium', 'high'],
                                 default='off',
                                 group_by='change_temperature')

    devices = BooleanParameter('Devices in use', default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    acq_delay = FloatParameter('Acquisition Delay (s)', default=2)
    acq_length = IntegerParameter('Acquisition Length (s)', default=3600)

    def startup(self):
        self._capture_metadata()
        self._tctrl_cfg = None
        if self.change_temperature:
            self._tctrl_cfg = tctrl.require_config()
            try:
                tctrl.write_field(self._tctrl_cfg, 'target', self.target_temp)
                tctrl.write_field(self._tctrl_cfg, 'ramp', self.ramp_rate)
                tctrl.set_heater_output(self._tctrl_cfg,
                                        str(self.heater_range).lower())
                readback = float(tctrl.read_field(self._tctrl_cfg, 'target'))
                if abs(readback - self.target_temp) > \
                        max(0.1, abs(self.target_temp) * 1e-3):
                    raise RuntimeError(
                        "Set Point did not take (read back %s K)" % readback)
                log.info("LabVIEW set point %.3f K, ramp %.3f K/min, "
                         "heater range %s",
                         readback, self.ramp_rate, self.heater_range)
            except Exception:
                log.exception("LabVIEW temperature control failed at startup")
                raise

    def _read_labview(self):
        """[set point, actual temp, heater range] from the LabVIEW panel."""
        if self._tctrl_cfg is None:
            return [math.nan, math.nan, '']
        vals = []
        for field in ('target', 'temp'):
            try:
                vals.append(float(tctrl.read_field(self._tctrl_cfg, field)))
            except Exception as exc:
                log.warning("LabVIEW read of '%s' failed: %s", field, exc)
                vals.append(math.nan)
        try:
            vals.append(tctrl.read_heater(self._tctrl_cfg))
        except Exception as exc:
            log.warning("LabVIEW heater read failed: %s", exc)
            vals.append('')
        return vals

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0, mid_extras=self._read_labview())

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)

        current_time = 0.0

        while current_time < self.acq_length:
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * data[0] / self.acq_length)
            current_time = data[0]
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Measurement stopped")
                break

    def shutdown(self):
        log.info("Finished measuring")


proc_resistance_temperature = {
"Resistance temperature measurement": dict(
        cls=Resistance_temperature_measurement,
        category=["Time-based", "Temperature"],
        description="Resistance vs time while the on-screen LabVIEW "
                    "temperature control sets Set Point, Ramp Rate and "
                    "Heater Range.\n"
                    "Logs LabVIEW set point, actual panel temperature and "
                    "heater range with every point.",
        inputs=[
                'Title', 'Resistor', 'Contacts',
                'change_temperature', 'target_temp', 'ramp_rate',
                'heater_range',
                'devices',
                'use_magnet',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'acq_delay', 'acq_length',
        ],
        displays=[
            'Title',
            'change_temperature', 'target_temp', 'ramp_rate', 'heater_range',
            'acq_delay', 'acq_length'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}
