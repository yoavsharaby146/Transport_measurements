"""
Self-check: verify DATA_COLUMNS length matches _read_standard() value count
across multiple connection scenarios (all connected, partial, none).

Run: python -m procedures.self_check_columns
"""
import math
import types
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

# Mock instruments: truthy = connected
class _MockInst:
    def __getattr__(self, name):
        return 0.0
    def snap(self, *a):
        return [0.0, 0.0]
    def read_demod(self):
        return [0.0, 0.0]
    def measure__voltage(self):
        return 0.0
    def measure__current(self):
        return 0.0
    def magnet_field_write_query(self):
        pass
    def magnet_field_read_response(self):
        return 0.0

class _MockSMU:
    def measure__voltage(self): return 0.0
    def measure__current(self): return 0.0

class _MockDualGate(_MockInst):
    def __init__(self):
        self.smua = _MockSMU()
        self.smub = _MockSMU()

import procedures
import procedures.base as base
from procedures.base import ICEProcedure, _rebuild_all_columns, _is_connected

# Instrument names in base module
_INSTR_NAMES = [
    "magnet", "Dual_gate", "Gate_1", "Gate_2",
    "SRS860_1", "SRS860_2", "SRS830_1", "SRS830_2", "SRS830_3",
    "MFLI_1", "MFLI_2", "MFLI_3",
]

# SMU value counts: Dual_gate=4, Gate_1=2, Gate_2=2
_SMU_COUNTS = {"Dual_gate": 4, "Gate_1": 2, "Gate_2": 2}
# Lock-in value counts: each = 2
_LOCKIN_NAMES = ["SRS860_1", "SRS860_2", "MFLI_1", "MFLI_2", "MFLI_3",
                 "SRS830_1", "SRS830_2", "SRS830_3"]


def _set_connections(connected):
    """Set base globals: connected dict maps name->True/False."""
    for name in _INSTR_NAMES:
        if connected.get(name, False):
            if name == "Dual_gate":
                setattr(base, name, _MockDualGate())
            else:
                setattr(base, name, _MockInst())
        else:
            setattr(base, name, None)


def _expected_count(connected, mid_len):
    """Compute expected value count for a connection scenario."""
    count = 5  # time + 4 temps
    for smu, n in _SMU_COUNTS.items():
        if connected.get(smu, False):
            count += n
    count += mid_len
    for lockin in _LOCKIN_NAMES:
        if connected.get(lockin, False):
            count += 2
    if connected.get("magnet", False):
        count += 1
    return count


# Scenarios to test
scenarios = [
    {"name": "all connected", "connected": {n: True for n in _INSTR_NAMES}},
    {"name": "none connected", "connected": {}},
    {"name": "only magnet", "connected": {"magnet": True}},
    {"name": "only SMUs", "connected": {"Dual_gate": True, "Gate_1": True, "Gate_2": True}},
    {"name": "only lock-ins", "connected": {n: True for n in _LOCKIN_NAMES}},
    {"name": "session #1 (2x k2450, srs860, srs830)", "connected": {
        "Gate_1": True, "Gate_2": True, "SRS860_1": True, "SRS830_1": True}},
    {"name": "session #2 (2604B + 3 MFLI)", "connected": {
        "Dual_gate": True, "MFLI_1": True, "MFLI_2": True, "MFLI_3": True}},
    {"name": "mixed partial", "connected": {
        "magnet": True, "Gate_1": True, "SRS860_1": True, "MFLI_2": True}},
]

total_errors = 0

for scenario in scenarios:
    _set_connections(scenario["connected"])
    _rebuild_all_columns()

    errors = []
    seen = set()

    for mod_name in list(sys.modules.keys()):
        mod = sys.modules.get(mod_name)
        if mod is None or not hasattr(mod, "__file__") or not mod.__file__:
            continue
        if "procedures" not in mod.__name__:
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if not (isinstance(obj, type) and issubclass(obj, ICEProcedure) and obj is not ICEProcedure):
                continue
            if obj in seen:
                continue
            seen.add(obj)

            cols = obj.DATA_COLUMNS
            mid = getattr(obj, "_MID_COLUMNS", [])
            expected = _expected_count(scenario["connected"], len(mid))

            if len(cols) != expected:
                errors.append(
                    f"  {obj.__name__}: {len(cols)} cols, expected {expected}"
                )
                total_errors += 1

    status = "OK" if not errors else "FAIL"
    print(f"[{status}] {scenario['name']}")
    for e in errors:
        print(e)

print(f"\n{'='*40}")
if total_errors == 0:
    print("All scenarios passed: column counts match value counts.")
else:
    print(f"{total_errors} mismatches found.")
    sys.exit(1)