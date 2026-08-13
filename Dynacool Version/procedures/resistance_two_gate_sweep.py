"""
Resistance two gate sweep measurement procedure.
"""
from .base import *
from . import base


class Resistance_two_gate_scan_sweep_measurement(DynacoolProcedure):
    # --- Parameters ---
    Title = Parameter('Rn or RD measurement', default='Rn')
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
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    use_keithley_3 = BooleanParameter('Use k2450_3', group_by='devices', default=False)

    # --- Sweep Configuration ---
    sweeping = BooleanParameter('Sweeping Configuration', default=True)
    # Gate 1 Settings
    smu_1 = ListParameter('Top Gate SMU', default='Gate_1',
                          choices=['Gate_1', 'Gate_2', 'Gate_3'],
                          group_by='sweeping', group_condition=True)
    smu_1_sp1 = FloatParameter('Top Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_1_sp2 = FloatParameter('Top Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)
    # Gate 2 Settings
    smu_2 = ListParameter('Bottom Gate SMU', default='Gate_2',
                          choices=['Gate_1', 'Gate_2', 'Gate_3'],
                          group_by='sweeping', group_condition=True)
    smu_2_sp1 = FloatParameter('Bottom Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_2_sp2 = FloatParameter('Bottom Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_points = IntegerParameter('Number of Points', default=50, group_by='sweeping', group_condition=True)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.getMagneticField()
        return self._read_standard(t0)

    def execute(self):
        time_0 = time.time()
        top_gate = self.smu_choice(self.smu_1)
        bottom_gate = self.smu_choice(self.smu_2)
        if self.smu_1 == self.smu_2:
            log.error("Top Gate and Bottom Gate cannot be the same SMU!")
            return
        self.smu_output(top_gate, self.smu_1)
        self.smu_output(bottom_gate, self.smu_2)
        top_gate_list = np.linspace(self.smu_1_sp1, self.smu_1_sp2, self.smu_points)
        bottom_gate_list = np.linspace(self.smu_2_sp1, self.smu_2_sp2, self.smu_points)
        log.info(f"Moving to Start: Top={self.smu_1_sp1}V, Bottom={self.smu_2_sp1}V")
        top_gate.voltage_ramping(top_gate_list[0], 2, 0.1)
        log.info(f"Top ramped to {self.smu_1_sp1}V")
        bottom_gate.voltage_ramping(bottom_gate_list[0], 2, 0.1)
        log.info(f"Bottom ramped to {self.smu_2_sp1}V")
        time.sleep(30)
        for i in range(self.smu_points):
            top_gate.ramp_voltage(top_gate_list[i], 5, 0.05)
            bottom_gate.ramp_voltage(bottom_gate_list[i], 5, 0.05)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * i / self.smu_points)
            if self.should_stop():
                log.warning("Sweep stopped by user.")
                break

    def shutdown(self):
        log.info("Finished measuring two gate sweep")


proc_resistance_two_gate_sweep = {
"Resistance two gate sweep measurement": dict(
        cls=Resistance_two_gate_scan_sweep_measurement,
        category=["Gate Sweep"],
    description="Sweeps two gates simultaneously along a line defined by Start/End points for each gate.\n"
                "Useful for Carrier Density/Displacement Field scans.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_keithley_1', 'use_keithley_2', 'use_keithley_3',
            'sweeping',
            'smu_1', "smu_1_sp1", "smu_1_sp2",
            'smu_2', "smu_2_sp1", "smu_2_sp2",
            'smu_points', 'acq_delay',
        ],
        displays=[
            'Title',
            'smu_1', "smu_1_sp1", "smu_1_sp2",
            'smu_2', "smu_2_sp1", "smu_2_sp2",
            'smu_points',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}