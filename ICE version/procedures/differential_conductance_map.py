"""
Differential Conductance Gate Map (ICE Version).

2D mapping: Gate voltage stepped on any connected SMU (outer loop), DC bias
swept on the excitation lock-in's sine-output DC offset (inner loop) — the
same dI/dV setup as "Differential Conductance (unified)" (AC excitation
from an SRS860 / MFLI sine output, conductance computed live as
I_XY / V_ac), inherited by subclassing.

Scan modes for the DC sweep at each gate step:
- Snake: alternates sweep direction every gate row (fastest)
- Forward/Backward: full forward AND backward sweep at every gate row
"""

from .base import *
from . import base
from .differential_conductance import (Differential_Conductance,
                                       _requires_exc_source,
                                       _connected_exc_sources,
                                       _ALL_LOCKIN_NAMES)


class Differential_Conductance_map(Differential_Conductance):
    """2D map: gate stepped (outer), DC bias on the excitation lock-in swept
    (inner), dI/dV readout."""

    # --- Parameters ---
    Title = Parameter('dI/dV gate map measurement', default='dI/dV map')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping', default=True)

    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward'],
                              group_by='mapping', group_condition=True)

    # --- Gate Parameters (Stepped - Outer Loop) ---
    smu = base._make_smu_parameter('Gate SMU', default='Gate_1',
                                   group_by='mapping', group_condition=True)
    gate_start = FloatParameter('Gate start voltage (V)', group_by='mapping', group_condition=True, default=-1)
    gate_end = FloatParameter('Gate end voltage (V)', group_by='mapping', group_condition=True, default=1)
    gate_step = FloatParameter('Gate step size (mV)', group_by='mapping', group_condition=True, default=50)

    # --- DC Offset Parameters (Swept - Inner Loop) ---
    dc_start = FloatParameter('DC start voltage (V)', group_by='mapping', group_condition=True, default=0)
    dc_end = FloatParameter('DC end voltage (V)', group_by='mapping', group_condition=True, default=0.01)
    # dc_offset_step inherited from the parent ('DC Step Size (mV)') = DC step

    # --- Delays ---
    gate_delay = FloatParameter('Delay after gate step (s)', default=5, group_by='mapping', group_condition=True)
    acq_delay = FloatParameter('Acquisition delay (s)', default=0.1)

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh SMU + excitation/measuring dropdowns to connected instruments."""
        exc = _connected_exc_sources() or ['(none connected)']
        cls.exc_source = ListParameter('Excitation lock-in', choices=exc, default=exc[0])
        meas = [n for n in _ALL_LOCKIN_NAMES
                if base._is_connected(getattr(base, n, 0))] or ['(none connected)']
        cls.meas_lockin = ListParameter('Measuring lock-in (dI/dV input)',
                                        choices=meas, default=meas[0])
        cls.smu = base._make_smu_parameter('Gate SMU', default='Gate_1',
                                           group_by='mapping', group_condition=True)

    def ramp_gate_with_abort(self, gate, target_voltage, step_size_mv=2, delay=0.1):
        """Ramp gate voltage to target in small steps, abortable. Returns
        True if completed, False if aborted (same as the AUX map)."""
        current_voltage = gate.measure__voltage()
        step_size_v = step_size_mv / 1000.0
        tolerance = step_size_v / 2

        while abs(current_voltage - target_voltage) > tolerance:
            if self.should_stop():
                log.warning("User aborted during gate voltage ramping")
                return False
            if current_voltage < target_voltage:
                next_voltage = min(current_voltage + step_size_v, target_voltage)
            else:
                next_voltage = max(current_voltage - step_size_v, target_voltage)
            gate.ramp_voltage(next_voltage, 5, 0.01)
            time.sleep(delay)
            current_voltage = gate.measure__voltage()
        return True

    def execute(self):
        """Execute the 2D dI/dV gate map measurement."""
        self._exc_instrument()  # fail fast if the chosen source vanished
        time_0 = time.time()
        log.info("Starting dI/dV gate map measurement")
        log.info(f"Scan mode: {self.scan_mode}")
        log.info(f"Gate: {self.gate_start}V to {self.gate_end}V, step {self.gate_step}mV")
        log.info(f"DC offset: {self.dc_start}V to {self.dc_end}V, step {self.dc_offset_step}mV")

        # --- SMU Setup ---
        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        # --- Generate Ranges ---
        gate_range = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        dc_range_fwd = self.generate_range(self.dc_start, self.dc_end, self.dc_offset_step)
        dc_range_bwd = dc_range_fwd[::-1]

        pts_per_gate = len(dc_range_fwd)
        if self.scan_mode == 'Forward/Backward':
            pts_per_gate *= 2
        total_points = len(gate_range) * pts_per_gate
        log.info(f"Total measurement points: {total_points}")

        # --- Initial Gate Ramping (with abort capability, no emissions) ---
        log.info(f"Ramping gate to initial position: {self.gate_start}V")
        if not self.ramp_gate_with_abort(gate, self.gate_start, step_size_mv=2, delay=0.1):
            return
        time.sleep(self.gate_delay)

        # --- Initial DC-offset Ramping (no emissions) ---
        log.info(f"Ramping DC offset to initial position: {self.dc_start}V")
        for v in self.generate_range(self._read_dc(), self.dc_start, self.dc_offset_step):
            self._set_dc(v)
            if self.should_stop():
                log.warning("User stopped during initial DC ramp")
                return

        # --- Main Measurement Loop ---
        iteration = 1
        for i, gate_volt in enumerate(gate_range):
            if i > 0:
                gate.ramp_voltage(gate_volt, 5, 0.01)
                time.sleep(self.gate_delay)

            if self.should_stop():
                log.warning("User stopped measurement")
                return

            rows = [dc_range_fwd, dc_range_bwd] if self.scan_mode == 'Forward/Backward' \
                else [dc_range_fwd if i % 2 == 0 else dc_range_bwd]
            for dc_row in rows:
                for v in dc_row:
                    self._set_dc(v)
                    time.sleep(self.acq_delay)

                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1

                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

    def shutdown(self):
        """Cleanup after measurement."""
        log.info("Measurement complete. Procedure shutdown finished.")


proc_differential_conductance_map = {
    "Differential Conductance Gate Map": dict(
        cls=Differential_Conductance_map,
        category=["2D Mapping", "Gate Sweep", "Tunneling junction"],
        description="2D Gate vs DC-bias differential conductance (dI/dV) map.\n\n"
                    "Gate voltage is stepped (outer loop, any connected SMU) and the "
                    "DC offset on the excitation lock-in's sine output is swept "
                    "(inner loop; any connected SRS860 / MFLI).\n"
                    "Differential_Conductance_X/Y(S) = I_XY / V_ac is computed live "
                    "from the 'Measuring lock-in' — tick that lock-in in the "
                    "Devices group or the conductance columns stay NaN.\n\n"
                    "Scan modes (DC sweep at each gate step):\n"
                    "- Snake: alternates sweep direction every gate row\n"
                    "- Forward/Backward: full forward then backward sweep\n\n"
                    "Magnet field can be optionally recorded.",
        requires=_requires_exc_source,
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221',
            'exc_source', 'meas_lockin',
            'mapping',
            'scan_mode',
            'smu', 'gate_start', 'gate_end', 'gate_step',
            'dc_start', 'dc_end', 'dc_offset_step',
            'gate_delay', 'acq_delay',
        ],
        displays=[
            'Title', 'scan_mode',
            'smu', 'gate_start', 'gate_end',
            'exc_source', 'meas_lockin',
            'dc_start', 'dc_end',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}


