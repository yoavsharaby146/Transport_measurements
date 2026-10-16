"""
Differential Resistance AUX measurement — unified.

dV/dI sweep using the AUX output of any connected lock-in (SRS860, SRS830
or MFLI). The source is picked from the AUX-source dropdown which lists
only instruments connected at launch — this replaces the old separate
"Differential Resistance SRS860" and "Differential Resistance Zurich"
procedures.

MFLI notes: aux channel is 0-based internally (dropdown/slot numbers are
1-based BNC numbers, converted here); the output is set to manual mode
(select = -1) at startup so the offset ramp appears on the BNC.
"""

from .base import *
from . import base


# Lock-ins that can source an AUX output voltage, in display order.
_AUX_SOURCE_NAMES = ['SRS860_1', 'SRS860_2',
                     'SRS830_1', 'SRS830_2', 'SRS830_3',
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


class Differential_Resistance_AUX(ICEProcedure):
    # --- Parameters ---
    Title = Parameter('dV/dI sweep measurement', default='dV/dI sweep measurement')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Hardware Selection ---
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

    # --- Sweep Parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              default='Sweep to setpoint')
    aux_source = _make_aux_source_parameter()
    aux_Target = FloatParameter('Auxiliary DC Bias Target  (V)', default=0)
    aux_signal = ListParameter('Aux output 1-4:', choices=[1, 2, 3, 4], default=1)
    aux_step = FloatParameter('Auxiliary step (mV)', default=2)
    acq_delay = FloatParameter('Acquisition  Delay (s)', default=0.1)

    # --- Dynamic column recipe ---
    _MID_COLUMNS = ['AUX_DC_offset(V)']
    _LOCKIN_COL_TYPE = 'voltage'

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh AUX-source dropdown choices to the connected lock-ins."""
        cls.aux_source = _make_aux_source_parameter()

    # --- AUX source helpers -------------------------------------------

    def _aux_instrument(self):
        """Resolve the chosen AUX source name to a connected instrument."""
        inst = getattr(base, self.aux_source, 0)
        if not base._is_connected(inst):
            raise ValueError(
                f"{self.aux_source} selected as AUX source but is not "
                f"connected (check the pre-launch dialog)")
        return inst

    def _read_aux(self):
        """Read back the programmed AUX output voltage."""
        inst = self._aux_instrument()
        if self.aux_source.startswith('MFLI'):
            return float(inst.get_auxout(self.aux_signal - 1))  # MFLI: 0-based
        return float(getattr(inst, f'dac{self.aux_signal}'))    # SRS: 1-based

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

    # --- Procedure -----------------------------------------------------

    def startup(self):
        self._capture_metadata()
        # MFLI AUX output must be in manual mode for the offset ramp to
        # appear on the BNC. -1 == AUX_MANUAL. Harmless no-op for SRS.
        if self.aux_source.startswith('MFLI'):
            self._aux_instrument().set_auxout(signal=self.aux_signal - 1, select=-1)

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        # Mid column: chosen source AUX value
        aux = self._read_aux()
        return self._read_standard(t0, mid_extras=[aux])

    def execute(self):
        self._aux_instrument()  # fail fast if the source vanished
        time_0 = time.time()

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

    def shutdown(self):
        log.info("Finished measuring")


proc_differential_resistance_AUX = {
    "Differential Resistance AUX": dict(
        cls=Differential_Resistance_AUX,
        category="Differential Resistance",
        description="dV/dI Sweep using the AUX output of any connected lock-in "
                    "(SRS860 / SRS830 / MFLI — connected units only, chosen from "
                    "the 'AUX source' dropdown).\n"
                    "Replaces the old separate SRS860 and Zurich (MFLI) procedures.\n"
                    "1. Sweep to Setpoint: Measures from [Origin] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: Measures from [Origin] -> [Target] -> [Origin]. Returns voltage to start.",
        inputs=[
            'Title', 'Resistor', 'Contacts', 'Gate_contacts',
            'acq_delay',
            'devices',
            'use_magnet',
            'aux_source', 'aux_Target', 'aux_step', 'aux_signal',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2', 'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221',
            'scan_mode',
        ],
        displays=[
            'Title', 'scan_mode', 'aux_source', 'aux_Target'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}

