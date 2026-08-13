"""
Sequencer for Rt, RV and RH measurements.
"""
from .base import *
from . import base


class Rt_RV_RH_sequencer_measurement(DynacoolProcedure):
    Title = Parameter('Combination sequence measurement', default='measurement type')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')
    Type = ListParameter('Measurement Type', choices=['Rt', 'RV', 'RH'], default='Rt')
    Target_field = FloatParameter('Target field (T)', group_by='Type', group_condition='RH', default=0)
    sweep_rate = FloatParameter('Sweep rate (T/min)', group_by='Type', group_condition='RH', default=0.1)
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'Gate_3'], group_by='Type', group_condition='RV', default='Gate_1')
    acq_length = IntegerParameter('Acquisition Length (s)', group_by='Type', group_condition='Rt', default=3600)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    devices = BooleanParameter("Device in use", default=False)
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

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.getMagneticField()
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

    def run_RH(self):
        if self.use_magnet == False:
            log.warning("Magnet was not chosen measurement aborted")
            return
        magnet = base.magnet
        # PPMS firmware manages ramp safety; no per-range limits or persistent
        # switch heater like the Cryomagnetics supply.
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla at %g T/min",
                 self.Target_field, self.sweep_rate)
        origin_field = magnet.getMagneticField()
        magnet.go_to_target_field(self.Target_field, self.sweep_rate)
        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero
        current_field = origin_field
        # --- Monitoring Loop ---
        while abs(current_field - self.Target_field) > 0.003:
            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                return
        log.info("Magnetic field Reached!")

    def execute(self):
        if self.Type == 'RH':
            self.run_RH()
        elif self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'Rt':
            self.run_Rt()

    def shutdown(self):
        magnet = base.magnet
        if self.Type == 'RH' and self.use_magnet:
            current_field = magnet.getMagneticField()
            if abs(current_field - self.Target_field) > 0.003:
                magnet.pause_field()
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")


proc_Rt_RV_RH_sequencer = {
    "Rt_RV_RH sequencer measurement": dict(
        cls=Rt_RV_RH_sequencer_measurement,
        category=["Magnetic Field", "Gate Sweep", "Keithley 2450", "Time-based"],
        description="Procedure to sequence between Rt, RV and RH measurements.",
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'Type', 'Target_field', 'sweep_rate',
                'Target_voltage', 'step_size', 'smu', 'acq_length', 'devices', 'use_magnet',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3', 'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_keithley_1', 'use_keithley_2', 'use_keithley_3', 'acq_delay'],
        displays=['Type', 'Target_field', 'sweep_rate', 'smu', 'Target_voltage', 'step_size', 'acq_length', 'acq_delay'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_field', 'sweep_rate', 'use_magnet', 'Target_voltage', 'step_size', 'smu', 'acq_length', 'acq_delay'],
    ),
}
