# How to Add Additional Instruments

This guide explains the **6-layer architecture** of the ICE measurement system and walks through the exact steps needed to add a new instrument of **any type** — a lock-in (SRS860/SRS830), a Keithley SMU (2450/2604B), the magnet (Cryomagnetics MPS4G), or a Zurich MFLI.

---

## Architecture Overview (The 6 Layers)

When you add an instrument, you must touch **all 6 layers** so the signal flows end-to-end:

```
┌──────────────────────────────────┐
│  1. config_prelaunch.py (GUI)    │  User picks instrument + address (VISA/COM/Host)
│     ↓ writes instrument_overrides.json
├──────────────────────────────────┤
│  2. configuration.py             │  Reads JSON, creates instrument objects
│     ↓ exposes Python globals (SRS860_1, Gate_1, MFLI_1, magnet, etc.)
├──────────────────────────────────┤
│  3. procedures/base.py           │  Binds globals + rebind helper + DATA_COLUMNS
│     ↓ from .base import *
├──────────────────────────────────┤
│  4. procedures/__init__.py       │  Re-exports from base
├──────────────────────────────────┤
│  5. Transport measurements.py    │  Adds to closeEvent instrument_list
├──────────────────────────────────┤
│  6. Individual procedure files   │  Uses the instrument in startup/execute
│     (resistance_time.py, etc.)   │  Adds BooleanParameter toggle + columns
└──────────────────────────────────┘
```

**Key principle:** Every layer must use the **same name** (e.g. `SRS860_2`). If the GUI writes `use_srs860_2`, `configuration.py` must read `use_srs860_2`, `base.py` must expose `SRS860_2`, and procedure files must reference `SRS860_2`.

---

## Current State (All Instruments)

| Instrument | Type | config_prelaunch field | configuration.py global | base.py global |
|---|---|---|---|---|
| Magnet | Cryomagnetics MPS4G (COM) | `use_magnet`, `magnet_com` | `magnet` | `magnet` |
| Gate_1 | Keithley 2450 (VISA) | `use_gate1`, `gate1_visa` | `Gate_1` | `Gate_1` |
| Gate_2 | Keithley 2450 (VISA) | `use_gate2`, `gate2_visa` | `Gate_2` | `Gate_2` |
| Dual_gate | Keithley 2604B (VISA) | `use_dual_gate`, `dual_gate_visa` | `Dual_gate` | `Dual_gate` |
| SRS860 #1 | SRS860 Lock-in (VISA) | `use_srs860_1`, `srs860_1_visa` | `SRS860_1` | `SRS860_1` |
| SRS860 #2 | SRS860 Lock-in (VISA) | `use_srs860_2`, `srs860_2_visa` | `SRS860_2` | `SRS860_2` |
| SRS830 #1 | SRS830 Lock-in (VISA) | `use_srs830_1`, `srs830_1_visa` | `SRS830_1` | `SRS830_1` |
| SRS830 #2 | SRS830 Lock-in (VISA) | `use_srs830_2`, `srs830_2_visa` | `SRS830_2` | `SRS830_2` |
| SRS830 #3 | SRS830 Lock-in (VISA) | `use_srs830_3`, `srs830_3_visa` | `SRS830_3` | `SRS830_3` |
| MFLI #1 | Zurich MFLI (TCP) | `use_mfli_1`, `mfli_1_host`, `mfli_1_port`, `mfli_1_dev` | `MFLI_1` | `MFLI_1` |
| MFLI #2 | Zurich MFLI (TCP) | `use_mfli_2`, `mfli_2_host`, `mfli_2_port`, `mfli_2_dev` | `MFLI_2` | `MFLI_2` |
| MFLI #3 | Zurich MFLI (TCP) | `use_mfli_3`, `mfli_3_host`, `mfli_3_port`, `mfli_3_dev` | `MFLI_3` | `MFLI_3` |

> **✅ COMPLETE — All 13 procedure files have been updated to the numbered scheme.**

