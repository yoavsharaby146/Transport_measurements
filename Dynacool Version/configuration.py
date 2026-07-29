


################# configuration.py  #################

# This file is given to you AS IS by yoav sharaby
# The following configuration file must be saved togather in the same folder as new procedures.
# In this file the various instruments being use can be modified to fit your measurements.

#####################################################


import math, time, csv
import numpy as np
from datetime import datetime
import json, os
from pathlib import Path

import pyvisa.errors
from serial import SerialException
import sys
from pathlib import Path

# Ensure parent directory is in sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
  
from Instruments.SR830_with_add_ons import SR830
from Instruments.SR860_with_add_ons import SR860
from Instruments.keithley2450_with_add_ons import Keithley2450
# Dual_gate (Keithley 2604B) disabled by request
# from Instruments.keithley2604B import Keithley2604B
# MFLI disabled by request
# from Instruments.MFLI import MFLIController
from DynacoolPPMSClient import Cryostat



# ---------------- configuration.py PATCH ----------------
# Paste AT THE TOP of your existing configuration.py, replacing the hard-coded
# instrument creation. This keeps the *same names* used by your Procedures.




# === BEGIN: dynamic overrides via pre-launcher ===


_OVERRIDES_JSON = Path(__file__).with_name("instrument_overrides.json")
try:
    overrides = json.loads(_OVERRIDES_JSON.read_text("utf-8")) if _OVERRIDES_JSON.is_file() else {}
except Exception:
    overrides = {}

# Helper: if the user disabled or left empty -> return 0 (as in your current code style)
def _maybe(obj, *, enabled: bool, addr: str):
    return obj if (enabled and addr) else 0




def _maybe(instrument_class, enabled=True, addr="", name="Instrument"):
    """
    Safely initialize a VISA instrument with error handling.

    Args:
        instrument_class: The instrument class to initialize
        enabled: Whether this instrument should be used
        addr: VISA address string
        name: Instrument name for logging

    Returns:
        Instrument instance, None, or 0 based on configuration
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

# Dynacool PPMS (temperature + magnetic field over MultiPyVu)
if overrides.get("use_ppms"):
    try:
        magnet = Cryostat(
            host=overrides.get("ppms_host", "10.0.0.10"),
            port=int(overrides.get("ppms_port", 5000)),
        )
        print(f"[configuration] Dynacool PPMS connected at "
              f"{overrides.get('ppms_host', '10.0.0.10')}:"
              f"{overrides.get('ppms_port', 5000)}")

        # Wait for the PPMS to start returning real data (first poll after
        # server connect can return 0 K). Matches the example scripts'
        # `while ppms.getSampleTemperature() == 0` pattern, but bounded by a
        # timeout so import does not hang indefinitely.
        _ppms_wait_t0 = time.time()
        _ppms_wait_timeout = float(overrides.get("ppms_connect_timeout_s", 60.0))
        while True:
            try:
                _t = magnet.getSampleTemperature()
            except Exception:
                _t = 0
            if _t != 0:
                break
            if (time.time() - _ppms_wait_t0) > _ppms_wait_timeout:
                print(f"[configuration] PPMS temperature still 0 after "
                      f"{_ppms_wait_timeout:g}s — continuing anyway.")
                break
            print(".", end="", flush=True)
            time.sleep(0.5)
        print(f"[configuration] PPMS sample temperature: {magnet.getSampleTemperature()} K")
    except Exception as e:
        print(f"[configuration] Dynacool PPMS not opened: {e}")
        magnet = None
else:
    magnet = None


def read_temperature():
    '''
    Return the Dynacool sample/platform temperature as a 1-element array.

    Shape matches the single 'sample_temp(K)' column in
    procedures.base.BASE_DATA_COLUMNS. The Dynacool exposes only the sample
    temperature over MultiPyVu (no separate 4K/VTI/reservoir sensors), unlike
    the ICE setup which read four stages from a text log.
    '''
    if magnet is None:
        return np.array([math.nan], dtype=float)
    return np.array([magnet.getSampleTemperature()], dtype=float)

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

# Dual_gate disabled by request
# Dual_gate = _maybe(
#     Keithley2604B,
#     enabled=overrides.get("use_dual_gate", False),
#     addr=overrides.get("dual_gate_visa", ""),
#     name="Dual_gate"
# )
Dual_gate = None
# Dual_gate = Keithley2600 only
# Dual_gate = None
# if overrides.get("use_dual_gate") and overrides.get("dual_gate_visa"):
#     if Keithley2600 is None:
#         print("[configuration] Keithley2600 driver not available; Dual_gate disabled.")
#     else:
#         addr = overrides["dual_gate_visa"]
#         visa_lib = overrides.get("dual_gate_visa_library") or None
#         try:
#             kwargs = {"visa_library": visa_lib} if visa_lib else {}
#             Dual_gate = Keithley2600(addr, **kwargs)
#             print(f"[configuration] Dual_gate connected via Keithley2600 at {addr}"
#                   + (f" (visa_library={visa_lib})" if visa_lib else ""))
#         except Exception as e:
#             print(f"[configuration] Dual_gate (Keithley2600) failed to open: {e}")
#             Dual_gate = None
# else:
#     Dual_gate = None


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


# Zurich MFLI disabled by request
# MFLI_1 = None
# if overrides.get("use_mfli_1") and overrides.get("mfli_1_host") and overrides.get("mfli_1_dev"):
#     try:
#         MFLI_1 = MFLIController(
#             overrides["mfli_1_host"],
#             int(overrides.get("mfli_1_port", 8004)),
#             6,
#             overrides["mfli_1_dev"],
#         )
#         print(f"[configuration] MFLI connected successfully at {overrides['mfli_1_host']}")
#     except Exception as e:
#         print(f"[configuration] MFLI not opened: {e}")
#         MFLI_1 = None
MFLI_1 = None

# MFLI_2 = None
# if overrides.get("use_mfli_2") and overrides.get("mfli_2_host") and overrides.get("mfli_2_dev"):
#     try:
#         MFLI_2 = MFLIController(
#             overrides["mfli_2_host"],
#             int(overrides.get("mfli_2_port", 8004)),
#             6,
#             overrides["mfli_2_dev"],
#         )
#         print(f"[configuration] MFLI connected successfully at {overrides['mfli_2_host']}")
#     except Exception as e:
#         print(f"[configuration] MFLI not opened: {e}")
#         MFLI_2 = None
MFLI_2 = None

# MFLI_3 = None
# if overrides.get("use_mfli_3") and overrides.get("mfli_3_host") and overrides.get("mfli_3_dev"):
#     try:
#         MFLI_3 = MFLIController(
#             overrides["mfli_3_host"],
#             int(overrides.get("mfli_3_port", 8004)),
#             6,
#             overrides["mfli_3_dev"],
#         )
#         print(f"[configuration] MFLI connected successfully at {overrides['mfli_3_host']}")
#     except Exception as e:
#         print(f"[configuration] MFLI not opened: {e}")
#         MFLI_3 = None
MFLI_3 = None

