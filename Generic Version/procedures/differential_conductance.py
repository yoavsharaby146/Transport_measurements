"""
Differential conductance (dI/dV) — voltage-biased, lock-in only
(Generic Version).

One unified procedure: the excitation lock-in is picked from the connected
SRS860 and MFLI units in the 'Excitation lock-in' dropdown. It sources the
AC voltage excitation (sine output, amplitude + frequency set here) and the
DC bias is swept on an AUX output of the same unit. The sample current is
measured with any ticked lock-in (current preamp readout — lock-in current
columns). The differential conductance is computed live as I_XY / V_ac and
recorded in Differential_Conductance_X/Y(S); tick the measuring lock-in in
the Devices group or those columns stay NaN.

The 2D variant (gate stepped outer, AUX bias swept inner) lives in
differential_conductance_gate_map.py.

Distinct from the dV/dI family (differential_resistance_*.py), which is
current-biased (AC from a lock-in into a current excitation) and sweeps DC
on the K6221 or a lock-in AUX.

The procedure leaves all sources running at the end (lab preference).
"""

from .base import *
from . import base


# Lock-ins usable as conductance measurement input, in read order
# (must match _build_lockin_columns / _read_lockin_values in base.py).
_ALL_LOCKIN_NAMES = ['SRS830_1', 'SRS830_2', 'SRS830_3',
                     'SRS860_1', 'SRS860_2', 'SRS860_3', 'SRS860_4',
                     'MFLI_1', 'MFLI_2', 'MFLI_3']

# Lock-ins usable as excitation source (sine + AUX output), display order.
_EXC_SOURCE_NAMES = ['SRS860_1', 'SRS860_2', 'SRS860_3', 'SRS860_4',
                     'MFLI_1', 'MFLI_2', 'MFLI_3']


def _connected_lockins():
    """Names of connected lock-ins, in _read_lockin_values order."""
    return [n for n in _ALL_LOCKIN_NAMES
            if base._is_connected(getattr(base, n, 0))]


def _connected_exc_sources():
    """Names of connected lock-ins usable as excitation (SRS860 / MFLI)."""
    return [n for n in _EXC_SOURCE_NAMES
            if base._is_connected(getattr(base, n, 0))]


def _requires_exc_source(cfg):
    return any(base._is_connected(getattr(cfg, n, 0))
               for n in _EXC_SOURCE_NAMES)


def _lockin_x_index(name):
    """Index of the X reading of `name` inside _read_lockin_values() output."""
    idx = 0
    for n in _ALL_LOCKIN_NAMES:
        if base._is_connected(getattr(base, n, 0)):
            if n == name:
                return idx
            idx += 2
    return None


