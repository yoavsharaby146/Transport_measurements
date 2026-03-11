"""
Resistance Magnet and 2-Gate Mapping Measurement.

2D mapping using Magnetic field and two gate voltages simultaneously.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature,
    BASE_DATA_COLUMNS,LOCKIN_VOLTAGE_COLUMNS, MAGNET_COLUMNS,
)
from . import base



class Resistance_magnet_and_2gate_mapping_measurement(Procedure):
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

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping Configuration', default=True)

    # Scan Logic
    scan_mode = ListParameter('Gate Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    # Magnet Settings
    field_start = FloatParameter('Magnetic field start (T)', default=0, group_by='mapping', group_condition=True)
    field_end = FloatParameter('Magnetic field end (T)', default=1, group_by='mapping', group_condition=True)
    field_step = FloatParameter('Magnetic field step size (mT)', default=50, group_by='mapping', group_condition=True)
    mag_delay = FloatParameter('Delay after Magnetic sweep (s)', default=60, group_by='mapping', group_condition=True)

    # Gate 1 Settings
    smu_1 = ListParameter('Top Gate SMU', default='Gate_1',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='mapping', group_condition=True)
    smu_1_sp1 = FloatParameter('Top Gate Start (V)', default=0.0, group_by='mapping', group_condition=True)
    smu_1_sp2 = FloatParameter('Top Gate End (V)', default=0.0, group_by='mapping', group_condition=True)

    # Gate 2 Settings
    smu_2 = ListParameter('Bottom Gate SMU', default='Gate_2',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='mapping', group_condition=True)
    smu_2_sp1 = FloatParameter('Bottom Gate Start (V)', default=0.0, group_by='mapping', group_condition=True)
    smu_2_sp2 = FloatParameter('Bottom Gate End (V)', default=0.0, group_by='mapping', group_condition=True)

    # Sweep resolution and timing
    smu_points = IntegerParameter('Number of Gate Points', default=50, group_by='mapping', group_condition=True)
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

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        magnet = base.magnet
        time_0 = time.time()
        log.info("Starting Magnet + 2-Gate Map")

        # --- 1. Instrument Setup ---
        gate_1_inst = self.smu_choice(self.smu_1)
        gate_2_inst = self.smu_choice(self.smu_2)

        if self.smu_1 == self.smu_2:
            log.error("Gate 1 and Gate 2 cannot be the same instrument!")
            return

        self.smu_output(gate_1_inst, self.smu_1)
        self.smu_output(gate_2_inst, self.smu_2)

        # --- 2. Generate Arrays ---
        field_range = self.generate_range(self.field_start, self.field_end, self.field_step)
        gate_1_list_fwd = np.linspace(self.smu_1_sp1, self.smu_1_sp2, self.smu_points)
        gate_2_list_fwd = np.linspace(self.smu_2_sp1, self.smu_2_sp2, self.smu_points)
        gate_1_list_bwd = gate_1_list_fwd[::-1]
        gate_2_list_bwd = gate_2_list_fwd[::-1]

        # --- 3. Initial Magnet Safety & Positioning ---
        if magnet.persistent_switch_heater == '0':
            magnet.persistent_switch_heater = 'ON'
            log.info("Magnet heater ON. Waiting 10min...")
            time.sleep(600)

        log.info(f"Ramping Magnet to start: {self.field_start}T")
        magnet.go_to_target_field(self.field_start)

        log.info(f"Ramping Gates to Start: {self.smu_1_sp1}V, {self.smu_2_sp1}V")
        gate_1_inst.voltage_ramping(gate_1_list_fwd[0], 2, 0.1)
        gate_2_inst.voltage_ramping(gate_2_list_fwd[0], 2, 0.1)

        while abs(magnet.magnet_field - self.field_start) > 0.003:
            if self.should_stop():
                magnet.sweep_mode = 'PAUSE'
                log.warning("Measurement stopped by user, MAGNET is PAUSED")
                return
            time.sleep(self.acq_delay)

        time.sleep(self.mag_delay)

        # --- 4. Main Loops ---
        steps_per_field = self.smu_points * (2 if self.scan_mode == 'Forward/Backward' else 1)
        total_steps = len(field_range) * steps_per_field
        iteration_count = 1

        for i, field in enumerate(field_range):
            if i > 0:
                magnet.go_to_target_field(field)
                while abs(magnet.magnet_field - field) > 0.003:
                    if self.should_stop():
                        magnet.sweep_mode = 'PAUSE'
                        log.warning("User stopped during magnet ramp")
                        return
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    time.sleep(self.acq_delay)
                log.info(f"Field reached {field}T. Stabilizing...")
                time.sleep(self.mag_delay)

            lists_to_run = []
            if self.scan_mode == 'Snake':
                if i % 2 == 0:
                    lists_to_run.append((gate_1_list_fwd, gate_2_list_fwd))
                else:
                    lists_to_run.append((gate_1_list_bwd, gate_2_list_bwd))
            elif self.scan_mode == 'Forward/Backward':
                lists_to_run.append((gate_1_list_fwd, gate_2_list_fwd))
                lists_to_run.append((gate_1_list_bwd, gate_2_list_bwd))

            for (g1_list, g2_list) in lists_to_run:
                for v1, v2 in zip(g1_list, g2_list):
                    gate_1_inst.ramp_voltage(v1, steps=5, delay=0.01)
                    gate_2_inst.ramp_voltage(v2, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration_count / total_steps)
                    iteration_count += 1
                    if self.should_stop():
                        log.warning("Measurement stopped by user during gate sweep")
                        magnet.sweep_mode = 'PAUSE'
                        return

    def shutdown(self):
        magnet = base.magnet
        magnet.sweep_mode = 'PAUSE'
        log.info("Finished measuring")


proc_resistance_magnet_2gate_map = {
"Resistance Magnet and 2-Gate Map": dict(
        cls=Resistance_magnet_and_2gate_mapping_measurement,
        category=["2D Mapping", "Gate Sweep", "Magnetic Field"],
        description="2D Map: Magnetic Field (Outer) vs Simultaneous Two-Gate Sweep (Inner).\n"
                    "The two-Gate sweep must be calculated in advance to determine Carrier density/Displacement.\n"
                    "Selects between 'Snake' or 'Forward/Backward' scan modes for the gates.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'mapping', 'scan_mode',
            'field_start', 'field_end', 'field_step',
            'smu_1', 'smu_1_sp1', 'smu_1_sp2',
            'smu_2', 'smu_2_sp1', 'smu_2_sp2',
            'smu_points',
            'mag_delay', 'acq_delay',
        ],
        displays=[
            'Title', 'scan_mode',
            'field_start', 'field_end',
            'smu_1', 'smu_2', 'smu_points'
        ],
        x='time(s)',
        y=['field(T)', 'SMUa(V)']
    ),
}
