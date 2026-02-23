import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import time, math
import numpy as np
from scipy.constants import e
from scipy.constants import epsilon_0
from pymeasure.log import console_log
from pymeasure.display.Qt import QtWidgets, QtGui, QtCore
from pymeasure.display.windows.managed_dock_window import ManagedDockWindow

from pymeasure.experiment import Procedure, BooleanParameter
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter

import pyqtgraph as pg
pg.setConfigOption("useOpenGL", True)

# from configuration import magnet, MFLI_1, SRS860, SRS830_1,SRS830_2,Dual_gate, Gate_1, Gate_2
# from configuration import read_temperature, auto_range,auto_range_magnet

import configuration as _cfg
from configuration import read_temperature, read_dilution_field

# ,auto_range, auto_range_magnet

# Safe bindings (fall back to 0 if the attribute doesn't exist)
magnet            = getattr(_cfg, "magnet", 0)
MFLI_1            = getattr(_cfg, "MFLI_1", 0)
MFLI_2            = getattr(_cfg, "MFLI_2", 0)
MFLI_3            = getattr(_cfg, "MFLI_3", 0)
SRS860            = getattr(_cfg, "SRS860", 0)
SRS830_1          = getattr(_cfg, "SRS830_1", 0)
SRS830_2          = getattr(_cfg, "SRS830_2", 0)
Dual_gate         = getattr(_cfg, "Dual_gate", 0)
Gate_1            = getattr(_cfg, "Gate_1", 0)
Gate_2            = getattr(_cfg, "Gate_2", 0)
# dilution instrument (if configured)
dilution          = getattr(_cfg, "dilution", 0)

save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav"

def _rebind_instruments_from_configuration():
    """Refresh module-level instrument globals after configuration reload."""
    global magnet, MFLI_1,MFLI_2,MFLI_3, SRS860, SRS830_1,SRS830_2, Dual_gate, Gate_1, Gate_2
    magnet = _cfg.magnet
    MFLI_1 = _cfg.MFLI_1
    MFLI_2 = _cfg.MFLI_2
    MFLI_3 = _cfg.MFLI_3
    SRS860 = _cfg.SRS860
    SRS830_1 = _cfg.SRS830_1
    SRS830_2 = _cfg.SRS830_2
    Dual_gate = _cfg.Dual_gate
    Gate_1 = _cfg.Gate_1
    Gate_2 = _cfg.Gate_2


def _as_cat_list(cat_value):
    if cat_value is None:
        return []
    if isinstance(cat_value, (list, tuple, set)):
        return [str(c) for c in cat_value]
    return [str(cat_value)]

def _proc_matches(proc_dict, selected_names):
    """AND logic: a procedure must include ALL selected categories to match."""
    if not selected_names:  # no filter => match all
        return True
    proc_cats = set(_as_cat_list(proc_dict.get('category')))
    return set(selected_names).issubset(proc_cats)

#### Measurement for a given acquisition time
class Resistance_time_measurement(Procedure):

    Title = Parameter('Rt measurement', default='Rt')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
    acq_length = IntegerParameter('Acquisition Length (s)', default=3600)

    devices = BooleanParameter('Devices in use',default=False)
    use_magnet = BooleanParameter('Use Magnet',group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1',group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860 = BooleanParameter('Use srs860',group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1',group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Metadata Definitions ---
    srs860_sine_voltage = Metadata("SRS860 sine voltage", default=math.nan)
    srs860_frequency = Metadata("SRS860 frequency (Hz)", default=math.nan)

    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)

    MFLI_1_sine_voltage = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_1_bias = Metadata("MFLI_1 bias offset(V)", default=math.nan)
    MFLI_1_aux = Metadata("MFLI_1 aux output", default=math.nan)

    MFLI_2_sine_voltage = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency = Metadata("MFLI_2 frequency (Hz)", default=math.nan)

    MFLI_3_sine_voltage = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency = Metadata("MFLI_3 frequency (Hz)", default=math.nan)

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

    def startup(self):
        # Capture metadata for active instruments
        if self.use_srs860:
            self.srs860_sine_voltage = SRS860.sine_voltage
            self.srs860_frequency = SRS860.frequency

        if self.use_MFLI_1:
            self.MFLI_1_sine_voltage = MFLI_1.sine_amplitude
            self.MFLI_1_frequency = MFLI_1.frequency
            self.MFLI_1_bias = MFLI_1.dc_offset
            self.MFLI_1_aux = MFLI_1.get_auxout()

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
        temperature = read_temperature()
        # expect a one-element array
        vals = [time.time() - t0, float(temperature[0])]  # mixing chamber temp

        if self.use_magnet:
            magnet.get_magnet_field_write()

        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4
        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan] * 2
        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan] * 2
        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1),
                          (self.use_MFLI_2, MFLI_2),
                          (self.use_MFLI_3, MFLI_3)]:
            if use:
                vals += list(inst.read_demod())
            else:
                vals += [math.nan] * 2
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan] * 2
        return vals

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)

        # While Loop through until acquisition length is done
        current_time = 0.0


        while current_time < self.acq_length:
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress',100 * data[0]/self.acq_length)
            current_time = data[0]
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Measurement stopped")
                break

    def shutdown(self):
        log.info("Finished measuring")
proc_resistance_time = {
"Resistance time measurement": dict(
        cls=Resistance_time_measurement,
        category=["Time-based","Keithley 2450"],
        description="Measurement of resistance over a specified time period.\n"
                    "Monitors temperature,magnetic field, and various lock-in amplifier readings.",
        inputs=[
                'Title','Resistor','Contacts',
                'devices',
                'use_magnet',
                'use_MFLI_1' ,'use_MFLI_2','use_MFLI_3',
                'use_srs860','use_srs830_1','use_srs830_2',
                'use_dual_gate','use_keithley_1','use_keithley_2',
                'acq_delay', 'acq_length',
        ],
        displays=[
            'Title',
            'acq_delay', 'acq_length'],
        x = ['time(s)'],
        y =  ['mixing_chamber_temp(K)']
    ),
}

#### Gave voltage sweep using a specified SMU
class Resistance_gate_sweep_measurement(Procedure):
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate',group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1',group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2',group_by='devices', default=False)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        if self.use_magnet:
            magnet.get_magnet_field_write()

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
            vals.append(magnet.get_magnet_field_read())
        else:
            vals.append(math.nan)

        return vals

    def smu_choice(self, Gate_name):
        if self.smu == 'Gate_1': return Gate_1
        if self.smu == 'Gate_2': return Gate_2
        if self.smu == 'smua': return Dual_gate.smua
        if self.smu == 'smub': return Dual_gate.smub
        log.error("SMU selection not supported")
        raise ValueError("Invalid SMU selected")

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

        # #### change step size to mV units
        # if self.smu == 'Gate_1' or self.smu == 'Gate_2':
        #     milli_step = np.sign(self.target_voltage-Gate.measure__voltage()) * self.step_size / 1000
        #     gate_ranges = np.arange(Gate.measure__voltage(), self.target_voltage + milli_step * 1e-3, milli_step)
        # elif self.smu == 'smua' or self.smu == 'smub':
        #     milli_step = np.sign(self.target_voltage - Dual_gate.measure__voltage(Gate)) * self.step_size / 1000
        #     gate_ranges = np.arange(Dual_gate.measure__voltage(Gate), self.target_voltage + milli_step * 1e-3, milli_step)

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
            #
            # if self.smu == 'Gate_1' or self.smu == 'Gate_2':
            #     Gate.ramp_voltage(gate_volt,2,0.001)
            # elif self.smu == 'smua' or self.smu == 'smub':
            #     Dual_gate.ramp_to_voltage(Gate,gate_volt,0.001,0.002)

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
        category=["Gate Sweep", "Keithley 2450"],
    description="Sweeps a Gate Voltage while measuring Resistance (via Lock-ins).\n"
                "Supports Keithley 2450 and Dual Gate SMUs (Keithley 2604B).",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2','use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
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

#### Magnet Sweep measurement
class Resistance_magnet_sweep_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('RH measurement', default='RH')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')

    Target_field = FloatParameter('Target field (T)', group_by='use_magnet', default=0)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.5)

    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        # 1. Magnet Write (Trigger)
        if self.use_magnet:
            magnet.get_magnet_field_write()

        # 2. Temperature & Time
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        # 3. Dual Gate
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        # 4. Keithleys
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        # 5. Lock-ins
        vals += list(SRS860.snap("X", "Y")) if self.use_srs860 else [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        # 6. Magnet Read (Last Column)
        if self.use_magnet:
            vals.append(magnet.get_magnet_field_read())
        else:
            vals.append(math.nan)

        return vals

    def execute(self):
        if self.use_magnet == False:
            log.warning("Manget was not chosen measurement aborted")
            return
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla", self.Target_field)
        # --- 1. Persistent Heater Logic ---
        current_field = magnet.get_magnet_field()
        persistent_heater_status = magnet.get_persistent_switch_heater()
        print('Persistent switch heater mode: %s' % persistent_heater_status)
        # Test if the magnet heater is on, in case the persistent heater is off
        # turn it on and wait 10 min
        if persistent_heater_status == '0':
            log.info("Heater is OFF. Turning ON and waiting 600s...")
            magnet.set_persistent_switch_heater('ON')
            time.sleep(600)
            log.info("Heater warm-up complete.")

        # --- 2. Setup Sweep ---
        #### magnetic field at beginning for progress

        origin_field = magnet.get_magnet_field()
        magnet.go_to_target_field(self.Target_field)

        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero

        # --- 3. Monitoring Loop ---
        # We loop until the difference between current field and target is less than 3mT (0.003T)
        while abs(current_field - self.Target_field) > 0.003:

            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))  # Clamp between 0-100

            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                break
        log.info("Magnetic field Reached!")

    def shutdown(self):
        if self.use_magnet == True:
            current_field = magnet.get_magnet_field()
            if abs(current_field-self.Target_field) > 0.003:
                magnet.set_sweep_mode('PAUSE')
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")
proc_resistance_magnet = {
"Resistance magnet sweep measurement": dict(
        cls=Resistance_magnet_sweep_measurement,
        category="Magnetic Field",
        description="Measurement of resistance vs magnetic field sweep.",
        inputs=[
                'Title','Resistor','Contacts','Gate_contacts',
                'devices',
                'use_magnet','Target_field',
                'use_MFLI_1','use_MFLI_2' ,'use_MFLI_3',
                'use_srs860','use_srs830_1','use_srs830_2',
                'use_dual_gate','use_keithley_1','use_keithley_2',
                'acq_delay',
        ],
        displays=[
            'Title',
            'Target_field'],
        x=['time(s)'],
        y=['probe_temp(K)','field(T)'],
    ),
}

