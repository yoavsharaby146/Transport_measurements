"""
Sequencer for Rt and RV measurements (Generic Version — no magnet/RH).

Port of the ICE Rt_RV_RH sequencer with the magnet branch removed.
"""

from .base import *
from . import base


class Rt_RV_sequencer_measurement(GenericProcedure):
    Title = Parameter('Combination sequence measurement', default='measurement type')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')
    Type = ListParameter('Measurement Type', choices=['Rt', 'RV'], default='Rt')
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                   group_by='Type', group_condition='RV')
    acq_length = IntegerParameter('Acquisition Length (s)', group_by='Type', group_condition='Rt', default=3600)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh SMU dropdown choices to the connected instruments."""
        cls.smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                           group_by='Type', group_condition='RV')

    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs860_3 = BooleanParameter('Use srs860_3', group_by='devices', default=False)
    use_srs860_4 = BooleanParameter('Use srs860_4', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    use_yoko_gs200_1 = BooleanParameter('Use Yoko GS200_1', group_by='devices', default=False)
    use_yoko_gs200_2 = BooleanParameter('Use Yoko GS200_2', group_by='devices', default=False)
    use_yoko7651_1 = BooleanParameter('Use Yoko7651_1', group_by='devices', default=False)
    use_yoko7651_2 = BooleanParameter('Use Yoko7651_2', group_by='devices', default=False)
    use_k6221 = BooleanParameter('Use k6221 (record amplitude column)', group_by='devices', default=False)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        return self._read_standard(t0)

    def run_Rt(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)
        current_time = 0.0
        while current_time < self.acq_length:
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * data[0] / self.acq_length)
            current_time = data[0]
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Measurement stopped")
                return

    def run_RV(self):
        time_0 = time.time()
        log.info(f"starting voltage sweep to {self.Target_voltage} V")
        Gate = self.smu_choice(self.smu)
        if not Gate.is_output_on():
            self.smu_output(Gate, self.smu)
        start_volts = Gate.measure__voltage()
        gate_ranges = self.generate_range(start_volts, self.Target_voltage, self.step_size)
        log.info(f"Sweeping {self.smu} from {start_volts:.4f}V to {self.Target_voltage:.4f}V")
        iteration = 1
        for gate_volt in gate_ranges:
            Gate.ramp_voltage(gate_volt, 2, 0.001)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(gate_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                return
        if self.Target_voltage == 0:
            log.info(f"Target reached 0V.  {self.smu} is still ON.")

    def execute(self):
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'Rt':
            self.run_Rt()

    def shutdown(self):
        log.info("Finished measuring")


proc_Rt_RV_sequencer = {
    "Rt_RV sequencer measurement": dict(
        cls=Rt_RV_sequencer_measurement,
        category=["Gate Sweep", "Time-based"],
        description="Procedure to sequence between Rt and RV measurements.",
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'Type',
                'Target_voltage', 'step_size', 'smu', 'acq_length', 'devices',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221',
                'acq_delay'],
        displays=['Type', 'smu', 'Target_voltage', 'step_size', 'acq_length', 'acq_delay'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu', 'acq_length', 'acq_delay'],
    ),
}
