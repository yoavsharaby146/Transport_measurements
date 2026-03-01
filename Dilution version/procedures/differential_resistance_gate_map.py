"""
Differential resistance gate mapping using Zurich MFLI AUX.
"""

from .base import *

AUX_COLUMNS = ['AUX_DC_offset(V)']


class Differential_Resistance_Gate_map_Zurich(Procedure):
    Title = Parameter('dV/dI sweep measurement', default='dV/dI sweep measurement')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
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

    aux_signal = IntegerParameter('Auxiliary DC Signal ', group_by='use_MFLI_1', default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ", group_by='use_MFLI_1', default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['use_MFLI_1', 'aux_select'],
                                 group_condition=[True, lambda v: v == 11 or v == 13])

    mapping = BooleanParameter('Mapping', default=False)
    scan_mode = ListParameter('Scan Mode', default='Snake', choices=['Snake', 'Forward/Backward', 'Hysteresis'],
                              group_by='mapping', group_condition=True)

    long_delay = FloatParameter('Delay after long ramp (s)', default=60, group_by='mapping', group_condition=True)
    short_delay = FloatParameter('Delay after short ramp (s)', default=5, group_by='mapping', group_condition=True)

    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], group_by='mapping',
                        group_condition=True, default='Gate_1')
    gate_sp1 = FloatParameter('Gate set point 1  voltage(V)', group_by='mapping', group_condition=True, default=-1)
    gate_sp2 = FloatParameter('Gate set point 2  voltage(V)', group_by='mapping', group_condition=True, default=1)
    gate_step = IntegerParameter('Gate Voltage step size (mV)', group_by='mapping', group_condition=True, default=5)

    aux_sp1 = FloatParameter('Auxiliary DC Bias Sp1  (V)', group_by='mapping', group_condition=True, default=0)
    aux_sp2 = FloatParameter('Auxiliary DC Bias Sp2  (V)', group_by='mapping', group_condition=True, default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='mapping', group_condition=True, default=2)

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + AUX_COLUMNS + MAGNET_COLUMNS

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

        if self.use_magnet_dilution:
            dilution.read_magnet()

        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        if self.use_srs860:
            x, y = SRS860.snap("X", "Y")
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]

        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals += list(dilution.read_magnet()) if self.use_magnet_dilution else [math.nan] * 3
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

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure dV/dI bias and gate map sweep measurement")

        Gate = self.smu_choice(self.smu)
        if not Gate.is_output_on():
            self.smu_output(Gate, self.smu)
            log.info("SMU output is now on")
        else:
            log.info("SMU output was on")

        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)

        if self.scan_mode == 'Hysteresis':
            aux_range_1 = self.generate_range(aux_origin, self.aux_sp1, self.aux_step)
            aux_range_2 = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_3 = self.generate_range(self.aux_sp2, aux_origin, self.aux_step)
            full_aux_sweep = np.concatenate([aux_range_1, aux_range_2, aux_range_3])
            pts_per_gate = len(full_aux_sweep)
        elif self.scan_mode == 'Forward/Backward':
            aux_range_1 = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_2 = self.generate_range(self.aux_sp2, self.aux_sp1, self.aux_step)
            full_aux_sweep = np.concatenate([aux_range_1, aux_range_2])
            pts_per_gate = len(full_aux_sweep)
        elif self.scan_mode == 'Snake':
            aux_range_odd = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_even = self.generate_range(self.aux_sp2, self.aux_sp1, self.aux_step)
            pts_per_gate = len(aux_range_even)

        voltage_range = self.generate_range(self.gate_sp1, self.gate_sp2, self.gate_step)
        total = pts_per_gate * len(voltage_range)

        iteration, direction = 1, 1

        log.info("Ramping Gate to Start Position...")
        start_gate_val = Gate.measure__voltage()
        voltage_ramp = self.generate_range(start_gate_val, self.gate_sp1, 2)
        for v in voltage_ramp:
            Gate.ramp_to_voltage(v, 5, 0.01)
            if self.should_stop():
                return
        time.sleep(self.long_delay)

        for volt in voltage_range:
            if iteration != 1:
                Gate.voltage_ramping(volt, 2, 0.001)
                time.sleep(self.short_delay)

            if self.scan_mode == 'Hysteresis':
                if iteration == 1:
                    log.info("Starting Hysteresis measurement...")
                for aux in full_aux_sweep:
                    MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration / total)
                    iteration += 1
                    if self.should_stop():
                        return

            elif self.scan_mode == 'Forward/Backward':
                if iteration == 1:
                    log.info("Starting Forward/Backward measurement...")
                    MFLI_1.aux_ramping(self.aux_signal, self.aux_sp1, 5, 0.1)

                for aux in full_aux_sweep:
                    MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration / total)
                    iteration += 1
                    if self.should_stop():
                        return

            elif self.scan_mode == 'Snake':
                if iteration == 1:
                    log.info("Starting Snake measurement...")
                    MFLI_1.aux_ramping(self.aux_signal, self.aux_sp1, 5, 0.1)

                if direction % 2 == 1:
                    for aux in aux_range_odd:
                        MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                        time.sleep(self.acq_delay)
                        data = self.getmeas(time_0)
                        self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                        self.emit('progress', 100 * iteration / total)
                        iteration += 1
                        if self.should_stop():
                            return
                    direction += 1
                else:
                    for aux in aux_range_even:
                        MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                        time.sleep(self.acq_delay)
                        data = self.getmeas(time_0)
                        self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                        self.emit('progress', 100 * iteration / total)
                        iteration += 1
                        if self.should_stop():
                            return
                        direction += 1

    def shutdown(self):
        log.info("Measurement complete. Instruments are being held at final setpoints.")
        log.info("Procedure shutdown finished.")

proc_differential_resistance_gate_map_zurich = {
    "Differential Resistance Gate Map Zurich": dict(
        cls=Differential_Resistance_Gate_map_Zurich,
        category="Differential Resistance",
        description="2D Gate vs Bias map. Sweeps Auxiliary voltage and performs a gate ramp "
                    "Scan modes (Auxiliary bias sweep at each gate step):\n"
                    "Hysteresis- Origin -> SP1 -> SP2 -> Origin \n"
                    "Forward/Backward - SP1 -> SP2 -> SP1 \n"
                    "Snake - SP1 -> SP2 for odd and SP2 to SP1 for even.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet_dilution',
            'use_MFLI_1',
            'aux_signal', 'aux_select', 'aux_demod',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'mapping',
            'scan_mode', 'smu', 'gate_sp1', 'gate_sp2', 'gate_step',
            'aux_sp1', 'aux_sp2', 'aux_step',
            'long_delay', 'short_delay',
            'acq_delay',
        ],
        displays=[
            'Title', 'scan_mode', 'gate_sp1', 'gate_sp2', 'aux_sp1', 'aux_sp2'
        ],
        x=['Gate_1_voltage(V)'],
        y=['AUX_DC_offset(V)', 'MFLI_Lockin_1_Voltage_X(V)'],
    ),
}