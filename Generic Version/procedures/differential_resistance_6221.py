"""
Differential resistance (dV/dI) — DC bias on the Keithley 6221
(Generic Version).

The DC bias is swept on the K6221 current source (starting from the
present level). Compliance and current range are set manually on the
instrument — this procedure does not touch them. The AC excitation comes
from a lock-in sine output that is assumed already configured on the
instrument itself — this procedure never configures the K6221 waveform.

Distinct from "Differential Resistance AUX" (differential_resistance_aux.py),
which sweeps the DC bias on a lock-in AUX output instead.

The procedure leaves all sources running at the end (lab preference).
"""

from .base import *
from . import base


class Differential_Resistance_6221(GenericProcedure):
    """dV/dI: DC bias swept on the K6221 current source, AC from a lock-in
    sine output (pre-configured on the instrument)."""

    Title = Parameter('dV/dI sweep measurement', default='dV/dI 6221 DC')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')

    # --- DC sweep parameters ---
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
        log.info("K6221 compliance and current range set manually on the "
                 "instrument — not configured here")
        time_0 = time.time()

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


proc_diff_resistance_6221 = {
    "Differential Resistance 6221 (DC bias on K6221)": dict(
        cls=Differential_Resistance_6221,
        category="Differential Resistance",
        description="dV/dI sweep with the DC bias on the Keithley 6221 current "
                    "source (target / step size / delay, starting from the "
                    "present level).\n"
                    "K6221 compliance and current range are set manually on the "
                    "instrument. AC excitation from a lock-in sine output "
                    "(set amplitude/frequency on the lock-in itself — the 6221 "
                    "waveform is never configured here).\n"
                    "The 6221 DC level is recorded in DC_current(A). It is the DC "
                    "source here, so no 6221 AC amplitude column is recorded.\n"
                    "Sources are NOT turned off at the end.",
        requires=lambda cfg: base._is_connected(getattr(cfg, 'K6221', 0)),
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Source_contacts',
            'target_current', 'step_size', 'acq_delay',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
        ],
        displays=[
            'Title', 'target_current', 'step_size',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}
