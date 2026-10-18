"""
AC+DC current ramp measurement procedure using two Keithley 6221 units.

One 6221 runs a continuous AC waveform (user picks which unit is the AC
source), the other ramps its DC current from a start point to a target
point while lock-in / SMU readings are recorded at each step.

Only selectable when BOTH 6221 units are connected (see 'requires' in the
registration dict at the bottom). AC amplitude is entered in RMS; the
instrument is commanded in peak (sent = RMS x 1.4142).
"""

from .base import *
from . import base


class AC_DC_current_ramp_measurement(GenericProcedure):
    Title = Parameter('AC+DC current ramp', default='AC+DC ramp')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')

    # --- Role assignment: which 6221 is AC, which is DC ---
    ac_source = ListParameter('AC source unit', choices=['K6221', 'K6221_2'],
                              default='K6221')
    dc_source = ListParameter('DC source unit', choices=['K6221', 'K6221_2'],
                              default='K6221_2')

    # --- AC source configuration ---
    waveform = ListParameter('Waveform', choices=['sine', 'square', 'ramp'],
                             default='sine')
    frequency = FloatParameter('AC frequency (Hz)', default=100)
    ac_current = FloatParameter('AC current RMS (A)', default=1e-6)
    ac_compliance = FloatParameter('AC compliance (V)', default=10)

    # --- DC source ramp configuration ---
    dc_compliance = FloatParameter('DC compliance (V)', default=10)
    start_current = FloatParameter('DC start current (A)', default=0)
    target_current = FloatParameter('DC target current (A)', default=1e-6)
    step_size = FloatParameter('DC step size (A)', default=1e-8)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs860_3 = BooleanParameter('Use srs860_3', group_by='devices', default=False)
    use_srs860_4 = BooleanParameter('Use srs860_4', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    use_yoko_gs200_1 = BooleanParameter('Use Yoko GS200_1', group_by='devices', default=False)
    use_yoko_gs200_2 = BooleanParameter('Use Yoko GS200_2', group_by='devices', default=False)
    use_yoko7651_1 = BooleanParameter('Use Yoko7651_1', group_by='devices', default=False)
    use_yoko7651_2 = BooleanParameter('Use Yoko7651_2', group_by='devices', default=False)
    use_k6221 = BooleanParameter('Use k6221 (record amplitude column)', group_by='devices', default=False)
    use_k6221_2 = BooleanParameter('Use k6221_2 (record amplitude column)', group_by='devices', default=False)

    _MID_COLUMNS = ['AC_amplitude_RMS(A)', 'DC_current(A)']

    def _pick_6221s(self):
        ac = base.K6221 if self.ac_source == 'K6221' else base.K6221_2
        dc = base.K6221 if self.dc_source == 'K6221' else base.K6221_2
        if not base._is_connected(ac):
            raise ValueError(f"{self.ac_source} selected as AC source but is not "
                             f"connected (check the pre-launch dialog)")
        if not base._is_connected(dc):
            raise ValueError(f"{self.dc_source} selected as DC source but is not "
                             f"connected (check the pre-launch dialog)")
        if ac is dc:
            raise ValueError("AC source unit and DC source unit must be different "
                             "6221 instruments")
        return ac, dc

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0, ac, dc):
        mid = [ac.waveform_amplitude / base.RMS_TO_PEAK,
               float(dc.source_current)]
        return self._read_standard(t0, mid_extras=mid)

    def execute(self):
        ac, dc = self._pick_6221s()

        peak_amp = self.ac_current * base.RMS_TO_PEAK
        if not (2e-12 <= abs(peak_amp) <= 0.105):
            raise ValueError(f"AC current {self.ac_current} A RMS out of range "
                             f"(2e-12..0.105 A peak)")

        time_0 = time.time()
        log.info(f"Configuring {self.ac_source} as AC source: {self.waveform} @ "
                 f"{self.frequency} Hz, {self.ac_current} A RMS, compliance "
                 f"{self.ac_compliance} V")
        ac.waveform_function = self.waveform
        ac.waveform_frequency = self.frequency
        ac.waveform_amplitude = peak_amp
        ac.waveform_offset = 0
        ac.waveform_dutycycle = 50
        ac.source_compliance = self.ac_compliance
        ac.waveform_ranging = 'best'
        ac.waveform_duration_set_infinity()
        ac.waveform_arm()
        ac.enable_source()
        ac.waveform_start()

        log.info(f"Configuring {self.dc_source} as DC source: compliance "
                 f"{self.dc_compliance} V")
        dc.source_compliance = self.dc_compliance
        dc.source_auto_range = True
        dc.enable_source()
        dc.source_current = self.start_current

        current_ranges = self.generate_range(self.start_current, self.target_current,
                                             self.step_size * 1000)  # step in milli-units

        log.info(f"Ramping DC current on {self.dc_source} from {self.start_current} A "
                 f"to {self.target_current} A in {len(current_ranges)} steps, "
                 f"AC running on {self.ac_source}")

        iteration = 1
        for val in current_ranges:
            dc.source_current = float(val)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0, ac, dc)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(current_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        # Ramp both roles safely down regardless of which unit held them
        try:
            ac, dc = self._pick_6221s()
        except Exception:
            ac = dc = None
        if base._is_connected(ac):
            log.info("Shutting down AC unit: abort, amplitude 0, output off")
            try:
                ac.waveform_abort()
                ac.waveform_amplitude = 0
                ac.disable_source()
            except Exception as e:
                log.warning(f"AC 6221 shutdown issue: {e}")
        if base._is_connected(dc):
            log.info("Shutting down DC unit: current 0, output off")
            try:
                dc.source_current = 0
                dc.disable_source()
            except Exception as e:
                log.warning(f"DC 6221 shutdown issue: {e}")
        log.info("AC+DC current ramp finished")


proc_ac_dc_ramp = {
"AC and DC current ramp measurement": dict(
        cls=AC_DC_current_ramp_measurement,
        category="AC+DC",
        description="Uses TWO Keithley 6221 units: one runs a continuous AC waveform\n"
                    "(selected as 'AC source unit'), the other ramps its DC current from\n"
                    "start to target (selected as 'DC source unit') while lock-in readings\n"
                    "are recorded at every step. AC amplitude entered in RMS (sent as peak\n"
                    "= RMS x 1.4142). CSV columns AC_amplitude_RMS(A) and DC_current(A).\n"
                    "This procedure only appears when both 6221 units are connected.",
        requires=lambda cfg: (base._is_connected(getattr(cfg, 'K6221', 0))
                              and base._is_connected(getattr(cfg, 'K6221_2', 0))),
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Source_contacts',
            'ac_source', 'dc_source',
            'waveform', 'frequency', 'ac_current', 'ac_compliance',
            'dc_compliance', 'start_current', 'target_current', 'step_size',
            'acq_delay',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
            'use_k6221', 'use_k6221_2',
        ],
        displays=[
            'Title',
            'ac_source', 'dc_source',
            'waveform', 'frequency', 'ac_current',
            'start_current', 'target_current', 'step_size',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)']
    ),
}