#### Measurement that changes both gates at every point.
class Resistance_two_gate_scan_sweep_measurement(Procedure):
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

    # --- Sweep Configuration ---
    sweeping = BooleanParameter('Sweeping Configuration', default=True)

    # Gate 1 Settings
    smu_1 = ListParameter('Top Gate SMU', default='Gate_1',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='sweeping', group_condition=True)
    smu_1_sp1 = FloatParameter('Top Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_1_sp2 = FloatParameter('Top Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)

    # Gate 2 Settings
    smu_2 = ListParameter('Bottom Gate SMU', default='Gate_2',
                          choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                          group_by='sweeping', group_condition=True)
    smu_2_sp1 = FloatParameter('Bottom Gate Start (V)', default=0.0, group_by='sweeping', group_condition=True)
    smu_2_sp2 = FloatParameter('Bottom Gate End (V)', default=0.0, group_by='sweeping', group_condition=True)

    smu_points = IntegerParameter('Number of Points', default=50, group_by='sweeping', group_condition=True)
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


    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]
    # Voltage ramping function so that the Keithley will show the ramping on the screen

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
        # 1. Magnet Write (Trigger)
        if self.use_magnet:
            magnet.get_magnet_field_write()

        # 2. Temperature & Time
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        # 3. Dual Gate
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        # 4. Keithleys
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        # 5. Lock-ins
        vals += list(SRS860.snap("X", "Y")) if self.use_srs860 else [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        # 6. Magnet Read (Last Column)
        if self.use_magnet:
            vals.append(magnet.get_magnet_field_read())
        else:
            vals.append(math.nan)

        return vals

    def smu_choice(self, Gate_name):
        """Resolves instrument object by name string."""
        if Gate_name == 'Gate_1': return Gate_1
        if Gate_name == 'Gate_2': return Gate_2
        if Gate_name == 'smua': return Dual_gate.smua
        if Gate_name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {Gate_name}")

    def smu_output(self, Gate, Gate_name):
        """Checks if output is on, if not, configures and turns it on."""
        if not Gate.is_output_on():
            log.info(f"{Gate_name} output was OFF. Turning it ON.")
            # Configure based on instrument type
            if Gate_name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                # Dual gate SMUChannel
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def execute(self):
        time_0 = time.time()
        ### Verify smu for measurements and turn them on
        top_gate = self.smu_choice(self.smu_1)
        bottom_gate = self.smu_choice(self.smu_2)

        # 2. Safety Check (Prevent same SMU for both)
        if self.smu_1 == self.smu_2:
            log.error("Top Gate and Bottom Gate cannot be the same SMU!")
            return
        # 3. Turn On Outputs
        self.smu_output(top_gate, self.smu_1)
        self.smu_output(bottom_gate, self.smu_2)


        # List of values for bottom gate and top gate for carrier density

        # 4. Generate Sweep Trajectories
        top_gate_list = np.linspace(self.smu_1_sp1,self.smu_1_sp2,self.smu_points)
        bottom_gate_list =  np.linspace(self.smu_2_sp1,self.smu_2_sp2,self.smu_points)

        # 5. Ramp to Initial Positions (Start Point)
        log.info(f"Moving to Start: Top={self.smu_1_sp1}V, Bottom={self.smu_2_sp1}V")

        top_gate.voltage_ramping(top_gate_list[0], 2, 0.1)
        log.info(f"Top ramped to {self.smu_1_sp1}V")

        bottom_gate.voltage_ramping(bottom_gate_list[0], 2, 0.1)
        log.info(f"Bottom ramped to {self.smu_2_sp1}V")

        time.sleep(30)
        # 6. The Sweep Loop
        for i in range[self.smu_points]:
            # Move both gates to next point
            top_gate.ramp_voltage(top_gate_list[i], 5, 0.05)
            bottom_gate.ramp_voltage(bottom_gate_list[i], 5, 0.05)

            # Wait & Measure
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * i / self.smu_points)

            if self.should_stop():
                log.warning("Sweep stopped by user.")
                break


    def shutdown(self):
        ##        sys.exit()
        # Return to 0 after sweep for device safety
        # Gate_2.shutdown()
        # log.info("Keithley off")
        log.info("Finished measuring two gate sweep")
proc_resistance_two_gate_sweep = {"Resistance two gate sweep measurement": dict(
        cls=Resistance_two_gate_scan_sweep_measurement,
        category=["Gate Sweep"],
    description="Sweeps two gates simultaneously along a line defined by Start/End points for each gate.\n"
                "Useful for Carrier Density/Displacement Field scans.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'sweeping',
            'smu_1',"smu_1_sp1","smu_1_sp2",
            'smu_2',"smu_2_sp1","smu_2_sp2",
            'smu_points', 'acq_delay',
        ],
        displays=[
            'Title',
            'smu_1',"smu_1_sp1","smu_1_sp2",
            'smu_2',"smu_2_sp1","smu_2_sp2",
            'smu_points',
        ],
        x='time(s)',
        y=['probe_temp(K)', 'SMUa(V)']
    ),}

#### ------ Not used for now ------ ####
#### Measurement with carrier density sweep with two gate voltage and constant Displacement electric field
class Resistance_carrier_density_farward_backward_measurement(Procedure):
    Title = Parameter(' Rn measurement', default='Rn')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers ', default='Insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

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

    sweeping = BooleanParameter('Mapping Rn', default=False)

    smu_1 = ListParameter('User defined top gate SMU', default='Gate_1', choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                          group_by='sweeping', group_condition=True)
    smu_2 = ListParameter('User defined bottom gate SMU', default='Gate_2',
                          choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                          group_by='sweeping', group_condition=True)
    displacement = FloatParameter('Displacement field [V/nm]', default=0, group_by='mapping'
                                  , group_condition=True, minimum=-1.1, maximum=1.1)

    top_gate_CNP = FloatParameter("Top gate voltage from CNP [V]", default=0.01, group_by='sweeping',
                                  group_condition=True)
    top_capacitance = FloatParameter("Top electrode hBN capacitance [F/m^2] ", default=0.1, group_by='sweeping',
                                     group_condition=True)
    bottom_gate_CNP = FloatParameter("Bottom gate voltage from CNP [V]", default=0.01, group_by='sweeping'
                                     , group_condition=True)
    bottom_capacitance = FloatParameter("Bottom electrode hBN capacitance [F/m^2]", default=0.1, group_by='sweeping'
                                        , group_condition=True)

    max_carrier = FloatParameter('Maximum induced carrier density (10¹⁶ m⁻²)', default=0.1, group_by='sweeping'
                                 , group_condition=True)
    min_carrier = FloatParameter('Minimum induced carrier density (10¹⁶ m⁻²)', default=-0.1, group_by='sweeping'
                                 , group_condition=True)
    carrier_points = IntegerParameter('Number of points for carrier density sweep', default=1, group_by='sweeping'
                                      , group_condition=True)

    mag_delay = FloatParameter('Delay after Magnetic sweep (s)', default=120, group_by='sweeping', group_condition=True)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

    # Voltage ramping function so that the Keithley will show the ramping on the screen

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
        temperature = read_temperature()
        vals = [time.time() - t0, temperature[0], temperature[1], temperature[2], temperature[3]]
        if self.use_magnet:
            magnet.get_magnet_field_write()
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan, math.nan, math.nan, math.nan]
        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_1:
            x, y = MFLI_1.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_2:
            x, y = MFLI_2.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_3:
            x, y = MFLI_3.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_magnet:
            vals += [magnet.get_magnet_field_read()]
        else:
            vals += [math.nan]
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def milli_step(self, start, end, step):
        if start > end:
            step = step / -1000
        elif start < end:
            step = step / 1000
        else:
            exit()
        return step

    def voltage_list(self, start, end):
        disp = self.displacement * epsilon_0 * 1e9
        v_tg_start = (2 * disp + start * 1e16 * e) / (2 * self.top_capacitance) + self.top_gate_CNP
        v_tg_end = (2 * disp + end * 1e16 * e) / (2 * self.top_capacitance) + self.top_gate_CNP

        v_bg_start = (2.0 * disp - start * 1e16 * e) / (-2.0 * self.bottom_capacitance) + self.bottom_gate_CNP
        v_bg_end = (2.0 * disp - end * 1e16 * e) / (-2.0 * self.bottom_capacitance) + self.bottom_gate_CNP

        top_voltage_list = np.linspace(v_tg_start, v_tg_end, self.carrier_points)
        bottom_voltage_list = np.linspace(v_bg_start, v_bg_end, self.carrier_points)

        return top_voltage_list, bottom_voltage_list

    def execute(self):
        time_0 = time.time()
        ### Verify smu for measurements and turn them on
        top_gate = self.smu_choice(self.smu_1)
        if not top_gate.is_output_on() == True:
            self.smu_output(top_gate, self.smu_1)

        bottom_gate = self.smu_choice(self.smu_2)
        if not bottom_gate.is_output_on() == True:
            self.smu_output(bottom_gate, self.smu_2)

        iteration = 1
        # List of values for bottom gate and top gate for carrier density
        top_gate_list, bottom_gate_list = self.voltage_list(self.min_carrier, self.max_carrier)

        i = 0
        for gate_volt in top_gate_list:
            log.info("starting gate sweep")
            if gate_volt == top_gate_list[0] and top_gate.measure__voltage() != gate_volt:
                log.info("Gate voltage ramping to initial value")
                top_gate.voltage_ramping(top_gate_list[0], 2, 0.1)
                log.info("Top gate ramped to initial value")
                bottom_gate.voltage_ramping(bottom_gate_list[0], 2, 0.1)
                log.info("Bottom gate ramped to initial value")
                time.sleep(60)
            else:
                top_gate.ramp_voltage(top_gate_list[i], 5, 0.1)
                bottom_gate.ramp_voltage(bottom_gate_list[i], 5, 0.1)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / self.carrier_points)
            iteration += 1
            i += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        ##        sys.exit()
        # Return to 0 after sweep for device safety
        magnet.set_sweep_mode('PAUSE')
        # Gate_2.shutdown()
        # log.info("Keithley off")
        log.info("Finished measuring")
proc_resistance_carrier_density ={

"Resistance carrier density sweep measurement": dict(
        cls=Resistance_carrier_density_farward_backward_measurement,
        category=["Gate Sweep"],
        description="Measurement of resistance vs carrier density sweep using two gate sources./\n"
                    " For this measurement the user needs to know the capacitance of each gate and the distance from CNP.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2','use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'sweeping',
            'smu_1', 'smu_2',
            'displacement',
            'top_gate_CNP','top_capacitance',
            'bottom_gate_CNP','bottom_capacitance',
            'max_carrier','min_carrier','carrier_points',
            'mag_delay', 'acq_delay',
        ],
        displays=[
            'Title',
            'displacement',
            'max_carrier','min_carrier',
        ],
        x='time(s)',
        y=['probe_temp(K)', 'field(T)', 'SMUa(V)']
    ),
}
#### ------ Not used for now ------ ####