---

## The 3 Connection Patterns

Different instrument types use different init patterns in `configuration.py`. Know which one applies:

### Pattern A — VISA instruments (`_maybe()` helper)
**Used by:** SRS860, SRS830, Keithley 2450, Keithley 2604B

These all take a single VISA address string. The `_maybe()` helper handles errors:

```python
NEW_INST = _maybe(
    InstrumentClass,           # e.g. SR860, SR830, Keithley2450, Keithley2604B
    enabled=overrides.get("use_new_inst", False),
    addr=overrides.get("new_inst_visa", ""),
    name="NEW_INST"
)
```

### Pattern B — Serial/COM instruments (manual try/except)
**Used by:** Cryomagnetics MPS4G magnet

These take a COM port + baudrate + timeout:

```python
if overrides.get("use_new_inst") and overrides.get("new_inst_com"):
    try:
        new_inst = InstrumentClass(
            overrides["new_inst_com"],
            baudrate=int(overrides.get("new_inst_baud", 9600)),
            timeout=float(overrides.get("new_inst_timeout_s", 0.3)),
        )
        new_inst.remote()
    except Exception as e:
        print(f"[configuration] new_inst not opened: {e}")
        new_inst = None
else:
    new_inst = None
```

### Pattern C — TCP/Network instruments (manual try/except)
**Used by:** Zurich MFLI

These take a host, port, and device ID:

```python
new_inst = None
if overrides.get("use_new_inst") and overrides.get("new_inst_host") and overrides.get("new_inst_dev"):
    try:
        new_inst = MFLIController(
            overrides["new_inst_host"],
            int(overrides.get("new_inst_port", 8004)),
            6,  # API level
            overrides["new_inst_dev"],
        )
        print(f"[configuration] new_inst connected at {overrides['new_inst_host']}")
    except Exception as e:
        print(f"[configuration] new_inst not opened: {e}")
        new_inst = None
```

---

## Recipe 1: Adding a VISA Lock-in (SRS860 or SRS830)

**Example: Adding a third SRS860 (`SRS860_3`)**

### Layer 1: `config_prelaunch.py`

**1a.** Add fields to the `InstrumentConfig` dataclass:
```python
use_srs860_3: bool = False
srs860_3_visa: str = ""
```

**1b.** Add UI widgets in `_build_lockins_tab()`:
```python
self.chk_srs860_3 = QtWidgets.QCheckBox("Use SRS860_3")
self.cmb_srs860_3 = QtWidgets.QComboBox(); self.cmb_srs860_3.setEditable(True)
grid.addWidget(self.chk_srs860_3, 5, 0)
grid.addWidget(self.cmb_srs860_3, 5, 1)
```

**1c.** Register the combo box in `_fill_visa_comboboxes()`:
```python
for cmb in (..., self.cmb_srs860_3, ...):
```

**1d.** Load saved values in `_apply_cfg_to_widgets()`:
```python
self.chk_srs860_3.setChecked(self._cfg.use_srs860_3)
self.cmb_srs860_3.setEditText(self._cfg.srs860_3_visa)
```

**1e.** Save on OK in `accept()`:
```python
use_srs860_3=self.chk_srs860_3.isChecked(),
srs860_3_visa=self.cmb_srs860_3.currentText().strip(),
```

### Layer 2: `configuration.py` (Pattern A)
```python
SRS860_3 = _maybe(
    SR860,  # ← use SR830 class if it's an SRS830
    enabled=overrides.get("use_srs860_3", False),
    addr=overrides.get("srs860_3_visa", ""),
    name="SRS860_3"
)
```

> **SRS860 vs SRS830:** Use `SR860` class for SRS860 instruments, `SR830` class for SRS830 instruments. The wrapper classes (`SR860_with_add_ons.py`, `SR830_with_add_ons.py`) abstract the SCPI differences so `.snap()`, `.sine_voltage`, `.frequency`, `.sensitivity`, `.time_constant` all work the same way.

