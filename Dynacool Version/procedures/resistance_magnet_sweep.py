"""
Resistance magnet sweep measurement procedure.
"""
from .base import *
from . import base
class Resistance_magnet_sweep_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('RH measurement', default='RH')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')
    Target_field = FloatParameter('Target field (T)', group_by='use_magnet', default=0)
    sweep_rate = FloatParameter('Sweep rate (T/min)', group_by='use_magnet', default=0.1)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.5)
    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    # --- Metadata ---
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
        magnet = base.magnet
        # 1. Temperature & Time
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)
        # 3. Keithleys
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2
        # 4. Lock-ins
        vals += list(SRS860_1.snap("X", "Y")) if self.use_srs860_1 else [math.nan] * 2
        vals += list(SRS860_2.snap("X", "Y")) if self.use_srs860_2 else [math.nan] * 2
        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2), (self.use_srs830_3, SRS830_3)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2
        # 6. Magnet Read (Last Column)
        if self.use_magnet:
            vals.append(magnet.getMagneticField())
        else:
            vals.append(math.nan)
        return vals
    def execute(self):
        magnet = base.magnet
        if self.use_magnet == False:
            log.warning("Magnet was not chosen measurement aborted")
            return
        # PPMS firmware manages ramp safety; no per-range limits or persistent
        # switch heater like the Cryomagnetics supply.
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla at %g T/min",
                 self.Target_field, self.sweep_rate)
        origin_field = magnet.getMagneticField()
        magnet.go_to_target_field(self.Target_field, self.sweep_rate)
        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero
        current_field = origin_field
        # --- Monitoring Loop ---
        while abs(current_field - self.Target_field) > 0.003:
            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                return
        log.info("Magnetic field Reached!")
    def shutdown(self):
        magnet = base.magnet
        if self.use_magnet == True:
            current_field = magnet.getMagneticField()
            if abs(current_field - self.Target_field) > 0.003:
                magnet.pause_field()
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")
proc_resistance_magnet = {
"Resistance magnet sweep measurement": dict(
        cls=Resistance_magnet_sweep_measurement,
        category="Magnetic Field",
        description="Measurement of resistance vs magnetic field sweep.",
        inputs=[
                'Title','Resistor','Contacts','Gate_contacts',
                'devices',
                'use_magnet','Target_field','sweep_rate',
                'use_srs860_1','use_srs860_2',
                'use_srs830_1','use_srs830_2','use_srs830_3',
                'use_keithley_1','use_keithley_2',
                'acq_delay',
        ],
        displays=[
            'Title',
            'Target_field'],
        x=['time(s)'],
        y=['sample_temp(K)','field(T)'],
    ),
}
