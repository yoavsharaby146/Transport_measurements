


################# configuration.py  #################

# This file is given to you AS IS by yoav sharaby
# The following configuration file must be saved togather in the same folder as new procedures.
# In this file the various instruments being use can be modified to fit your measurements.

#####################################################


import time, csv
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
from Instruments.Cryomagnetics_MPS4G import Cryomagnetics_MPS4G
from Instruments.keithley2450_with_add_ons import Keithley2450
from Instruments.keithley2604B import Keithley2604B
#from keithley2600 import Keithley2600
from Instruments.MFLI import MFLIController



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

#Magnet (COM)
if overrides.get("use_magnet") and overrides.get("magnet_com"):
    try:
        magnet = Cryomagnetics_MPS4G(
            overrides.get("magnet_com"),
            baudrate=int(overrides.get("magnet_baud", 9600)),
            timeout=float(overrides.get("magnet_timeout_s", 0.3)),
        )
        magnet.remote()
    except Exception as e:
        # e.g., SerialException: Access is denied (COM5 in use)
        print(f"[configuration] Magnet not opened: {e}")
        print("Establishing connection to magnet after previous connection. ")
        magnet.close()
        magnet = Cryomagnetics_MPS4G(
            overrides.get("magnet_com"),
            baudrate=int(overrides.get("magnet_baud", 9600)),
            timeout=float(overrides.get("magnet_timeout_s", 0.3)),
        )
else:
    magnet = None

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

Dual_gate = _maybe(
    Keithley2604B,
    enabled=overrides.get("use_dual_gate", False),
    addr=overrides.get("dual_gate_visa", ""),
    name="Dual_gate"
)
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


# Zurich MFLI
MFLI_1 = None
if overrides.get("use_mfli_1") and overrides.get("mfli_1_host") and overrides.get("mfli_1_dev"):
    try:
        MFLI_1 = MFLIController(
            overrides["mfli_1_host"],
            int(overrides.get("mfli_1_port", 8004)),
            6,
            overrides["mfli_1_dev"],
        )
        print(f"[configuration] MFLI connected successfully at {overrides['mfli_1_host']}")
    except Exception as e:
        print(f"[configuration] MFLI not opened: {e}")
        MFLI_1 = None

MFLI_2 = None
if overrides.get("use_mfli_2") and overrides.get("mfli_2_host") and overrides.get("mfli_2_dev"):
    try:
        MFLI_2 = MFLIController(
            overrides["mfli_2_host"],
            int(overrides.get("mfli_2_port", 8004)),
            6,
            overrides["mfli_2_dev"],
        )
        print(f"[configuration] MFLI connected successfully at {overrides['mfli_2_host']}")
    except Exception as e:
        print(f"[configuration] MFLI not opened: {e}")
        MFLI_2 = None

MFLI_3 = None
if overrides.get("use_mfli_3") and overrides.get("mfli_3_host") and overrides.get("mfli_3_dev"):
    try:
        MFLI_3 = MFLIController(
            overrides["mfli_3_host"],
            int(overrides.get("mfli_3_port", 8004)),
            6,
            overrides["mfli_3_dev"],
        )
        print(f"[configuration] MFLI connected successfully at {overrides['mfli_3_host']}")
    except Exception as e:
        print(f"[configuration] MFLI not opened: {e}")
        MFLI_3 = None
def read_temperature(root=r"C:\\Users\\ICE\\Desktop\\ICElog\\Results",
                     ext=".log",
                     timeout=5.0,
                     poll=0.25,
                     encoding="utf-8") -> np.ndarray:
    """
    Return columns 5-8 (indices 4-7) from the last *complete* line of today’s
    log, as a NumPy array of floats. Will wait for the log file if it hasn't
    been created yet (e.g., after midnight).
    """
    root = Path(root)
    t0 = time.time()

    while True:
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = root / today / f"{today}{ext}"

        if file_path.is_file():
            break

        if (time.time() - t0) > timeout:
            raise FileNotFoundError(f"File not found within timeout: {file_path}")
        time.sleep(poll)

    # Now file exists: try to read last complete line
    t0 = time.time()
    while True:
        try:
            with file_path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    raise RuntimeError("Log file is empty")

                pos = f.tell() - 1
                while pos >= 0:
                    f.seek(pos)
                    if f.read(1) not in (b"\n", b"\r"):
                        break
                    pos -= 1
                if pos < 0:
                    raise RuntimeError("File contains only newlines")

                while pos >= 0:
                    f.seek(pos)
                    if f.read(1) == b"\n":
                        pos += 1
                        break
                    pos -= 1

                f.seek(max(pos, 0))
                line = f.readline()
        except PermissionError:
            line = b""

        if line.endswith(b"\n") or (time.time() - t0) > timeout:
            break
        time.sleep(poll)

    raw = line.decode(encoding, errors="replace").rstrip("\r\n")
    fields = next(csv.reader([raw]))

    try:
        values = [float(fields[i]) for i in range(4, 8)]
    except (IndexError, ValueError) as e:
        raise RuntimeError(f"Cannot parse columns 5-8: {e}") from e

    return np.array(values, dtype=float)