### Layer 3: `procedures/base.py`
```python
# Module-level binding:
SRS860_3 = getattr(_cfg, "SRS860_3", 0)

# In _rebind_instruments_from_configuration():
#   - Add to global line
#   - Add: SRS860_3 = _cfg.SRS860_3
#   - Add 'SRS860_3' to _inst_names list

# In LOCKIN_VOLTAGE_COLUMNS:
'Lockin_Voltage_SRS860_3_X(V)', 'Lockin_Voltage_SRS860_3_Y(V)',

# In LOCKIN_CURRENT_COLUMNS:
'Lockin_Current_SRS860_3_X(A)', 'Lockin_Current_SRS860_3_Y(A)',
```

### Layer 4: `procedures/__init__.py`
Add `SRS860_3` to the `from .base import (...)` and `__all__` list.

### Layer 5: `Transport measurements.py`
Add `cfg.SRS860_3` to the `instrument_list` in `closeEvent`.

### Layer 6: Each procedure file
```python
# Import:
from .base import (..., SRS860_3, ...)

# Toggle:
use_srs860_3 = BooleanParameter('Use srs860_3', group_by='devices', default=False)

# Metadata:
srs860_3_sine_voltage = Metadata("SRS860_3 sine voltage", default=math.nan)
srs860_3_frequency = Metadata("SRS860_3 frequency (Hz)", default=math.nan)

# startup():
if self.use_srs860_3:
    self.srs860_3_sine_voltage = SRS860_3.sine_voltage
    self.srs860_3_frequency = SRS860_3.frequency

# getmeas()/execute():
if self.use_srs860_3:
    x, y = SRS860_3.snap("X", "Y")
    vals += [x, y]
else:
    vals += [math.nan] * 2

# DATA_COLUMNS:
'Lockin_Voltage_SRS860_3_X(V)', 'Lockin_Voltage_SRS860_3_Y(V)',

# inputs list:
'use_srs860_3',
```

---

## Recipe 2: Adding a Keithley SMU (2450 or 2604B)

**Example: Adding a third Keithley 2450 (`Gate_3`)**

Keithley SMUs are **VISA instruments** (Pattern A), but in procedures they are measured differently from lock-ins — they return voltage + current pairs and are selected via a `ListParameter` dropdown.

### Layer 1: `config_prelaunch.py`

**1a.** Add dataclass fields:
```python
use_gate3: bool = False
gate3_visa: str = ""
```

**1b.** Add UI widgets in `_build_keithley_tab()`:
```python
self.chk_gate3 = QtWidgets.QCheckBox("Use Gate_3 (Keithley 2450)")
self.cmb_gate3 = QtWidgets.QComboBox(); self.cmb_gate3.setEditable(True)
grid.addWidget(self.chk_gate3, 3, 0); grid.addWidget(self.cmb_gate3, 3, 1)
```

**1c.** Register in `_fill_visa_comboboxes()`:
```python
for cmb in (self.cmb_gate1, self.cmb_gate2, self.cmb_gate3, self.cmb_dual, ...):
```

**1d.** Load in `_apply_cfg_to_widgets()`:
```python
self.chk_gate3.setChecked(self._cfg.use_gate3)
self.cmb_gate3.setEditText(self._cfg.gate3_visa)
```

**1e.** Save in `accept()`:
```python
use_gate3=self.chk_gate3.isChecked(),
gate3_visa=self.cmb_gate3.currentText().strip(),
```

### Layer 2: `configuration.py` (Pattern A)
```python
Gate_3 = _maybe(
    Keithley2450,  # ← use Keithley2604B if it's a 2604B
    enabled=overrides.get("use_gate3", False),
    addr=overrides.get("gate3_visa", ""),
    name="Gate_3"
)
```

### Layer 3: `procedures/base.py`
```python
Gate_3 = getattr(_cfg, "Gate_3", 0)

# Update _rebind_instruments_from_configuration() — global line, assignment, _inst_names

# Add to BASE_DATA_COLUMNS:
'Gate_3_voltage(V)', 'Gate_3_Leakage(A)',
```

