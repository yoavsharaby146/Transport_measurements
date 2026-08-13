"""
Differential Conductance Zurich Measurement.

dI/dV measurement for Tunnel junction using Zurich MFLI.
"""
from .base import *
from . import base


class Differential_conductance_Zurich(DynacoolProcedure):
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
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    use_keithley_3 = BooleanParameter('Use k2450_3', group_by='devices', default=False)

    # --- Sweep Configuration ---
    scan_mode = ListParameter('Scan Mode', default='Sweep and Return',
                              choices=['Sweep to Setpoint', 'Sweep and Return'],
                              group_by='use_MFLI_1', group_condition=True)
    dc_offset_setpoint = FloatParameter('Target Setpoint (V)', group_by='use_MFLI_1', default=0.1)
    dc_offset_step = FloatParameter('DC Step Size (mV)', group_by='use_MFLI_1', default=1)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.3)

    # --- Dynamic column recipe ---
    _MID_COLUMNS = ['DC_offset(V)']
    _LOCKIN_COL_TYPE = 'current'

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.getMagneticField()
        # Mid column: MFLI_1 DC offset
        dc = MFLI_1.dc_offset if (self.use_MFLI_1 and base._is_connected(MFLI_1)) else math.nan
        return self._read_standard(t0, mid_extras=[dc])

    def execute(self):
        time_0 = time.time()
        start_v = MFLI_1.dc_offset
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
            MFLI_1.dc_offset = v
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
                MFLI_1.dc_offset = v
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


proc_differential_conductance_Zurich = {
    "Differential conductance Zurich": dict(
        cls=Differential_conductance_Zurich,
        category="Tunneling junction",
        description="dI/dV Sweep starting from CURRENT DC Offset using Zurich MFLI_1.\n"
                    "1. Sweep to Setpoint: Measures from [Current] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Current] -> [Target] -> [Current]. Returns voltage to start.",
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1',
            'scan_mode', 'dc_offset_setpoint', 'dc_offset_step',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_keithley_1', 'use_keithley_2', 'use_keithley_3',
            'acq_delay',
        ],
        displays=['Title', 'scan_mode', 'dc_offset_setpoint', 'dc_offset_step'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}