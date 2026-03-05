"""
Differential Resistance Zurich AUX with Gate Voltage Mapping Measurement.

2D mapping with Gate voltage stepped (outer loop) and AUX voltage swept (inner loop).
Supports Snake, Forward/Backward, and Hysteresis scan modes.
Magnet field can be optionally recorded.
"""

from .base import (
    log, time, math, np,
    Procedure, BooleanParameter, IntegerParameter, FloatParameter, Parameter, Metadata, ListParameter,
    magnet, MFLI_1, MFLI_2, MFLI_3, SRS860, SRS830_1, SRS830_2, Dual_gate, Gate_1, Gate_2,
    read_temperature,
)


class Differential_Resistance_Zurich_AUX_map(Procedure):
    """
    2D mapping measurement with Gate voltage stepped and AUX voltage swept.
    
    The gate voltage is changed in discrete steps (outer loop), and at each
    gate step, the AUX output is swept through its full range (inner loop).
    
    Three scan modes are available for the AUX sweep:
    - Snake: Alternates sweep direction at each gate step
    - Forward/Backward: Full forward then backward sweep at each gate step
    - Hysteresis: Origin → Start → End → Origin at each gate step
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
    use_srs860 = BooleanParameter('Use srs860', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    # --- AUX Configuration (MFLI_1 only) ---
    aux_signal = IntegerParameter('AUX output channel (0-3)', group_by='use_MFLI_1', default=0)
    aux_select = IntegerParameter("AUX signal select (-1=Manual)", group_by='use_MFLI_1', default=-1)
    aux_demod = IntegerParameter("AUX demod select", group_by=['use_MFLI_1', 'aux_select'],
                                 group_condition=[True, lambda v: v == 11 or v == 13], default=0)

    # --- Mapping Configuration ---
    mapping = BooleanParameter('Mapping', default=True)
    
    scan_mode = ListParameter('Scan Mode', default='Snake',
                              choices=['Snake', 'Forward/Backward', 'Hysteresis'],
                              group_by='mapping', group_condition=True)

    # --- Gate Parameters (Stepped - Outer Loop) ---
    smu = ListParameter('Gate SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'],
                        group_by='mapping', group_condition=True, default='Gate_1')
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

    # --- Metadata ---
    MFLI_1_sine_voltage = Metadata("MFLI_1 sine voltage", default=math.nan)
    MFLI_1_frequency = Metadata("MFLI_1 frequency (Hz)", default=math.nan)
    MFLI_2_sine_voltage = Metadata("MFLI_2 sine voltage", default=math.nan)
    MFLI_2_frequency = Metadata("MFLI_2 frequency (Hz)", default=math.nan)
    MFLI_3_sine_voltage = Metadata("MFLI_3 sine voltage", default=math.nan)
    MFLI_3_frequency = Metadata("MFLI_3 frequency (Hz)", default=math.nan)
    srs860_sine_voltage = Metadata("SRS860 sine voltage", default=math.nan)
    srs860_frequency = Metadata("SRS860 frequency (Hz)", default=math.nan)
    srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
    srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
    srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
    srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)

    DATA_COLUMNS = [
        'time(s)',
        '50K_plate(K)', '4K_plate(K)', 'VTI_temp(K)', 'probe_temp(K)',
        'SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)',
        'Gate_1_voltage(V)', 'Gate_1_Leakage(A)', 'Gate_2_voltage(V)', 'Gate_2_Leakage(A)',
        'Lockin_Voltage_SRS860_X(V)', 'Lockin_Voltage_SRS860_Y(V)',
        'AUX_DC_offset(V)',
        'MFLI_Lockin_1_Voltage_X(V)', 'MFLI_Lockin_1_Voltage_Y(V)',
        'MFLI_Lockin_2_Voltage_X(V)', 'MFLI_Lockin_2_Voltage_Y(V)',
        'MFLI_Lockin_3_Voltage_X(V)', 'MFLI_Lockin_3_Voltage_Y(V)',
        'Lockin_Voltage_SRS830_1_X(V)', 'Lockin_Voltage_SRS830_1_Y(V)',
        'Lockin_Voltage_SRS830_2_X(V)', 'Lockin_Voltage_SRS830_2_Y(V)',
        'field(T)',
    ]

    def startup(self):
        """Record instrument metadata at startup."""
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
        """Acquire measurements from all enabled instruments."""
        temperature = read_temperature()
        vals = [time.time() - t0] + list(temperature)

        # Magnet field query
        if self.use_magnet:
            magnet.magnet_field_write_query()

        # Dual gate measurements
        if self.use_dual_gate:
            vals += [Dual_gate.smua.measure__voltage(), Dual_gate.smua.measure__current(),
                     Dual_gate.smub.measure__voltage(), Dual_gate.smub.measure__current()]
        else:
            vals += [math.nan] * 4

        # Keithley gate measurements
        vals += [Gate_1.measure__voltage(), Gate_1.measure__current()] if self.use_keithley_1 else [math.nan] * 2
        vals += [Gate_2.measure__voltage(), Gate_2.measure__current()] if self.use_keithley_2 else [math.nan] * 2

        # Lock-in measurements
        if self.use_srs860:
            x, y = SRS860.snap("X", "Y")
            vals += [x, y]
        else:
            vals += [math.nan, math.nan]

        if self.use_MFLI_1:
            auxout = MFLI_1.get_auxout(self.aux_signal)
            vals += [auxout]
            vals += list(MFLI_1.read_demod())
        else:
            vals += [math.nan] * 3

        for use, inst in [(self.use_MFLI_2, MFLI_2), (self.use_MFLI_3, MFLI_3)]:
            vals += list(inst.read_demod()) if use else [math.nan] * 2

        for use, inst in [(self.use_srs830_1, SRS830_1), (self.use_srs830_2, SRS830_2)]:
            vals += list(inst.snap("X", "Y")) if use else [math.nan] * 2

        # Magnet field reading
        vals.append(magnet.magnet_field_read_response() if self.use_magnet else math.nan)
        return vals

    def smu_choice(self, name):
        """Return the SMU object based on name selection."""
        if name == 'Gate_1':
            return Gate_1
        if name == 'Gate_2':
            return Gate_2
        if name == 'smua':
            return Dual_gate.smua
        if name == 'smub':
            return Dual_gate.smub
        raise ValueError(f"Unknown SMU: {name}")

    def smu_output(self, Gate, name):
        """Enable SMU output with appropriate configuration."""
        if not Gate.is_output_on():
            log.info(f"{name} output was OFF. Turning it ON.")
            if name in ['Gate_1', 'Gate_2']:
                Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
            else:
                Gate.configure_voltage_source(voltage=0, current_limit=110e-9)
            Gate.output_on()

    def generate_range(self, start, end, step_units):
        """Generate a voltage range array from start to end with given step size.
        
        Args:
            start: Start voltage in Volts
            end: End voltage in Volts  
            step_units: Step size in millivolts (mV)
            
        Returns:
            numpy array of voltage values
        """
        step = abs(step_units / 1000.0)
        if step == 0:
            step = 0.001
        num_points = int(abs(end - start) / step) + 1
        return np.linspace(start, end, num_points)

    def ramp_gate_with_abort(self, gate, target_voltage, step_size_mv=2, delay=0.1):
        """Ramp gate voltage to target using while loop for abort capability.
        
        This method ramps the gate voltage in small steps, checking for
        abort requests between each step. No measurements are emitted.
        
        Args:
            gate: The gate SMU object
            target_voltage: Target voltage in Volts
            step_size_mv: Step size in millivolts (default: 2 mV)
            delay: Delay between steps in seconds (default: 0.1)
            
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
            
            gate.ramp_voltage(next_voltage, steps=1, delay=0.01)
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
        MFLI_1.set_auxout(self.aux_signal, self.aux_select, self.aux_demod)
        aux_origin = MFLI_1.get_auxout(self.aux_signal)
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
        MFLI_1.aux_ramping(self.aux_signal, self.aux_start, step_size=2, delay=0.1)
        if self.should_stop():
            log.warning("User aborted during initial AUX ramping")
            return

        # --- Main Measurement Loop ---
        iteration = 1
        
        for i, gate_volt in enumerate(gate_range):
            # Move to next gate position (skip first since we're already there)
            if i > 0:
                gate.ramp_voltage(gate_volt, steps=5, delay=0.01)
                time.sleep(self.gate_delay)
            
            if self.should_stop():
                log.warning("User stopped measurement")
                return

            # --- SNAKE MODE ---
            if self.scan_mode == 'Snake':
                # Alternate AUX sweep direction based on gate step index
                current_aux_range = aux_range_fwd if i % 2 == 0 else aux_range_bwd
                
                for aux_volt in current_aux_range:
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
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
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
                    time.sleep(self.acq_delay)
                    
                    self.emit('results', dict(zip(self.DATA_COLUMNS, self.getmeas(time_0))))
                    self.emit('progress', 100 * iteration / total_points)
                    iteration += 1
                    
                    if self.should_stop():
                        log.warning("User stopped measurement")
                        return
                
                # Backward sweep
                for aux_volt in aux_range_bwd:
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
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
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
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
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
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
                    MFLI_1.aux_ramp(self.aux_signal, aux_volt, steps=3, delay=0.05)
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
proc_differential_resistance_Zurich_AUX_map = {
    "Differential Resistance Zurich AUX Map": dict(
        cls=Differential_Resistance_Zurich_AUX_map,
        category=["2D Mapping", "Gate Sweep", "AUX Sweep"],
        description="2D Gate vs AUX map measurement.\n\n"
                    "Gate voltage is stepped (outer loop) and AUX voltage is swept (inner loop).\n\n"
                    "Scan modes (AUX sweep at each gate step):\n"
                    "• Snake - Alternates sweep direction at each gate step\n"
                    "• Forward/Backward - Full forward then backward sweep\n"
                    "• Hysteresis - Origin → Start → End → Origin\n\n"
                    "AUX output is controlled via MFLI_1.\n"
                    "Magnet field can be optionally recorded.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860', 'use_srs830_1', 'use_srs830_2',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'aux_signal', 'aux_select', 'aux_demod',
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
        x='time(s)',
        y=['AUX_DC_offset(V)', 'Gate_1_voltage(V)'],
    ),
}