### Layer 4 & 5: `__init__.py` + `Transport measurements.py`
Add `Gate_3` to imports/`__all__` and `cfg.Gate_3` to `instrument_list`.

### Layer 6: Each procedure file

Keithley SMUs are unique: they appear in **two** places — the `devices` toggle section AND the `smu_choice()` dropdown list.

**6a.** Add a toggle:
```python
use_keithley_3 = BooleanParameter('Use k2450_3', group_by='devices', default=False)
```

**6b.** Add to measurement reading (in `getmeas`):
```python
vals += [Gate_3.measure__voltage(), Gate_3.measure__current()] if self.use_keithley_3 else [math.nan] * 2
```

**6c.** Update `DATA_COLUMNS`:
```python
'Gate_3_voltage(V)', 'Gate_3_Leakage(A)',
```

**6d.** Update the `smu_choice()` method (so this SMU can be *selected as the sweeping source*):
```python
def smu_choice(self, name):
    if name == 'Gate_1': return Gate_1
    if name == 'Gate_2': return Gate_2
    if name == 'Gate_3': return Gate_3   # ← ADD THIS
    if name == 'smua': return Dual_gate.smua
    if name == 'smub': return Dual_gate.smub
    raise ValueError(f"Unknown SMU: {name}")
```

**6e.** Update the `smu_output()` method's condition for Keithley configuration:
```python
if name in ['Gate_1', 'Gate_2', 'Gate_3']:  # ← add 'Gate_3'
    Gate.configure_voltage_source(nplc=1, current=1e-7, auto_range=False)
```

**6f.** Update `ListParameter` choices for `smu` / `smu_1` / `smu_2` / `slow_smu` / `fast_smu`:
```python
smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'Gate_3', 'smua', 'smub'], ...)
```

**6g.** Add `'use_keithley_3'` to `inputs` list.

---

## Recipe 3: Adding a Second Magnet (or Replacing the Cryomagnetics)

Magnet instruments use **serial/COM** connections (Pattern B). The magnet is a singleton in the current code, so adding a second one means creating a `magnet_2`.

### Layer 1: `config_prelaunch.py`

**1a.** Add dataclass fields:
```python
use_magnet_2: bool = False
magnet_2_com: str = ""
magnet_2_baud: int = 9600
magnet_2_timeout_s: float = 0.3
```

**1b.** Add UI in `_build_magnet_tab()` (a second block):
```python
self.chk_magnet_2 = QtWidgets.QCheckBox("Use Magnet #2")
self.cmb_magnet_2_port = QtWidgets.QComboBox(); self.cmb_magnet_2_port.setEditable(True)
self.spn_magnet_2_baud = QtWidgets.QSpinBox(); self.spn_magnet_2_baud.setRange(1200, 921600)
self.spn_magnet_2_baud.setValue(9600)
self.dsb_magnet_2_timeout = QtWidgets.QDoubleSpinBox(); self.dsb_magnet_2_timeout.setValue(0.30)
```

**1c.** Register the COM port combo in `_fill_com_ports()`:
```python
def _fill_com_ports(self, ports: List[str]):
    for cmb in (self.cmb_magnet_port, self.cmb_magnet_2_port):
        cmb.clear(); cmb.addItems(ports); cmb.setEditable(True)
```

**1d.** Load in `_apply_cfg_to_widgets()` and save in `accept()` — same pattern as the magnet.

### Layer 2: `configuration.py` (Pattern B)
```python
if overrides.get("use_magnet_2") and overrides.get("magnet_2_com"):
    try:
        magnet_2 = Cryomagnetics_MPS4G(
            overrides["magnet_2_com"],
            baudrate=int(overrides.get("magnet_2_baud", 9600)),
            timeout=float(overrides.get("magnet_2_timeout_s", 0.3)),
        )
        magnet_2.remote()
    except Exception as e:
        print(f"[configuration] Magnet #2 not opened: {e}")
        magnet_2 = None
else:
    magnet_2 = None
```

