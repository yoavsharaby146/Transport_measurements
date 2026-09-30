"""
Base class for Dilution procedures with dynamic instrument handling.

DATA_COLUMNS are built from the instruments that are actually connected
(see instruments_config), and getmeas() reads exactly those instruments —
disconnected devices are skipped entirely (no column, no read).

Column layout (fixed order, matching getmeas):
    time | temps (dilution) | SMUs (dual, gate1, gate2) | mid extras
    | lock-ins (860_1, 860_2, 830_1, 830_2, 830_3) | Bx,By,Bz (dilution)
"""

import time
import math
import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.experiment import Procedure

import instruments_config as _cfg

_PROCEDURE_SUBCLASSES = []


def _is_connected(inst):
    return inst not in (None, 0)


# ---------------- Dynamic column builders ----------------

def _build_temp_columns(record_magnet_temp=False):
    if not _is_connected(_cfg.Dilution):
        return []
    cols = ['Mixing_chanber(K)']
    if record_magnet_temp:
        cols.append('Magnet Temperature(K)')
    return cols


def _build_smu_columns():
    cols = []
    if _is_connected(_cfg.Dual_gate):
        cols += ['SMUa(V)', 'SMUa_Leakage(A)', 'SMUb(V)', 'SMUb_Leakage(A)']
    if _is_connected(_cfg.Gate_1):
        cols += ['Gate_1_voltage(V)', 'Gate_1_Leakage(A)']
    if _is_connected(_cfg.Gate_2):
        cols += ['Gate_2_voltage(V)', 'Gate_2_Leakage(A)']
    return cols


def _build_lockin_columns():
    """Lock-in columns for connected instruments, in fixed read order."""
    cols = []
    for inst, name in ((_cfg.SRS860_1, 'SRS860_1'),
                       (_cfg.SRS860_2, 'SRS860_2'),
                       (_cfg.SRS830_1, 'SRS830_1'),
                       (_cfg.SRS830_2, 'SRS830_2'),
                       (_cfg.SRS830_3, 'SRS830_3')):
        if _is_connected(inst):
            cols += ['Lockin_Voltage_%s_X(V)' % name,
                     'Lockin_Voltage_%s_Y(V)' % name]
    return cols


def _build_magnet_columns():
    return ['B_x (T)', 'B_y (T)', 'B_z (T)'] \
        if (_is_connected(_cfg.Dilution) and _cfg.MAGNET_ENABLED) else []


def build_columns(mid_columns=(), record_magnet_temp=False):
    return (['time(s)'] + _build_temp_columns(record_magnet_temp) +
            _build_smu_columns() + list(mid_columns) +
            _build_lockin_columns() + _build_magnet_columns())


def rebuild_all():
    """Rebuild DATA_COLUMNS on every registered DilutionProcedure subclass.

    Called by instruments_config after (re)connecting instruments.
    """
    for cls in _PROCEDURE_SUBCLASSES:
        cls.DATA_COLUMNS = build_columns(
            getattr(cls, '_MID_COLUMNS', []),
            getattr(cls, '_RECORD_MAGNET_TEMP', False))
        log.info('Rebuilt columns for %s (%d columns)',
                 cls.__name__, len(cls.DATA_COLUMNS))

# ---------------- Base procedure ----------------

