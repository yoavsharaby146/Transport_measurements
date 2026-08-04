"""
Resistance two gate mapping measurement procedure.
"""

from .base import *
from . import base


class Resistance_two_gate_mapping_measurement(ICEProcedure):
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
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
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

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0)

    def execute(self):
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
            # To avoid voltage spikes, ramp slower for larger slow gate steps sizes.
            #  Threshold of 50 mV is arbitrary and can be adjusted based on the specific device and requirements.
            if self.slow_step > 50:
                slow_gate.voltage_ramping(slow_v, 2, 0.001)
            else:
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
        category=["2D Mapping", "Gate Sweep"],
        description="2D Resistance Map with Selectable Scan Mode.\n"
                    "1. Snake: Alternates direction every row (Start->End, End->Start). Fastest.\n"
                    "2. Forward/Backward: Sweeps both directions (Start->End AND End->Start) at every row. Use for hysteresis.\n",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
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
