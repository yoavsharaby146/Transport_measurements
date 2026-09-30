"""
Instrument configuration for the Dilution version.

Reads instruments.json (same folder), connects every enabled instrument,
and exposes module-level references that Dilution_procedure_base and the
procedures use. Failed connections are skipped (reference stays None) so a
missing device never blocks the others — its data columns are simply absent.

Mirrors the ICE version's configuration.py / instrument_overrides.json design.
"""

import os
import sys
import json
import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

JSON_PATH = os.path.join(_HERE, 'instruments.json')

DEFAULTS = {
    "use_dilution": True, "dilution_ip": "132.66.132.173",
    "dilution_port": 33576,
    "use_srs860_1": True,
    "srs860_1_visa": "USB0::0xB506::0x2000::007030::INSTR",
    "use_srs860_2": False, "srs860_2_visa": "",
    "use_srs830_1": True, "srs830_1_visa": "GPIB::17",
    "use_srs830_2": True, "srs830_2_visa": "GPIB::18",
    "use_srs830_3": False, "srs830_3_visa": "GPIB::9",
    "use_gate_1": True,
    "gate_1_visa": "USB0::0x05E6::0x2450::04416746::INSTR",
    "use_gate_2": False, "gate_2_visa": "",
    "use_dual_gate": False, "dual_gate_visa": "",
    "use_magnet": True,
}

# Device layout for the GUI dialog: (key_prefix, label, address_key)
DEVICE_LAYOUT = [
    ("dilution",  "Dilution fridge (TCP)", "dilution_ip"),
    ("srs860_1",  "SRS860 #1 (lock-in)",   "srs860_1_visa"),
    ("srs860_2",  "SRS860 #2 (lock-in)",   "srs860_2_visa"),
    ("srs830_1",  "SRS830 #1 (lock-in)",   "srs830_1_visa"),
    ("srs830_2",  "SRS830 #2 (lock-in)",   "srs830_2_visa"),
    ("srs830_3",  "SRS830 #3 (lock-in)",   "srs830_3_visa"),
    ("gate_1",    "Gate 1 (Keithley 2450)", "gate_1_visa"),
    ("gate_2",    "Gate 2 (Keithley 2450)", "gate_2_visa"),
    ("dual_gate", "Dual gate (Keithley 2604B)", "dual_gate_visa"),
]

# Connected instrument references (None = not connected)
Dilution = None
SRS860_1 = None
SRS860_2 = None
SRS830_1 = None
SRS830_2 = None
SRS830_3 = None
Gate_1 = None
Gate_2 = None
Dual_gate = None

_connected_once = False

# Separate toggle: record Bx/By/Bz magnet readout (needs dilution connected).
# Temperature columns follow use_dilution only.
MAGNET_ENABLED = True

def load_settings():
    """Merge DEFAULTS with instruments.json (file wins when present)."""
    settings = dict(DEFAULTS)
    try:
        with open(JSON_PATH, 'r') as f:
            settings.update(json.load(f))
    except Exception as e:
        print("[instruments_config] could not read %s (%s) — using defaults"
              % (JSON_PATH, e))
    return settings


def save_settings(settings):
    with open(JSON_PATH, 'w') as f:
        json.dump(settings, f, indent=2)


def _try(name, func):
    try:
        inst = func()
        print("[instruments_config] %s connected" % name)
        return inst
    except Exception as e:
        print("[instruments_config] %s FAILED: %s" % (name, e))
        return None


_INSTR_NAMES = ('Dilution', 'SRS860_1', 'SRS860_2', 'SRS830_1', 'SRS830_2',
                'SRS830_3', 'Gate_1', 'Gate_2', 'Dual_gate')


def close_all():
    """Disconnect everything (best effort)."""
    for name in _INSTR_NAMES:
        inst = globals().get(name)
        if inst is None:
            continue
        for method in ('close', 'shutdown'):
            try:
                getattr(inst, method)()
                break
            except Exception:
                pass
        globals()[name] = None


def connect_all(force=False):
    """Connect all enabled instruments; returns {name: bool} status map.

    Also rebuilds the dynamic DATA_COLUMNS of every DilutionProcedure
    subclass afterwards.
    """
    global Dilution, SRS860_1, SRS860_2, SRS830_1, SRS830_2, SRS830_3, \
        Gate_1, Gate_2, Dual_gate, _connected_once

    if _connected_once and not force:
        return {name: globals()[name] is not None
                for name in _INSTR_NAMES}

    close_all()
    s = load_settings()
    global MAGNET_ENABLED
    MAGNET_ENABLED = bool(s.get('use_magnet', True))

    if s.get('use_dilution') and s.get('dilution_ip'):
        from Instruments.dilution_connection import DilutionInstrument

        def _dil():
            inst = DilutionInstrument(ip=s['dilution_ip'],
                                      port=int(s.get('dilution_port', 33576)))
            inst.connect()
            return inst
        global Dilution
        Dilution = _try('Dilution', _dil)

    from Instruments.SR860_with_add_ons import SR860
    from Instruments.SR830_with_add_ons import SR830
    from Instruments.keithley2450_with_add_ons import Keithley2450
    from Instruments.keithley2604B import Keithley2604B

    if s.get('use_srs860_1') and s.get('srs860_1_visa'):
        SRS860_1 = _try('SRS860_1', lambda: SR860(s['srs860_1_visa']))
    if s.get('use_srs860_2') and s.get('srs860_2_visa'):
        SRS860_2 = _try('SRS860_2', lambda: SR860(s['srs860_2_visa']))
    if s.get('use_srs830_1') and s.get('srs830_1_visa'):
        SRS830_1 = _try('SRS830_1', lambda: SR830(s['srs830_1_visa']))
    if s.get('use_srs830_2') and s.get('srs830_2_visa'):
        SRS830_2 = _try('SRS830_2', lambda: SR830(s['srs830_2_visa']))
    if s.get('use_srs830_3') and s.get('srs830_3_visa'):
        SRS830_3 = _try('SRS830_3', lambda: SR830(s['srs830_3_visa']))
    if s.get('use_gate_1') and s.get('gate_1_visa'):
        Gate_1 = _try('Gate_1', lambda: Keithley2450(s['gate_1_visa']))
    if s.get('use_gate_2') and s.get('gate_2_visa'):
        Gate_2 = _try('Gate_2', lambda: Keithley2450(s['gate_2_visa']))
    if s.get('use_dual_gate') and s.get('dual_gate_visa'):
        Dual_gate = _try('Dual_gate',
                         lambda: Keithley2604B(s['dual_gate_visa']))

    _connected_once = True

    # rebuild dynamic columns for all procedure classes
    try:
        import Dilution_procedure_base
        Dilution_procedure_base.rebuild_all()
    except Exception as e:
        print("[instruments_config] column rebuild skipped: %s" % e)

    return {name: globals()[name] is not None for name in _INSTR_NAMES}


def reload():
    """Re-read instruments.json and reconnect everything."""
    global _connected_once
    _connected_once = False
    return connect_all(force=True)

