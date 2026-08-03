"""
Differential Resistance SRS860 Measurement.

dV/dI measurement using SRS860 aux for DC current.
"""

from .base import *
from . import base


class Differential_Resistance_SRS860(ICEProcedure):
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
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Sweep Parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target  (V)', group_by='use_srs860_1', default=0)
    aux_signal = ListParameter('Aux output 1-4:', group_by='use_srs860_1', choices=[1, 2, 3, 4], default=1)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='use_srs860_1', default=2)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

    # --- Dynamic column recipe ---
    _MID_COLUMNS = ['AUX_DC_offset(V)']
    _LOCKIN_COL_TYPE = 'voltage'

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and _is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        # Mid column: SRS860_1 AUX DAC value
        aux = getattr(SRS860_1, f'dac{self.aux_signal}') if (self.use_srs860_1 and _is_connected(SRS860_1)) else math.nan
        return self._read_standard(t0, mid_extras=[aux])

    def execute(self):
        time_0 = time.time()

        aux_origin = getattr(SRS860_1, f'dac{self.aux_signal}')
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
            SRS860_1.ramp_aux(self.aux_signal, aux, 5, 0.01)
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
                SRS860_1.ramp_aux(self.aux_signal, aux, 5, 0.01)
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


proc_differential_resistance_SRS860 = {
    "Differential Resistance SRS860": dict(
        cls=Differential_Resistance_SRS860,
        category="Differential Resistance",
        description="dV/dI Sweep starting from Origin DC AUX using SRS860.\n"
                    "1. Sweep to Setpoint: Measures from [Origin] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Origin] -> [Target] -> [Origin]. Returns voltage to start.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'acq_delay',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1',
            'aux_Target', 'aux_step', 'aux_signal',
            'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'scan_mode',
        ],
        displays=[
            'Title', 'scan_mode', 'aux_Target'],
        x=['AUX_DC_offset(V)'],
        y=['MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)'],
    ),
}