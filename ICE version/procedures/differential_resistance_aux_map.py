"""
Differential Resistance AUX Map with Gate Voltage Mapping Measurement.

2D mapping with Gate voltage stepped (outer loop) and AUX voltage swept (inner loop).
Supports Snake, Forward/Backward, and Hysteresis scan modes.
Magnet field can be optionally recorded.
"""

from .base import *
from . import base
from .differential_resistance_aux import _make_aux_source_parameter, _AUX_SOURCE_NAMES


class Differential_Resistance_AUX_map(ICEProcedure):
    """
    2D mapping measurement with Gate voltage stepped and AUX voltage swept.
    
    The gate voltage is changed in discrete steps (outer loop), and at each
    gate step, the AUX output is swept through its full range (inner loop).
    
    Three scan modes are available for the AUX sweep:
    - Snake: Alternates sweep direction at each gate step
    - Forward/Backward: Full forward then backward sweep at each gate step
    - Hysteresis: Origin -> Start -> End -> Origin at each gate step
    """
    
    # --- Parameters ---
    Title = Parameter('dV/dI AUX map measurement', default='dV/dI AUX map')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Hardware Selection ---
    devices = BooleanParameter('Devices in use', default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=True)
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
    use_k6221 = BooleanParameter('Use k6221 (record amplitude column)', group_by='devices', default=False)

    # --- AUX Configuration (any connected lock-in) ---
    aux_source = _make_aux_source_parameter()
    aux_signal = ListParameter('Aux output 1-4:', choices=[1, 2, 3, 4], default=1)

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping', default=True)
    
    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward', 'Hysteresis'],
                              group_by='mapping', group_condition=True)

    # --- Gate Parameters (Stepped - Outer Loop) ---
    smu = base._make_smu_parameter('Gate SMU', default='Gate_1',
                                   group_by='mapping', group_condition=True)

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh SMU + AUX-source dropdown choices to connected instruments."""
        cls.smu = base._make_smu_parameter('Gate SMU', default='Gate_1',
                                           group_by='mapping', group_condition=True)
        cls.aux_source = _make_aux_source_parameter()
    gate_start = FloatParameter('Gate start voltage (V)', group_by='mapping', group_condition=True, default=-1)
    gate_end = FloatParameter('Gate end voltage (V)', group_by='mapping', group_condition=True, default=1)
    gate_step = FloatParameter('Gate step size (mV)', group_by='mapping', group_condition=True, default=50)

    # --- AUX Parameters (Swept - Inner Loop) ---
    aux_start = FloatParameter('AUX start voltage (V)', group_by='mapping', group_condition=True, default=0)
    aux_end = FloatParameter('AUX end voltage (V)', group_by='mapping', group_condition=True, default=1)
    aux_step = FloatParameter('AUX step size (mV)', group_by='mapping', group_condition=True, default=10)

    # --- Delays ---
    gate_delay = FloatParameter('Delay after gate step (s)', default=5, group_by='mapping', group_condition=True)
    acq_delay = FloatParameter('Acquisition delay (s)', default=0.1)

    # --- Dynamic column recipe ---
    _MID_COLUMNS = ['AUX_DC_offset(V)']
    _LOCKIN_COL_TYPE = 'voltage'

    # --- AUX source helpers (same logic as the unified AUX procedure) ---

    def _aux_instrument(self):
        """Resolve the chosen AUX source name to a connected instrument."""
        inst = getattr(base, self.aux_source, 0)
        if not base._is_connected(inst):
            raise ValueError(
                f"{self.aux_source} selected as AUX source but is not "
                f"connected (check the pre-launch dialog)")
        return inst

    def _read_aux(self, attempts=3, delay=0.5):
        """Read back the programmed AUX output voltage.

        MFLI aux channels are 0-based internally, the dropdown/slot numbers
        are 1-based BNC numbers — converted here. Retries transient VISA
        timeouts; re-raises the last error if the instrument stays unreadable.
        """
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

    def _ramp_aux_slow(self, target, step_size_mv=2, delay=0.1):
        """Long AUX ramp in small steps with abort checks.

        Replaces the MFLI-only aux_ramping() call: works for every AUX
        source type (SRS860/SRS830/MFLI) via _ramp_aux_to().
        Returns True if completed, False if aborted.
        """
        step = max(abs(step_size_mv), 1e-3) / 1000.0
        current = self._read_aux()
        while abs(current - target) > step / 2:
            if self.should_stop():
                log.warning("User aborted during AUX ramping")
                return False
            if current < target:
                nxt = min(current + step, target)
            else:
                nxt = max(current - step, target)
            self._ramp_aux_to(nxt)
            time.sleep(delay)
            current = self._read_aux()
        return True

    def startup(self):
        """Record instrument metadata at startup."""
        self._capture_metadata()

    def getmeas(self, t0):
        """Acquire measurements from all enabled instruments."""
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        # Mid column: chosen source AUX value
        aux = math.nan
        if self.aux_source in _AUX_SOURCE_NAMES:
            try:
                aux = self._read_aux()
            except Exception as e:
                log.warning("AUX read failed: %s", e)
        return self._read_standard(t0, mid_extras=[aux])

    def ramp_gate_with_abort(self, gate, target_voltage, step_size_mv=2, delay=0.1):
        """Ramp gate voltage to target using while loop for abort capability.
        
        This method ramps the gate voltage in small steps, checking for
        abort requests between each step. No measurements are emitted.
        
        Args:
            gate: The gate SMU object
            target_voltage: Target voltage in Volts
            step_size_mv: Step size in millivolts (default: 2 mV)
            delay: Delay between steps in seconds (default: 0.1 s)
            
        Returns:
            bool: True if completed, False if aborted
        """
        current_voltage = gate.measure__voltage()
        step_size_v = step_size_mv / 1000.0  # Convert mV to V
        tolerance = step_size_v / 2
        
        while abs(current_voltage - target_voltage) > tolerance:
            if self.should_stop():
                log.warning("User aborted during gate voltage ramping")
                return False
            
            # Calculate next step towards target
            if current_voltage < target_voltage:
                next_voltage = min(current_voltage + step_size_v, target_voltage)
            else:
                next_voltage = max(current_voltage - step_size_v, target_voltage)
            
            gate.ramp_voltage(next_voltage, 5, 0.01)
            time.sleep(delay)
            current_voltage = gate.measure__voltage()
        
        return True

    def execute(self):
        """Execute the 2D AUX vs Gate mapping measurement."""
        time_0 = time.time()
        log.info("Starting dV/dI AUX map measurement")
        log.info(f"Scan mode: {self.scan_mode}")
        log.info(f"Gate: {self.gate_start}V to {self.gate_end}V, step {self.gate_step}mV")
        log.info(f"AUX: {self.aux_start}V to {self.aux_end}V, step {self.aux_step}mV")

        # --- SMU Setup ---
        gate = self.smu_choice(self.smu)
        self.smu_output(gate, self.smu)

        # --- AUX Setup ---
        inst = self._aux_instrument()  # fail fast if the chosen source vanished
        if self.aux_source.startswith('MFLI'):
            # manual mode (-1) so the offset ramp appears on the BNC
            inst.set_auxout(signal=self.aux_signal - 1, select=-1)
        aux_origin = self._read_aux()
        gate_origin = gate.measure__voltage()

        # --- Generate Ranges ---
        gate_range = self.generate_range(self.gate_start, self.gate_end, self.gate_step)
        aux_range_fwd = self.generate_range(self.aux_start, self.aux_end, self.aux_step)
        aux_range_bwd = aux_range_fwd[::-1]

        # --- Calculate Total Points ---
        if self.scan_mode == 'Snake':
            pts_per_gate = len(aux_range_fwd)
            total_points = len(gate_range) * pts_per_gate
        elif self.scan_mode == 'Forward/Backward':
            pts_per_gate = 2 * len(aux_range_fwd)
            total_points = len(gate_range) * pts_per_gate
        elif self.scan_mode == 'Hysteresis':
            # Origin -> Start -> End -> Origin
            aux_to_start = self.generate_range(aux_origin, self.aux_start, self.aux_step)
            aux_start_to_end = self.generate_range(self.aux_start, self.aux_end, self.aux_step)
            aux_end_to_origin = self.generate_range(self.aux_end, aux_origin, self.aux_step)
            pts_per_gate = len(aux_to_start) + len(aux_start_to_end) + len(aux_end_to_origin) - 2
            total_points = len(gate_range) * pts_per_gate

        log.info(f"Total measurement points: {total_points}")

        # --- Initial Gate Ramping (with abort capability, no emissions) ---
        log.info(f"Ramping gate to initial position: {self.gate_start}V")
        if not self.ramp_gate_with_abort(gate, self.gate_start, step_size_mv=2, delay=0.1):
            return  # Aborted
        time.sleep(self.gate_delay)

        # --- Initial AUX Ramping ---
        log.info(f"Ramping AUX to initial position: {self.aux_start}V")
        if not self._ramp_aux_slow(self.aux_start, step_size_mv=2, delay=0.1):
            return  # Aborted

        # --- Main Measurement Loop ---
        iteration = 1
        
        for i, gate_volt in enumerate(gate_range):
            # Move to next gate position (skip first since we're already there)
            if i > 0:
                gate.ramp_voltage(gate_volt, 5, 0.01)
                time.sleep(self.gate_delay)
            
            if self.should_stop():
                log.warning("User stopped measurement")
                return

            # --- SNAKE MODE ---
            if self.scan_mode == 'Snake':
                # Alternate AUX sweep direction based on gate step index
                current_aux_range = aux_range_fwd if i % 2 == 0 else aux_range_bwd
                
                for aux_volt in current_aux_range:
                    self._ramp_aux_to(aux_volt)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

            # --- FORWARD/BACKWARD MODE ---
            elif self.scan_mode == 'Forward/Backward':
                # Forward sweep
                for aux_volt in aux_range_fwd:
                    self._ramp_aux_to(aux_volt)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                
                # Backward sweep
                for aux_volt in aux_range_bwd:
                    self._ramp_aux_to(aux_volt)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return

            # --- HYSTERESIS MODE ---
            elif self.scan_mode == 'Hysteresis':
                # Origin -> Start
                aux_to_start = self.generate_range(aux_origin, self.aux_start, self.aux_step)
                for aux_volt in aux_to_start:
                    self._ramp_aux_to(aux_volt)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                
                # Start -> End
                aux_start_to_end = self.generate_range(self.aux_start, self.aux_end, self.aux_step)
                for aux_volt in aux_start_to_end[1:]:  # Skip first point (already at start)
                    self._ramp_aux_to(aux_volt)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                
                # End -> Origin
                aux_end_to_origin = self.generate_range(self.aux_end, aux_origin, self.aux_step)
                for aux_volt in aux_end_to_origin[1:]:  # Skip first point (already at end)
                    self._ramp_aux_to(aux_volt)
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


# Procedure registration dictionary
proc_differential_resistance_AUX_map = {
    "Differential Resistance AUX Map": dict(
        cls=Differential_Resistance_AUX_map,
        category=["2D Mapping", "Gate Sweep", "AUX Sweep"],
        description="2D Gate vs AUX map measurement.\n\n"
                    "Gate voltage is stepped (outer loop) and AUX voltage is swept (inner loop).\n\n"
                    "Scan modes (AUX sweep at each gate step):\n"
                    "- Snake: Alternates sweep direction at each gate step\n"
                    "- Forward/Backward: Full forward then backward sweep\n"
                    "- Hysteresis: Origin -> Start -> End -> Origin\n\n"
                    "AUX source selectable from connected lock-ins (SRS860/SRS830/MFLI).\n"
                    "Magnet field can be optionally recorded.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221',
            'aux_source', 'aux_signal',
            'mapping',
            'scan_mode',
            'smu', 'gate_start', 'gate_end', 'gate_step',
            'aux_start', 'aux_end', 'aux_step',
            'gate_delay', 'acq_delay',
        ],
        displays=[
            'Title', 'scan_mode',
            'smu', 'gate_start', 'gate_end',
            'aux_start', 'aux_end',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}