#### 2D mapping using two SMUs
class Resistance_two_gate_mapping_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('RVV measurement', default='RVV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers', default='Insert contact numbers')
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

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping', default=True)

    # Scan Mode Toggle
    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    # Slow Axis
    slow_smu = ListParameter('Slow Axis SMU', default='Gate_1', group_by='mapping', group_condition=True,
                             choices=['Gate_1', 'Gate_2', 'smua', 'smub'])
    slow_start = FloatParameter('Slow Start (V)', default=-1, group_by='mapping', group_condition=True)
    slow_end = FloatParameter('Slow End (V)', default=1, group_by='mapping', group_condition=True)
    slow_step = FloatParameter('Slow Step (mV)', default=10, group_by='mapping', group_condition=True)
    long_delay = FloatParameter('Slow Axis Delay (s)', default=1.0, group_by='mapping', group_condition=True)

    # Fast Axis
    fast_smu = ListParameter('Fast Axis SMU', default='Gate_2', group_by='mapping', group_condition=True,
                             choices=['Gate_1', 'Gate_2', 'smua', 'smub'])
    fast_start = FloatParameter('Fast Start (V)', default=-2, group_by='mapping', group_condition=True)
    fast_end = FloatParameter('Fast End (V)', default=2, group_by='mapping', group_condition=True)
    fast_step = FloatParameter('Fast Step (mV)', default=5, group_by='mapping', group_condition=True)
    short_delay = FloatParameter('Fast Axis Delay (s)', default=0.1, group_by='mapping', group_condition=True)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        if self.use_magnet:
            magnet.get_magnet_field_write()

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
            vals.append(magnet.get_magnet_field_read())
        else:
            vals.append(math.nan)
        return vals

    def smu_choice(self, name):
        if name == 'Gate_1': return Gate_1
        if name == 'Gate_2': return Gate_2
        if name == 'smua': return Dual_gate.smua
        if name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {name}")

    def smu_output(self, Gate, name):
        if not Gate.is_output_on():
            log.info(f"{name} output was OFF. Turning it ON.")
            if name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_mv):
        step_v = abs(step_mv / 1000.0)
        if step_v == 0: step_v = 0.001
        num_points = int(abs(end - start) / step_v) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        #1/ SMU setup
        slow_gate = self.smu_choice(self.slow_smu)
        fast_gate = self.smu_choice(self.fast_smu)

        if self.slow_smu == self.fast_smu:
            log.error("Slow and Fast SMUs cannot be the same!")
            return

        self.smu_output(slow_gate,self.slow_smu)
        self.smu_output(fast_gate,self.fast_smu)

        # 2. Generate Sweep Arrays
        slow_range = self.generate_range(self.slow_start, self.slow_end, self.slow_step)

        # Forward Trace: Start -> End
        fast_range_forward = self.generate_range(self.fast_start, self.fast_end, self.fast_step)
        # Backward Trace: End -> Start (inverted forward array)
        fast_range_backward = fast_range_forward[::-1]

        # Calculate Total Points for Progress Bar
        points_per_line = len(fast_range_forward)
        if self.scan_mode == 'Forward/Backward':
            points_per_line *= 2

        total_points = len(slow_range) * points_per_line
        point_counter = 0

        # 3. Move to Initial Position (Slow Start, Fast Start)
        log.info(f"Moving to start: Slow={self.slow_start}V, Fast={self.fast_start}V")
        slow_gate.voltage_ramping(self.slow_start, 2, 0.1)
        if self.should_stop():
            log.warning("User stopped measurement during initial slow SMU ramp")
            return
        time.sleep(self.long_delay)

        fast_gate.voltage_ramping(self.fast_start, 2, 0.1)
        if self.should_stop():
            log.warning("User stopped measurement during initial fast SMU ramp")
            return
        log.info(f"Stabilizing before {self.scan_mode} sweep...")
        time.sleep(self.long_delay)


        for i, slow_v in enumerate(slow_range):

            # --- Move Slow Axis ---
            slow_gate.ramp_voltage(slow_v, steps=5, delay=0.01)
            time.sleep(self.short_delay)

            # --- CASE 1: SNAKE MODE ---
            # If Row is Even (0, 2..): Forward (Start -> End)
            # If Row is Odd  (1, 3..): Backward (End -> Start)
            if self.scan_mode == 'Snake':
                if i % 2 == 0:
                    current_range = fast_range_forward
                else:
                    current_range = fast_range_backward
                # Execute One Pass
                for fast_v in current_range:
                    fast_gate.ramp_voltage(fast_v, steps=5, delay=0.05)
                    time.sleep(self.short_delay)

                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return


            # --- CASE 2: FORWARD/BACKWARD MODE ---
            # Every Row: Forward (Start -> End) THEN Backward (End -> Start)
            elif self.scan_mode == 'Forward/Backward':

                # Part A: Forward
                for fast_v in fast_range_forward:
                    fast_gate.ramp_voltage(fast_v, steps=5, delay=0.05)
                    time.sleep(self.short_delay)

                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

                # Part B: Backward
                for fast_v in fast_range_backward:
                    fast_gate.ramp_voltage(fast_v, steps=2, delay=0.005)
                    time.sleep(self.short_delay)

                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

                    point_counter += 1
                    self.emit('progress', 100 * (point_counter / total_points))
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
        log.info(f"Finished measuring {self.scan_mode} 2D mapping")
proc_resistance_two_gate_map = {
    "Resistance two gate mapping measurement": dict(
        cls=Resistance_two_gate_mapping_measurement,
        category=["2D Mapping", "Gate Sweep", "Keithley 2450"],
        description="2D Resistance Map with Selectable Scan Mode.\n"
                    "1. Snake: Alternates direction every row (Start->End, End->Start). Fastest.\n"
                    "2. Forward/Backward: Sweeps both directions (Start->End AND End->Start) at every row. Use for hysteresis.\n",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2','use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1','use_keithley_2',
            'mapping',
            'scan_mode',
            'slow_smu', 'slow_start', 'slow_end', 'slow_step', 'long_delay',
            'fast_smu', 'fast_start', 'fast_end', 'fast_step', 'short_delay',
        ],
        displays=[
            'Title','scan_mode',
            'slow_start', 'slow_end', 'slow_step', 'slow_smu',
            'fast_start', 'fast_end', 'fast_step', 'fast_smu'
        ],
        x=['time(s)'],
        y=['probe_temp(K)', 'SMUa(V)'],
    ),}

#### 2D mapping using Magnetic field and SMU
class Resistance_magnet_and_gate_mapping_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter(' RHV measurement', default='RHV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contact numbers ', default='Insert contact numbers')
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

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping RHV', default=True)

    scan_mode = ListParameter('Gate Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    smu = ListParameter('User defined SMU', default='Gate_1', choices=['smua', 'smub', 'Gate_1', 'Gate_2'],
                        group_by='mapping', group_condition=True)
    gate_start = FloatParameter('Gate min voltage(V)', default=-1, group_by='mapping', group_condition=True)
    gate_end = FloatParameter('Gate max voltage(V)', default=1, group_by='mapping', group_condition=True)
    gate_step = FloatParameter('Gate Voltage step size (mV)', default=5, group_by='mapping', group_condition=True)

    field_start = FloatParameter('Magnetic field start (T)', default=0, group_by='mapping', group_condition=True)
    field_end = FloatParameter('Magnetic field end (T)', default=1, group_by='mapping', group_condition=True)
    field_step = FloatParameter('Magnetic field step size (mT)', default=50, group_by='mapping', group_condition=True)

    mag_delay = FloatParameter('Delay after Magnetic sweep (s)', default=120, group_by='mapping', group_condition=True)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

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


    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

    # Voltage ramping function so that the Keithley will show the ramping on the screen

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
        temperature = read_temperature()
        vals = [time.time() - t0, temperature[0], temperature[1], temperature[2], temperature[3]]
        if self.use_magnet:
            magnet.get_magnet_field_write()
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan, math.nan, math.nan, math.nan]
        if self.use_keithley_1:
            vals += [Gate_1.measure__voltage(), Gate_1.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_keithley_2:
            vals += [Gate_2.measure__voltage(), Gate_2.measure__current()]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_1:
            x, y = MFLI_1.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_2:
            x, y = MFLI_2.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_3:
            x, y = MFLI_3.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_magnet:
            vals += [magnet.get_magnet_field_read()]
        else:
            vals += [math.nan]
        return vals

    def smu_choice(self, name):
        if name == 'Gate_1': return Gate_1
        if name == 'Gate_2': return Gate_2
        if name == 'smua': return Dual_gate.smua
        if name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {name}")

    def smu_output(self, Gate, name):
        if not Gate.is_output_on():
            log.info(f"{name} output was OFF. Turning it ON.")
            if name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        # step_units is mT for magnet, mV for gate
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    # Auto range function to incorporate several devices which need to change sensitivity at the same time
    def execute(self):
        time_0 = time.time()

        # SMU handelling
        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        # 1. Generate Sweep Arrays
        field_range = self.generate_range(self.field_start, self.field_end, self.field_step)
        gate_range_fwd = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        gate_range_bwd = gate_range_fwd[::-1]

        # 2. Magnet Safety Check
        if magnet.get_persistent_switch_heater() == '0':
            magnet.set_persistent_switch_heater('ON')
            log.info("Persistent switch heater turned ON. Delaying 10min.")
            time.sleep(600)
            # 3. Initial Ramping (Start positions)
            log.info(f"Moving to Initial Position: Field={self.field_start}T, Gate={self.gate_start}V")
            magnet.go_to_target_field(self.field_start)
            # We wait for magnet to reach start while taking data
        while abs(magnet.get_magnet_field() - self.field_start) > 0.003:
            if self.should_stop():
                magnet.set_sweep_mode('PAUSE')
                log.warning("User stopped measurement during initial magnet sweep, magnet is Paused")
                return

            self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
            time.sleep(self.acq_delay)
        gate.voltage_ramping(self.gate_start, 2, 0.1)
        if self.should_stop():
            log.warning("User stopped measurement during initial gate ramping")
            return
        time.sleep(self.mag_delay)

        # 4. Main Loop
        iteration = 1
        total_steps = len(field_range) * len(gate_range_fwd) * (2 if self.scan_mode == 'Forward/Backward' else 1)
        for i, field in enumerate(field_range):
            # Move Field (skip wait on first iteration if already there)
            if i > 0:
                magnet.go_to_target_field(field)
                while abs(magnet.get_magnet_field() - field) > 0.003:
                    if self.should_stop():
                        magnet.set_sweep_mode('PAUSE')
                        log.warning("User stopped measurement during  magnet ramp, magnet is Paused")
                        return
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    time.sleep(self.acq_delay)
                log.info(f"Field at {field}T. Stabilizing...")
                time.sleep(self.mag_delay)

            # Define Gate logic
            # --- CASE 1: SNAKE MODE ---
            if self.scan_mode == 'Snake':
                current_gate_range = gate_range_fwd if i % 2 == 0 else gate_range_bwd
                for g_volt in current_gate_range:
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

            # --- CASE 2: FORWARD/BACKWARD MODE ---
            # Every Row: Forward (Start -> End) THEN Backward (End -> Start)
            elif self.scan_mode == 'Forward/Backward':
                log.info("Forward/Backward scanning")

                # Part A: Forward
                for g_volt in gate_range_fwd:
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

                # Part B: Backward
                for g_volt in gate_range_bwd:
                    gate.ramp_voltage(g_volt, steps=5, delay=0.01)
                    time.sleep(self.acq_delay)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_steps)
                    iteration += 1
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
        magnet.set_sweep_mode('PAUSE')
        log.info("Finished measuring")