### Layer 3: `procedures/base.py`
```python
magnet_2 = getattr(_cfg, "magnet_2", 0)

# Update _rebind_instruments_from_configuration()
# Add 'field_2(T)' to MAGNET_COLUMNS if you want to track the second field
```

### Layer 4 & 5: Standard re-export and `instrument_list` addition.

### Layer 6: Procedure files
```python
# Toggle:
use_magnet_2 = BooleanParameter('Use Magnet #2', group_by='devices', default=False)

# Reading:
if self.use_magnet_2:
    magnet_2.magnet_field_write_query()
    vals.append(magnet_2.magnet_field_read_response())
else:
    vals.append(math.nan)

# DATA_COLUMNS:
'field_2(T)',
```

---

## Recipe 4: Adding a Fourth Zurich MFLI

MFLI instruments use **TCP/network** connections (Pattern C). They need host, port, and device ID.

### Layer 1: `config_prelaunch.py`

**1a.** Add dataclass fields:
```python
use_mfli_4: bool = False
mfli_4_host: str = ""
mfli_4_port: int = 8004
mfli_4_dev: str = ""
```

**1b.** Add UI in `_build_mfli_tab()` — copy the MFLI_3 block and change indices to `4`:
```python
self.chk_mfli_4 = QtWidgets.QCheckBox("Use MFLI _4")
self.edt_mfli_4_host = QtWidgets.QLineEdit()
self.spn_mfli_4_port = QtWidgets.QSpinBox(); self.spn_mfli_4_port.setRange(1, 65535)
self.spn_mfli_4_port.setValue(8004)
self.cmb_mfli_4_dev = QtWidgets.QComboBox(); self.cmb_mfli_4_dev.setEditable(True)
self.btn_mfli_4_find = QtWidgets.QPushButton("Find on server")
self.btn_mfli_4_test = QtWidgets.QPushButton("Test connection")
self.btn_mfli_4_find.clicked.connect(self._scan_mfli_devices)
self.btn_mfli_4_test.clicked.connect(lambda: self._test_mfli_connection(4))
```

**1c.** Update `_scan_mfli_devices()` — the `range(1, 4)` loop needs to become `range(1, 5)` so MFLI #4 dropdown is populated.

**1d.** Load in `_apply_cfg_to_widgets()` and save in `accept()`.

### Layer 2: `configuration.py` (Pattern C)
```python
MFLI_4 = None
if overrides.get("use_mfli_4") and overrides.get("mfli_4_host") and overrides.get("mfli_4_dev"):
    try:
        MFLI_4 = MFLIController(
            overrides["mfli_4_host"],
            int(overrides.get("mfli_4_port", 8004)),
            6,
            overrides["mfli_4_dev"],
        )
        print(f"[configuration] MFLI_4 connected at {overrides['mfli_4_host']}")
    except Exception as e:
        print(f"[configuration] MFLI_4 not opened: {e}")
        MFLI_4 = None
```

### Layer 3: `procedures/base.py`
```python
MFLI_4 = getattr(_cfg, "MFLI_4", 0)

# Update _rebind_instruments_from_configuration() — global, assignment, _inst_names

# In LOCKIN_VOLTAGE_COLUMNS:
'MFLI_Lockin_4_Voltage_X(V)', 'MFLI_Lockin_4_Voltage_Y(V)',

# In LOCKIN_CURRENT_COLUMNS:
'MFLI_Lockin_4_Current_X(A)', 'MFLI_Lockin_4_Current_Y(A)',
```

### Layer 4 & 5: Standard re-export and `instrument_list` addition.

