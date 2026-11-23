"""
Differential Conductance measurement — unified (ICE Version).

dI/dV for tunnel junctions, voltage-biased. One procedure replaces the old
separate "Differential Conductance SRS860" / "Differential Conductance
Zurich" modules: the excitation lock-in is picked from the connected
SRS860 / MFLI units in the 'Excitation lock-in' dropdown.

The chosen lock-in sources the AC excitation on its sine output (set
amplitude/frequency on the instrument — recorded as metadata only) and the
DC bias is swept on the SAME sine output's DC offset (SRS860: set_dc_offset,
MFLI: dc_offset property). The sample current is measured with the lock-ins
ticked in the Devices group (current columns). The differential conductance
is computed live as I_XY / V_ac from the 'Measuring lock-in' and recorded in
Differential_Conductance_X/Y(S) — tick that lock-in too or those columns
stay NaN.

The 2D variant (gate stepped outer, DC offset swept inner) lives in
differential_conductance_map.py.
"""

from .base import *
from . import base


# Lock-ins usable as excitation source (sine + DC offset), display order.
_EXC_SOURCE_NAMES = ['SRS860_1', 'SRS860_2', 'MFLI_1', 'MFLI_2', 'MFLI_3']

# All lock-ins in _read_lockin_values order (must match base.py).
_ALL_LOCKIN_NAMES = ['SRS860_1', 'SRS860_2', 'MFLI_1', 'MFLI_2', 'MFLI_3',
                     'SRS830_1', 'SRS830_2', 'SRS830_3']


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