proc_resistance_magnet_gate_map = {
"Resistance magnet and gate mapping measurement": dict(
        cls=Resistance_magnet_and_gate_mapping_measurement,
        category=["2D Mapping","Gate Sweep", "Magnetic Field"],
    description="Resistance vs Magnet and Gate."
                " Includes Snake or Hysteresis (Forward/Backward) gate sweep options.",
    inputs=[
        'Title', 'Resistor', 'Contacts', 'Gate_contacts',
        'devices',
        'use_magnet',
        'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
        'use_srs860', 'use_srs830_1', 'use_srs830_2',
        'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
        'mapping', 'scan_mode',
        'field_start', 'field_end', 'field_step',
        'smu', 'gate_start', 'gate_end', 'gate_step',
        'mag_delay', 'acq_delay',
    ],
    displays=[
        'Title', 'scan_mode',
        'smu', 'gate_start', 'gate_end',
        'field_start', 'field_end'
    ],
        x = 'time(s)',
        y = ['probe_temp(K)','field(T)','SMUa(V)']
    ),
}

###### Measurement with two gate voltages and magnetic field to
######  sweep carrier density while change the magnetic field between sweeps
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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        if self.use_magnet:
            magnet.get_magnet_field_write()

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
            vals.append(magnet.get_magnet_field_read())
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
        time_0 = time.time()
        log.info("Starting Magnet + 2-Gate Map")

        # --- 1. Instrument Setup ---
        # Resolve Instruments
        gate_1_inst = self.smu_choice(self.smu_1)
        gate_2_inst = self.smu_choice(self.smu_2)

        if self.smu_1 == self.smu_2:
            log.error("Gate 1 and Gate 2 cannot be the same instrument!")
            return

        # Turn ON
        self.smu_output(gate_1_inst, self.smu_1)
        self.smu_output(gate_2_inst, self.smu_2)

        # --- 2. Generate Arrays ---
        # Magnet
        field_range = self.generate_range(self.field_start, self.field_end, self.field_step)

        # Gates (Forward Lists)
        # We use linspace because we want both gates to move proportionally over 'smu_points'
        gate_1_list_fwd = np.linspace(self.smu_1_sp1, self.smu_1_sp2, self.smu_points)
        gate_2_list_fwd = np.linspace(self.smu_2_sp1, self.smu_2_sp2, self.smu_points)

        # Gates (Backward Lists)
        gate_1_list_bwd = gate_1_list_fwd[::-1]
        gate_2_list_bwd = gate_2_list_fwd[::-1]

        # --- 3. Initial Magnet Safety & Positioning ---
        if magnet.get_persistent_switch_heater() == '0':
            magnet.set_persistent_switch_heater('ON')
            log.info("Magnet heater ON. Waiting 10min...")
            time.sleep(600)

        # Ramp Magnet to Start
        log.info(f"Ramping Magnet to start: {self.field_start}T")
        magnet.go_to_target_field(self.field_start)

        # Ramp Gates to Start (Start of FWD list)
        log.info(f"Ramping Gates to Start: {self.smu_1_sp1}V, {self.smu_2_sp1}V")
        gate_1_inst.voltage_ramping(gate_1_list_fwd[0], 2, 0.1)
        gate_2_inst.voltage_ramping(gate_2_list_fwd[0], 2, 0.1)

        # Wait for Magnet to reach start
        # decide at a later time if i want to document the ramping data
        while abs(magnet.get_magnet_field() - self.field_start) > 0.003:
            if self.should_stop():
                magnet.set_sweep_mode('PAUSE')
                log.warning("Measurement stopped by user, MAGNET is PAUSED")
                return
            #self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
            time.sleep(self.acq_delay)

        time.sleep(self.mag_delay)  # Initial stabilization

        # --- 4. Main Loops ---

        # Calculate total iterations for progress bar
        # If 'Forward/Backward', we do 2 sweeps per field step. If 'Snake', we do 1 sweep per field step.
        steps_per_field = self.smu_points * (2 if self.scan_mode == 'Forward/Backward' else 1)
        total_steps = len(field_range) * steps_per_field
        iteration_count = 1

        for i, field in enumerate(field_range):

            # --- Move Magnet (Skip first point as we are already there) ---
            if i > 0:
                magnet.go_to_target_field(field)
                while abs(magnet.get_magnet_field() - field) > 0.003:
                    if self.should_stop():
                        magnet.set_sweep_mode('PAUSE')
                        log.warning("User stopped during magnet ramp")
                        return
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    time.sleep(self.acq_delay)

                log.info(f"Field reached {field}T. Stabilizing...")
                time.sleep(self.mag_delay)

            # --- Define Gate Lists based on Scan Mode ---
            lists_to_run = []  # List of tuples: (gate1_list, gate2_list)

            if self.scan_mode == 'Snake':
                # Even iteration (0, 2, 4): Forward
                if i % 2 == 0:
                    lists_to_run.append((gate_1_list_fwd, gate_2_list_fwd))
                # Odd iteration (1, 3, 5): Backward
                else:
                    lists_to_run.append((gate_1_list_bwd, gate_2_list_bwd))

            elif self.scan_mode == 'Forward/Backward':
                # Always do Forward THEN Backward
                lists_to_run.append((gate_1_list_fwd, gate_2_list_fwd))
                lists_to_run.append((gate_1_list_bwd, gate_2_list_bwd))

            # --- Execute Gate Sweeps ---
            for (g1_list, g2_list) in lists_to_run:

                # Zip the two gate lists together to move them simultaneously
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
                        magnet.set_sweep_mode('PAUSE')
                        return

    def shutdown(self):
        magnet.set_sweep_mode('PAUSE')
        log.info("Finished measuring")
proc_resistance_magnet_2gate_map = {
    "Resistance Magnet and 2-Gate Map": dict(
        cls=Resistance_magnet_and_2gate_mapping_measurement,
        category=["2D Mapping", "Gate Sweep", "Magnetic Field"],
        description="2D Map: Magnetic Field (Outer) vs Simultaneous Two-Gate Sweep (Inner).\n"
                    "The two-Gate sweep must be calculated ion advance to determine Carrier density/Displacement.\n"
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
        y=['probe_temp(K)', 'field(T)', 'SMUa(V)']
    ),
}

######## Differential conductance measurement for Tunnel junction using SRS860
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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'DC_offset(V)',
        'Lockin_Current_SRS860_X(A)', 'Lockin_Current_SRS860_Y(A)',
        'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
        'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
        'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
        'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
        'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

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

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()

        # 1. Determine Start Position (Wherever we are right now)
        start_v = SRS860.dc_offset
        target_v = self.dc_offset_setpoint
        log.info(f"Starting dI/dV {self.scan_mode}. Start={start_v:.4f}V, Target={target_v:.4f}V")

        # 2. Generate Sweep Arrays
        # Trace A: Origin -> Target
        range_to_target = self.generate_range(start_v, target_v, self.dc_offset_step)

        #Trace B: Target -> Origin(only for return mode)
        # Note: We generate this from Target back to Start.
        range_return = self.generate_range(target_v, start_v, self.dc_offset_step)

        # Calculate total points for progress bar
        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        # --- PART 1: Sweep to Setpoint ---
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

        # --- PART 2: Sweep back to Origin (Optional) ---
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

        # Note: If mode is "Sweep to Setpoint", we simply finish here.
        # The voltage remains at 'target_v'.

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

######### Differential conductance measurement for Tunnel junction using Zurich MFLI
class Differential_conductance_Zurich(Procedure):
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

    scan_mode = ListParameter('Scan Mode', default='Sweep and Return',
                              choices=['Sweep to Setpoint', 'Sweep and Return'],
                              group_by='use_MFLI_1', group_condition=True)

    dc_offset_setpoint = FloatParameter('Target Setpoint (V)', group_by='use_MFLI_1', default=0.1)
    dc_offset_step = FloatParameter('DC Step Size (mV)', group_by='use_MFLI_1', default=1)
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


    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Current_SRS860_X(A)', 'Lockin_Current_SRS860_Y(A)',
        'DC_offset(V)',
        'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
        'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
        'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
        'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
        'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
        'field(T)',

    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        if self.use_srs860:
            r, th = SRS860.snap("X", "Y")
            vals += [r, th]
        else:
            vals += [math.nan, math.nan, math.nan]

        # extra if term for dc_offset
        if self.use_MFLI_1:
            dc_offset = MFLI_1.dc_offset
            vals += [dc_offset]
        else:
            vals += [math.nan]
        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def generate_range(self, start, end, step_mv):
        """Generates a linspace from Start to End."""
        step_v = abs(step_mv / 1000.0)
        if step_v == 0: step_v = 0.001

        # Calculate number of points based on absolute distance
        distance = abs(end - start)
        num_points = int(distance / step_v) + 1

        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        start_v = MFLI_1.dc_offset
        target_v = self.dc_offset_setpoint
        log.info(f"Starting dI/dV {self.scan_mode}. Start={start_v:.4f}V, Target={target_v:.4f}V")

        # 2. Generate Sweep Arrays
        # Trace A: Origin -> Target
        range_to_target = self.generate_range(start_v, target_v, self.dc_offset_step)

        # Trace B: Target -> Origin(only for return mode)
        # Note: We generate this from Target back to Start.
        range_return = self.generate_range(target_v, start_v, self.dc_offset_step)

        # Calculate total points for progress bar
        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0
        # --- PART 1: Sweep to Setpoint ---
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
        # --- PART 2: Sweep back to Origin (Optional) ---
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
##        sys.exit()
        log.info("Finished measuring")
proc_differential_conductance_Zurich = {
    "Differential conductance Zurich": dict(
        cls=Differential_conductance_Zurich,
        category="Tunneling junction",
        description="dI/dV Sweep starting from CURRENT DC Offset using ZUrich MFLI_1.\n"
                    "1. Sweep to Setpoint: Measures from [Current] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Current] -> [Target] -> [Current]. Returns voltage to start.",
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1',
            'scan_mode', 'dc_offset_setpoint', 'dc_offset_step',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'acq_delay',
        ],
        displays=['Title', 'scan_mode', 'dc_offset_setpoint', 'dc_offset_step'],
        x=['DC_offset(V)'],
        y=['MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)'],
    ),
}

