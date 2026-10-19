"""
Differential resistance (dV/dI) procedures — single-6221 configuration.

Two 6221 units cannot run together (they conflict on the bus), so each
procedure below uses at most the single K6221 connection, paired with a
lock-in:

1. "Differential Resistance AUX" — DC bias swept on a lock-in AUX output.
   AC excitation selectable: the lock-in sine output (pre-configured on the
   instrument) or the K6221 waveform output (configured from parameters).

2. "Differential Resistance 6221 DC" — DC bias swept on the K6221 current
   source; AC excitation from a lock-in sine output (pre-configured on the
   instrument).

Both procedures leave all sources running at the end (lab preference).
"""

from .base import *
from . import base


# Lock-ins that can source an AUX output voltage, in display order.
_AUX_SOURCE_NAMES = ['SRS830_1', 'SRS830_2', 'SRS830_3',
                     'SRS860_1', 'SRS860_2', 'SRS860_3', 'SRS860_4',
                     'MFLI_1', 'MFLI_2', 'MFLI_3']


def _connected_aux_sources():
    """Names of connected lock-ins usable as AUX voltage source."""
    return [n for n in _AUX_SOURCE_NAMES
            if base._is_connected(getattr(base, n, 0))]


def _make_aux_source_parameter():
    choices = _connected_aux_sources()
    return ListParameter(
        'AUX source',
        choices=choices or ['(none connected)'],
        default=choices[0] if choices else '(none connected)',
    )