# def auto_range_magnet():
#     # In case magnetic field is sweeping
#     magnet_mode = magnet.get_sweep_mode()
#     magnet.set_sweep_mode('Pause')
#
#     magnitude_srs860 = Lockin_srs860_5.snap("R")
#     magnitude_srs830_2 = Lockin_srs830_6.snap("R")
#     # magnitude_srs830_3 = self.lockin_3.snap("R")
#     # magnitude_zurich = self.lockin_4.read_demod()
#     while (magnitude_srs860[0] > 0.85 * Lockin_srs860_5.sensitivity or magnitude_srs860[
#         0] < 0.15 * Lockin_srs860_5.sensitivity or
#            magnitude_srs830_2[0] > 0.85 * Lockin_srs830_6.sensitivity or magnitude_srs830_2[
#                0] < 0.15 * Lockin_srs830_6.sensitivity):
#
#         ######      SRS 860_1 block     ######
#         new_sensitivity = magnitude_srs860[0]
#         if magnitude_srs860[0] > 0.85 * Lockin_srs860_5.sensitivity:
#             Lockin_srs860_5.write("SCAL %d" % (int(Lockin_srs860_5.ask("SCAL?")) - 1))
#             new_sensitivity = 1.5 * magnitude_srs860[0]
#         elif magnitude_srs860[0] < 0.15 * Lockin_srs860_5.sensitivity:
#             Lockin_srs860_5.write("SCAL %d" % (int(Lockin_srs860_5.ask("SCAL?")) + 1))
#             new_sensitivity = 0.3 * abs(magnitude_srs860[0])
#         Lockin_srs860_5.write("*CLS")
#         Lockin_srs860_5.sensitivity = new_sensitivity
#
#         ######      SRS 830_2 block     ######
#         new_sensitivity = magnitude_srs830_2[0]
#         if magnitude_srs830_2[0] > 0.85 * Lockin_srs830_6.sensitivity:
#             Lockin_srs830_6.write("SENS%d" % (int(Lockin_srs830_6.ask("SENS?")) + 1))
#             new_sensitivity = 1.5 * magnitude_srs830_2[0]
#         elif magnitude_srs830_2[0] < 0.15 * Lockin_srs830_6.sensitivity:
#             Lockin_srs830_6.write("SENS%d" % (int(Lockin_srs830_6.ask("SENS?")) - 1))
#             new_sensitivity = 0.3 * abs(magnitude_srs830_2[0])
#         Lockin_srs830_6.write("*CLS")
#         Lockin_srs830_6.sensitivity = new_sensitivity
#
#         #######    SRS 830_3 block     ######
#
#         # new_sensitivity = magnitude_srs830_3[0]
#         # if magnitude_srs830_3[0] > 0.85 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) + 1))
#         #     new_sensitivity = 1.5 * magnitude_srs830_3[0]
#         # elif magnitude_srs830_3[0] < 0.15 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) - 1))
#         #     new_sensitivity = 0.3 * abs(magnitude_srs830_3)
#         # self.lockin_3.write("*CLS")
#         # self.lockin_3.sensitivity = new_sensitivity
#
#         #######     Zurich block     ######
#
#         # new_sensitivity = magnitude_zurich[0]
#         # if magnitude_srs830_3[0] > 0.85 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) + 1))
#         #     new_sensitivity = 1.5 * magnitude_srs830_3[0]
#         # elif magnitude_srs830_3[0] < 0.15 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) - 1))
#         #     new_sensitivity = 0.3 * abs(magnitude_srs830_3)
#         # self.lockin_3.write("*CLS")
#         # self.lockin_3.sensitivity = new_sensitivity
#
#         time_const = [Lockin_srs860_5.time_constant
#             , Lockin_srs830_6.time_constant
#                       # ,self.lockin_3.time_constant
#                       # ,self.lockin_4.get_time_contastant()
#                       ]
#         time.sleep(7.0 * max(time_const))
#         magnitude_srs860 = Lockin_srs860_5.snap("R")
#         magnitude_srs830_2 = Lockin_srs830_6.snap("R")
#         # magnitude_srs830_3 = self.lockin_3.snap("R")
#         # magnitude_zurich = self.lockin_4.read_demod()
#
#     # Continue mangetic field sweeping
#     magnet.set_sweep_mode(magnet_mode)
#
# def auto_range():
#
#     magnitude_srs860 = Lockin_srs860_5.snap("R")
#     magnitude_srs830_2 = Lockin_srs830_6.snap("R")
#     # magnitude_srs830_3 = self.lockin_3.snap("R")
#     # magnitude_zurich = self.lockin_4.read_demod()
#     while (magnitude_srs860[0] > 0.85 * Lockin_srs860_5.sensitivity or magnitude_srs860[
#         0] < 0.15 * Lockin_srs860_5.sensitivity or
#            magnitude_srs830_2[0] > 0.85 * Lockin_srs830_6.sensitivity or magnitude_srs830_2[
#                0] < 0.15 * Lockin_srs830_6.sensitivity):
#
#         ######      SRS 860_1 block     ######
#         new_sensitivity = magnitude_srs860[0]
#         if magnitude_srs860[0] > 0.85 * Lockin_srs860_5.sensitivity:
#             Lockin_srs860_5.write("SCAL %d" % (int(Lockin_srs860_5.ask("SCAL?")) - 1))
#             new_sensitivity = 1.5 * magnitude_srs860[0]
#         elif magnitude_srs860[0] < 0.15 * Lockin_srs860_5.sensitivity:
#             Lockin_srs860_5.write("SCAL %d" % (int(Lockin_srs860_5.ask("SCAL?")) + 1))
#             new_sensitivity = 0.3 * abs(magnitude_srs860[0])
#         Lockin_srs860_5.write("*CLS")
#         Lockin_srs860_5.sensitivity = new_sensitivity
#
#         ######      SRS 830_2 block     ######
#         new_sensitivity = magnitude_srs830_2[0]
#         if magnitude_srs830_2[0] > 0.85 * Lockin_srs830_6.sensitivity:
#             Lockin_srs830_6.write("SENS%d" % (int(Lockin_srs830_6.ask("SENS?")) + 1))
#             new_sensitivity = 1.5 * magnitude_srs830_2[0]
#         elif magnitude_srs830_2[0] < 0.15 * Lockin_srs830_6.sensitivity:
#             Lockin_srs830_6.write("SENS%d" % (int(Lockin_srs830_6.ask("SENS?")) - 1))
#             new_sensitivity = 0.3 * abs(magnitude_srs830_2[0])
#         Lockin_srs830_6.write("*CLS")
#         Lockin_srs830_6.sensitivity = new_sensitivity
#
#         #######    SRS 830_3 block     ######
#
#         # new_sensitivity = magnitude_srs830_3[0]
#         # if magnitude_srs830_3[0] > 0.85 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) + 1))
#         #     new_sensitivity = 1.5 * magnitude_srs830_3[0]
#         # elif magnitude_srs830_3[0] < 0.15 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) - 1))
#         #     new_sensitivity = 0.3 * abs(magnitude_srs830_3)
#         # self.lockin_3.write("*CLS")
#         # self.lockin_3.sensitivity = new_sensitivity
#
#         #######     Zurich block     ######
#
#         # new_sensitivity = magnitude_zurich[0]
#         # if magnitude_srs830_3[0] > 0.85 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) + 1))
#         #     new_sensitivity = 1.5 * magnitude_srs830_3[0]
#         # elif magnitude_srs830_3[0] < 0.15 * self.lockin_3.sensitivity:
#         #     self.lockin_3.write("SENS%d" % (int(self.lockin_3.ask("SENS?")) - 1))
#         #     new_sensitivity = 0.3 * abs(magnitude_srs830_3)
#         # self.lockin_3.write("*CLS")
#         # self.lockin_3.sensitivity = new_sensitivity
#
#         time_const = [Lockin_srs860_5.time_constant
#             , Lockin_srs830_6.time_constant
#                       # ,self.lockin_3.time_constant
#                       # ,self.lockin_4.get_time_contastant()
#                       ]
#         time.sleep(7.0 * max(time_const))
#         magnitude_srs860 = Lockin_srs860_5.snap("R")
#         magnitude_srs830_2 = Lockin_srs830_6.snap("R")
#         # magnitude_srs830_3 = self.lockin_3.snap("R")
#         # magnitude_zurich = self.lockin_4.read_demod()
def read_dilution_temp():
    ### acquire the function and tool to read temperature of the dilution fridge
    return math.nan
