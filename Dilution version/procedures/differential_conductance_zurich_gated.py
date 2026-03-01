"""
Differential conductance measurement using Zurich MFLI with gate sweep.
"""

from .base import *

DC_COLUMNS = ['DC_offset(V)']


class Differential_conductance_Zurich_gated(Procedure):
    Title = Parameter('dI/dV measurement', default='Rt')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    dc_offset_start = FloatParameter('DC offset set point 1 (V)', group_by='use_MFLI_1', default=0)
    dc_offset_end = FloatParameter('DC offset set point 2 (V)', group_by='use_MFLI_1', default=-0)
    dc_offset_step = FloatParameter(' dc offset step (mV)', group_by='use_MFLI_1', default=1)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=float(5 * 0.1))

    smu = ListParameter('User defined SMU', choices=['smua', 'smub', 'Gate_1', 'Gate_2'], default='smua')
    gate_target = FloatParameter('Target Voltage(V)', default=0)

    devices = BooleanParameter('Devices in use', default=False)
    use_magnet_dilution = BooleanParameter('Use Magnet', group_by='devices', default=False)
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

    DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_CURRENT_COLUMNS + DC_COLUMNS + MAGNET_COLUMNS

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
        temperature = dilution.get_temperature(8)
        vals = [time.time() - t0, temperature]

        if self.use_magnet_dilution:
            dilution.read_magnet()

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
            vals += [math.nan, math.nan]

        if self.use_MFLI_1:
            x, y = MFLI_1.read_demod()
            dc_offset = MFLI_1.dc_offset
            vals += [dc_offset, x, y]
        else:
            vals += [math.nan, math.nan, math.nan]

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

        vals += list(dilution.read_magnet()) if self.use_magnet_dilution else [math.nan] * 3
        return vals

    def smu_choice(self, Gate_name):
        if Gate_name == 'Gate_1': return Gate_1
        if Gate_name == 'Gate_2': return Gate_2
        if Gate_name == 'smua': return Dual_gate.smua
        if Gate_name == 'smub': return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {Gate_name}")

    def smu_output(self, Gate, Gate_name):
        if Gate_name in ['Gate_1', 'Gate_2']:
            Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False, compliance_current=1.5e-8)
            Gate.output_on()
        else:
            Gate.configure_voltage_source(0, 110e-9)
            Gate.output_on()

    def milli_step(self, start, end, step):
        if start > end:
            step = step / -1000
        elif start < end:
            step = step / 1000
        return step

    def execute(self):
        time_0 = time.time()
        log.info("starting to measure")

        Gate = self.smu_choice(self.smu)

        if not Gate.is_output_on():
            self.smu_output(Gate, self.smu)
            log.info("SMU output is now on")
        else:
            log.info("SMU output was on")

        if Gate.measure__voltage() != self.gate_target:
            Gate.voltage_ramping(self.gate_target, 2, 0.1)

        dc_offset_origin = MFLI_1.dc_offset
        milli_step = self.milli_step(dc_offset_origin, self.dc_offset_start, self.dc_offset_step)

        for dc_offset in np.arange(dc_offset_origin, self.dc_offset_start + milli_step * 1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

        milli_step = self.milli_step(self.dc_offset_start, self.dc_offset_end, self.dc_offset_step)

        for dc_offset in np.arange(MFLI_1.dc_offset, self.dc_offset_end + milli_step * 1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

        milli_step = self.milli_step(self.dc_offset_end, dc_offset_origin, self.dc_offset_step)

        for dc_offset in np.arange(MFLI_1.dc_offset, dc_offset_origin + milli_step * 1e-3, milli_step):
            MFLI_1.dc_offset = dc_offset
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        log.info("Finished measuring")

proc_differential_conductance_Zurich_gate = {
    "Differential conductance Zurich gated": dict(
        cls=Differential_conductance_Zurich_gated,
        category=["Tunneling junction"],
        description="New measurement for renu",
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet_dilution',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'dc_offset_start', 'dc_offset_end', 'dc_offset_step',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'smu', 'gate_target',
            'acq_delay',
        ],
        displays=[
            'Title',
            'dc_offset_start', 'dc_offset_end', 'dc_offset_step'
        ],
        x=['time(s)', 'DC_offset(V)'],
        y=['Mixing_chanber(K)', 'MFLI_Lockin_1_Current_X(A)'],
    ),
}