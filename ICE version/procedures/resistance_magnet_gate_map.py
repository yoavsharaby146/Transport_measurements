"""
Resistance Magnet and Gate Mapping Measurement.

2D mapping using Magnetic field and SMU gate voltage.
"""

from .base import *
from . import base


class Resistance_magnet_and_gate_mapping_measurement(ICEProcedure):
    # --- Parameters ---
    Title = Parameter(' RHV measurement', default='RHV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers ', default='Insert contact numbers')
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
    mapping = BooleanParameter('Mapping RHV', default=True)
    line_transition = BooleanParameter('Document between gate sweeps', default=False, group_by='mapping', group_condition=True)
    scan_mode = ListParameter('Gate Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    smu = ListParameter('User defined SMU', default='Gate_1', choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                        group_by='mapping', group_condition=True)
    gate_start = FloatParameter('Gate min voltage(V)', default=-1, group_by='mapping', group_condition=True)
    gate_end = FloatParameter('Gate max voltage(V)', default=1, group_by='mapping', group_condition=True)
    gate_step = FloatParameter('Gate Voltage step size (mV)', default=5, group_by='mapping', group_condition=True)

    field_start = FloatParameter('Magnetic field start (T)', default=0, group_by='mapping', group_condition=True)
    field_end = FloatParameter('Magnetic field end (T)', default=1, group_by='mapping', group_condition=True)
    field_step = FloatParameter('Magnetic field step size (mT)', default=50, group_by='mapping', group_condition=True)

    mag_delay = FloatParameter('Delay after Magnetic sweep (s)', default=120, group_by='mapping', group_condition=True)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0)

    def execute(self):
        magnet = base.magnet
        time_0 = time.time()

        # SMU handling
        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        # 1. Generate Sweep Arrays
        field_range = self.generate_range(self.field_start, self.field_end, self.field_step)
        gate_range_fwd = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        gate_range_bwd = gate_range_fwd[::-1]

        # 2. Magnet Safety Check
        if magnet.persistent_switch_heater == '0':
            magnet.persistent_switch_heater = 'ON'
            log.info("Persistent switch heater turned ON. Delaying 10min.")
            time.sleep(600)

        # 3. Initial Ramping (Start positions)
        log.info(f"Moving to Initial Position: Field={self.field_start}T, Gate={self.gate_start}V")
        magnet.go_to_target_field(self.field_start)
        # We wait for magnet to reach start while taking data
        while abs(magnet.magnet_field - self.field_start) > 0.003:
            if self.should_stop():
                magnet.sweep_mode = 'PAUSE'
                log.warning("User stopped measurement during initial magnet sweep, magnet is Paused")
                return
            if self.line_transition:
                self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                time.sleep(self.acq_delay)
        gate.voltage_ramping(self.gate_start, 2, 0.1)
        if self.should_stop():
            log.warning("User stopped measurement during initial gate ramping")
            return
        time.sleep(self.mag_delay)

        # 4. Main Loop
        iteration = 1
        total_steps = len(field_range) * len(gate_range_fwd) * (2 if self.scan_mode == 'Forward/Backward' else 1)
        for i, field in enumerate(field_range):
            # Move Field (skip wait on first iteration if already there)
            if i > 0:
                magnet.go_to_target_field(field)
                while abs(magnet.magnet_field - field) > 0.003:
                    if self.should_stop():
                        magnet.sweep_mode = 'PAUSE'
                        log.warning("User stopped measurement during  magnet ramp, magnet is Paused")
                        return
                    if self.line_transition:
                        self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                        time.sleep(self.acq_delay)
                log.info(f"Field at {field}T. Stabilizing...")
                time.sleep(self.mag_delay)

            # Define Gate logic
            # --- CASE 1: SNAKE MODE ---
            if self.scan_mode == 'Snake':
                current_gate_range = gate_range_fwd if i % 2 == 0 else gate_range_bwd
                for g_volt in current_gate_range:
                    gate.ramp_voltage(g_volt, 5, 0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

            # --- CASE 2: FORWARD/BACKWARD MODE ---
            elif self.scan_mode == 'Forward/Backward':
                log.info("Forward/Backward scanning")
                # Part A: Forward
                for g_volt in gate_range_fwd:
                    gate.ramp_voltage(g_volt, 5, 0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                # Part B: Backward
                for g_volt in gate_range_bwd:
                    gate.ramp_voltage(g_volt, 5, 0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
        magnet = base.magnet
        magnet.sweep_mode = 'PAUSE'
        log.info("Finished measuring")


proc_resistance_magnet_gate_map = {
"Resistance magnet and gate mapping measurement": dict(
        cls=Resistance_magnet_and_gate_mapping_measurement,
        category=["2D Mapping","Gate Sweep", "Magnetic Field"],
    description="Resistance vs Magnet and Gate."
                " Includes Snake or Hysteresis (Forward/Backward) gate sweep options.",
    inputs=[
        'Title', 'Resistor', 'Contacts', 'Gate_contacts',
        'devices',
        'use_magnet',
        'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
        'use_srs860_1', 'use_srs860_2',
        'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
        'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
        'mapping', 'line_transition', 'scan_mode',
        'field_start', 'field_end', 'field_step',
        'smu', 'gate_start', 'gate_end', 'gate_step',
        'mag_delay', 'acq_delay',
    ],
    displays=[
        'Title', 'scan_mode',
        'smu', 'gate_start', 'gate_end',
        'field_start', 'field_end'
    ],
        x = 'time(s)',
        y = ['field(T)', 'time(s)']
    ),
}