### Layer 6: Procedure files
```python
# Import:
from .base import (..., MFLI_4, ...)

# Toggle:
use_MFLI_4 = BooleanParameter('use_MFLI_4', group_by='devices', default=False)

# Metadata:
MFLI_4_sine_voltage = Metadata("MFLI_4 sine voltage", default=math.nan)
MFLI_4_frequency = Metadata("MFLI_4 frequency (Hz)", default=math.nan)

# startup():
if self.use_MFLI_4:
    self.MFLI_4_sine_voltage = MFLI_4.sine_amplitude  # ← note: srs uses .sine_voltage, mfli uses .sine_amplitude
    self.MFLI_4_frequency = MFLI_4.frequency

# getmeas()/execute():
vals += list(MFLI_4.read_demod()) if self.use_MFLI_4 else [math.nan] * 2

# DATA_COLUMNS:
'MFLI_Lockin_4_Voltage_X(V)', 'MFLI_Lockin_4_Voltage_Y(V)',

# inputs list:
'use_MFLI_4',
```

> **Important API difference:** SRS lock-ins use `.snap("X", "Y")` to read data and `.sine_voltage` for amplitude. MFLI uses `.read_demod()` to read data and `.sine_amplitude` for amplitude. `.frequency` is the same for both.

---

## Quick Reference: API Cheat Sheet

| Instrument Class | Read X,Y | Sine amplitude | Frequency | Sensitivity | Voltage (SMU) | Current (SMU) |
|---|---|---|---|---|---|---|
| `SR860` / `SR830` | `.snap("X", "Y")` | `.sine_voltage` | `.frequency` | `.sensitivity` | — | — |
| `MFLIController` | `.read_demod()` | `.sine_amplitude` | `.frequency` | — | — | — |
| `Keithley2450` | — | — | — | — | `.measure__voltage()` | `.measure__current()` |
| `Keithley2604B` | — | — | — | — | `.smua.measure__voltage()` | `.smua.measure__current()` |
| `Cryomagnetics_MPS4G` | — | — | — | — | `.magnet_field` | — |

> The Keithley 2604B (Dual_gate) has **two channels** (`smua`, `smub`), so it produces 4 values per reading: smua V/I + smub V/I.

---

## Completed: All Procedure Files Updated

All 13 procedure files have been refactored to the numbered scheme:

1. ✅ `procedures/resistance_time.py`
2. ✅ `procedures/resistance_gate_sweep.py`
3. ✅ `procedures/resistance_magnet_sweep.py`
4. ✅ `procedures/resistance_two_gate_sweep.py`
5. ✅ `procedures/resistance_two_gate_map.py`
6. ✅ `procedures/resistance_magnet_gate_map.py`
7. ✅ `procedures/resistance_magnet_2gate_map.py`
8. ✅ `procedures/differential_conductance_srs860.py`
9. ✅ `procedures/differential_conductance_zurich.py`
10. ✅ `procedures/differential_resistance_zurich.py`
11. ✅ `procedures/differential_resistance_zurich_AUX_map.py`
12. ✅ `procedures/sequencer_rt_rv_rh.py`
13. ✅ `procedures/sequencer_rv_dvdi.py`

---

## Quick Checklist for Any New Instrument

| Step | File | What to do |
|------|------|------------|
| ☐ 1 | `config_prelaunch.py` | Add dataclass fields, UI widgets, register combo in fill method, load in `_apply_cfg_to_widgets`, save in `accept()` |
| ☐ 2 | `configuration.py` | Add init block using Pattern A/B/C (see above) |
| ☐ 3 | `procedures/base.py` | Add `getattr` binding, update `_rebind_instruments_from_configuration()`, add `DATA_COLUMNS` |
| ☐ 4 | `procedures/__init__.py` | Add to import + `__all__` |
| ☐ 5 | `Transport measurements.py` | Add to `instrument_list` in `closeEvent` |
| ☐ 6 | Each procedure file | Add `BooleanParameter`, `Metadata` (if applicable), `startup()` recording, `execute()`/`getmeas()` reading, `DATA_COLUMNS`, `inputs` list |