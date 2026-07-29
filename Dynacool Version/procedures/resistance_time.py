"""
Resistance time measurement procedure.
"""
from .base import *
from . import base
class Resistance_time_measurement(Procedure):
    Title = Parameter('Rt measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
    acq_length = IntegerParameter('Acquisition Length (s)', default=3600)
    devices = BooleanParameter('Devices in use',default=False)
    use_magnet = BooleanParameter('Use Magnet',group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1',group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    # --- Metadata Definitions ---
    srs860_1_sine_voltage = Metadata("SRS860_1 sine voltage", default=math.nan)
    srs860_1_frequency = Metadata("SRS860_1 frequency (Hz)", default=math.nan)
    srs860_2_sine_voltage = Metadata("SRS860_2 sine voltage", default=math.nan)
    srs860_2_frequency = Metadata("SRS860_2 frequency (Hz)", default=math.nan)
    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)
    srs830_3_sine_voltage = Metadata("SRS830_3 sine voltage", default=math.nan)
    srs830_3_frequency = Metadata("SRS830_3 frequency (Hz)", default=math.nan)
    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS
    def startup(self):
        # Capture metadata for active instruments
        if self.use_srs860_1:
            self.srs860_1_sine_voltage = SRS860_1.sine_voltage
            self.srs860_1_frequency = SRS860_1.frequency
        if self.use_srs860_2:
            self.srs860_2_sine_voltage = SRS860_2.sine_voltage
            self.srs860_2_frequency = SRS860_2.frequency
        if self.use_srs830_1:
            self.srs830_1_sine_voltage = SRS830_1.sine_voltage
            self.srs830_1_frequency = SRS830_1.frequency
        if self.use_srs830_2:
            self.srs830_2_sine_voltage = SRS830_2.sine_voltage
            self.srs830_2_frequency = SRS830_2.frequency
        if self.use_srs830_3:
            self.srs830_3_sine_voltage = SRS830_3.sine_voltage
            self.srs830_3_frequency = SRS830_3.frequency
    def getmeas(self, t0):
        temperature = read_temperature()
        magnet = base.magnet
        vals = [time.time() - t0]+ list(temperature)
        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan] * 2
        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan] * 2
        if self.use_srs860_1:
            r, th = SRS860_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_srs860_2:
            r, th = SRS860_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_srs830_3:
            r, th = SRS830_3.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_magnet:
            vals += [magnet.getMagneticField()]
        else:
            vals.append(math.nan)
        return vals
    def execute(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)
        # While Loop through until acquisition length is done
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
                'use_srs860_1','use_srs860_2',
                'use_srs830_1','use_srs830_2','use_srs830_3',
                'use_keithley_1','use_keithley_2',
                'acq_delay', 'acq_length',
        ],
        displays=[
            'Title',
            'acq_delay', 'acq_length'],
        x = ['time(s)'],
        y =  ['sample_temp(K)']
    ),
}