#### ------ Not used for now ------ ####
########## Differential conductance measurement for Tunnel junction using MFLI for certain gate voltage
class Differential_conductance_Zurich_gated(Procedure):

    Title = Parameter('dI/dV measurement', default='Rt')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    dc_offset_start = FloatParameter('DC offset set point 1 (V)',group_by = 'use_MFLI_1', default = 0)
    dc_offset_end = FloatParameter('DC offset set point 2 (V)',group_by = 'use_MFLI_1', default = -0)
    dc_offset_step = FloatParameter(' dc offset step (mV)',group_by = 'use_MFLI_1', default = 1)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=float(5 * 0.1))

    smu = ListParameter('User defined SMU',choices=['smua','smub','Gate_1','Gate_2'], default='smua')
    gate_target = FloatParameter('Target Voltage(V)', default = 0)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Current_SRS860_X(A)', 'Lockin_Voltage_SRS860_Y(V)',
        'DC_offset(V)',
        'MFLI_Lockin_1_Current_X(A)', 'MFLI_Lockin_1_Current_Y(A)',
        'MFLI_Lockin_2_Current_X(A)', 'MFLI_Lockin_2_Current_Y(A)',
        'MFLI_Lockin_3_Current_X(A)', 'MFLI_Lockin_3_Current_Y(A)',
        'Lockin_Current_SRS830_1_X(A)', 'Lockin_Current_SRS830_1_Y(A)',
        'Lockin_Current_SRS830_2_X(A)', 'Lockin_Current_SRS830_2_Y(A)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0, temperature[0], temperature[1], temperature[2], temperature[3]]
        if self.use_magnet:
            magnet.get_magnet_field_write()

        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan, math.nan, math.nan, math.nan]
        if self.use_srs860:
            r, th = SRS860.snap("X", "Y");
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_1:
            x, y = MFLI_1.read_demod();
            dc_offset = MFLI_1.dc_offset
            vals += [dc_offset,x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_2:
            x, y = MFLI_2.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_MFLI_3:
            x, y = MFLI_3.read_demod()
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_1:
            r, th = SRS830_1.snap("X", "Y");
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_srs830_2:
            r, th = SRS830_2.snap("X", "Y");
            vals += [r, th]
        else:
            vals += [math.nan, math.nan]
        if self.use_magnet:
            vals += [magnet.get_magnet_field_read()]
        else:
            vals += [math.nan]
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def milli_step(self, start, end, step):
        if start > end:
            step = step / -1000
        elif start < end:
            step = step / 1000
        else:
            exit()
        return step

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure")
        #### Determine chosen smu
        Gate = self.smu_choice(self.smu)

        #### Turn on output if it was off
        if not Gate.is_output_on() == True:
            self.smu_output(Gate, self.smu)
            log.info("SMU output is now on")
        else:
            log.info("SMU output was on")
        if Gate.measure__voltage != self.gate_target:
            Gate.voltage_ramping(self.gate_target,2,0.1)

        dc_offset_origin = MFLI_1.dc_offset
        milli_step = self.milli_step(dc_offset_origin, self.dc_offset_start, self.dc_offset_step)

        for dc_offset in np.arange(dc_offset_origin, self.dc_offset_start + milli_step*1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break
        #MFLI_1.set_dc_offset(self.dc_offset_start)

        milli_step = self.milli_step(self.dc_offset_start, self.dc_offset_end, self.dc_offset_step)

        for dc_offset in np.arange(MFLI_1.dc_offset, self.dc_offset_end + milli_step*1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset
            time.sleep(self.acq_delay)

            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break
        #MFLI_1.set_dc_offset(self.dc_offset_end)
        milli_step = self.milli_step(self.dc_offset_end, dc_offset_origin, self.dc_offset_step)

        for dc_offset in np.arange(MFLI_1.dc_offset, dc_offset_origin + milli_step*1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset
            time.sleep(self.acq_delay)

            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break
        #MFLI_1.set_dc_offset(dc_offset_origin)

    def shutdown(self):
##        sys.exit()
        log.info("Finished measuring")
proc_differential_conductance_Zurich_gate = {    "Differential conductance Zurich gated": dict(
        cls=Differential_conductance_Zurich_gated,
        category=["Tunneling junction"],
        description="New measurement for renu",
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1','use_MFLI_2','use_MFLI_3',
            'dc_offset_start', 'dc_offset_end', 'dc_offset_step',
            'use_srs860', 'use_srs830_1','use_srs830_2',
            'use_dual_gate','use_keithley_1','use_keithley_2',
            'gate_sweep','gate_target',
            'acq_delay',
        ],
        displays=[
            'Title',
            'dc_offset_start', 'dc_offset_end', 'dc_offset_step'
        ],
        x=['time(s)', 'DC_offset(V)'],
        y=['probe_temp(K)', 'MFLI_Lockin_1_Current_X(A)'],
    ),}
#### ------ Not used for now ------ ####

########### Differential resistance measurement using MFLI aux for DC current
class Differential_Resistance_Zurich(Procedure):
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- Sweep Parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                               default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target  (V)', group_by='use_MFLI_1', default=0)
    aux_signal = IntegerParameter('Auxiliary DC Signal ', group_by='use_MFLI_1', default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ", group_by='use_MFLI_1', default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['use_MFLI_1', 'aux_select'],
                                 group_condition=[True, lambda v: v == 11 or v == 13])
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='use_MFLI_1', default=2)

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

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

        # extra if term for aux
        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)
        target_aux = self.aux_Target
        log.info(f"Starting dV/dI {self.scan_mode}. Start={aux_origin:.4f}V, Target={target_aux:.4f}V")

        # 2. Generate Sweep Arrays
        # Trace A: Origin -> Target
        range_to_target = self.generate_range(aux_origin, target_aux, self.aux_step)

        # Trace B: Target -> Origin(only for return mode)
        # Note: We generate this from Target back to Start.
        range_return = self.generate_range(target_aux, aux_origin, self.aux_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        # --- PART 1: Sweep to Setpoint ---
        log.info("Sweeping to Setpoint...")
        for aux in range_to_target:
            MFLI_1.aux_ramp(self.aux_signal,aux, 5,0.01)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100* point_counter/total_points)
            point_counter += 1
            if self.should_stop():
                log.warning("User stopped measurement while in Sweep")
                return

        # --- PART 2: Sweep back to Origin (Optional) ---
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


    def shutdown(self):
        log.info("Finished measuring")
proc_differential_resistance_Zurich = {
    "Differential Resistance Zurich": dict(
        cls=Differential_Resistance_Zurich,
        category="Differential Resistance",
        description="dV/dI Sweep starting from Origin DC AUX using MFLI_1.\n"
                    "1. Sweep to Setpoint: Measures from [Origin] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Origin] -> [Target] -> [Origin]. Returns voltage to start.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'acq_delay',
            'devices',
            'use_magnet',
            'use_MFLI_1',
            'aux_Target', 'aux_step', 'aux_signal', 'aux_select', 'aux_demod',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate','use_keithley_1','use_keithley_2',
            'scan_mode',
        ],
        displays=[
            'Title','scan_mode', 'aux_Target'],
        x=['AUX_DC_offset(V)'],
        y=['MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)'],

    ),
}


########### Differential resistance mapping using MFLI aux for DC current and SMU for gating
class Differential_Resistance_Gate_map_Zurich(Procedure):
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    aux_signal = IntegerParameter('Auxiliary DC Signal ',group_by= 'use_MFLI_1', default = 0)
    aux_select = IntegerParameter("Auxiliary DC Select ",group_by = 'use_MFLI_1', default = -1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by = ['use_MFLI_1','aux_select'],group_condition=[True, lambda v: v==11 or v==13])

    mapping = BooleanParameter('Mapping', default=False)
    # Scan Mode Toggle
    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward','Hysteresis'],
                               group_by='mapping', group_condition=True)

    long_delay = FloatParameter('Delay after long ramp (s)', default=60, group_by='mapping', group_condition=True)
    short_delay = FloatParameter('Delay after short ramp (s)', default=5, group_by='mapping', group_condition=True)

    smu = ListParameter('User defined SMU',choices=['Gate_1','Gate_2','smua','smub'],group_by='mapping', group_condition=True, default='Gate_1')
    gate_sp1 = FloatParameter('Gate set point 1  voltage(V)',group_by='mapping', group_condition=True, default=-1)
    gate_sp2 = FloatParameter('Gate set point 2  voltage(V)',group_by='mapping', group_condition=True, default=1)
    gate_step = IntegerParameter('Gate Voltage step size (mV)',group_by='mapping', group_condition=True, default=5)

    aux_sp1 = FloatParameter('Auxiliary DC Bias Sp1  (V)', group_by='mapping',group_condition=True, default=0)
    aux_sp2 = FloatParameter('Auxiliary DC Bias Sp2  (V)', group_by='mapping',group_condition=True, default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='mapping',group_condition=True, default=2)

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

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

        # extra if term for aux
        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure dV/dI bias and gate map sweep measurement")

        Gate = self.smu_choice(self.smu)
        #### Turn on output if it was off
        if not Gate.is_output_on() == True:
            self.smu_output(Gate, self.smu)
            log.info("SMU output is now on")
        else:
            log.info("SMU output was on")

        ## set the MFLI instrument to aux signal manual mode unless specified differently
        MFLI_1.set_auxout(self.aux_signal,self.aux_select,self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)

        #  Define Aux Sweep Arrays
        if self.scan_mode == 'Hysteresis':
            aux_range_1 = self.generate_range(aux_origin,self.aux_sp1, self.aux_step)
            aux_range_2 = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_3 = self.generate_range(self.aux_sp2,aux_origin, self.aux_step)
            full_aux_sweep = np.concatenate([aux_range_1, aux_range_2, aux_range_3])
            pts_per_gate = len(full_aux_sweep)

        elif self.scan_mode == 'Forward/Backward':
            aux_range_1 = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_2 = self.generate_range(self.aux_sp2, self.aux_sp1, self.aux_step)
            full_aux_sweep = np.concatenate([aux_range_1, aux_range_2])
            pts_per_gate = len(full_aux_sweep)

        elif self.scan_mode == 'Snake':
            aux_range_odd = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)
            aux_range_even = self.generate_range(self.aux_sp2, self.aux_sp1, self.aux_step)
            pts_per_gate = len(aux_range_even)

        voltage_range = self.generate_range(self.gate_sp1,self.gate_sp2, self.gate_step)

        # number of point for Snake is N for Forward/Backward is 2N and for Hysteresis is 3N
        total = pts_per_gate*len(voltage_range)

        # iteration variable for progress bar and direction variable for Snake scan mode
        iteration, direction  = 1,1

        # first long gave ramp with option to stop in the middle
        log.info("Ramping Gate to Start Position...")
        start_gate_val = Gate.measure__voltage()
        voltage_ramp = self.generate_range(start_gate_val, self.gate_sp1, 2)
        for v in voltage_ramp:
            Gate.ramp_to_voltage(v, 5, 0.01)
            if self.should_stop():
                log.warning("Measurement stopped by user")
                return
        time.sleep(self.long_delay)

        for volt in voltage_range:
            if iteration != 1:
                Gate.voltage_ramping(volt, 2, 0.001)
                time.sleep(self.short_delay)

            #### Handling Hysteresis type scan
            if self.scan_mode == 'Hysteresis':
                if iteration == 1:
                    log.info("Starting Hysteresis measurement...")
                for aux in full_aux_sweep:
                    MFLI_1.aux_ramp(self.aux_signal,aux, 5,0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100* iteration/total)
                    iteration += 1
                    if self.should_stop():
                        log.warning("Measurement stopped by user")
                        return
                    #### Handling Forward/Backward type scan
            elif self.scan_mode == 'Forward/Backward':
                if iteration == 1:
                    log.info("Starting Forward/Backward measurement...")
                    log.info("Ramp AUX to initial voltage...")
                    MFLI_1.aux_ramping(self.aux_signal,self.aux_sp1 , 5, 0.1)

                for aux in full_aux_sweep:
                    MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration / total)
                    iteration += 1
                    if self.should_stop():
                        log.warning("Measurement stopped by user")
                        return
                #### Handling Snake type scan
            elif self.scan_mode == 'Snake':
                if iteration == 1:
                    log.info("Starting Snake measurement...")
                    log.info("Ramp AUX to initial voltage...")
                    MFLI_1.aux_ramping(self.aux_signal, self.aux_sp1, 5, 0.1)

                if direction % 2 == 1:
                    for aux in aux_range_odd:
                        MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                        time.sleep(self.acq_delay)
                        data = self.getmeas(time_0)
                        self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                        self.emit('progress', 100 * iteration / total)
                        iteration += 1
                        if self.should_stop():
                            log.warning("Measurement stopped by user")
                            return
                    direction += 1
                else:
                    for aux in aux_range_even:
                        MFLI_1.aux_ramp(self.aux_signal, aux, 5, 0.01)
                        time.sleep(self.acq_delay)
                        data = self.getmeas(time_0)
                        self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                        self.emit('progress', 100 * iteration / total)
                        iteration += 1
                        if self.should_stop():
                            log.warning("Measurement stopped by user")
                            return
                        direction += 1

    def shutdown(self):
        log.info("Measurement complete. Instruments are being held at final setpoints.")

        # # Optional: Log the final voltages for the record
        # try:
        #     Gate = self.smu_choice(self.smu)
        #     final_gate = Gate.measure__voltage()
        #     final_bias = MFLI_1.get_auxout(self.aux_signal)
        #     log.info(f"Final State: Gate = {final_gate:.4f} V, Bias = {final_bias:.4f} V")
        # except:
        #     log.warning("Could not read final instrument states.")

        # In some frameworks, you might want to finalize the data file here
        log.info("Procedure shutdown finished.")
