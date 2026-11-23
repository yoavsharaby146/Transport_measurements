"""
Differential Conductance Gate Map (Generic Version).

2D mapping: Gate voltage stepped on any connected SMU (outer loop), DC bias
swept on the excitation lock-in AUX output (inner loop) — the same dI/dV
setup as "Differential Conductance (AC + AUX bias)" (AC voltage from an
SRS860 / MFLI sine output, conductance computed live as I_XY / V_ac),
inherited by subclassing.

Scan modes for the AUX sweep at each gate step:
- Snake: alternates sweep direction every gate row (fastest)
- Forward/Backward: full forward AND backward sweep at every gate row
"""

from .base import *
from . import base
from .differential_conductance import (Differential_Conductance,
                                        _requires_exc_source,
                                        _connected_exc_sources,
                                        _connected_lockins)


class Differential_Conductance_gate_map(Differential_Conductance):
    """2D map: gate stepped (outer), AUX DC bias swept (inner), dI/dV
    readout."""

    Title = Parameter('dI/dV gate map measurement', default='dI/dV map')
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
    aux_end = FloatParameter('AUX end voltage (V)', default=0.01)
    # aux_step inherited from the parent ('Auxiliary step (mV)') = AUX step

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh excitation/measuring/SMU dropdowns to connected instruments."""
        exc = _connected_exc_sources() or ['(none connected)']
        cls.exc_source = ListParameter('Excitation lock-in', choices=exc, default=exc[0])
        meas = _connected_lockins() or ['(none connected)']
        cls.meas_lockin = ListParameter('Measuring lock-in (dI/dV input)',
                                        choices=meas, default=meas[0])
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
        self._exc_instrument()  # fail fast if the source vanished
        time_0 = time.time()

        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        log.info(f"Starting dI/dV gate map on {self.exc_source} "
                 f"AUX{self.aux_signal}, mode={self.scan_mode}")
        log.info(f"Gate ({self.smu}): {self.gate_start}V to {self.gate_end}V, "
                 f"step {self.gate_step}mV")
        log.info(f"AUX: {self.aux_start}V to {self.aux_end}V, "
                 f"step {self.aux_step}mV")

        # --- Ranges ---
        gate_range = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        aux_fwd = self.generate_range(self.aux_start, self.aux_end, self.aux_step)
        aux_bwd = aux_fwd[::-1]

        total_points = len(gate_range) * len(aux_fwd)
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

        log.info(f"Ramping AUX to initial position: {self.aux_start}V")
        for aux_volt in self.generate_range(self._read_aux(), self.aux_start, self.aux_step):
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
        # Sources intentionally left running (AC excitation + AUX bias stay
        # as they are).
        log.info("dI/dV gate map measurement finished (sources left on)")


proc_diff_conductance_gate_map = {
    "Differential Conductance Gate Map": dict(
        cls=Differential_Conductance_gate_map,
        category=["2D Mapping", "Gate Sweep", "Differential Conductance"],
        description="2D Gate vs AUX-bias differential conductance (dI/dV) map.\n\n"
                    "Gate voltage is stepped (outer loop, any connected SMU) and the "
                    "DC bias on the excitation lock-in's AUX output is swept "
                    "(inner loop). AC voltage excitation from the same lock-in's "
                    "sine output (any connected SRS860 / MFLI; amplitude + "
                    "frequency set by this procedure). "
                    "Differential_Conductance_X/Y(S) = I_XY / V_ac is computed "
                    "live from the 'Measuring lock-in' — tick that lock-in in "
                    "the Devices group or the conductance columns stay NaN.\n\n"
                    "Scan modes (AUX sweep at each gate step):\n"
                    "- Snake: alternates sweep direction every gate row\n"
                    "- Forward/Backward: full forward then backward sweep\n\n"
                    "Sources are NOT turned off at the end.",
        requires=_requires_exc_source,
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts', 'Source_contacts',
            'scan_mode',
            'smu', 'gate_start', 'gate_end', 'gate_step', 'gate_delay',
            'exc_source', 'meas_lockin', 'ac_voltage', 'ac_frequency',
            'aux_signal', 'aux_start', 'aux_end', 'aux_step',
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
            'exc_source', 'meas_lockin', 'ac_voltage',
            'aux_start', 'aux_end',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}
