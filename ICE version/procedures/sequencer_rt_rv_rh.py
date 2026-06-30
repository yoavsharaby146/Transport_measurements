"""
Sequencer for Rt, RV and RH measurements.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860_1, SRS860_2, SRS830_1, SRS830_2, SRS830_3, Dual_gate, Gate_1, Gate_2,
    read_temperature,
    BASE_DATA_COLUMNS, LOCKIN_VOLTAGE_COLUMNS, MAGNET_COLUMNS
)
from . import base



class Rt_RV_RH_sequencer_measurement(Procedure):
    Title = Parameter('Combination sequence measurement', default='measurement type')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')
    Type = ListParameter('Measurement Type', choices=['Rt', 'RV', 'RH'], default='Rt')
    Target_field = FloatParameter('Target field (T)', group_by='Type', group_condition='RH', default=0)
    sweep_control = ListParameter('Sweep speed', group_by='Type', group_condition='RH', choices=["Slow","Normal","Fast"], default="Normal")
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], group_by='Type', group_condition='RV', default='Gate_1')
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
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    srs860_1_sine_voltage = Metadata("SRS860_1 sine voltage", default=math.nan)
    srs860_1_frequency = Metadata("SRS860_1 frequency (Hz)", default=math.nan)
    srs860_2_sine_voltage = Metadata("SRS860_2 sine voltage", default=math.nan)
    srs860_2_frequency = Metadata("SRS860_2 frequency (Hz)", default=math.nan)
    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)
    srs830_3_sine_voltage = Metadata("SRS830_3 sine voltage", default=math.nan)
    srs830_3_frequency = Metadata("SRS830_3 frequency (Hz)", default=math.nan)
    MFLI_1_sine_voltage = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_2_sine_voltage = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency = Metadata("MFLI_2 frequency (Hz)", default=math.nan)
    MFLI_3_sine_voltage = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency = Metadata("MFLI_3 frequency (Hz)", default=math.nan)

    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS

    def startup(self):
        if self.use_srs860_1:
            self.srs860_1_sine_voltage = SRS860_1.sine_voltage
            self.srs860_1_frequency = SRS860_1.frequency
        if self.use_srs860_2:
            self.srs860_2_sine_voltage = SRS860_2.sine_voltage
            self.srs860_2_frequency = SRS860_2.frequency
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
        if self.use_srs830_3:
            self.srs830_3_sine_voltage = SRS830_3.sine_voltage
            self.srs830_3_frequency = SRS830_3.frequency

    def getmeas(self, t0):
        magnet = base.magnet
        if self.use_magnet:
            magnet.magnet_field_write_query()
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(), Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2
        vals += list(SRS860_1.snap("X", "Y")) if self.use_srs860_1 else [math.nan] * 2
        vals += list(SRS860_2.snap("X", "Y")) if self.use_srs860_2 else [math.nan] * 2
        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2
        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2), (self.use_srs830_3, SRS830_3)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2
        vals.append(magnet.magnet_field_read_response() if self.use_magnet else math.nan)
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

    def run_Rt(self):
        time_0 = time.time()
        magnet = base.magnet
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
        magnet = base.magnet
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
        time_0 = time.time()
        magnet = base.magnet
        if self.use_magnet == False:
            log.info("Forgot to choose magnet in magnetic field measurement")
            return
        if self.sweep_control == "fast":
            if abs(self.Target_field) < 1 and abs(magnet.magnet_field) < 1:
                log.info("Magnetic field -1<B<1 Tesla, Fast sweep rate 0.2 T/min")
                magnet.current_rate0 = (0.2*10.375)/60
            else:
                log.info("Magnetic field outside of range -1 < B < 1 Tesla, Fast sweep rate cannot be used")
                return
        if self.sweep_control == "normal":
            log.info("Normal sweep rate 0.1 T/min")
            magnet.current_rate0 = (0.1*10.375)/60
        if self.sweep_control == "slow":
            if abs(self.Target_field) < 0.5 and abs(magnet.magnet_field) < 0.5:
                log.info("Magnetic field -0.5<B<0.5 Tesla, Slow sweep rate 0.05 T/min")
                magnet.current_rate0 = (0.05*10.375)/60
            else:
                log.info("Magnetic field outside of range -0.5 < B < 0.5 Tesla, Slow sweep rate cannot be used")
                return
        
        log.info("starting to sweep field to %g Tesla", self.Target_field)
        current_field = magnet.magnet_field
        persistent_heater_status = magnet.persistent_switch_heater
        if persistent_heater_status == '0':
            log.info("Heater is OFF. Turning ON and waiting 600s...")
            magnet.persistent_switch_heater = 'ON'
            time.sleep(600)
        origin_field = magnet.magnet_field
        magnet.go_to_target_field(self.Target_field)
        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0
        while abs(current_field - self.Target_field) > 0.003:
            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                magnet.sweep_mode = 'PAUSE'
                return
        log.info("Magnetic field Reached!")

    def execute(self):
        magnet = base.magnet
        if self.Type == 'RH':
            self.run_RH()
        elif self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'Rt':
            self.run_Rt()

    def shutdown(self):
        magnet = base.magnet
        if self.Type == 'RH' and self.use_magnet:
            current_field = magnet.magnet_field
            if abs(current_field - self.Target_field) > 0.003:
                magnet.sweep_mode = 'PAUSE'
        log.info("Finished measuring")


proc_Rt_RV_RH_sequencer = {
    "Rt_RV_RH sequencer measurement": dict(
        cls=Rt_RV_RH_sequencer_measurement,
        category=["Magnetic Field", "Gate Sweep", "Keithley 2450", "Time-based"],
        description="Procedure to sequence between Rt, RV and RH measurements.",
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'Type', 'Target_field','sweep_control',
                'Target_voltage', 'step_size', 'smu', 'acq_length', 'devices', 'use_magnet',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3', 'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2', 'acq_delay'],
        displays=['Type','Target_field','smu','Target_voltage','step_size','acq_length','acq_delay'],
        x=['time(s)'],
        y=['probe_temp(K)', 'field(T)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_field', 'use_magnet', 'Target_voltage', 'step_size', 'smu', 'acq_length','acq_delay'],
    ),
}