proc_differential_resistance_gate_map_zurich = {"Differential Resistance Gate Map Zurich": dict(
    cls=Differential_Resistance_Gate_map_Zurich,
    category="Differential Resistance",
    description="2D Gate vs Bias map. Sweeps Auxiliary voltage and performs a gate ramp "
                "Scan modes (Auxiliary bias sweep at each gate step):\n"
                "Hysteresis- Origin -> SP1 -> SP2 -> Origin \n"
                "Forward/Backward - SP1 -> SP2 -> SP1 \n"
                "Snake - SP1 -> SP2 for odd and SP2 to SP1 for even.",
    inputs=[
        'Title', 'Resistor', 'Contacts', 'Gate_contacts',
        'devices',
        'use_magnet',
        'use_MFLI_1',
        'aux_signal', 'aux_select', 'aux_demod',
        'use_MFLI_2', 'use_MFLI_3',
        'use_srs860', 'use_srs830_1', 'use_srs830_2',
        'use_dual_gate', 'use_keithley_1', 'use_keithley_2',

        'mapping',
        'scan_mode','smu', 'gate_sp1', 'gate_sp2', 'gate_step',
        'aux_sp1', 'aux_sp2', 'aux_step',
        'long_delay', 'short_delay',
        'acq_delay',

    ],
    displays=[
        'Title','scan_mode', 'gate_sp1', 'gate_sp2', 'aux_sp1', 'aux_sp2'
    ],
    # For a 2D Map, 'x' and 'y' usually define what you want to plot live.
    # In a Gate Map, DC_offset is the fast axis (X) and Gate Voltage is the slow axis (Y).
    x=['Gate_1_voltage(V)'],
    y=['AUX_DC_offset(V)', 'MFLI_Lockin_1_Voltage_X(V)'],
)}


########### Differential resistance mapping using MFLI aux for DC current and SMU for gating mapping gate for different bias
class Differential_Resistance_AUX_map_gate_sweep_Zurich(Procedure):
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    aux_signal = IntegerParameter('Auxiliary DC Signal ', group_by='use_MFLI_1', default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ", group_by='use_MFLI_1', default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['use_MFLI_1', 'aux_select'],
                                 group_condition=[True, lambda v: v == 11 or v == 13])

    mapping = BooleanParameter('Mapping', default=False)
    # Scan Mode Toggle
    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward', 'Hysteresis'],
                              group_by='mapping', group_condition=True)

    long_delay = FloatParameter('Delay after long ramp (s)', default=60, group_by='mapping', group_condition=True)
    short_delay = FloatParameter('Delay after short ramp (s)', default=5, group_by='mapping', group_condition=True)

    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], group_by='mapping',
                        group_condition=True, default='Gate_1')
    gate_sp1 = FloatParameter('Gate set point 1  voltage(V)', group_by='mapping', group_condition=True, default=-1)
    gate_sp2 = FloatParameter('Gate set point 2  voltage(V)', group_by='mapping', group_condition=True, default=1)
    gate_step = IntegerParameter('Gate Voltage step size (mV)', group_by='mapping', group_condition=True, default=5)

    aux_sp1 = FloatParameter('Auxiliary DC Bias Sp1  (V)', group_by='mapping', group_condition=True, default=0)
    aux_sp2 = FloatParameter('Auxiliary DC Bias Sp2  (V)', group_by='mapping', group_condition=True, default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='mapping', group_condition=True, default=2)

    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

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

        # extra if term for aux
        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure dV/dI gate and bias map sweep measurement")

        Gate = self.smu_choice(self.smu)
        #### Turn on output if it was off
        if not Gate.is_output_on() == True:
            self.smu_output(Gate, self.smu)
            log.info("SMU output is now on")
        else:
            log.info("SMU output was on")

        ## set the MFLI instrument to aux signal manual mode unless specified differently
        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        gate_origin = Gate.measure__voltage()

        #  Define gate Sweep Arrays
        if self.scan_mode == 'Hysteresis':
            gate_range_1 = self.generate_range(gate_origin, self.gate_sp1, self.gate_step)
            gate_range_2 = self.generate_range(self.gate_sp1, self.gate_sp2, self.gate_step)
            gate_range_3 = self.generate_range(self.gate_sp2, gate_origin, self.gate_step)
            full_gate_sweep = np.concatenate([gate_range_1, gate_range_2, gate_range_3])
            pts_per_aux = len(full_gate_sweep)

        elif self.scan_mode == 'Forward/Backward':
            gate_range_1 = self.generate_range(self.gate_sp1, self.gate_sp2, self.gate_step)
            gate_range_2 = self.generate_range(self.gate_sp2, self.gate_sp1, self.gate_step)
            full_gate_sweep = np.concatenate([gate_range_1, gate_range_2])
            pts_per_aux = len(full_gate_sweep)

        elif self.scan_mode == 'Snake':
            gate_range_odd = self.generate_range(self.gate_sp1, self.gate_sp2, self.gate_step)
            gate_range_even = self.generate_range(self.gate_sp2, self.gate_sp1, self.gate_step)
            pts_per_aux = len(gate_range_even)

        aux_range = self.generate_range(self.aux_sp1, self.aux_sp2, self.aux_step)

        # number of point for Snake is N for Forward/Backward is 2N and for Hysteresis is 3N
        total = pts_per_aux * len(aux_range)

        # iteration variable for progress bar and direction variable for Snake scan mode
        iteration, direction = 1, 1

        # first long aux ramp with option to stop in the middle
        log.info("Ramping aux voltage to Start Position...")
        aux_origin = MFLI_1.get_auxout(self.aux_signal)
        aux_ramp = self.generate_range(aux_origin, self.aux_sp1, 2)
        for v in aux_ramp:
            MFLI_1.aux_ramp(self.aux_signal,v, 5, 0.5)
            if self.should_stop():
                log.warning("Measurement stopped by user")
                return
        time.sleep(self.long_delay)

        for aux in aux_range:
            if iteration != 1:
                MFLI_1.aux_ramping(self.aux_signal,aux, 2, 0.3)
                time.sleep(self.short_delay)

            #### Handling Hysteresis type scan
            if self.scan_mode == 'Hysteresis':
                if iteration == 1:
                    log.info("Starting Hysteresis measurement...")
                for volt in full_gate_sweep:
                    Gate.ramp_to_voltage(volt, 5, 0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration / total)
                    iteration += 1
                    if self.should_stop():
                        log.warning("Measurement stopped by user")
                        return

            #### Handling Forward/Backward type scan
            elif self.scan_mode == 'Forward/Backward':
                if iteration == 1:
                    log.info("Starting Forward/Backward measurement...")
            # First ramping of the gate may take a long time, Loop is for when the user wants to stop the ramping
                    log.info("Ramp gate to initial voltage...")
                    voltage_ramp = self.generate_range(gate_origin, self.gate_sp1, 2)
                    for v in voltage_ramp:
                        Gate.ramp_to_voltage(v, 5, 0.001)
                        if self.should_stop():
                            log.warning("Measurement stopped by user")
                            return
                    time.sleep(self.long_delay)

                for volt in full_gate_sweep:
                    Gate.ramp_to_voltage(volt, 5, 0.01)
                    time.sleep(self.acq_delay)
                    data = self.getmeas(time_0)
                    self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                    self.emit('progress', 100 * iteration / total)
                    iteration += 1
                    if self.should_stop():
                        log.warning("Measurement stopped by user")
                        return

            #### Handling Snake type scan
            elif self.scan_mode == 'Snake':
                if iteration == 1:
                    log.info("Starting Snake measurement...")
                    # First ramping of the gate may take a long time, Loop is for when the user wants to stop the ramping
                    log.info("Ramp gate to initial voltage...")
                    voltage_ramp = self.generate_range(gate_origin, self.gate_sp1, 2)
                    for v in voltage_ramp:
                        Gate.ramp_to_voltage(v, 5, 0.001)
                        if self.should_stop():
                            log.warning("Measurement stopped by user")
                            return
                    time.sleep(self.long_delay)

                if direction % 2 == 1:
                        for volt in gate_range_odd:
                            Gate.ramp_to_voltage(volt, 5, 0.01)
                            time.sleep(self.acq_delay)
                            data = self.getmeas(time_0)
                            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                            self.emit('progress', 100 * iteration / total)
                            iteration += 1
                            if self.should_stop():
                                log.warning("Measurement stopped by user")
                                return
                        direction += 1
                else:
                        for volt in gate_range_even:
                            Gate.ramp_to_voltage(volt, 5, 0.01)
                            time.sleep(self.acq_delay)
                            data = self.getmeas(time_0)
                            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                            self.emit('progress', 100 * iteration / total)
                            iteration += 1
                            if self.should_stop():
                                log.warning("Measurement stopped by user")
                                return
                        direction += 1

    def shutdown(self):
        log.info("Measurement complete. Instruments are being held at final setpoints.")

        # # Optional: Log the final voltages for the record
        # try:
        #     Gate = self.smu_choice(self.smu)
        #     final_gate = Gate.measure__voltage()
        #     final_bias = MFLI_1.get_auxout(self.aux_signal)
        #     log.info(f"Final State: Gate = {final_gate:.4f} V, Bias = {final_bias:.4f} V")
        # except:
        #     log.warning("Could not read final instrument states.")

        # In some frameworks, you might want to finalize the data file here
        log.info("Procedure shutdown finished.")