class Differential_Resistance_AUX(GenericProcedure):
    """dV/dI: DC bias on a lock-in AUX output, AC from lock-in sine or K6221."""

    Title = Parameter('dV/dI sweep measurement', default='dV/dI AUX')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')

    # --- Sweep parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              default='Sweep to setpoint')
    aux_source = _make_aux_source_parameter()
    aux_signal = ListParameter('Aux output 1-4:', choices=[1, 2, 3, 4], default=1)
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)', default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', default=2)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

    # --- AC source selection ---
    ac_source = ListParameter('AC source',
                              choices=['Lock-in sine output', 'K6221 waveform'],
                              default='Lock-in sine output')
    ac_running = BooleanParameter('AC already running (skip setup)', default=False)
    waveform = ListParameter('Waveform', choices=['sine', 'square', 'ramp'],
                             default='sine')
    frequency = FloatParameter('AC frequency (Hz)', default=100)
    ac_current = FloatParameter('AC current RMS (A)', default=1e-6)
    ac_compliance = FloatParameter('AC compliance (V)', default=10)

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
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

    _MID_COLUMNS = ['AUX_DC_offset(V)']

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh aux_source choices to the connected lock-ins."""
        cls.aux_source = _make_aux_source_parameter()

    # --- AUX helpers (same as resistance_aux_sweep) ---

    def _aux_instrument(self):
        inst = getattr(base, self.aux_source, 0)
        if not base._is_connected(inst):
            raise ValueError(
                f"{self.aux_source} selected as AUX source but is not "
                f"connected (check the pre-launch dialog)")
        return inst

    def _read_aux(self, attempts=3, delay=0.5):
        """Read back the programmed AUX output voltage (retries VISA hiccups)."""
        inst = self._aux_instrument()
        if self.aux_source.startswith('MFLI'):
            reader = lambda: inst.get_auxout(self.aux_signal - 1)  # MFLI: 0-based
        else:
            reader = lambda: getattr(inst, f'dac{self.aux_signal}')  # SRS: 1-based
        last_err = None
        for i in range(attempts):
            try:
                return float(reader())
            except Exception as e:
                last_err = e
                log.warning("%s AUX read failed (attempt %d/%d): %s",
                            self.aux_source, i + 1, attempts, e)
                time.sleep(delay)
        raise last_err

    def _ramp_aux_to(self, target):
        """Ramp the AUX output to target (short ramp, called per sweep point)."""
        inst = self._aux_instrument()
        if self.aux_source.startswith('MFLI'):
            inst.aux_ramp(signal=self.aux_signal - 1, aux=float(target),
                          steps=5, delay=0.01)
        elif self.aux_source.startswith('SRS860'):
            inst.ramp_aux(self.aux_signal, float(target), 5, 0.01)
        else:
            # SRS830 driver has no ramp_aux: software ramp via the dac property
            start = self._read_aux()
            for v in np.linspace(start, float(target), 6)[1:]:
                setattr(inst, f'dac{self.aux_signal}', float(v))
                time.sleep(0.01)

    # --- AC setup ---

    def _setup_ac(self):
        """Start AC excitation. K6221 chosen -> configure here; lock-in sine
        output assumed already configured on the instrument itself."""
        if self.ac_source != 'K6221 waveform':
            log.info("AC excitation: lock-in sine output "
                     "(amplitude/frequency set on the instrument)")
            return
        inst = base.K6221
        if not base._is_connected(inst):
            raise ValueError("K6221 selected as AC source but is not "
                             "connected (check the pre-launch dialog)")
        peak_amp = self.ac_current * base.RMS_TO_PEAK
        if not (2e-12 <= abs(peak_amp) <= 0.105):
            raise ValueError(f"AC current {self.ac_current} A RMS out of range "
                             f"(2e-12..0.105 A peak)")
        if self.ac_running:
            # Waveform duration is infinite and nothing turns it off, so a
            # waveform started once just keeps running — skip setup entirely.
            log.info("K6221 AC assumed already running - skipping setup")
            inst.enable_source()
            return
        log.info(f"Configuring K6221 as AC source: {self.waveform} @ "
                 f"{self.frequency} Hz, {self.ac_current} A RMS, compliance "
                 f"{self.ac_compliance} V")
        inst.waveform_function = self.waveform
        inst.waveform_frequency = self.frequency
        inst.waveform_amplitude = peak_amp
        inst.waveform_offset = 0
        inst.waveform_dutycycle = 50
        inst.source_compliance = self.ac_compliance
        inst.waveform_ranging = 'best'
        inst.waveform_duration_set_infinity()
        inst.waveform_arm()
        inst.enable_source()
        inst.waveform_start()

    # --- Procedure -----------------------------------------------------

    def startup(self):
        self._capture_metadata()
        # MFLI AUX output must be in manual mode for the offset ramp to
        # appear on the BNC. -1 == AUX_MANUAL. Harmless no-op for SRS.
        if self.aux_source.startswith('MFLI'):
            self._aux_instrument().set_auxout(signal=self.aux_signal - 1, select=-1)
        self._setup_ac()

    def getmeas(self, t0):
        return self._read_standard(t0, mid_extras=[self._read_aux()])

    def execute(self):
        self._aux_instrument()  # fail fast if the source vanished
        time_0 = time.time()

        aux_origin = self._read_aux()
        target_aux = self.aux_Target
        log.info(f"Starting dV/dI {self.scan_mode} on {self.aux_source} "
                 f"AUX{self.aux_signal}. Start={aux_origin:.4f}V, "
                 f"Target={target_aux:.4f}V, AC={self.ac_source}")

        range_to_target = self.generate_range(aux_origin, target_aux, self.aux_step)
        range_return = self.generate_range(target_aux, aux_origin, self.aux_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        log.info("Sweeping to Setpoint...")
        for aux in range_to_target:
            self._ramp_aux_to(aux)
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
                self._ramp_aux_to(aux)
                time.sleep(self.acq_delay)
                data = self.getmeas(time_0)
                self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
                self.emit('progress', 100 * point_counter / total_points)
                point_counter += 1
                if self.should_stop():
                    log.warning("User stopped measurement while in return Sweep")
                    return

    def shutdown(self):
        # Sources intentionally left running (AC waveform + AUX bias stay
        # as they are).
        log.info("dV/dI AUX measurement finished (sources left on)")


class Differential_Resistance_6221DC(GenericProcedure):
    """dV/dI: DC bias swept on the K6221, AC from a lock-in sine output."""

    Title = Parameter('dV/dI sweep measurement', default='dV/dI 6221 DC')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')

    # --- DC sweep parameters ---
    dc_compliance = FloatParameter('DC compliance (V)', default=10)
    target_current = FloatParameter('DC target current (A)', default=1e-6)
    step_size = FloatParameter('DC step size (A)', default=1e-8)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
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

    _MID_COLUMNS = ['DC_current(A)']

    def _k6221(self):
        inst = base.K6221
        if not base._is_connected(inst):
            raise ValueError("K6221 not connected (check the pre-launch dialog)")
        return inst

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0, dc):
        return self._read_standard(t0, mid_extras=[float(dc.source_current)])

    def execute(self):
        dc = self._k6221()
        log.info("AC excitation: lock-in sine output "
                 "(amplitude/frequency set on the instrument)")
        time_0 = time.time()

        log.info(f"Configuring K6221 as DC source: compliance "
                 f"{self.dc_compliance} V")
        dc.source_compliance = self.dc_compliance
        dc.source_auto_range = True
        dc.enable_source()

        # Start from wherever the DC source actually is — no forced jump
        # to a user-entered start value.
        start_current = float(dc.source_current)
        current_ranges = self.generate_range(start_current, self.target_current,
                                             self.step_size * 1000)  # step in milli-units

        log.info(f"Sweeping DC current from {start_current:.4e} A to "
                 f"{self.target_current} A in {len(current_ranges)} steps")

        iteration = 1
        for val in current_ranges:
            dc.source_current = float(val)

            time.sleep(self.acq_delay)
            data = self.getmeas(time_0, dc)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(current_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                break

    def shutdown(self):
        # Sources intentionally left running (lock-in AC untouched, DC
        # current stays at the last sweep value).
        log.info("dV/dI 6221 DC measurement finished (sources left on)")


def _requires_aux_source(cfg):
    return len([n for n in _AUX_SOURCE_NAMES
                if base._is_connected(getattr(cfg, n, 0))]) > 0


proc_diff_resistance_AUX = {
    "Differential Resistance AUX (DC on lock-in AUX)": dict(
        cls=Differential_Resistance_AUX,
        category="Differential Resistance",
        description="dV/dI sweep with the DC bias on a lock-in AUX output "
                    "(any connected lock-in, chosen from the 'AUX source' dropdown).\n"
                    "AC excitation selectable: lock-in sine output (set amplitude/"
                    "frequency on the instrument itself) or the K6221 waveform "
                    "output (configured from the parameters below).\n"
                    "Sweep to Setpoint: Origin -> Target (voltage left at Target).\n"
                    "Sweep and Return: Origin -> Target -> Origin.\n"
                    "Sources are NOT turned off at the end.",
        requires=_requires_aux_source,
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Source_contacts',
            'scan_mode', 'acq_delay',
            'aux_source', 'aux_signal', 'aux_Target', 'aux_step',
            'ac_source', 'ac_running', 'waveform', 'frequency',
            'ac_current', 'ac_compliance',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
            'use_k6221',
        ],
        displays=[
            'Title', 'scan_mode', 'aux_source', 'aux_Target',
            'ac_source',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}

proc_diff_resistance_6221dc = {
    "Differential Resistance 6221 DC (AC on lock-in)": dict(
        cls=Differential_Resistance_6221DC,
        category="Differential Resistance",
        description="dV/dI sweep with the DC bias on the Keithley 6221 current "
                    "source (target / step size / delay, starting from the "
                    "present level) and the AC excitation from a lock-in sine "
                    "output (set amplitude/frequency on the lock-in itself).\n"
                    "Sources are NOT turned off at the end.",
        requires=lambda cfg: base._is_connected(getattr(cfg, 'K6221', 0)),
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Source_contacts',
            'dc_compliance', 'target_current', 'step_size', 'acq_delay',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
            'use_k6221',
        ],
        displays=[
            'Title', 'target_current', 'step_size',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}
