"""
Resistance gate sweep measurement procedure.
"""

from .base import *


class Resistance_gate_sweep_measurement(Procedure):
    Title = Parameter(' RV gate sweep ', default='RV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='Insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=1)
    target_voltage = FloatParameter('Target Voltage(V)', default=0)
    step_size = FloatParameter('Step size(mV)', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], default='Gate_1')

    # --- Hardware Selection ---
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

    def smu_choice(self, Gate_name):
        if self.smu == 'Gate_1':
            return Gate_1
        if self.smu == 'Gate_2':
            return Gate_2
        if self.smu == 'smua':
            return Dual_gate.smua
        if self.smu == 'smub':
            return Dual_gate.smub
        log.error("SMU selection not supported")
        raise ValueError("Invalid SMU selected")

    def execute(self):
        log.info(f"starting voltage sweep to {self.target_voltage} V")
        time_0 = time.time()

        Gate = self.smu_choice(self.smu)

        if not Gate.is_output_on():
            log.info(f'{self.smu} output was OFF. Turning it ON.')

            if self.smu in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1,
                                              current=1e-7,
                                              auto_range=False,
                                              compliance_current=1.5e-8)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=35e-9)

            Gate.output_on()
            log.info(f"{self.smu} output turned ON")

        start_volts = Gate.measure__voltage()
        step_v = self.step_size / 1000.0
        if step_v == 0:
            step_v = 0.001
        num_points = int(abs(self.target_voltage - start_volts) / step_v) + 1
        gate_ranges = np.linspace(start_volts, self.target_voltage, num_points)

        log.info(f"Sweeping {self.smu} from {start_volts:.4f}V to {self.target_voltage:.4f}V")

        iteration = 1
        for gate_volt in gate_ranges:
            Gate.ramp_voltage(gate_volt, 2, 0.001)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(gate_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break
        if self.target_voltage == 0:
            log.info(f"Target reached 0V. Turning {self.smu} OFF.")
            Gate.output_off()

    def shutdown(self):
        log.info("Gate sweep measurement finished")


proc_resistance_gate = {
    "Resistance gate sweep measurement": dict(
        cls=Resistance_gate_sweep_measurement,
        category=["Gate Sweep"],
        description="Sweeps a Gate Voltage while measuring Resistance (via Lock-ins).\n"
                    "Supports Keithley 2450 and Dual Gate SMUs (Keithley 2604B).",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet_dilution',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'smu', 'target_voltage', 'step_size',
            'acq_delay',
        ],
        displays=[
            'Title',
            'target_voltage', 'step_size'],
        x=['time(s)'],
        y=['Mixing_chanber(K)', 'SMUa(V)']
    ),
}