proc_differential_resistance_aux_map_gate_zurich = {"Differential Resistance AUX Map Zurich": dict(
    cls=Differential_Resistance_AUX_map_gate_sweep_Zurich,
    category="Differential Resistance",
    description="2D Gate vs Bias map. Sweeps Gate voltage and performs a aux ramp "
                "Scan modes (gate sweep at each auxiliary bias step):\n"
                "Hysteresis- Origin -> SP1 -> SP2 -> Origin \n"
                "Forward/Backward - SP1 -> SP2 -> SP1 \n"
                "Snake - SP1 -> SP2 for odd and SP2 to SP1 for even.",
    inputs=[
        'Title', 'Resistor', 'Contacts', 'Gate_contacts',
        'devices',
        'use_magnet',
        'use_MFLI_1',
        'aux_signal', 'aux_select', 'aux_demod',
        'use_MFLI_2', 'use_MFLI_3',
        'use_srs860', 'use_srs830_1', 'use_srs830_2',
        'use_dual_gate', 'use_keithley_1', 'use_keithley_2',

        'mapping',
        'scan_mode', 'smu', 'gate_sp1', 'gate_sp2', 'gate_step',
        'aux_sp1', 'aux_sp2', 'aux_step',
        'long_delay', 'short_delay',
        'acq_delay',

    ],
    displays=[
        'Title','scan_mode', 'gate_sp1', 'gate_sp2', 'aux_sp1', 'aux_sp2'
    ],
    # For a 2D Map, 'x' and 'y' usually define what you want to plot live.
    # In a Gate Map, DC_offset is the fast axis (X) and Gate Voltage is the slow axis (Y).
    x=['AUX_DC_offset(V)'],
    y=['Gate_1_voltage(V)', 'MFLI_Lockin_1_Voltage_X(V)'],
)}

########## Sequencer measurement for Rt, RV and RH
class Rt_RV_RH_sequencer_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('Combination sequence measurement', default='measurement type')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')

    Type = ListParameter('Measurement Type',choices=['Rt','RV','RH'], default='Rt')

    Target_field = FloatParameter('Target field (T)',group_by = 'Type',group_condition='RH', default=0)

    Target_voltage = FloatParameter('Target Voltage(V)',group_by = 'Type',group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)',group_by = 'Type',group_condition='RV', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'],group_by = 'Type',group_condition='RV', default='Gate_1')

    acq_length = IntegerParameter('Acquisition Length (s)',group_by = 'Type',group_condition='Rt', default=3600)

    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]
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
        # 1. Magnet Write (Trigger)
        if self.use_magnet:
            magnet.get_magnet_field_write()

        # 2. Temperature & Time
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        # 3. Dual Gate
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        # 4. Keithleys
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        # 5. Lock-ins
        vals += list(SRS860.snap("X", "Y")) if self.use_srs860 else [math.nan] * 2

        for use, inst in [(self.use_MFLI_1, MFLI_1), (self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        # 6. Magnet Read (Last Column)
        if self.use_magnet:
            vals.append(magnet.get_magnet_field_read())
        else:
            vals.append(math.nan)

        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def run_Rt(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)

        # While Loop through until acquisition length is done
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

        #### Determine chosen smu
        Gate = self.smu_choice(self.smu)

        # 1. Output Check & Turn On
        if not Gate.is_output_on():
            log.info(f'{self.smu} output was OFF. Turning it ON.')
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

    def run_RH(self):
        time_0 = time.time()
        if self.use_magnet == False:
            log.info("Forgot to choose magnet in magnetic field measurement")
            return

        log.info("starting to sweep field to %g Tesla", self.Target_field)
        # --- 1. Persistent Heater Logic ---
        current_field = magnet.get_magnet_field()
        persistent_heater_status = magnet.get_persistent_switch_heater()
        print('Persistent switch heater mode: %s' % persistent_heater_status)
        # Test if the magnet heater is on, in case the persistent heater is off
        # turn it on and wait 10 min
        if persistent_heater_status == '0':
            log.info("Heater is OFF. Turning ON and waiting 600s...")
            magnet.set_persistent_switch_heater('ON')
            time.sleep(600)
            log.info("Heater warm-up complete.")

        # --- 2. Setup Sweep ---
        #### magnetic field at beginning for progress

        origin_field = magnet.get_magnet_field()
        magnet.go_to_target_field(self.Target_field)

        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero

        # --- 3. Monitoring Loop ---
        # We loop until the difference between current field and target is less than 3mT (0.003T)
        while abs(current_field - self.Target_field) > 0.003:

            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))  # Clamp between 0-100

            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                magnet.set_sweep_mode('PAUSE')
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
        if self.Type == 'RH' and self.use_magnet:
            current_field = magnet.get_magnet_field()
            if abs(current_field-self.Target_field) > 0.003:
                magnet.set_sweep_mode('PAUSE')
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")
proc_Rt_RV_RH_sequencer = {
"Rt_RV_RH sequencer measurement": dict(
        cls=Rt_RV_RH_sequencer_measurement,
        category=["Magnetic Field","Gate Sweep", "Keithley 2450","Time-based"],
        description="Procedure in order to sequence between Rt, RV and RH.\n"
                    "The user can choose measurement type and the relevant parameter will pop up.\n"
                    "Rt -> acquisition length is required.\n"
                    "RV -> Target voltage, step size and smu choise.\n"
                    "RH -> Target field, use_magnet must be clicked.\n"
                    "Loading a sequence file is available",
        inputs=[
                'Title','Resistor','Contacts','Gate_contacts',
                'Type',
                'Target_field',
                'Target_voltage','step_size','smu',
                'acq_length',
                'devices',
                'use_magnet',
                'use_MFLI_1','use_MFLI_2' ,'use_MFLI_3',
                'use_srs860','use_srs830_1','use_srs830_2',
                'use_dual_gate','use_keithley_1','use_keithley_2',

                'acq_delay',
        ],
        displays=[
            'Title',
            'Type'],
        x=['time(s)'],
        y=['probe_temp(K)','field(T)'],
        sequencer=True,
        sequencer_inputs=['Type',                                   # Measurement Type Rt, RV, RH
                          'Target_field', 'use_magnet',                          # RH parameter
                          'Target_voltage','step_size','smu',       # RV parameters
                          'acq_length'                              # Rt parameter
                        ],
        #sequence_file="gui_sequencer_example_sequence.txt",  # Added line, optional
    ),
}

class RV_dV_dI_sequencer_measurement(Procedure):
    # --- Parameters ---
    Title = Parameter('Measurement type', default='RV and dV/dI in sequence')

    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')


    Type = ListParameter('Measurement Type', choices=['RV', 'dV_dI'], default='RV')

    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              group_by='Type',
                              group_condition='dV_dI',
                              default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)',
                                group_by=['use_MFLI_1','Type'],
                                group_condition='dV_dI',
                                default=0)
    aux_signal = IntegerParameter('Auxiliary DC Signal ',
                                  group_by=['use_MFLI_1', 'Type'],
                                  group_condition='dV_dI',
                                  default=0)
    aux_select = IntegerParameter("Auxiliary DC Select ",
                                  group_by=['use_MFLI_1', 'Type'],
                                  group_condition='dV_dI',
                                  default=-1)
    aux_demod = IntegerParameter("Auxiliary DC demode", group_by=['Type','use_MFLI_1', 'aux_select'],
                                 group_condition=['dV_dI',True, lambda v: v == 11 or v == 13])
    aux_step = FloatParameter('Auxiliary step (mV)',
                              group_by=['use_MFLI_1', 'Type'],
                              group_condition='dV_dI',
                              default=2)

    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], group_by='Type',
                        group_condition='RV', default='Gate_1')

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

    # --- Sweep Parameters ---
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

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

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

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
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        if self.use_magnet:
            magnet.get_magnet_field_write()

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

        # extra if term for aux
        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        vals.append(magnet.get_magnet_field_read() if self.use_magnet else math.nan)
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1':
            Gate = Gate_1
        elif Gate_name == 'Gate_2':
            Gate = Gate_2
        elif Gate_name == 'smua':
            Gate = Dual_gate.smua
        elif Gate_name == 'smub':
            Gate = Dual_gate.smub
        else:
            log.info("SMU not supported")
            exit()
        return Gate

    def smu_output(self, Gate, Gate_name):
        if Gate_name == 'Gate_1' or Gate_name == 'Gate_2':
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        elif Gate_name == 'smua' or Gate_name == 'smub':
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        step = abs(step_units / 1000.0)
        if step == 0: step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def run_RV(self):
        time_0 = time.time()
        log.info(f"starting voltage sweep to {self.Target_voltage} V")

        #### Determine chosen smu
        Gate = self.smu_choice(self.smu)

        # 1. Output Check & Turn On
        if not Gate.is_output_on():
            log.info(f'{self.smu} output was OFF. Turning it ON.')
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

        # 2. Generate Sweep Arrays
        # Trace A: Origin -> Target
        range_to_target = self.generate_range(aux_origin, target_aux, self.aux_step)

        # Trace B: Target -> Origin(only for return mode)
        # Note: We generate this from Target back to Start.
        range_return = self.generate_range(target_aux, aux_origin, self.aux_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        # --- PART 1: Sweep to Setpoint ---
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

        # --- PART 2: Sweep back to Origin (Optional) ---
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
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type =='dV_dI':
            self.run_dV_dI()


    def shutdown(self):
        log.info("Finished measuring")
proc_RV_dV_dI_sequencer = {
    "RV dV_dI sequencer measurement": dict(
        cls=RV_dV_dI_sequencer_measurement,
        category=["Differential Resistance","Gate Sweep", "Keithley 2450"],
        description="dV/dI Sweep starting from Origin DC AUX using MFLI_1.\n"
                    "1. Sweep to Setpoint: Measures from [Origin] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Origin] -> [Target] -> [Origin]. Returns voltage to start."
                    "The sequencer procedure allows for RV and dV/dI measurment to run one after the other\n"
                    "RV    -> Target voltage, step size and smu choise.\n"
                    "dV_dI -> scan mode, and Auxiliary options\n"
                    "Loading a sequence file is available",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'acq_delay',
            'Type',
            'scan_mode',
            'Target_voltage', 'step_size', 'smu',
            'devices',
            'use_magnet',
            'use_MFLI_1',
            'aux_Target', 'aux_step', 'aux_signal', 'aux_select', 'aux_demod',
            'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate','use_keithley_1','use_keithley_2',


        ],
        displays=['Type','Target_voltage','scan_mode','aux_Target'],
        x=['AUX_DC_offset(V)'],
        y=['MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)'],
        sequencer=True,                                      # Added line
        sequencer_inputs=['Type',                                 # Measurement Type RV, dV_dI
                        'Target_voltage', 'step_size', 'smu',     # RV parameters
                        'scan_mode','aux_Target', 'aux_step',     # dV_dI parameters
                        ],

    ),
}


