"""
Resistance time measurement procedure.
"""

from .base import *


class Resistance_time_measurement(Procedure):

    Title = Parameter('Rt measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
    acq_length = IntegerParameter('Acquisition Length (s)', default=3600)

    devices = BooleanParameter('Devices in use', default=False)
    use_magnet_dilution = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Metadata Definitions ---
    srs860_sine_voltage = Metadata("SRS860 sine voltage", default=math.nan)
    srs860_frequency = Metadata("SRS860 frequency (Hz)", default=math.nan)

    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)

    MFLI_1_sine_voltage = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_1_bias = Metadata("MFLI_1 bias offset(V)", default=math.nan)
    MFLI_1_aux = Metadata("MFLI_1 aux output", default=math.nan)

    MFLI_2_sine_voltage = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency = Metadata("MFLI_2 frequency (Hz)", default=math.nan)

    MFLI_3_sine_voltage = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency = Metadata("MFLI_3 frequency (Hz)", default=math.nan)

    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS

    def startup(self):
        # Capture metadata for active instruments
        if self.use_srs860:
            self.srs860_sine_voltage = SRS860.sine_voltage
            self.srs860_frequency = SRS860.frequency

        if self.use_MFLI_1:
            self.MFLI_1_sine_voltage = MFLI_1.sine_amplitude
            self.MFLI_1_frequency = MFLI_1.frequency
            self.MFLI_1_bias = MFLI_1.dc_offset
            self.MFLI_1_aux = MFLI_1.get_auxout()

        if self.use_MFLI_2:
            self.MFLI_2_sine_voltage = MFLI_2.sine_amplitude
            self.MFLI_2_frequency = MFLI_2.frequency
        if self.use_MFLI_3:
            self.MFLI_3_sine_voltage = MFLI_3.sine_amplitude
            self.MFLI_3_frequency = MFLI_3.frequency

        if self.use_srs830_1:
            self.srs830_1_sine_voltage = SRS830_1.sine_voltage
            self.srs830_1_frequency = SRS830_1.frequency
        if self.use_srs830_2:
            self.srs830_2_sine_voltage = SRS830_2.sine_voltage
            self.srs830_2_frequency = SRS830_2.frequency

    def getmeas(self, t0):
        temperature = dilution.get_temperature(8)
        vals = [time.time() - t0, temperature]

        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan] * 2

        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan] * 2

        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1),
                          (self.use_MFLI_2, MFLI_2),
                          (self.use_MFLI_3, MFLI_3)]:
            if use:
                vals += list(inst.read_demod())
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

        if self.use_magnet_dilution:
            vals += list(dilution.read_magnet())
        else:
            vals += [math.nan] * 3

        return vals

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


proc_resistance_time = {
    "Resistance time measurement": dict(
        cls=Resistance_time_measurement,
        category=["Time-based"],
        description="Measurement of resistance over a specified time period.\n"
                    "Monitors temperature, magnetic field, and various lock-in amplifier readings.",
        inputs=[
            'Title', 'Resistor', 'Contacts',
            'devices',
            'use_magnet_dilution',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'acq_delay', 'acq_length',
        ],
        displays=[
            'Title',
            'acq_delay', 'acq_length'],
        x=['time(s)'],
        y=['Mixing_chanber(K)']
    ),
}