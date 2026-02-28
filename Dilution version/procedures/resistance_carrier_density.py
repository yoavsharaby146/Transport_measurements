"""
Resistance carrier density sweep measurement procedure.
"""

from .base import *


class Resistance_carrier_density_farward_backward_measurement(Procedure):
    Title = Parameter(' Rn measurement', default='Rn')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers ', default='Insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

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

    sweeping = BooleanParameter('Mapping Rn', default=False)

    smu_1 = ListParameter('User defined top gate SMU', default='Gate_1', choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                          group_by='sweeping', group_condition=True)
    smu_2 = ListParameter('User defined bottom gate SMU', default='Gate_2',
                          choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                          group_by='sweeping', group_condition=True)
    displacement = FloatParameter('Displacement field [V/nm]', default=0, group_by='sweeping', group_condition=True,
                                  minimum=-1.1, maximum=1.1)

    top_gate_CNP = FloatParameter("Top gate voltage from CNP [V]", default=0.01, group_by='sweeping', group_condition=True)
    top_capacitance = FloatParameter("Top electrode hBN capacitance [F/m^2] ", default=0.1, group_by='sweeping', group_condition=True)
    bottom_gate_CNP = FloatParameter("Bottom gate voltage from CNP [V]", default=0.01, group_by='sweeping', group_condition=True)
    bottom_capacitance = FloatParameter("Bottom electrode hBN capacitance [F/m^2]", default=0.1, group_by='sweeping', group_condition=True)

    max_carrier = FloatParameter('Maximum induced carrier density (10¹⁶ m⁻²)', default=0.1, group_by='sweeping', group_condition=True)
    min_carrier = FloatParameter('Minimum induced carrier density (10¹⁶ m⁻²)', default=-0.1, group_by='sweeping', group_condition=True)
    carrier_points = IntegerParameter('Number of points for carrier density sweep', default=1, group_by='sweeping', group_condition=True)

    mag_delay = FloatParameter('Delay after Magnetic sweep (s)', default=120, group_by='sweeping', group_condition=True)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=1)

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
        if Gate_name == 'Gate_1': return Gate_1
        if Gate_name == 'Gate_2': return Gate_2
        if Gate_name == 'smua': return Dual_gate.smua
        if Gate_name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {Gate_name}")

    def smu_output(self, Gate, Gate_name):
        if Gate_name in ['Gate_1', 'Gate_2']:
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        else:
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def voltage_list(self, start, end):
        disp = self.displacement * epsilon_0 * 1e9
        v_tg_start = (2 * disp + start * 1e16 * e) / (2 * self.top_capacitance) + self.top_gate_CNP
        v_tg_end = (2 * disp + end * 1e16 * e) / (2 * self.top_capacitance) + self.top_gate_CNP
        v_bg_start = (2.0 * disp - start * 1e16 * e) / (-2.0 * self.bottom_capacitance) + self.bottom_gate_CNP
        v_bg_end = (2.0 * disp - end * 1e16 * e) / (-2.0 * self.bottom_capacitance) + self.bottom_gate_CNP

        top_voltage_list = np.linspace(v_tg_start, v_tg_end, self.carrier_points)
        bottom_voltage_list = np.linspace(v_bg_start, v_bg_end, self.carrier_points)
        return top_voltage_list, bottom_voltage_list

    def execute(self):
        time_0 = time.time()
        top_gate = self.smu_choice(self.smu_1)
        if not top_gate.is_output_on():
            self.smu_output(top_gate, self.smu_1)

        bottom_gate = self.smu_choice(self.smu_2)
        if not bottom_gate.is_output_on():
            self.smu_output(bottom_gate, self.smu_2)

        top_gate_list, bottom_gate_list = self.voltage_list(self.min_carrier, self.max_carrier)

        for i, gate_volt in enumerate(top_gate_list):
            if i == 0 and top_gate.measure__voltage() != gate_volt:
                log.info("Gate voltage ramping to initial value")
                top_gate.voltage_ramping(top_gate_list[0], 2, 0.1)
                bottom_gate.voltage_ramping(bottom_gate_list[0], 2, 0.1)
                time.sleep(60)
            else:
                top_gate.ramp_voltage(top_gate_list[i], 5, 0.1)
                bottom_gate.ramp_voltage(bottom_gate_list[i], 5, 0.1)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * (i + 1) / self.carrier_points)

            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        log.info("Finished measuring")


proc_resistance_carrier_density = {
    "Resistance carrier density sweep measurement": dict(
        cls=Resistance_carrier_density_farward_backward_measurement,
        category=["Gate Sweep"],
        description="Measurement of resistance vs carrier density sweep using two gate sources.\n"
                    "For this measurement the user needs to know the capacitance of each gate and the distance from CNP.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet_dilution',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'sweeping',
            'smu_1', 'smu_2',
            'displacement',
            'top_gate_CNP', 'top_capacitance',
            'bottom_gate_CNP', 'bottom_capacitance',
            'max_carrier', 'min_carrier', 'carrier_points',
            'mag_delay', 'acq_delay',
        ],
        displays=[
            'Title',
            'displacement',
            'max_carrier', 'min_carrier',
        ],
        x='time(s)',
        y=['Mixing_chanber(K)', 'B_z (T)', 'SMUa(V)']
    ),
}