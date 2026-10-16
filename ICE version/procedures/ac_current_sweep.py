"""
AC current sweep measurement procedure using the Keithley 6221.

Sweeps the AC current amplitude (entered in RMS) from a start point to a
target point while recording lock-in / SMU readings at each step.
The 6221 receives the amplitude as a PEAK value: sent = RMS * 1.4142.
Port of the Generic Version procedure, adapted for the ICE instrument set.
"""

from .base import *
from . import base


class AC_current_sweep_measurement(ICEProcedure):
    Title = Parameter('AC current sweep', default='AC sweep')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')

    # --- AC source configuration ---
    waveform = ListParameter('Waveform', choices=['sine', 'square', 'ramp'],
                             default='sine')
    frequency = FloatParameter('Frequency (Hz)', default=100)
    compliance = FloatParameter('Compliance (V)', default=10)

    # --- Sweep configuration (all values in RMS Amps) ---
    start_current = FloatParameter('Start current RMS (A)', default=0)
    target_current = FloatParameter('Target current RMS (A)', default=1e-6)
    step_size = FloatParameter('Step size RMS (A)', default=1e-8)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

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
    use_yoko_gs200_1 = BooleanParameter('Use Yoko GS200_1', group_by='devices', default=False)
    use_yoko_gs200_2 = BooleanParameter('Use Yoko GS200_2', group_by='devices', default=False)
    use_yoko7651_1 = BooleanParameter('Use Yoko7651_1', group_by='devices', default=False)
    use_yoko7651_2 = BooleanParameter('Use Yoko7651_2', group_by='devices', default=False)
    use_k6221 = BooleanParameter('Use k6221 (record amplitude column)', group_by='devices', default=True)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        return self._read_standard(t0)

    def execute(self):
        K6221 = base.K6221
        if not base._is_connected(K6221):
            raise ValueError("K6221 selected but not connected (check the pre-launch dialog)")

        # RMS bounds: instrument accepts 2e-12..0.105 A peak amplitude
        peak_target = self.target_current * base.RMS_TO_PEAK
        if not (2e-12 <= abs(peak_target) <= 0.105):
            raise ValueError(f"Target {self.target_current} A RMS out of range "
                             "(2e-12 .. 0.074 A RMS)")

        time_0 = time.time()
        log.info(f"Configuring K6221: {self.waveform} @ {self.frequency} Hz, "
                 f"compliance {self.compliance} V")
        K6221.waveform_function = self.waveform
        K6221.waveform_frequency = self.frequency
        K6221.waveform_offset = 0
        K6221.waveform_dutycycle = 50
        K6221.source_compliance = self.compliance
        K6221.waveform_ranging = 'best'
        K6221.waveform_duration_set_infinity()
        K6221.enable_source()

        current_ranges = self.generate_range(self.start_current, self.target_current,
                                             self.step_size * 1000)  # step in milli-units
        # drop points below the instrument's minimum amplitude
        current_ranges = [rms for rms in current_ranges if rms * base.RMS_TO_PEAK >= 2e-12]

        log.info(f"Sweeping AC current RMS from {self.start_current}A to {self.target_current}A "
                 f"in {len(current_ranges)} steps (sent as peak = RMS x 1.4142)")

        iteration = 1
        for rms in current_ranges:
            # 6221 requires re-arm after a parameter change
            K6221.waveform_abort()
            K6221.waveform_amplitude = rms * base.RMS_TO_PEAK
            K6221.waveform_arm()
            K6221.waveform_start()

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(current_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        K6221 = base.K6221
        if base._is_connected(K6221):
            log.info("Shutting down K6221: abort, amplitude to 0, output off")
            try:
                K6221.waveform_abort()
                K6221.waveform_amplitude = 0
                K6221.disable_source()
            except Exception as e:
                log.warning(f"K6221 shutdown issue: {e}")
        log.info("AC current sweep finished")


proc_ac_current_sweep = {
"AC current sweep measurement": dict(
        cls=AC_current_sweep_measurement,
        category="AC Current Sweep",
        description="Sweeps the AC current amplitude of a Keithley 6221 from a start to a target value\n"
                    "while recording lock-in readings at every step.\n"
                    "Amplitudes are entered in RMS; the instrument is commanded in peak\n"
                    "(sent value = RMS x 1.4142). CSV column K6221_AC_amplitude_RMS(A) is in RMS.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Source_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
            'use_k6221',
            'waveform', 'frequency', 'compliance',
            'start_current', 'target_current', 'step_size',
            'acq_delay',
        ],
        displays=[
            'Title',
            'waveform', 'frequency', 'compliance',
            'start_current', 'target_current', 'step_size',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)']
    ),
}

