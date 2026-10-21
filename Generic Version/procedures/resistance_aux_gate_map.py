"""
Resistance vs AUX and Gate 2D mapping measurement (Generic Version).

2D mapping: Gate voltage stepped on any connected SMU (outer loop), lock-in
AUX output voltage swept (inner loop) while recording the standard
resistance readings — the same AUX-source machinery as
"Resistance aux voltage sweep", inherited by subclassing.

Scan modes for the AUX sweep at each gate step:
- Snake: alternates sweep direction every gate row (fastest)
- Forward/Backward: full forward AND backward sweep at every gate row
"""

from .base import *
from . import base
from .resistance_aux_sweep import (Resistance_aux_voltage_measurement,
                                   _make_aux_source_parameter,
                                   _connected_aux_sources)


def _requires_aux_source(cfg):
    return len(_connected_aux_sources()) > 0


class Resistance_aux_gate_map(Resistance_aux_voltage_measurement):
    """2D map: gate stepped (outer), AUX swept (inner), R readout."""

    Title = Parameter('R_AUX gate map measurement', default='R_AUX map')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Map parameters ---
    scan_mode = ListParameter('Scan Mode', choices=['Snake', 'Forward/Backward'],
                              default='Snake')
    smu = base._make_smu_parameter('Gate SMU', default='Gate_1')
    gate_start = FloatParameter('Gate start voltage (V)', default=-1)
    gate_end = FloatParameter('Gate end voltage (V)', default=1)
    gate_step = FloatParameter('Gate step size (mV)', default=50)
    gate_delay = FloatParameter('Delay after gate step (s)', default=1)
    aux_start = FloatParameter('AUX start voltage (V)', default=0)
    aux_end = FloatParameter('AUX end voltage (V)', default=1)
    # step_size inherited from the parent ('Step size(mV)') = AUX step

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh aux_source and SMU dropdowns to connected instruments."""
        cls.aux_source = _make_aux_source_parameter()
        cls.smu = base._make_smu_parameter('Gate SMU', default='Gate_1')

    def _ramp_aux_range(self, values, time_0, counter, total_points):
        """Sweep the AUX output through `values`, emitting a point each step.

        Returns (aborted, new_counter)."""
        for aux_volt in values:
            self._ramp_aux_to(aux_volt)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * counter / total_points)
            counter += 1
            if self.should_stop():
                log.warning("User stopped measurement")
                return True, counter
        return False, counter

    def execute(self):
        self._aux_instrument()  # fail fast if the source vanished
        time_0 = time.time()

        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        log.info(f"Starting R_AUX gate map on {self.aux_source} AUX{self.aux}, "
                 f"mode={self.scan_mode}")
        log.info(f"Gate ({self.smu}): {self.gate_start}V to {self.gate_end}V, "
                 f"step {self.gate_step}mV")
        log.info(f"AUX: {self.aux_start}V to {self.aux_end}V, step {self.step_size}mV")

        # --- Ranges ---
        gate_range = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        aux_fwd = self.generate_range(self.aux_start, self.aux_end, self.step_size)
        aux_bwd = aux_fwd[::-1]

        pts_per_gate = len(aux_fwd)
        if self.scan_mode == 'Forward/Backward':
            pts_per_gate *= 2
        total_points = len(gate_range) * pts_per_gate
        log.info(f"Total measurement points: {total_points}")

        # --- Initial ramps (no emissions) ---
        log.info(f"Ramping gate to initial position: {self.gate_start}V")
        gate.ramp_voltage(self.gate_start, 2, 0.001)
        time.sleep(self.gate_delay)
        if self.should_stop():
            log.warning("User stopped during initial gate ramp")
            return

        log.info(f"Ramping AUX to initial position: {self.aux_start}V")
        for aux_volt in self.generate_range(self._read_aux(), self.aux_start, self.step_size):
            self._ramp_aux_to(aux_volt)
            if self.should_stop():
                log.warning("User stopped during initial AUX ramp")
                return

        # --- Main loop: gate outer, AUX inner ---
        counter = 1
        for i, gate_volt in enumerate(gate_range):
            if i > 0:
                gate.ramp_voltage(gate_volt, 2, 0.001)
                time.sleep(self.gate_delay)
                if self.should_stop():
                    log.warning("User stopped measurement")
                    return

            if self.scan_mode == 'Snake':
                row = aux_fwd if i % 2 == 0 else aux_bwd
                aborted, counter = self._ramp_aux_range(row, time_0, counter, total_points)
                if aborted:
                    return
            else:  # Forward/Backward
                aborted, counter = self._ramp_aux_range(aux_fwd, time_0, counter, total_points)
                if aborted:
                    return
                aborted, counter = self._ramp_aux_range(aux_bwd, time_0, counter, total_points)
                if aborted:
                    return

    def shutdown(self):
        log.info("R_AUX gate map measurement finished")


proc_resistance_aux_gate_map = {
    "Resistance AUX Gate Map": dict(
        cls=Resistance_aux_gate_map,
        category=["2D Mapping", "Gate Sweep", "Aux Sweep"],
        description="2D Gate vs AUX resistance map measurement.\n\n"
                    "Gate voltage is stepped (outer loop, any connected SMU) and the "
                    "AUX output voltage of a chosen lock-in (SRS830 / SRS860 / MFLI — "
                    "connected units only) is swept (inner loop) while measuring "
                    "Resistance (via the other lock-ins).\n\n"
                    "Scan modes (AUX sweep at each gate step):\n"
                    "- Snake: alternates sweep direction every gate row\n"
                    "- Forward/Backward: full forward then backward sweep",
        requires=_requires_aux_source,
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'scan_mode',
            'smu', 'gate_start', 'gate_end', 'gate_step', 'gate_delay',
            'aux_source', 'aux', 'aux_start', 'aux_end', 'step_size',
            'acq_delay',
            'devices',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs860_3', 'use_srs860_4',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2',
            'use_k6221',
        ],
        displays=[
            'Title', 'scan_mode',
            'smu', 'gate_start', 'gate_end',
            'aux_source', 'aux_start', 'aux_end',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}

