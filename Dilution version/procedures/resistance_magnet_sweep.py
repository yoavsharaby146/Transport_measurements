"""
Resistance magnet sweep measurement procedure.
"""

from .base import *


class Resistance_magnet_sweep_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('RH measurement', default='RH')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')

    Target_field = FloatParameter('Target field (T)', group_by='use_magnet_dilution', default=0)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.5)

    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
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

    # --- Metadata ---
    srs860_sine_voltage = Metadata("SRS860 sine voltage", default=math.nan)
    srs860_frequency = Metadata("SRS860 frequency (Hz)", default=math.nan)
    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)
    MFLI_1_sine_voltage = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_2_sine_voltage = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency = Metadata("MFLI_2 frequency (Hz)", default=math.nan)
    MFLI_3_sine_voltage = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency = Metadata("MFLI_3 frequency (Hz)", default=math.nan)

    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS

    def startup(self):
        if self.use_srs860:
            self.srs860_sine_voltage = SRS860.sine_voltage
            self.srs860_frequency = SRS860.frequency
        if self.use_MFLI_1:
            self.MFLI_1_sine_voltage = MFLI_1.sine_amplitude
            self.MFLI_1_frequency = MFLI_1.frequency
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

        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        vals += list(SRS860.snap("X", "Y")) if self.use_srs860 else [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        if self.use_magnet_dilution:
            vals += list(dilution.read_magnet())
        else:
            vals += [math.nan] * 3

        return vals

    def execute(self):
        if not self.use_magnet_dilution:
            log.warning("Magnet was not chosen measurement aborted")
            return
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla", self.Target_field)
        
        current_field = dilution.read_magnet()[2]  # B_z component
        
        origin_field = current_field
        dilution.set_magnet_field(self.Target_field)

        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0

        while abs(current_field - self.Target_field) > 0.003:
            data = self.getmeas(time_0)
            current_field = data[-1]  # Last column is B_z
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))

            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                break
        log.info("Magnetic field Reached!")

    def shutdown(self):
        if self.use_magnet_dilution:
            current_field = dilution.read_magnet()[2]
            if abs(current_field - self.Target_field) > 0.003:
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")

proc_resistance_magnet = {
    "Resistance magnet sweep measurement": dict(
        cls=Resistance_magnet_sweep_measurement,
        category="Magnetic Field",
        description="Measurement of resistance vs magnetic field sweep.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet_dilution', 'Target_field',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'acq_delay',
        ],
        displays=[
            'Title',
            'Target_field'],
        x=['time(s)'],
        y=['Mixing_chanber(K)', 'B_z (T)'],
    ),
}