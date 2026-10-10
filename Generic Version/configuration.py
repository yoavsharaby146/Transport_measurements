################# configuration.py  #################

# Generic Version — Keithleys + lock-ins only (no magnet, no cryostat).
# Same override-JSON mechanism as the ICE version; see config_prelaunch.py.

#####################################################

import json
import sys
from pathlib import Path

import pyvisa.errors

# Ensure parent directory is in sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from Instruments.SR830_with_add_ons import SR830
from Instruments.SR860_with_add_ons import SR860
from Instruments.keithley2450_with_add_ons import Keithley2450
from Instruments.keithley2604B import Keithley2604B
from Instruments.yokogawags200_with_add_ons import YokogawaGS200
from Instruments.yokogawa7651_with_add_ons import Yokogawa7651
from Instruments.MFLI import MFLIController


# === dynamic overrides via pre-launcher ===

_OVERRIDES_JSON = Path(__file__).with_name("instrument_overrides.json")
try:
    overrides = json.loads(_OVERRIDES_JSON.read_text("utf-8")) if _OVERRIDES_JSON.is_file() else {}
except Exception:
    overrides = {}


def _maybe(instrument_class, enabled=True, addr="", name="Instrument"):
    """
    Safely initialize a VISA instrument with error handling.

    Returns instrument instance, None, or 0 based on configuration.
    """
    if not enabled or not addr:
        return None

    try:
        instrument = instrument_class(addr)
        print(f"[configuration] {name} connected successfully at {addr}")
        return instrument
    except pyvisa.errors.VisaIOError as e:
        print(f"[configuration] {name} not found at {addr}: {e}")
        return None
    except Exception as e:
        print(f"[configuration] {name} initialization failed: {e}")
        return None


# Keithley 2450 (Gate_1, Gate_2)
Gate_1 = _maybe(
    Keithley2450,
    enabled=overrides.get("use_gate1", False),
    addr=overrides.get("gate1_visa", ""),
    name="Gate_1"
)

Gate_2 = _maybe(
    Keithley2450,
    enabled=overrides.get("use_gate2", False),
    addr=overrides.get("gate2_visa", ""),
    name="Gate_2"
)

# Keithley 2604B dual SMU
Dual_gate = _maybe(
    Keithley2604B,
    enabled=overrides.get("use_dual_gate", False),
    addr=overrides.get("dual_gate_visa", ""),
    name="Dual_gate"
)

# Yokogawa GS200 sources
YokoGS200_1 = _maybe(
    YokogawaGS200,
    enabled=overrides.get("use_yoko_gs200_1", False),
    addr=overrides.get("yoko_gs200_1_visa", ""),
    name="YokoGS200_1"
)

YokoGS200_2 = _maybe(
    YokogawaGS200,
    enabled=overrides.get("use_yoko_gs200_2", False),
    addr=overrides.get("yoko_gs200_2_visa", ""),
    name="YokoGS200_2"
)

# Yokogawa 7651 sources
Yoko7651_1 = _maybe(
    Yokogawa7651,
    enabled=overrides.get("use_yoko7651_1", False),
    addr=overrides.get("yoko7651_1_visa", ""),
    name="Yoko7651_1"
)

Yoko7651_2 = _maybe(
    Yokogawa7651,
    enabled=overrides.get("use_yoko7651_2", False),
    addr=overrides.get("yoko7651_2_visa", ""),
    name="Yoko7651_2"
)

# SRS lock-ins
SRS860_1 = _maybe(
    SR860,
    enabled=overrides.get("use_srs860_1", False),
    addr=overrides.get("srs860_1_visa", ""),
    name="SRS860_1"
)

SRS860_2 = _maybe(
    SR860,
    enabled=overrides.get("use_srs860_2", False),
    addr=overrides.get("srs860_2_visa", ""),
    name="SRS860_2"
)

SRS860_3 = _maybe(
    SR860,
    enabled=overrides.get("use_srs860_3", False),
    addr=overrides.get("srs860_3_visa", ""),
    name="SRS860_3"
)

SRS860_4 = _maybe(
    SR860,
    enabled=overrides.get("use_srs860_4", False),
    addr=overrides.get("srs860_4_visa", ""),
    name="SRS860_4"
)

SRS830_1 = _maybe(
    SR830,
    enabled=overrides.get("use_srs830_1", False),
    addr=overrides.get("srs830_1_visa", ""),
    name="SRS830_1"
)

SRS830_2 = _maybe(
    SR830,
    enabled=overrides.get("use_srs830_2", False),
    addr=overrides.get("srs830_2_visa", ""),
    name="SRS830_2"
)

SRS830_3 = _maybe(
    SR830,
    enabled=overrides.get("use_srs830_3", False),
    addr=overrides.get("srs830_3_visa", ""),
    name="SRS830_3"
)

# Zurich MFLI lock-ins
def _maybe_mfli(n):
    if overrides.get(f"use_mfli_{n}") and overrides.get(f"mfli_{n}_host") and overrides.get(f"mfli_{n}_dev"):
        try:
            inst = MFLIController(
                overrides[f"mfli_{n}_host"],
                int(overrides.get(f"mfli_{n}_port", 8004)),
                6,
                overrides[f"mfli_{n}_dev"],
            )
            print(f"[configuration] MFLI_{n} connected successfully at {overrides[f'mfli_{n}_host']}")
            return inst
        except Exception as e:
            print(f"[configuration] MFLI_{n} not opened: {e}")
    return None

MFLI_1 = _maybe_mfli(1)
MFLI_2 = _maybe_mfli(2)
MFLI_3 = _maybe_mfli(3)


def read_temperature():
    """Generic version has no cryostat — no temperature columns."""
    return []
