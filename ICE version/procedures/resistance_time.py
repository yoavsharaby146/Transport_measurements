"""
Resistance time measurement procedure.
"""

from .base import *
from . import base


class Resistance_time_measurement(ICEProcedure):

    Title = Parameter('Rt measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
    acq_length = IntegerParameter('Acquisition Length (s)', default=3600)

    devices = BooleanParameter('Devices in use',default=False)
    use_magnet = BooleanParameter('Use Magnet',group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1',group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1',group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and _is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0)

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)

        current_time = 0.0

        while current_time < self.acq_length:
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress',100 * data[0]/self.acq_length)
            current_time = data[0]
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Measurement stopped")
                break

    def shutdown(self):
        log.info("Finished measuring")


proc_resistance_time = {
"Resistance time measurement": dict(
        cls=Resistance_time_measurement,
        category=["Time-based","Keithley 2450"],
        description="Measurement of resistance over a specified time period.\n"
                    "Monitors temperature,magnetic field, and various lock-in amplifier readings.",
        inputs=[
                'Title','Resistor','Contacts',
                'devices',
                'use_magnet',
                'use_MFLI_1' ,'use_MFLI_2','use_MFLI_3',
                'use_srs860_1','use_srs860_2',
                'use_srs830_1','use_srs830_2','use_srs830_3',
                'use_dual_gate','use_keithley_1','use_keithley_2',
                'acq_delay', 'acq_length',
        ],
        displays=[
            'Title',
            'acq_delay', 'acq_length'],
        x = ['time(s)'],
        y =  ['probe_temp(K)', 'VTI_temp(K)']
    ),
}