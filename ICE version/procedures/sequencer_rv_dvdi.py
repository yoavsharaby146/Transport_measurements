"""
Sequencer for RV and dV/dI measurements.
"""

from .base import *
from . import base
from .differential_resistance_aux import _make_aux_source_parameter, _AUX_SOURCE_NAMES


class RV_dV_dI_sequencer_measurement(ICEProcedure):
    Title = Parameter('Measurement type', default='RV and dV/dI in sequence')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')
    Type = ListParameter('Measurement Type', choices=['RV', 'dV_dI'], default='RV')
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              group_by='Type', group_condition='dV_dI', default='Sweep to setpoint')
    aux_source = _make_aux_source_parameter()
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)', group_by='Type',
                                group_condition='dV_dI', default=0)
    aux_signal = ListParameter('Aux output 1-4:', choices=[1, 2, 3, 4], default=1)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='Type',
                              group_condition='dV_dI', default=2)
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
    smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                   group_by='Type', group_condition='RV')

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh SMU + AUX-source dropdown choices to connected instruments."""
        cls.smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                           group_by='Type', group_condition='RV')
        cls.aux_source = _make_aux_source_parameter()
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
    use_k6221 = BooleanParameter('Use k6221 (record amplitude column)', group_by='devices', default=False)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

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

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        # Mid column: chosen source AUX value (only meaningful in dV/dI mode)
        aux = math.nan
        if self.Type == 'dV_dI' and self.aux_source in _AUX_SOURCE_NAMES:
            try:
                aux = self._read_aux()
            except Exception as e:
                log.warning("AUX read failed: %s", e)
        return self._read_standard(t0, mid_extras=[aux])

    def run_RV(self):
        time_0 = time.time()
        log.info(f"starting voltage sweep to {self.Target_voltage} V")
        Gate = self.smu_choice(self.smu)
        if not Gate.is_output_on():
            self.smu_output(Gate, self.smu)
        start_volts = Gate.measure__voltage()
        gate_ranges = self.generate_range(start_volts, self.Target_voltage, self.step_size)
        log.info(f"Sweeping {self.smu} from {start_volts:.4f}V to {self.Target_voltage:.4f}V")
        iteration = 1
        for gate_volt in gate_ranges:
            Gate.ramp_voltage(gate_volt, 2, 0.001)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(gate_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                return
        if self.Target_voltage == 0:
            log.info(f"Target reached 0V. Turning {self.smu} OFF.")
            Gate.output_off()

    def run_dV_dI(self):
        time_0 = time.time()

        inst = self._aux_instrument()  # fail fast if the chosen source vanished
        if self.aux_source.startswith('MFLI'):
            # manual mode (-1) so the offset ramp appears on the BNC
            inst.set_auxout(signal=self.aux_signal - 1, select=-1)
        aux_origin = self._read_aux()
        target_aux = self.aux_Target
        log.info(f"Starting dV/dI {self.scan_mode} on {self.aux_source} "
                 f"AUX{self.aux_signal}. Start={aux_origin:.4f}V, Target={target_aux:.4f}V")
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

    def execute(self):
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'dV_dI':
            self.run_dV_dI()

    def shutdown(self):
        log.info("Finished measuring")


proc_RV_dV_dI_sequencer = {
    "RV dV_dI sequencer measurement": dict(
        cls=RV_dV_dI_sequencer_measurement,
        category=["Differential Resistance", "Gate Sweep"],
        description="Sequencer for RV and dV/dI measurements.",
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'acq_delay', 'Type', 'scan_mode',
                'Target_voltage', 'step_size', 'smu', 'devices', 'use_magnet', 'use_MFLI_1',
                'aux_source', 'aux_Target', 'aux_step', 'aux_signal',
                'use_MFLI_2', 'use_MFLI_3', 'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221'],
        displays=['Type', 'Target_voltage', 'scan_mode', 'aux_source', 'aux_Target'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu', 'scan_mode',
                          'aux_source', 'aux_Target', 'aux_step'],
    ),
}