class Differential_Conductance(ICEProcedure):
    """dI/dV: AC excitation from an SRS860 / MFLI sine output, DC bias swept
    on the same output's DC offset."""

    # --- Parameters ---
    Title = Parameter('dI/dV measurement', default='dI/dV')
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

    # --- Excitation + Sweep Configuration ---
    exc_source = ListParameter('Excitation lock-in', choices=['(none connected)'],
                               default='(none connected)')
    meas_lockin = ListParameter('Measuring lock-in (dI/dV input)', choices=['(none connected)'],
                                default='(none connected)')
    scan_mode = ListParameter('Scan Mode', default='Sweep and Return',
                              choices=['Sweep to Setpoint', 'Sweep and Return'])
    dc_offset_setpoint = FloatParameter('Target Setpoint (V)', default=0.1)
    dc_offset_step = FloatParameter('DC Step Size (mV)', default=1)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.3)

    # --- Dynamic column recipe ---
    _MID_COLUMNS = ['DC_offset(V)', 'AC_voltage_RMS(V)',
                    'Differential_Conductance_X(S)', 'Differential_Conductance_Y(S)']
    _LOCKIN_COL_TYPE = 'current'

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh excitation/measuring dropdown choices to connected lock-ins."""
        exc = _connected_exc_sources() or ['(none connected)']
        cls.exc_source = ListParameter('Excitation lock-in', choices=exc, default=exc[0])
        meas = [n for n in _ALL_LOCKIN_NAMES
                if base._is_connected(getattr(base, n, 0))] or ['(none connected)']
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

    def _set_dc(self, value):
        """Set the sine-output DC offset of the excitation lock-in."""
        inst = self._exc_instrument()
        if self.exc_source.startswith('MFLI'):
            inst.dc_offset = float(value)
        else:  # SRS860
            inst.set_dc_offset(float(value))

    def _read_exc(self, attr_srs, attr_mfli, attempts=3, delay=0.5):
        """Read a property of the excitation lock-in (retries VISA hiccups).

        attr_srs / attr_mfli: attribute name for SRS860 / MFLI respectively.
        """
        inst = self._exc_instrument()
        attr = attr_mfli if self.exc_source.startswith('MFLI') else attr_srs
        last_err = None
        for i in range(attempts):
            try:
                return float(getattr(inst, attr))
            except Exception as e:
                last_err = e
                log.warning("%s %s read failed (attempt %d/%d): %s",
                            self.exc_source, attr, i + 1, attempts, e)
                time.sleep(delay)
        raise last_err

    def _read_dc(self):
        """Read back the DC offset of the excitation lock-in."""
        return self._read_exc('dc_offset', 'dc_offset')

    def _read_ac(self):
        """Read back the excitation RMS voltage (sine amplitude)."""
        return self._read_exc('sine_voltage', 'sine_amplitude')

    # --- Procedure -----------------------------------------------------

    def startup(self):
        self._capture_metadata()
        log.info("dI/dV on %s: AC excitation pre-configured on the instrument "
                 "(amplitude/frequency recorded as metadata); DC bias swept on "
                 "the sine output DC offset", self.exc_source)

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        # Lock-ins read once: reused for the standard columns and the live
        # conductance computation (G = I_XY / V_ac).
        lockvals = self._read_lockin_values()
        dc = self._read_dc()
        vac = self._read_ac()
        gx = gy = math.nan
        idx = _lockin_x_index(self.meas_lockin)
        if idx is not None and vac and vac > 0:
            gx = lockvals[idx] / vac
            gy = lockvals[idx + 1] / vac

        vals = [time.time() - t0] + list(read_temperature())
        vals += self._read_smu_values()
        vals += [dc, vac, gx, gy]
        vals += lockvals
        vals += self._read_magnet()
        return vals

    def execute(self):
        self._exc_instrument()  # fail fast if the source vanished
        time_0 = time.time()

        start_v = self._read_dc()
        target_v = self.dc_offset_setpoint
        log.info(f"Starting dI/dV {self.scan_mode} on {self.exc_source}. "
                 f"Start={start_v:.4f}V, Target={target_v:.4f}V")

        range_to_target = self.generate_range(start_v, target_v, self.dc_offset_step)
        range_return = self.generate_range(target_v, start_v, self.dc_offset_step)

        total_points = len(range_to_target)
        if self.scan_mode == 'Sweep and Return':
            total_points += len(range_return)

        point_counter = 0

        log.info("Sweeping to Setpoint...")
        for v in range_to_target:
            self._set_dc(v)
            time.sleep(self.acq_delay)

            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

            point_counter += 1
            self.emit('progress', 100 * point_counter / total_points)
            if self.should_stop():
                log.warning("Measurement stopped by user")
                return

        if self.scan_mode == 'Sweep and Return':
            log.info("Returning to Origin...")
            for v in range_return:
                self._set_dc(v)
                time.sleep(self.acq_delay)

                data = self.getmeas(time_0)
                self.emit('results', dict(zip(self.DATA_COLUMNS, data)))

                point_counter += 1
                self.emit('progress', 100 * point_counter / total_points)
                if self.should_stop():
                    log.warning("Measurement stopped by user")
                    return

    def shutdown(self):
        log.info("Finished measuring")


proc_differential_conductance = {
    "Differential Conductance (unified)": dict(
        cls=Differential_Conductance,
        category="Tunneling junction",
        description="dI/dV sweep, voltage-biased: AC excitation from the chosen "
                    "excitation lock-in's sine output (any connected SRS860 / MFLI; "
                    "set amplitude/frequency on the instrument), DC bias swept on "
                    "the same output's DC offset, starting from the CURRENT offset.\n"
                    "Replaces the old separate SRS860 and Zurich (MFLI) procedures.\n"
                    "Current is measured with the lock-ins ticked in the Devices "
                    "group. Differential_Conductance_X/Y(S) = I_XY / V_ac is "
                    "computed live from the 'Measuring lock-in' — tick that lock-in "
                    "too or the conductance columns stay NaN.\n"
                    "1. Sweep to Setpoint: [Current] -> [Target]. Leaves voltage at Target.\n"
                    "2. Sweep and Return: [Current] -> [Target] -> [Current].",
        requires=_requires_exc_source,
        inputs=[
            'Title', 'Contacts', 'Gate_contacts',
            'exc_source', 'meas_lockin',
            'scan_mode', 'dc_offset_setpoint', 'dc_offset_step',
            'acq_delay',
            'devices',
            'use_magnet',
            'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
            'use_srs860_1', 'use_srs860_2',
            'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
            'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
            'use_yoko_gs200_1', 'use_yoko_gs200_2',
            'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221',
        ],
        displays=['Title', 'scan_mode', 'exc_source', 'meas_lockin',
                  'dc_offset_setpoint', 'dc_offset_step'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}

