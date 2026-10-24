"""
Differential Resistance 6221 with Gate Voltage Mapping Measurement
(Generic Version).

2D mapping: Gate voltage stepped on any connected SMU (outer loop), K6221 DC
bias current swept (inner loop) — the same dV/dI setup as "Differential
Resistance 6221" (DC bias on the K6221 current source, compliance/current
range set manually on the instrument, AC from a lock-in sine output assumed
pre-configured), inherited by subclassing.

Scan modes for the DC sweep at each gate step:
- Snake: alternates sweep direction every gate row (fastest)
- Forward/Backward: full forward AND backward sweep at every gate row
"""

from .base import *
from . import base
from .differential_resistance_6221 import Differential_Resistance_6221


class Differential_Resistance_6221_map(Differential_Resistance_6221):
    """2D map: gate stepped (outer), K6221 DC current swept (inner), dV/dI
    readout."""

    Title = Parameter('dV/dI 6221 map measurement', default='dV/dI 6221 map')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Map parameters ---
    scan_mode = ListParameter('Scan Mode', choices=['Snake', 'Forward/Backward'],
                              default='Snake')
    smu = base._make_smu_parameter('Gate SMU', default='Gate_1')
    gate_start = FloatParameter('Gate start voltage (V)', default=-1)
    gate_end = FloatParameter('Gate end voltage (V)', default=1)
    gate_step = FloatParameter('Gate step size (mV)', default=50)
    gate_delay = FloatParameter('Delay after gate step (s)', default=1)
    dc_start = FloatParameter('DC start current (A)', default=0)
    dc_end = FloatParameter('DC end current (A)', default=1e-6)
    # step_size inherited from the parent ('DC step size (A)') = DC step

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh the SMU dropdown to the connected instruments."""
        cls.smu = base._make_smu_parameter('Gate SMU', default='Gate_1')

    def _ramp_dc_range(self, dc, values, time_0, counter, total_points):
        """Sweep the K6221 DC current through `values`, emitting a point each
        step.

        Returns (aborted, new_counter)."""
        for cur in values:
            dc.source_current = float(cur)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0, dc)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * counter / total_points)
            counter += 1
            if self.should_stop():
                log.warning("User stopped measurement")
                return True, counter
        return False, counter

    def execute(self):
        dc = self._k6221()  # fail fast if the source vanished
        time_0 = time.time()

        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        log.info(f"Starting dV/dI 6221 map, mode={self.scan_mode}")
        log.info("AC excitation: lock-in sine output "
                 "(amplitude/frequency set on the instrument)")
        log.info("K6221 compliance and current range set manually on the "
                 "instrument — not configured here")
        log.info(f"Gate ({self.smu}): {self.gate_start}V to {self.gate_end}V, "
                 f"step {self.gate_step}mV")
        log.info(f"DC current: {self.dc_start}A to {self.dc_end}A, "
                 f"step {self.step_size}A")

        dc.enable_source()

        # --- Ranges ---
        gate_range = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        dc_fwd = self.generate_range(self.dc_start, self.dc_end, self.step_size * 1000)
        dc_bwd = dc_fwd[::-1]

        total_points = len(gate_range) * len(dc_fwd)
        if self.scan_mode == 'Forward/Backward':
            total_points *= 2

        log.info(f"Total measurement points: {total_points}")

        # --- Initial ramps (no emissions) ---
        log.info(f"Ramping gate to initial position: {self.gate_start}V")
        gate.ramp_voltage(self.gate_start, 2, 0.001)
        time.sleep(self.gate_delay)
        if self.should_stop():
            log.warning("User stopped during initial gate ramp")
            return

        start_current = float(dc.source_current)
        log.info(f"Ramping DC current to initial position: {self.dc_start}A "
                 f"(from {start_current:.4e}A)")
        for cur in self.generate_range(start_current, self.dc_start,
                                       self.step_size * 1000):
            dc.source_current = float(cur)
            if self.should_stop():
                log.warning("User stopped during initial DC ramp")
                return

        # --- Main loop: gate outer, DC current inner ---
        counter = 1
        for i, gate_volt in enumerate(gate_range):
            if i > 0:
                gate.ramp_voltage(gate_volt, 2, 0.001)
                time.sleep(self.gate_delay)
                if self.should_stop():
                    log.warning("User stopped measurement")
                    return

            if self.scan_mode == 'Snake':
                row = dc_fwd if i % 2 == 0 else dc_bwd
                aborted, counter = self._ramp_dc_range(dc, row, time_0, counter,
                                                       total_points)
                if aborted:
                    return
            else:  # Forward/Backward
                aborted, counter = self._ramp_dc_range(dc, dc_fwd, time_0, counter,
                                                       total_points)
                if aborted:
                    return
                aborted, counter = self._ramp_dc_range(dc, dc_bwd, time_0, counter,
                                                       total_points)
                if aborted:
                    return

    def shutdown(self):
        # Sources intentionally left running (lock-in AC untouched, DC
        # current stays at the last sweep value).
        log.info("dV/dI 6221 map measurement finished (sources left on)")


proc_diff_resistance_6221_map = {
    "Differential Resistance 6221 Gate Map": dict(
        cls=Differential_Resistance_6221_map,
        category=["2D Mapping", "Gate Sweep", "Differential Resistance"],
        description="2D Gate vs DC-current dV/dI map measurement.\n\n"
                    "Gate voltage is stepped (outer loop, any connected SMU) and "
                    "the K6221 DC bias current is swept (inner loop).\n"
                    "K6221 compliance and current range are set manually on the "
                    "instrument. AC excitation from a lock-in sine output assumed "
                    "pre-configured.\n\n"
                    "Scan modes (DC sweep at each gate step):\n"
                    "- Snake: alternates sweep direction every gate row\n"
                    "- Forward/Backward: full forward then backward sweep\n\n"
                    "Sources are NOT turned off at the end.",
        requires=lambda cfg: base._is_connected(getattr(cfg, 'K6221', 0)),
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts', 'Source_contacts',
            'scan_mode',
            'smu', 'gate_start', 'gate_end', 'gate_step', 'gate_delay',
            'dc_start', 'dc_end', 'step_size',
            'acq_delay',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
        ],
        displays=[
            'Title', 'scan_mode',
            'smu', 'gate_start', 'gate_end',
            'dc_start', 'dc_end',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}