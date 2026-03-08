"""
Differential Conductance SRS860 Measurement.

dI/dV measurement for Tunnel junction using SRS860.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature,
    BASE_DATA_COLUMNS, LOCKIN_CURRENT_COLUMNS, MAGNET_COLUMNS,
)
from . import base


class Differential_conductance_SRS860(Procedure):
    # --- Parameters ---
    Title = Parameter('dI/dV measurement', default='Rt')
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

    # --- Sweep Configuration ---
    scan_mode = ListParameter('Scan Mode', default='Sweep and Return',
                              choices=['Sweep to Setpoint', 'Sweep and Return'],
                              group_by='use_srs860', group_condition=True)

    dc_offset_setpoint = FloatParameter('Target Setpoint (V)', group_by='use_srs860', default=0.1)
    dc_offset_step = FloatParameter('DC Step Size (mV)', group_by='use_srs860', default=1)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.3)

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

    DATA_COLUMNS = BASE_DATA_COLUMNS + ['DC_offset(V)'] + LOCKIN_CURRENT_COLUMNS + MAGNET_COLUMNS 
       

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
            r, th = SRS860.snap("X", "Y")
            vals += [SRS860.dc_offset, r, th]
        else:
            vals += [math.nan, math.nan, math.nan]

        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.magnet_field_read_response() if self.use_magnet else math.nan)
        return vals

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        magnet = base.magnet
        time_0 = time.time()

        start_v = SRS860.dc_offset
        target_v = self.dc_offset_setpoint
        log.info(f"Starting dI/dV {self.scan_mode}. Start={start_v:.4f}V, Target={target_v:.4f}V")

        range_to_target = self.generate_range(start_v, target_v, self.dc_offset_step)
        range_return = self.generate_range(target_v, start_v, self.dc_offset_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        log.info("Sweeping to Setpoint...")
        for v in range_to_target:
            SRS860.set_dc_offset(v)
            time.sleep(self.acq_delay)

            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

            point_counter += 1
            self.emit('progress', 100 * point_counter / total_points)
            if self.should_stop():
                log.warning("Measurement stopped by user")
                return

        if self.scan_mode == 'Sweep and Return':
            log.info("Returning to Origin...")
            for v in range_return:
                SRS860.set_dc_offset(v)
                time.sleep(self.acq_delay)

                data = self.getmeas(time_0)
                self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

                point_counter += 1
                self.emit('progress', 100 * point_counter / total_points)
                if self.should_stop():
                    log.warning("Measurement stopped by user")
                    return

    def shutdown(self):
        log.info("Finished measuring")


proc_differential_conductance_SRS860 = {
    "Differential conductance SRS860": dict(
        cls=Differential_conductance_SRS860,
        category="Tunneling junction",
        description="dI/dV Sweep starting from CURRENT DC Offset using SRS860.\n"
                    "1. Sweep to Setpoint: Measures from [Current] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Current] -> [Target] -> [Current]. Returns voltage to start.",
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860',
            'scan_mode', 'dc_offset_setpoint', 'dc_offset_step',
            'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'acq_delay',
        ],
        displays=['Title', 'scan_mode', 'dc_offset_setpoint', 'dc_offset_step'],
        x=['DC_offset(V)'],
        y=['Lockin_Current_SRS860_X(A)', 'Lockin_Current_SRS860_Y(A)'],
    ),
}