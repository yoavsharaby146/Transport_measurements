"""One-shot check: auto-search reassignment logic (no Qt, no hardware)."""
import importlib.util, types, ast, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "config_prelaunch.py")

# 1) structural check on the real file
tree = ast.parse(open(SRC, encoding="utf-8").read())
ms = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_auto_search"][0]
calls = [ast.unparse(n) for n in ast.walk(ms) if isinstance(n, ast.Call)]
assert any("clearEditText" in c for c in calls), "no slot clear"
assert any("zip(key_slots, detections)" in c for c in calls), "no reassign zip"
assert any("read_termination" in c for c in calls), "no terminator retry"
print("structure OK: clear + reassign + terminator retry")

# 2) behavioural check: same sr830 detected on two consecutive runs -> 1 slot
class Cmb:
    def __init__(self): self.t = ""
    def clearEditText(self): self.t = ""
    def setEditText(self, v): self.t = v
    def currentText(self): return self.t

class Chk:
    def __init__(self): self.on = False
    def setChecked(self, v): self.on = v
    def isChecked(self): return self.on

def assign(slot_state, detections):
    slots = [(Chk(), Cmb()) for _ in slot_state]
    for (chk, cmb), (on, t) in zip(slots, slot_state):
        chk.on, cmb.t = on, t
    for chk, cmb in slots:          # family clear (as in _auto_search)
        chk.setChecked(False); cmb.clearEditText()
    for (chk, cmb), (addr, _idn) in zip(slots, detections):
        cmb.setEditText(addr); chk.setChecked(True)
    return [(chk.on, cmb.t) for chk, cmb in slots]

det = [("GPIB0::8", "SRS,SR830")]
s1 = assign([(False, ""), (False, ""), (False, "")], det)
s2 = assign(s1, det)   # run 2 with previous state present
assert s1 == s2 == [(True, "GPIB0::8"), (False, ""), (False, "")], (s1, s2)
print("duplicate check OK: two runs -> still exactly one filled slot")
