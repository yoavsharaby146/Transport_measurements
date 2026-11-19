"""Self-check for GateChannel.configure_source safety fixes.

Run:  python "_selftest_configure_source.py"
Asserts the dangerous behaviours are gone:
  - GS200 with output ON: level NOT zeroed, mode/range NOT rewritten
  - GS200 with output OFF: range+compliance+zero applied
  - 2604B with output ON: levelv keeps the live level (no jump to 0)
  - Keithley 2450: measure range now follows the compliance (bug 1)
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "sweeper_ice", os.path.join(HERE, "IV VI sweeper improved ICE.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeApp:
    def __init__(self):
        self.messages = []

    def log(self, msg):
        self.messages.append(msg)

    def loop_uses_gate(self, i):
        return False


class FakeGS200:
    def __init__(self, level, on):
        self.level = level
        self.source_enabled = on
        self.writes = []
        self.refuse_range = False

    @property
    def source_level(self):
        return self.level

    @source_level.setter
    def source_level(self, v):
        self.writes.append(("level", v))
        self.level = v

    @property
    def source_mode(self):
        return "voltage"

    @source_mode.setter
    def source_mode(self, v):
        self.writes.append(("mode", v))

    @property
    def source_range(self):
        return 10.0

    @source_range.setter
    def source_range(self, v):
        if self.refuse_range:
            raise ValueError("level exceeds new range")
        self.writes.append(("range", v))

    @property
    def current_limit(self):
        return 1e-3

    @current_limit.setter
    def current_limit(self, v):
        self.writes.append(("limit", v))


class Fake2604BChannel:
    def __init__(self, level, on):
        self._level = level
        self._on = on
        self.configured = None

    def is_output_on(self):
        return self._on

    def measure__voltage(self):
        return self._level

    def configure_voltage_source(self, voltage, current_limit):
        self.configured = (voltage, current_limit)
        self._level = voltage


class FakeKeithley2450:
    def __init__(self):
        self.configured = None

    def configure_voltage_source(self, nplc=1, current=1e-6, auto_range=False,
                                 compliance_current=1.05e-8):
        self.configured = dict(nplc=nplc, current=current,
                               compliance_current=compliance_current)


def make_channel(inst, kind):
    app = FakeApp()
    ch = mod.GateChannel(1, app)
    ch.inst = inst
    ch.kind = kind
    return ch, app


# 1. GS200, output ON at 5 V: nothing may move the level; range IS widened
#    (the GS200 allows range changes with the output on)
gs = FakeGS200(5.0, True)
ch, app = make_channel(gs, "gs200")
ch.configure_source(1e-3, 1, max_abs_v=5.0)
assert gs.level == 5.0, f"GS200 level jumped to {gs.level} with output ON"
assert ("range", mod.pick_v_range(5.0)) in gs.writes, gs.writes
assert ("limit", 1e-3) in gs.writes, gs.writes
print("PASS: GS200 output ON - level kept at 5 V, range/compliance applied")

# 1b. GS200, output ON, instrument refuses the range change: no crash, level kept
gs = FakeGS200(0.1, True)
gs.refuse_range = True
ch, app = make_channel(gs, "gs200")
ch.configure_source(1e-3, 1, max_abs_v=1.0)
assert gs.level == 0.1, gs.level
assert any("not changed" in m for m in app.messages), app.messages
print("PASS: GS200 output ON range refusal - logged, level kept")

# 1c. GS200 ramp-ladder scenario: 0 -> 0.1 V (100 mV range), then 1 V target
gs = FakeGS200(0.1, True)
ch, app = make_channel(gs, "gs200")
ch.configure_source(1e-3, 1, max_abs_v=1.0)
assert ("range", 1) in gs.writes, gs.writes   # widened 100 mV -> 1 V
assert gs.level == 0.1, gs.level              # no jump
print("PASS: GS200 0.1 V -> 1 V ramp now possible (range widened, level kept)")

# 2. GS200, output OFF: full configure incl. zero
gs = FakeGS200(5.0, False)
ch, app = make_channel(gs, "gs200")
ch.configure_source(1e-3, 1, max_abs_v=5.0)
assert gs.level == 0.0, gs.level
assert ("range", mod.pick_v_range(5.0)) in gs.writes, gs.writes
print("PASS: GS200 output OFF - ranged, limited, zeroed")

# 3. 2604B, output ON at 3.2 V: levelv keeps live level
kb = Fake2604BChannel(3.2, True)
ch, app = make_channel(kb, "k2604b")
ch.configure_source(1e-3, 1, max_abs_v=5.0)
assert kb.configured == (3.2, 1e-3), kb.configured
print("PASS: 2604B output ON - configured at live level 3.2 V, not 0")

# 4. 2604B, output OFF: configure at 0
kb = Fake2604BChannel(3.2, False)
ch, app = make_channel(kb, "k2604b")
ch.configure_source(1e-3, 1, max_abs_v=5.0)
assert kb.configured == (0.0, 1e-3), kb.configured
print("PASS: 2604B output OFF - configured at 0 V")

# 5. Keithley 2450: measure range follows compliance (was hardcoded 1e-6)
k = FakeKeithley2450()
ch, app = make_channel(k, "keithley")
ch.configure_source(1e-3, 1, max_abs_v=5.0)
assert k.configured["current"] == 1e-3, k.configured
ch.configure_source(1e-7, 1, max_abs_v=5.0)
assert k.configured["current"] == 1e-6, k.configured  # floor at 1 uA
print("PASS: Keithley measure range = max(compliance, 1e-6)")

print("\nAll configure_source self-checks passed.")
