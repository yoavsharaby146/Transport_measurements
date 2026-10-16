"""
Resistance vs. lock-in AUX output voltage measurement procedure.

Sweeps the AUX output (DAC) of a chosen lock-in — SRS830, SRS860 or MFLI —
while recording the standard readings (other lock-ins, SMUs, ...).

The AUX source is picked from the lock-ins actually connected at launch;
the choices list is rebuilt whenever instruments are (re)bound, mirroring
the dynamic DATA_COLUMNS mechanism in base.py.
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


class Resistance_aux_voltage_measurement(GenericProcedure):

    Title = Parameter('Aux sweep', default='R_AUX')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')

    acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
    target_AUX_voltage = FloatParameter('Target Aux Voltage(V)', default=0)
    step_size = FloatParameter('Step size(mV)', default=1)
    aux = IntegerParameter('Aux output 1-4:', default=1)
    aux_source = _make_aux_source_parameter()

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

    _MID_COLUMNS = ['Auxiliary_Voltage(V)']

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh aux_source choices to the connected lock-ins.

        Called by base._rebuild_procedure_columns() after instruments
        are (re)bound, so the dropdown only offers usable sources.
        """
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
            return float(inst.get_auxout(self.aux - 1))  # MFLI: 0-based
        return float(getattr(inst, f'dac{self.aux}'))    # SRS: 1-based

    def _ramp_aux_to(self, target):
        """Ramp the AUX output to target (short ramp, called per sweep point)."""
        inst = self._aux_instrument()
        if self.aux_source.startswith('MFLI'):
            inst.aux_ramp(signal=self.aux - 1, aux=float(target),
                          steps=5, delay=0.01)
        elif self.aux_source.startswith('SRS860'):
            inst.ramp_aux(self.aux, float(target), 5, 0.01)
        else:
            # SRS830 driver has no ramp_aux: software ramp via the dac property
            start = self._read_aux()
            for v in np.linspace(start, float(target), 6)[1:]:
                setattr(inst, f'dac{self.aux}', float(v))
                time.sleep(0.01)

    # --- Procedure -----------------------------------------------------

    def startup(self):
        self._capture_metadata()
        # MFLI AUX output must be in manual mode for the offset ramp to
        # appear on the BNC. -1 == AUX_MANUAL. Harmless no-op for SRS.
        if self.aux_source.startswith('MFLI'):
            self._aux_instrument().set_auxout(signal=self.aux - 1, select=-1)

    def getmeas(self, t0):
        return self._read_standard(t0, [self._read_aux()])

    def execute(self):
        self._aux_instrument()  # fail fast if the source vanished
        log.info("starting aux voltage sweep to %s V on %s AUX%d",
                 self.target_AUX_voltage, self.aux_source, self.aux)
        time_0 = time.time()

        start_aux = self._read_aux()
        step_v = self.step_size / 1000.0
        if step_v == 0:
            step_v = 0.001
        num_points = int(abs(self.target_AUX_voltage - start_aux) / step_v) + 1
        aux_ranges = np.linspace(start_aux, self.target_AUX_voltage, num_points)

        log.info(f"Sweeping {self.aux_source} AUX{self.aux} from "
                 f"{start_aux:.4f}V to {self.target_AUX_voltage:.4f}V")

        iteration = 1
        for aux_volt in aux_ranges:
            self._ramp_aux_to(aux_volt)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(aux_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Measurement stopped")
                break
        log.info(f"AUX voltage reached {self._read_aux():.4f} V")

    def shutdown(self):
        log.info("Aux sweep measurement finished")


proc_resistance_aux = {
"Resistance aux voltage sweep measurement": dict(
        cls=Resistance_aux_voltage_measurement,
        category="Aux Sweep",
        description="Sweeps the AUX output voltage of a chosen lock-in "
                    "(SRS830 / SRS860 / MFLI — connected units only) while "
                    "measuring Resistance (via the other lock-ins).\n"
                    "Mirrors the Dilution Version R_AUX measurement.",
        inputs=[
                'Title', 'Resistor', 'Contacts',
                'devices',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2',
                'use_srs860_3', 'use_srs860_4',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2',
                'use_k6221',
                'aux_source', 'aux', 'target_AUX_voltage', 'step_size',
                'acq_delay',
        ],
        displays=[
            'Title',
            'target_AUX_voltage', 'step_size'],
        x=['time(s)'],
        y=['time(s)', 'time(s)']
    ),
}
