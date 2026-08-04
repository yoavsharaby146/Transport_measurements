"""
Resistance gate sweep measurement procedure.
"""

from .base import *
from . import base


class Resistance_gate_sweep_measurement(ICEProcedure):
    Title = Parameter(' RV gate sweep ', default='RV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='Insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=1)
    target_voltage = FloatParameter('Target Voltage(V)', default=0)
    step_size = FloatParameter('Step size(mV)', default=1)
    smu = ListParameter('User defined SMU',choices=['Gate_1','Gate_2','smua','smub'], default='Gate_1')

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
    use_dual_gate = BooleanParameter('Use dual gate',group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1',group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2',group_by='devices', default=False)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and _is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0)

    def execute(self):
        #### Begin of measurement
        log.info(f"starting voltage sweep to {self.target_voltage} V")
        time_0 = time.time()

        #### Determine chosen smu
        Gate = self.smu_choice(self.smu)

        # 1. Output Check & Turn On
        if not Gate.is_output_on():
            log.info(f'{self.smu} output was OFF. Turning it ON.')

            if self.smu in ['Gate_1','Gate_2']:
                Gate.configure_voltage_source(nplc=1,
                                          current=1e-7,
                                          auto_range=False,
                                          compliance_current=1.5e-8)
            else:
                Gate.configure_voltage_source(voltage =0, current_limit=35e-9)

            Gate.output_on()
            log.info(f"{self.smu} output turned ON")

        # 3. Create Sweep Array
        # Using linspace to guarantee we hit the exact target voltage

        start_volts = Gate.measure__voltage()
        step_v = self.step_size / 1000.0
        if step_v == 0: step_v = 0.001
        num_points = int(abs(self.target_voltage - start_volts) / step_v) + 1
        gate_ranges = np.linspace(start_volts, self.target_voltage, num_points)

        log.info(f"Sweeping {self.smu} from {start_volts:.4f}V to {self.target_voltage:.4f}V")

        iteration = 1
        for gate_volt in gate_ranges:
            Gate.ramp_voltage(gate_volt,2,0.001)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            # log.info("gate sweep at " + str(gate_volt) + " (V)")
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(gate_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break
        if self.target_voltage == 0:
            log.info(f"Target reached 0V. Turning {self.smu} OFF.")
            Gate.output_off()

    def shutdown(self):
        #log.info("Keithley still on")
        log.info("Gate sweep measurement finished")


proc_resistance_gate = {
"Resistance gate sweep measurement": dict(
        cls=Resistance_gate_sweep_measurement,
        category="Gate Sweep",
    description="Sweeps a Gate Voltage while measuring Resistance (via Lock-ins).\n"
                "Supports Keithley 2450 and Dual Gate SMUs (Keithley 2604B).",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2','use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1','use_keithley_2',
            'smu', 'target_voltage', 'step_size',
            'acq_delay',
        ],
        displays=[
            'Title',
            'target_voltage', 'step_size'],
        x=['time(s)'],
        y=['probe_temp(K)', 'SMUa(V)']
    ),
}