class DilutionProcedure(Procedure):
    """Base class: dynamic columns + centralized instrument reading."""

    _MID_COLUMNS = []
    # subclass sets True to also record 'Magnet Temperature(K)' — intended
    # for magnet sweeps (RH); mixing-chamber temp is always recorded
    _RECORD_MAGNET_TEMP = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _PROCEDURE_SUBCLASSES.append(cls)
        cls.DATA_COLUMNS = build_columns(getattr(cls, '_MID_COLUMNS', []),
                                         getattr(cls, '_RECORD_MAGNET_TEMP',
                                                 False))

    # --- lifecycle ---

    def startup(self):
        """Bind the shared instrument references from instruments_config."""
        import instruments_config as cfg
        self.Dilution = cfg.Dilution
        self.SRS860_1 = cfg.SRS860_1
        self.SRS860_2 = cfg.SRS860_2
        self.SRS830_1 = cfg.SRS830_1
        self.SRS830_2 = cfg.SRS830_2
        self.SRS830_3 = cfg.SRS830_3
        self.Gate_1 = cfg.Gate_1
        self.Gate_2 = cfg.Gate_2
        self.Dual_gate = cfg.Dual_gate
        for name in ('Dilution', 'SRS860_1', 'SRS860_2', 'SRS830_1',
                     'SRS830_2', 'SRS830_3', 'Gate_1', 'Gate_2', 'Dual_gate'):
            print('%-10s %s' % (name,
                                'connected' if getattr(cfg, name) is not None
                                else 'skipped (not connected)'))
        # make sure columns match what is connected right now
        self.__class__.DATA_COLUMNS = build_columns(
            self._MID_COLUMNS, self._RECORD_MAGNET_TEMP)

    def shutdown(self):
        # Instrument connections are shared for the whole session and closed
        # by the sequencer on exit — do NOT close them per measurement.
        print('Finished measuring')

    # --- SMU helpers ---

    def smu_choice(self, name):
        if name == 'Gate_1':
            return self.Gate_1
        if name == 'Gate_2':
            return self.Gate_2
        if name == 'smua':
            return self.Dual_gate.smua
        if name == 'smub':
            return self.Dual_gate.smub
        raise ValueError('Invalid SMU selected: %r' % name)

    # --- central readers ---

    def _read_temps(self):
        if not _is_connected(self.Dilution):
            return []
        vals = [self.Dilution.get_temperature(thermometer_num=8)]
        if self._RECORD_MAGNET_TEMP:
            vals.append(self.Dilution.get_temperature(thermometer_num=13))
        return vals

    def _read_smu_values(self):
        vals = []
        if _is_connected(self.Dual_gate):
            vals += [self.Dual_gate.smua.measure__voltage(),
                     self.Dual_gate.smua.measure__current(),
                     self.Dual_gate.smub.measure__voltage(),
                     self.Dual_gate.smub.measure__current()]
        if _is_connected(self.Gate_1):
            vals += [self.Gate_1.measure__voltage(),
                     self.Gate_1.measure__current()]
        if _is_connected(self.Gate_2):
            vals += [self.Gate_2.measure__voltage(),
                     self.Gate_2.measure__current()]
        return vals

    def _snap_with_retry(self, inst, label, retries=10):
        """snap('X','Y') with retry; RuntimeError after N failures."""
        for attempt in range(retries):
            try:
                x, y = inst.snap('X', 'Y')
                if not math.isnan(x) and not math.isnan(y):
                    return [x, y]
            except Exception:
                pass
            time.sleep(0.01)
        raise RuntimeError('Attempted Snap %d times in %s and failed, '
                           'Aborting measurement' % (retries, label))

    def _read_lockin_values(self):
        vals = []
        for inst, name in ((self.SRS860_1, 'SRS860_1'),
                           (self.SRS860_2, 'SRS860_2'),
                           (self.SRS830_1, 'SRS830_1'),
                           (self.SRS830_2, 'SRS830_2'),
                           (self.SRS830_3, 'SRS830_3')):
            if _is_connected(inst):
                vals += self._snap_with_retry(inst, name)
        return vals

    def _read_magnet(self):
        if not _is_connected(self.Dilution) or not _cfg.MAGNET_ENABLED:
            return []
        return list(self.Dilution.read_magnet())

    def _read_standard(self, t0, mid_extras=None):
        return ([time.time() - t0] + self._read_temps() +
                self._read_smu_values() + list(mid_extras or []) +
                self._read_lockin_values() + self._read_magnet())

    def getmeas(self, t0):
        return self._read_standard(t0)

