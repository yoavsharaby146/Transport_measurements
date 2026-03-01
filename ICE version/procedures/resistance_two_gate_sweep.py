"""
Resistance two gate sweep measurement procedure.
"""

from .base import *


class Resistance_two_gate_scan_sweep_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('Rn or RD measurement', default='Rn')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers ', default='Insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Sweep Configuration ---
    sweeping = BooleanParameter('Sweeping Configuration', default=True)

    # Gate 1 Settings
    smu_1 = ListParameter('Top Gate SMU', default='Gate_1',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='sweeping', group_condition=True)
    smu_1_sp1 = FloatParameter('Top Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_1_sp2 = FloatParameter('Top Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)

    # Gate 2 Settings
    smu_2 = ListParameter('Bottom Gate SMU', default='Gate_2',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='sweeping', group_condition=True)
    smu_2_sp1 = FloatParameter('Bottom Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_2_sp2 = FloatParameter('Bottom Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)

    smu_points = IntegerParameter('Number of Points', default=50, group_by='sweeping', group_condition=True)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

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
        if self.use_magnet:
            magnet.magnet_field_write_query()

        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

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

        if self.use_magnet:
            vals.append(magnet.magnet_field_read_response())
        else:
            vals.append(math.nan)

        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1': return Gate_1
        if Gate_name == 'Gate_2': return Gate_2
        if Gate_name == 'smua': return Dual_gate.smua
        if Gate_name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {Gate_name}")

    def smu_output(self, Gate, Gate_name):
        if not Gate.is_output_on():
            log.info(f"{Gate_name} output was OFF. Turning it ON.")
            if Gate_name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def execute(self):
        time_0 = time.time()
        top_gate = self.smu_choice(self.smu_1)
        bottom_gate = self.smu_choice(self.smu_2)

        if self.smu_1 == self.smu_2:
            log.error("Top Gate and Bottom Gate cannot be the same SMU!")
            return

        self.smu_output(top_gate, self.smu_1)
        self.smu_output(bottom_gate, self.smu_2)

        top_gate_list = np.linspace(self.smu_1_sp1, self.smu_1_sp2, self.smu_points)
        bottom_gate_list = np.linspace(self.smu_2_sp1, self.smu_2_sp2, self.smu_points)

        log.info(f"Moving to Start: Top={self.smu_1_sp1}V, Bottom={self.smu_2_sp1}V")
        top_gate.voltage_ramping(top_gate_list[0], 2, 0.1)
        log.info(f"Top ramped to {self.smu_1_sp1}V")
        bottom_gate.voltage_ramping(bottom_gate_list[0], 2, 0.1)
        log.info(f"Bottom ramped to {self.smu_2_sp1}V")

        time.sleep(30)

        for i in range(self.smu_points):
            top_gate.ramp_voltage(top_gate_list[i], 5, 0.05)
            bottom_gate.ramp_voltage(bottom_gate_list[i], 5, 0.05)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * i / self.smu_points)

            if self.should_stop():
                log.warning("Sweep stopped by user.")
                break

    def shutdown(self):
        log.info("Finished measuring two gate sweep")


proc_resistance_two_gate_sweep = {
"Resistance two gate sweep measurement": dict(
        cls=Resistance_two_gate_scan_sweep_measurement,
        category=["Gate Sweep"],
    description="Sweeps two gates simultaneously along a line defined by Start/End points for each gate.\n"
                "Useful for Carrier Density/Displacement Field scans.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'sweeping',
            'smu_1', "smu_1_sp1", "smu_1_sp2",
            'smu_2', "smu_2_sp1", "smu_2_sp2",
            'smu_points', 'acq_delay',
        ],
        displays=[
            'Title',
            'smu_1', "smu_1_sp1", "smu_1_sp2",
            'smu_2', "smu_2_sp1", "smu_2_sp2",
            'smu_points',
        ],
        x='time(s)',
        y=['probe_temp(K)', 'SMUa(V)']
    ),
}