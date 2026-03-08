"""
Resistance Magnet and Gate Mapping Measurement.

2D mapping using Magnetic field and SMU gate voltage.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature,
    BASE_DATA_COLUMNS,
)
from . import base
base.magnet = magnet


class Resistance_magnet_and_gate_mapping_measurement(Procedure):
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping RHV', default=True)

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

    DATA_COLUMNS = BASE_DATA_COLUMNS + ['field(T)']

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
        vals = [time.time() - t0, temperature[0], temperature[1], temperature[2], temperature[3]]
        if self.use_magnet:
            magnet.magnet_field_write_query()
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan, math.nan, math.nan, math.nan]
        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_1:
            x, y = MFLI_1.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_2:
            x, y = MFLI_2.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_3:
            x, y = MFLI_3.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_magnet:
            vals += [magnet.magnet_field_read_response()]
        else:
            vals += [math.nan]
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

    def generate_range(self, start, end, step_units):
        # step_units is mT for magnet, mV for gate
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
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
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    time.sleep(self.acq_delay)
                log.info(f"Field at {field}T. Stabilizing...")
                time.sleep(self.mag_delay)

            # Define Gate logic
            # --- CASE 1: SNAKE MODE ---
            if self.scan_mode == 'Snake':
                current_gate_range = gate_range_fwd if i % 2 == 0 else gate_range_bwd
                for g_volt in current_gate_range:
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
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
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                # Part B: Backward
                for g_volt in gate_range_bwd:
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
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
        'use_srs860', 'use_srs830_1', 'use_srs830_2',
        'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
        'mapping', 'scan_mode',
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
        y = ['field(T)','SMUa(V)']
    ),
}