class Differential_Conductance(GenericProcedure):
    """dI/dV: AC voltage excitation from an SRS860 or MFLI sine output,
    DC bias swept on an AUX output of the same unit."""

    Title = Parameter('dI/dV sweep measurement', default='dI/dV')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Source_contacts = Parameter('Source contacts', default='insert source contacts')


    # --- Excitation + sweep parameters ---
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              default='Sweep to setpoint')
    exc_source = ListParameter('Excitation lock-in', choices=['(none connected)'],
                               default='(none connected)')
    meas_lockin = ListParameter('Measuring lock-in (dI/dV input)', choices=['(none connected)'],
                                default='(none connected)')
    ac_voltage = FloatParameter('AC excitation RMS (V)', default=1e-3)
    ac_frequency = FloatParameter('AC frequency (Hz)', default=77)
    aux_signal = ListParameter('Aux output 1-4:', choices=[1, 2, 3, 4], default=1)
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)', default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', default=2)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.1)

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

    _LOCKIN_COL_TYPE = 'current'
    _MID_COLUMNS = ['AUX_DC_offset(V)', 'AC_voltage_RMS(V)',
                    'Differential_Conductance_X(S)', 'Differential_Conductance_Y(S)']

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh dropdown choices to the connected lock-ins."""
        exc = _connected_exc_sources() or ['(none connected)']
        cls.exc_source = ListParameter('Excitation lock-in', choices=exc, default=exc[0])
        meas = _connected_lockins() or ['(none connected)']
        cls.meas_lockin = ListParameter('Measuring lock-in (dI/dV input)',
                                        choices=meas, default=meas[0])

    # --- Excitation-lock-in helpers ---

    def _exc_instrument(self):
        inst = getattr(base, self.exc_source, 0)
        if not base._is_connected(inst):
            raise ValueError(
                f"{self.exc_source} selected as excitation lock-in but is not "
                f"connected (check the pre-launch dialog)")
        return inst

    def _setup_ac(self):
        """Set sine amplitude + frequency on the excitation lock-in."""
        inst = self._exc_instrument()
        if self.exc_source.startswith('MFLI'):
            inst.sine_amplitude = float(self.ac_voltage)
            inst.frequency = float(self.ac_frequency)
            inst.enable_amplitude()
            inst.turn_voltage(True)
        else:  # SRS860
            inst.sine_voltage = float(self.ac_voltage)
            inst.frequency = float(self.ac_frequency)

    def _read_ac(self, attempts=3, delay=0.5):
        """Read back the excitation RMS voltage (retries VISA hiccups)."""
        inst = self._exc_instrument()
        reader = (lambda: inst.sine_amplitude) if self.exc_source.startswith('MFLI') \
            else (lambda: inst.sine_voltage)
        last_err = None
        for i in range(attempts):
            try:
                return float(reader())
            except Exception as e:
                last_err = e
                log.warning("%s sine read failed (attempt %d/%d): %s",
                            self.exc_source, i + 1, attempts, e)
                time.sleep(delay)
        raise last_err

    # --- AUX helpers (same as differential_resistance_aux) ---

    def _read_aux(self, attempts=3, delay=0.5):
        """Read back the programmed AUX output voltage (retries VISA hiccups)."""
        inst = self._exc_instrument()
        if self.exc_source.startswith('MFLI'):
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
                            self.exc_source, i + 1, attempts, e)
                time.sleep(delay)
        raise last_err

    def _ramp_aux_to(self, target):
        """Ramp the AUX output to target (short ramp, called per sweep point)."""
        inst = self._exc_instrument()
        if self.exc_source.startswith('MFLI'):
            inst.aux_ramp(signal=self.aux_signal - 1, aux=float(target),
                          steps=5, delay=0.01)
        else:
            inst.ramp_aux(self.aux_signal, float(target), 5, 0.01)

    # --- Procedure -----------------------------------------------------

    def startup(self):
        self._capture_metadata()
        self._setup_ac()
        # MFLI AUX output must be in manual mode for the offset ramp to
        # appear on the BNC. -1 == AUX_MANUAL. Harmless no-op for SRS.
        if self.exc_source.startswith('MFLI'):
            self._exc_instrument().set_auxout(signal=self.aux_signal - 1, select=-1)
        log.info("dI/dV: AC voltage %.4g V RMS @ %g Hz from %s, DC bias on "
                 "AUX%d — tick the measuring lock-in in Devices",
                 float(self.ac_voltage), float(self.ac_frequency),
                 self.exc_source, int(self.aux_signal))

    def getmeas(self, t0):
        # Lock-ins read once: reused for both the standard columns and the
        # live conductance computation (G = I_XY / V_ac).
        lockvals = self._read_lockin_values()
        gx = gy = math.nan
        vac = self._read_ac()
        idx = _lockin_x_index(self.meas_lockin)
        if idx is not None and vac and vac > 0:
            gx = lockvals[idx] / vac
            gy = lockvals[idx + 1] / vac

        vals = [time.time() - t0] + list(read_temperature())
        vals += self._read_smu_values()
        vals += [self._read_aux(), vac, gx, gy]
        vals += lockvals
        vals += self._read_magnet()
        if len(vals) != len(self.DATA_COLUMNS):
            raise RuntimeError(
                f"Column misalignment: {len(vals)} values but "
                f"{len(self.DATA_COLUMNS)} columns. Your deployed files are "
                f"out of sync - copy ALL files of the Generic Version folder "
                f"from the repository (columns and readers must be the same "
                f"revision).")
        return vals

    def execute(self):
        self._exc_instrument()  # fail fast if the source vanished
        time_0 = time.time()

        aux_origin = self._read_aux()
        target_aux = self.aux_Target
        log.info(f"Starting dI/dV {self.scan_mode} on {self.exc_source} "
                 f"AUX{self.aux_signal}. Start={aux_origin:.4f}V, "
                 f"Target={target_aux:.4f}V")

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
        # Sources intentionally left running (AC excitation + AUX bias stay
        # as they are).
        log.info("dI/dV conductance measurement finished (sources left on)")


_COMMON_INPUTS = [
    'Title', 'Resistor', 'Contacts', 'Source_contacts',
    'scan_mode', 'acq_delay',
    'exc_source', 'meas_lockin', 'ac_voltage', 'ac_frequency',
    'aux_signal', 'aux_Target', 'aux_step',
    'devices',
    'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
    'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
    'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
    'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
    'use_yoko_gs200_1', 'use_yoko_gs200_2',
    'use_yoko7651_1', 'use_yoko7651_2',
]

_COMMON_DESCRIPTION = (
    "Voltage-biased differential conductance (dI/dV): AC voltage excitation "
    "from the excitation lock-in's sine output (any connected SRS860 / MFLI, "
    "chosen from the 'Excitation lock-in' dropdown; amplitude + frequency "
    "set by this procedure), DC bias swept on an AUX output of the same unit.\n"
    "Current is measured with the lock-ins ticked in the Devices group "
    "(current columns). Differential_Conductance_X/Y(S) = I_XY / V_ac is "
    "computed live from the 'Measuring lock-in' — tick that lock-in too or "
    "the conductance columns stay NaN.\n"
    "Sweep to Setpoint: Origin -> Target (voltage left at Target).\n"
    "Sweep and Return: Origin -> Target -> Origin.\n"
    "Sources are NOT turned off at the end."
)

proc_diff_conductance = {
    "Differential Conductance (AC + AUX bias)": dict(
        cls=Differential_Conductance,
        category="Differential Conductance",
        description=_COMMON_DESCRIPTION,
        requires=_requires_exc_source,
        inputs=_COMMON_INPUTS,
        displays=[
            'Title', 'scan_mode', 'exc_source', 'meas_lockin',
            'ac_voltage', 'aux_Target',
        ],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}



