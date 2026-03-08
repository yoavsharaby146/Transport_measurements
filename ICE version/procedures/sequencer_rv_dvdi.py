"""
Sequencer for RV and dV/dI measurements.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature, BASE_DATA_COLUMNS, LOCKIN_VOLTAGE_COLUMNS, MAGNET_COLUMNS,
)
from . import base



class RV_dV_dI_sequencer_measurement(Procedure):
    Title = Parameter('Measurement type', default='RV and dV/dI in sequence')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')
    Type = ListParameter('Measurement Type', choices=['RV', 'dV_dI'], default='RV')
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              group_by='Type', group_condition='dV_dI', default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)', group_by=['use_MFLI_1', 'Type'],
                                group_condition='dV_dI', default=0)
    aux_signal = IntegerParameter('Auxiliary DC Signal ', group_by=['use_MFLI_1', 'Type'],
                                  group_condition='dV_dI', default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ", group_by=['use_MFLI_1', 'Type'],
                                  group_condition='dV_dI', default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['Type', 'use_MFLI_1', 'aux_select'],
                                 group_condition=['dV_dI', True, lambda v: v == 11 or v == 13])
    aux_step = FloatParameter('Auxiliary step (mV)', group_by=['use_MFLI_1', 'Type'],
                              group_condition='dV_dI', default=2)
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                        group_by='Type', group_condition='RV', default='Gate_1')
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
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

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
    
    DATA_COLUMNS = BASE_DATA_COLUMNS + ['AUX_DC_offset(V)'] + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS

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
            x, y = SRS860.snap("X", "Y")
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout] + list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3
        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2
        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
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
            log.info(f"Target reached 0V. Turning {self.smu} OFF.")
            Gate.output_off()

    def run_dV_dI(self):
        time_0 = time.time()
        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)
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
            MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
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
                MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                time.sleep(self.acq_delay)
                data = self.getmeas(time_0)
                self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                self.emit('progress', 100 * point_counter / total_points)
                point_counter += 1
                if self.should_stop():
                    log.warning("User stopped measurement while in return Sweep")
                    return

    def execute(self):
        magnet = base.magnet
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'dV_dI':
            self.run_dV_dI()

    def shutdown(self):
        log.info("Finished measuring")


proc_RV_dV_dI_sequencer = {
    "RV dV_dI sequencer measurement": dict(
        cls=RV_dV_dI_sequencer_measurement,
        category=["Differential Resistance", "Gate Sweep", "Keithley 2450"],
        description="Sequencer for RV and dV/dI measurements.",
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'acq_delay', 'Type', 'scan_mode',
                'Target_voltage', 'step_size', 'smu', 'devices', 'use_magnet', 'use_MFLI_1',
                'aux_Target', 'aux_step', 'aux_signal', 'aux_select', 'aux_demod',
                'use_MFLI_2', 'use_MFLI_3', 'use_srs860', 'use_srs830_1', 'use_srs830_2',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2'],
        displays=['Type', 'Target_voltage', 'scan_mode', 'aux_Target'],
        x=['AUX_DC_offset(V)'],
        y=['MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu', 'scan_mode', 'aux_Target', 'aux_step'],
    ),
}