CATAGORIES = {
            "Time-based": "#BEE1F9",
            "Gate Sweep": "#BEF9C7",
            "Magnetic Field": "#F6F9BE",
            "2D Mapping": "#EABEF9",
            "Tunneling junction": "#F9BEC2",
            "Differential Resistance": "#F9E3BE",
            "Keithley 2450": "#FCBBD5"
}

PROCEDURES = {}
    #### ---- Base Procedures ---- ####
PROCEDURES.update(proc_resistance_time)
PROCEDURES.update(proc_resistance_gate)
PROCEDURES.update(proc_resistance_magnet)

    #### ---- Two instrument procedures ---- ####
PROCEDURES.update(proc_resistance_two_gate_sweep)
#PROCEDURES.update(proc_resistance_carrier_density)
PROCEDURES.update(proc_resistance_two_gate_map)
PROCEDURES.update(proc_resistance_magnet_gate_map)
PROCEDURES.update(proc_resistance_magnet_2gate_map)

    #### ---- Differential measurement using DC offset/AUX ---- ####
PROCEDURES.update(proc_differential_conductance_SRS860)
PROCEDURES.update(proc_differential_conductance_Zurich)
#PROCEDURES.update(   proc_differential_conductance_Zurich_gate)
PROCEDURES.update(proc_differential_resistance_Zurich)
PROCEDURES.update(proc_differential_resistance_gate_map_zurich)
PROCEDURES.update(proc_differential_resistance_aux_map_gate_zurich)

    ### ---- Sequenced procedures ---- ####
PROCEDURES.update(proc_Rt_RV_RH_sequencer)
PROCEDURES.update(proc_RV_dV_dI_sequencer)



class GenericWindow(ManagedDockWindow):
    """A ManagedWindow configured from a spec in PROCEDURES."""
    # def __init__(self, spec_name: str):
    #     spec = PROCEDURES[spec_name]
    #     super().__init__(
    #         procedure_class=spec['cls'],
    #         inputs=spec['inputs'],
    #         displays=spec['displays'],
    #         x_axis=spec.get('x'),
    #         y_axis=spec.get('y'),
    #         linewidth=1.5,
    #         inputs_in_scrollarea = True,
    #         if procedure_class == proc_Rt_RV_RH_sequencer or proc_RV_dV_dI_sequencer:
    #             sequencer=spec['sequencer'],
    #             sequencer_inputs=spec['sequencer_inputs'],
    #     )
    #     self.setWindowTitle(f"{spec_name} (ManagedWindow)")
    #     self.filename = f"{spec_name}"
    #     self.directory = save_dir
    #     try:
    #         self.plot_widget.plot.showGrid(x=True, y=True)
    #     except Exception:
    #         pass
    def __init__(self, spec_name: str):
        spec = PROCEDURES[spec_name]

        # 1. Define the base arguments that every window needs
        kwargs = {
            "procedure_class": spec['cls'],
            "inputs": spec['inputs'],
            "displays": spec['displays'],
            "x_axis": spec.get('x'),
            "y_axis": spec.get('y'),
            "linewidth": 1.5,
            "inputs_in_scrollarea": True
        }

        # 2. Add sequencer arguments ONLY if they are defined in the procedure spec
        if spec.get('sequencer'):
            kwargs['sequencer'] = spec['sequencer']
            kwargs['sequencer_inputs'] = spec['sequencer_inputs']

        # 3. Pass all arguments to the parent class
        super().__init__(**kwargs)

        self.setWindowTitle(f"{spec_name} (ManagedWindow)")
        self.filename = f"{spec_name}"
        self.directory = save_dir

        try:
            self.plot_widget.plot.showGrid(x=True, y=True)
        except Exception:
            pass



class Launcher(QtWidgets.QMainWindow):
    """Tiny picker that opens per-procedure ManagedWindows with multicategory filter."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Procedure Launcher")
        self.resize(800, 400)  # a bit wider for the filters
        self.setMinimumSize(400, 350)
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        # Use your global categories dict (typo preserved if that's how it's defined)
        # If you named it CATAGORIES, we'll stick to that. Otherwise, replace with your actual name.
        try:
            self.CAT = CATAGORIES
        except NameError:
            # Fallback to local legend from previous code (kept for safety)
            self.CAT = {
                "Time-based": "#BEE1F9",
                "Gate Sweep": "#BEF9C7",
                "Magnetic Field": "#F6F9BE",
                "2D Mapping": "#EABEF9",
                "Tunneling junction": "#F9BEC2",
                "Differential": "#F9E3BE",
                "Keithley 2450": "#FCBBD5",
            }

        layout = QtWidgets.QVBoxLayout(central)

        # General description section
        general_desc = QtWidgets.QLabel(
            "Select a measurement procedure below to open its dedicated window.\n"
            "You can filter by one or more categories; only matching procedures will be shown.\n"
        )
        general_desc.setStyleSheet("""
            QLabel {
                border: 1px solid #b0c4de;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        general_desc.setWordWrap(True)
        layout.addWidget(general_desc)

        layout.addSpacing(8)

        # NEW: Multi-category filter row
        filter_row = QtWidgets.QHBoxLayout()
        #filter_row.addWidget(QtWidgets.QLabel("Filter by categories (multi-select):"))
        filter_container = QtWidgets.QWidget()
        filter_h = QtWidgets.QHBoxLayout(filter_container)
        #filter_h.setContentsMargins(0,0,0,0)

        self.category_checks = {}  # name -> QCheckBox
        for name, color in self.CAT.items():
            cb = QtWidgets.QCheckBox(name)
            cb.setTristate(False)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    background-color: {color};
                    border: 1px solid #ccc;
                    border-radius: 6px;
                    padding: 2px 6px;
                    margin-right: 6px;
                }}
            """)
            cb.stateChanged.connect(self._apply_category_filter)
            self.category_checks[name] = cb
            filter_h.addWidget(cb)

        filter_h.addStretch()
        filter_row.addWidget(filter_container)

        # Clear/Show All button
        clear_btn = QtWidgets.QPushButton("Show All")
        clear_btn.clicked.connect(self._clear_category_filter)
        filter_row.addWidget(clear_btn)

        layout.addLayout(filter_row)

        layout.addSpacing(6)

        # Procedure selection row
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        row.addWidget(QtWidgets.QLabel("Procedure:"))
        self.combo = QtWidgets.QComboBox()
        self.combo.currentTextChanged.connect(self.update_description)
        row.addWidget(self.combo)

        self.btn = QtWidgets.QPushButton("Open window")
        self.btn.clicked.connect(self.open_window)
        row.addWidget(self.btn)

        # Category label (now can show multiple chips via rich text)
        self.category_label = QtWidgets.QLabel()
        self.category_label.setTextFormat(QtCore.Qt.RichText)
        self.category_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 4px 0px;
                margin-top: 5px;
                margin-bottom: 5px;
                font-size: 15px;
            }
        """)
        layout.addWidget(self.category_label)

        # Description section
        desc_label = QtWidgets.QLabel("Description:")
        desc_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(desc_label)

        self.description_text = QtWidgets.QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        self.description_text.setStyleSheet("""
            QTextEdit {
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.description_text)

        layout.addStretch()

        # Keep references so windows are not GC'ed
        self._windows = []
        console_log(log)

        # Populate procedures per current (empty) filter
        self._populate_combo()
        self.update_description()

        # Toolbar Exit action
        tb = self.addToolBar("App")
        exit_action = QtGui.QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._on_exit_clicked)
        tb.addAction(exit_action)

    # ---------- NEW helper UI logic ----------

    def _selected_categories(self):
        return [name for name, cb in self.category_checks.items() if cb.isChecked()]

    def _populate_combo(self):
        current = self.combo.currentText()
        self.combo.blockSignals(True)
        self.combo.clear()
        selected = self._selected_categories()

        names = []
        for name, spec in PROCEDURES.items():
            if _proc_matches(spec, selected):
                names.append(name)
        #names.sort()

        self.combo.addItems(names)
        self.combo.blockSignals(False)

        if current in names:
            idx = self.combo.findText(current)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        elif names:
            self.combo.setCurrentIndex(0)

    def _apply_category_filter(self):
        self._populate_combo()
        self.update_description()

    def _clear_category_filter(self):
        for cb in self.category_checks.values():
            cb.setChecked(False)
        self._populate_combo()
        self.update_description()

    # ---------- Existing methods (tweaked) ----------

    def update_description(self):
        """Update the description text and category chips when procedure selection changes."""
        name = self.combo.currentText()
        if name in PROCEDURES:
            proc = PROCEDURES[name]

            # Description
            description = proc.get('description', 'No description available.')
            self.description_text.setPlainText(description)

            # Categories (may be one or many)
            cat_list = _as_cat_list(proc.get('category', 'Unknown'))

            # Build colorful chips via HTML
            chips = []
            for c in cat_list:
                color = self.CAT.get(c, '#f0f0f0')

                # Chip span
                chips.append(
                    f'<span style="background-color:{color};'
                    f' border:1px solid #ccc; border-radius:6px;'
                    f' padding:2px 8px; margin-right:6px;">{QtCore.Qt.escape(c) if hasattr(QtCore.Qt, "escape") else c}</span>'
                )
            html = "Category: " + (" ".join(chips) if chips else "Unknown")
            self.category_label.setText(html)
        else:
            self.description_text.setPlainText('No description available.')
            self.category_label.setText('Category: Unknown')

    def open_window(self):
        name = self.combo.currentText()
        if not name:
            return
        w = GenericWindow(name)
        w.show()
        self._windows.append(w)  # keep alive

    def _on_exit_clicked(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Exit",
            "Stop any running measurement and exit?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.stop()
        except Exception:
            pass
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        # 1. Stop any running procedures
        try:
            self.stop()
        except Exception:
            pass

        # 2. Explicitly close instruments to prevent the "BaseException" error
        # We import the configuration to access the global objects
        try:
            import configuration as cfg
            # List all possible instruments from your config
            instrument_list = [
                cfg.magnet,
                cfg.Gate_1, cfg.Gate_2, cfg.Dual_gate,
                cfg.MFLI_1, cfg.MFLI_2, cfg.MFLI_3,
                cfg.SRS860, cfg.SRS830_1, cfg.SRS830_2
            ]

            for inst in instrument_list:
                # Check if the instrument exists (is not 0) and has an adapter
                if inst != 0 and hasattr(inst, 'adapter'):
                    try:
                        inst.adapter.close()
                    except Exception:
                        pass
        except Exception:
            pass

        # 3. Proceed with standard window close
        super().closeEvent(event)


# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     window = Launcher()
#     window.show()
#     sys.exit(app.exec())


if __name__ == "__main__":
    import sys
    from importlib import reload
    from PyQt5 import QtWidgets
    from config_prelaunch import run_and_optionally_launch  # the dialog we made

    def _start_launcher():
        # 1) Reload configuration so it re-reads instrument_overrides.json
        reload(_cfg)
        _rebind_instruments_from_configuration()

        # 2) Now start your Launcher window
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        win = Launcher()  # your existing launcher UI
        win.show()
        sys.exit(app.exec())

    # Show the config dialog FIRST, and only launch if the user clicked Save & Launch
    run_and_optionally_launch(_start_launcher)