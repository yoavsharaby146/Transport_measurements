"""
Differential Resistance Zurich Measurement.

dV/dI measurement using MFLI aux for DC current.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature,
)


class Differential_Resistance_Zurich(Procedure):
    # --- Parameters ---
    Title = Parameter('dV/dI sweep measurement', default='dV/dI sweep measurement')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Sweep Parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target  (V)', group_by='use_MFLI_1', default=0)
    aux_signal = IntegerParameter('Auxiliary DC Signal ', group_by='use_MFLI_1', default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ", group_by='use_MFLI_1', default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['use_MFLI_1', 'aux_select'],
                                 group_condition=[True, lambda v: v == 11 or v == 13])
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='use_MFLI_1', default=2)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.magnet_field_write_query()

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

        vals.append(magnet.magnet_field_read_response() if self.use_magnet else math.nan)
        return vals

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0:
            step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)
        target_aux = self.aux_Target
        log.info(f"Starting dV/dI {self.scan_mode}. Start={aux_origin:.4f}V, Target={target_aux:.4f}V")

        range_to_target = self.generate_range(aux_origin, target_aux, self.aux_step)
        range_return = self.generate_range(target_aux, aux_origin, self.aux_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        log.info("Sweeping to Setpoint...")
        for aux in range_to_target:
            MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * point_counter / total_points)
            point_counter += 1
            if self.should_stop():
                log.warning("User stopped measurement while in Sweep")
                return

        if self.scan_mode == 'Sweep and Return':
            log.info("Returning to Origin...")
            for aux in range_return:
                MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                time.sleep(self.acq_delay)
                data = self.getmeas(time_0)
                self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                self.emit('progress', 100 * point_counter / total_points)
                point_counter += 1
                if self.should_stop():
                    log.warning("User stopped measurement while in return Sweep")
                    return

    def shutdown(self):
        log.info("Finished measuring")


proc_differential_resistance_Zurich = {
    "Differential Resistance Zurich": dict(
        cls=Differential_Resistance_Zurich,
        category="Differential Resistance",
        description="dV/dI Sweep starting from Origin DC AUX using MFLI_1.\n"
                    "1. Sweep to Setpoint: Measures from [Origin] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Origin] -> [Target] -> [Origin]. Returns voltage to start.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'acq_delay',
            'devices',
            'use_magnet',
            'use_MFLI_1',
            'aux_Target', 'aux_step', 'aux_signal', 'aux_select', 'aux_demod',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'scan_mode',
        ],
        displays=[
            'Title', 'scan_mode', 'aux_Target'],
        x=['AUX_DC_offset(V)'],
        y=['MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)'],
    ),
}