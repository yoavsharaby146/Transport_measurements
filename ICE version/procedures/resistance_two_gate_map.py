"""
Resistance two gate mapping measurement procedure.
"""

from .base import *
from . import base



class Resistance_two_gate_mapping_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('RVV measurement', default='RVV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers', default='Insert contact numbers')
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

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping', default=True)

    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    slow_smu = ListParameter('Slow Axis SMU', default='Gate_1', group_by='mapping', group_condition=True,
                             choices=['Gate_1', 'Gate_2', 'smua', 'smub'])
    slow_start = FloatParameter('Slow Start (V)', default=-1, group_by='mapping', group_condition=True)
    slow_end = FloatParameter('Slow End (V)', default=1, group_by='mapping', group_condition=True)
    slow_step = FloatParameter('Slow Step (mV)', default=10, group_by='mapping', group_condition=True)
    long_delay = FloatParameter('Slow Axis Delay (s)', default=1.0, group_by='mapping', group_condition=True)

    fast_smu = ListParameter('Fast Axis SMU', default='Gate_2', group_by='mapping', group_condition=True,
                             choices=['Gate_1', 'Gate_2', 'smua', 'smub'])
    fast_start = FloatParameter('Fast Start (V)', default=-2, group_by='mapping', group_condition=True)
    fast_end = FloatParameter('Fast End (V)', default=2, group_by='mapping', group_condition=True)
    fast_step = FloatParameter('Fast Step (mV)', default=5, group_by='mapping', group_condition=True)
    short_delay = FloatParameter('Fast Axis Delay (s)', default=0.1, group_by='mapping', group_condition=True)

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
        magnet = base.magnet
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

    def smu_choice(self, name):
        if name == 'Gate_1': return Gate_1
        if name == 'Gate_2': return Gate_2
        if name == 'smua': return Dual_gate.smua
        if name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {name}")

    def smu_output(self, Gate, name):
        if not Gate.is_output_on():
            log.info(f"{name} output was OFF. Turning it ON.")
            if name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_mv):
        step_v = abs(step_mv / 1000.0)
        if step_v == 0: step_v = 0.001
        num_points = int(abs(end - start) / step_v) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        magnet = base.magnet
        time_0 = time.time()
        slow_gate = self.smu_choice(self.slow_smu)
        fast_gate = self.smu_choice(self.fast_smu)

        if self.slow_smu == self.fast_smu:
            log.error("Slow and Fast SMUs cannot be the same!")
            return

        self.smu_output(slow_gate, self.slow_smu)
        self.smu_output(fast_gate, self.fast_smu)

        slow_range = self.generate_range(self.slow_start, self.slow_end, self.slow_step)
        fast_range_forward = self.generate_range(self.fast_start, self.fast_end, self.fast_step)
        fast_range_backward = fast_range_forward[::-1]

        points_per_line = len(fast_range_forward)
        if self.scan_mode == 'Forward/Backward':
            points_per_line *= 2
        total_points = len(slow_range) * points_per_line
        point_counter = 0

        log.info(f"Moving to start: Slow={self.slow_start}V, Fast={self.fast_start}V")
        slow_gate.voltage_ramping(self.slow_start, 2, 0.001)
        if self.should_stop():
            log.warning("User stopped measurement during initial slow SMU ramp")
            return
        time.sleep(self.long_delay)

        fast_gate.voltage_ramping(self.fast_start, 2, 0.001)
        if self.should_stop():
            log.warning("User stopped measurement during initial fast SMU ramp")
            return
        log.info(f"Stabilizing before {self.scan_mode} sweep...")
        time.sleep(self.long_delay)

        for i, slow_v in enumerate(slow_range):
            slow_gate.ramp_voltage(slow_v, 5, 0.001)
            time.sleep(self.short_delay)

            if self.scan_mode == 'Snake':
                current_range = fast_range_forward if i % 2 == 0 else fast_range_backward
                for fast_v in current_range:
                    fast_gate.ramp_voltage(fast_v, 5, 0.001)
                    time.sleep(self.short_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

            elif self.scan_mode == 'Forward/Backward':
                for fast_v in fast_range_forward:
                    fast_gate.ramp_voltage(fast_v, 5, 0.001)
                    time.sleep(self.short_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

                for fast_v in fast_range_backward:
                    fast_gate.ramp_voltage(fast_v, 2, 0.001)
                    time.sleep(self.short_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
        log.info(f"Finished measuring {self.scan_mode} 2D mapping")


proc_resistance_two_gate_map = {
"Resistance two gate mapping measurement": dict(
        cls=Resistance_two_gate_mapping_measurement,
        category=["2D Mapping", "Gate Sweep", "Keithley 2450"],
        description="2D Resistance Map with Selectable Scan Mode.\n"
                    "1. Snake: Alternates direction every row (Start->End, End->Start). Fastest.\n"
                    "2. Forward/Backward: Sweeps both directions (Start->End AND End->Start) at every row. Use for hysteresis.\n",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'mapping',
            'scan_mode',
            'slow_smu', 'slow_start', 'slow_end', 'slow_step', 'long_delay',
            'fast_smu', 'fast_start', 'fast_end', 'fast_step', 'short_delay',
        ],
        displays=[
            'Title', 'scan_mode',
            'slow_start', 'slow_end', 'slow_step', 'slow_smu',
            'fast_start', 'fast_end', 'fast_step', 'fast_smu'
        ],
        x=['time(s)'],
        y=['probe_temp(K)', 'SMUa(V)'],
    ),
}
