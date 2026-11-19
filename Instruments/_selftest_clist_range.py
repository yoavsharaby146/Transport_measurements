"""Self-check: source range pinned before clist store (no auto-range jumps).

Run:  python _selftest_clist_range.py
Uses a fake VISA adapter; no hardware needed. Asserts:
  - :SOUR:<func>:RANG:AUTO 0 and RANG <max|Sp1|,|Sp2|> are sent
  - they are sent BEFORE the first :SOUR:CONF:LIST:STORE
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "k2450", os.path.join(HERE, "keithley2450_with_add_ons.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


from pymeasure.adapters import Adapter


class FakeAdapter(Adapter):
    """Records writes; answers queries from the last written command."""

    def __init__(self):
        super().__init__()
        self.writes = []
        self._last = ""

    def _write(self, cmd, **kw):
        self.writes.append(str(cmd))
        self._last = str(cmd)

    def _read(self, **kw):
        if "ROUT:TERM" in self._last:
            return "FRON"
        return "0,NO ERROR"


def make_keithley():
    ad = FakeAdapter()
    inst = mod.Keithley2450(ad)
    return inst, ad


def check(ad, auto_cmd, rang_cmd):
    idx_auto = ad.writes.index(auto_cmd)
    idx_rang = ad.writes.index(rang_cmd)
    idx_store = next(i for i, w in enumerate(ad.writes)
                     if "LIST:STORE" in w)
    assert idx_auto < idx_store and idx_rang < idx_store, \
        f"pin commands not before first store: {ad.writes}"


# --- voltage sweep (Sp in mV) ---
inst, ad = make_keithley()
inst.create_hysteresis_voltage_sweep_config_list(
    Sp1=1000, Sp2=-1000, step=10, curr_range=1e-6)
assert ":SOUR:VOLT:RANG:AUTO 0" in ad.writes, ad.writes
assert ":SOUR:VOLT:RANG 1" in ad.writes, ad.writes  # max(1000,1000)mV = 1 V
check(ad, ":SOUR:VOLT:RANG:AUTO 0", ":SOUR:VOLT:RANG 1")
print("PASS: voltage clist pins :SOUR:VOLT:RANG 1 (AUTO 0) before LIST:STORE")

# --- voltage sweep, asymmetric ---
inst, ad = make_keithley()
inst.create_hysteresis_voltage_sweep_config_list(
    Sp1=250, Sp2=-750, step=10, curr_range=1e-6)
assert ":SOUR:VOLT:RANG 0.75" in ad.writes, ad.writes
print("PASS: voltage clist range follows max(|Sp1|,|Sp2|) = 0.75 V")

# --- current sweep (Sp in A) ---
inst, ad = make_keithley()
inst.create_hysteresis_current_sweep_config_list(
    Sp1=1e-6, Sp2=-1e-6, step=1e-7, volt_range=20e-3)
assert ":SOUR:CURR:RANG:AUTO 0" in ad.writes, ad.writes
assert ":SOUR:CURR:RANG 1e-06" in ad.writes, ad.writes  # %g of 1e-6
check(ad, ":SOUR:CURR:RANG:AUTO 0", ":SOUR:CURR:RANG 1e-06")
print("PASS: current clist pins :SOUR:CURR:RANG 1e-06 (AUTO 0) before LIST:STORE")

print("\nAll clist range-pin self-checks passed.")
