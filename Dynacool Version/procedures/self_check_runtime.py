"""
Runtime self-check: instantiate procedures and call _read_standard()
to verify actual emitted value count matches DATA_COLUMNS.

Run: python -m procedures.self_check_runtime
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


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
    def getMagneticField(self):
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
from procedures.base import (
    DynacoolProcedure, _rebuild_all_columns, _rebuild_procedure_columns,
)

base.read_temperature = lambda: [0.0]

# All connected
base.magnet = _MockInst()
base.Gate_3 = _MockInst()
base.Gate_1 = _MockInst()
base.Gate_2 = _MockInst()
base.SRS860_1 = _MockInst()
base.SRS860_2 = _MockInst()
base.SRS830_1 = _MockInst()
base.SRS830_2 = _MockInst()
base.SRS830_3 = _MockInst()
base.MFLI_1 = _MockInst()
base.MFLI_2 = _MockInst()
base.MFLI_3 = _MockInst()


_USE_NAMES = [
    "use_magnet", "use_keithley_1", "use_keithley_2", "use_keithley_3",
    "use_srs860_1", "use_srs860_2", "use_srs830_1", "use_srs830_2", "use_srs830_3",
    "use_MFLI_1", "use_MFLI_2", "use_MFLI_3",
]


class _DummyProc(DynacoolProcedure):
    _MID_COLUMNS = []
    _LOCKIN_COL_TYPE = "voltage"


class _DummyProcMid(DynacoolProcedure):
    _MID_COLUMNS = ["AUX_DC_offset(V)"]
    _LOCKIN_COL_TYPE = "voltage"


class _DummyProcCurrent(DynacoolProcedure):
    _MID_COLUMNS = ["DC_offset(V)"]
    _LOCKIN_COL_TYPE = "current"


for _c in [_DummyProc, _DummyProcMid, _DummyProcCurrent]:
    _rebuild_procedure_columns(_c)

errors = []
for cls in [_DummyProc, _DummyProcMid, _DummyProcCurrent]:
    proc = cls.__new__(cls)
    for name in _USE_NAMES:
        object.__setattr__(proc, name, True)
    mid = getattr(cls, "_MID_COLUMNS", [])
    mid_extras = [0.0] * len(mid) if mid else None
    vals = proc._read_standard(0.0, mid_extras=mid_extras)
    cols = cls.DATA_COLUMNS
    match = len(vals) == len(cols)
    status = "OK" if match else "FAIL"
    print(f"[{status}] {cls.__name__}: {len(vals)} values, {len(cols)} columns")
    if not match:
        errors.append(f"{cls.__name__}: {len(vals)} vals != {len(cols)} cols")

# Partial: only MFLI_1 + magnet
base.magnet = _MockInst()
base.Gate_3 = None
base.Gate_1 = None
base.Gate_2 = None
base.SRS860_1 = None
base.SRS860_2 = None
base.SRS830_1 = None
base.SRS830_2 = None
base.SRS830_3 = None
base.MFLI_1 = _MockInst()
base.MFLI_2 = None
base.MFLI_3 = None
_rebuild_procedure_columns(_DummyProcMid)

proc = _DummyProcMid.__new__(_DummyProcMid)
for name in _USE_NAMES:
    object.__setattr__(proc, name, True)
vals = proc._read_standard(0.0, mid_extras=[0.0])
cols = _DummyProcMid.DATA_COLUMNS
match = len(vals) == len(cols)
status = "OK" if match else "FAIL"
print(f"[{status}] partial (MFLI_1+magnet): {len(vals)} values, {len(cols)} columns")
if not match:
    errors.append(f"partial: {len(vals)} vals != {len(cols)} cols")

print(f"\n{'='*40}")
if not errors:
    print("Runtime check passed: _read_standard() values match DATA_COLUMNS.")
else:
    print(f"{len(errors)} mismatches:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)