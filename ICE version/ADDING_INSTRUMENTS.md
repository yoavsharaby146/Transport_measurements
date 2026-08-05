# How to Add Additional Instruments

This guide walks through adding a new instrument of **any type** — a lock-in (SRS860/SRS830), a Keithley SMU (2450/2604B), the magnet (Cryomagnetics MPS4G), or a Zurich MFLI.

> **Dynamic columns.** Most work is centralized in `base.py`. Procedure files need at most 2 lines each (a toggle + inputs entry), and often nothing at all.

---

## The Full Process — 7 Steps

| Step | File | What |
|------|------|------|
| 1 | `config_prelaunch.py` | GUI fields + widgets |
| 2 | `configuration.py` | Open instrument (driver init) |
| 3 | `procedures/base.py` | Centralize: binding + columns + reader + metadata + filter |
| 4 | `procedures/__init__.py` | Export name |
| 5 | `Transport measurements.py` | Cleanup on exit |
| 6 | Procedure files (OPTIONAL) | Toggle + inputs entry (2 lines) |
| 7 | Verify | Run self-checks |

**Key principle:** Every layer must use the **same name** (e.g. `SRS860_3`). If the GUI writes `use_srs860_3`, `configuration.py` must read `use_srs860_3`, `base.py` must expose `SRS860_3`.

---

## Current Instruments

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

---

## The 3 Connection Patterns (Step 2)

### Pattern A — VISA (`_maybe()` helper)
**Used by:** SRS860, SRS830, Keithley 2450, Keithley 2604B

```python
NEW_INST = _maybe(
    InstrumentClass,
    enabled=overrides.get("use_new_inst", False),
    addr=overrides.get("new_inst_visa", ""),
    name="NEW_INST"
)
```

### Pattern B — Serial/COM (manual try/except)
**Used by:** Cryomagnetics MPS4G magnet

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

### Pattern C — TCP/Network (manual try/except)
**Used by:** Zurich MFLI

```python
new_inst = None
if overrides.get("use_new_inst") and overrides.get("new_inst_host") and overrides.get("new_inst_dev"):
    try:
        new_inst = MFLIController(
            overrides["new_inst_host"],
            int(overrides.get("new_inst_port", 8004)),
            6,
            overrides["new_inst_dev"],
        )
    except Exception as e:
        print(f"[configuration] new_inst not opened: {e}")
        new_inst = None
```

---

## What Step 3 Centralizes (the new part)

| Edit | Location | Purpose |
|---|---|---|
| Module binding | Top of `base.py` | Import global from `configuration.py` |
| Column generator | `_build_lockin_columns()` or `_build_smu_columns()` | Auto-generates columns when connected |
| Value reader | `ICEProcedure._read_lockin_values()` or `_read_smu_values()` | Auto-reads when connected + enabled |
| Metadata capture | `ICEProcedure._capture_metadata()` | Records sine voltage/frequency at startup |
| Metadata class attrs | `ICEProcedure` class body | Inherited by all procedures |
| GUI input filter | `_INPUT_CONNECTION_MAP` | Hides checkbox when disconnected |

> **Before:** Step 3 was editing all 13 procedure files with columns + reading + NaN + metadata. Now: one centralized edit in `base.py`. Step 6 became optional/2-lines.

---

## Recipe 1: VISA Lock-in (SRS860 or SRS830)

**Example: Adding `SRS860_3`**

### Step 1: `config_prelaunch.py`

```python
# dataclass
use_srs860_3: bool = False
srs860_3_visa: str = ""

# _build_lockins_tab(): checkbox + combobox
# _fill_visa_comboboxes(): register combobox
# _apply_cfg_to_widgets(): load saved
# accept(): save
```

### Step 2: `configuration.py` (Pattern A)

```python
SRS860_3 = _maybe(SR860,  # ← SR830 class if SRS830
    enabled=overrides.get("use_srs860_3", False),
    addr=overrides.get("srs860_3_visa", ""),
    name="SRS860_3")
```

### Step 3: `procedures/base.py` (4 edits)

**3a.** Binding + rebind:
```python
SRS860_3 = getattr(_cfg, "SRS860_3", 0)
# In _rebind_instruments_from_configuration(): add to global line, assignment, _inst_names
```

**3b.** `_build_lockin_columns()` — add to `_lockin_specs`:
```python
_lockin_specs = [
    (SRS860_1, 'SRS860_1', None),
    (SRS860_2, 'SRS860_2', None),
    (SRS860_3, 'SRS860_3', None),   # ← ADD (order must match reader)
    ...
]
```

**3c.** `_read_lockin_values()` — add (same order):
```python
if _is_connected(SRS860_3):
    vals += list(SRS860_3.snap("X", "Y")) if self.use_srs860_3 else [math.nan] * 2
```

**3d.** Metadata + filter:
```python
# ICEProcedure class body:
srs860_3_sine_voltage = Metadata("SRS860_3 sine voltage", default=math.nan)
srs860_3_frequency   = Metadata("SRS860_3 frequency (Hz)", default=math.nan)

# _capture_metadata():
if self.use_srs860_3 and _is_connected(SRS860_3):
    self.srs860_3_sine_voltage = SRS860_3.sine_voltage
    self.srs860_3_frequency = SRS860_3.frequency

# _INPUT_CONNECTION_MAP:
'use_srs860_3': lambda c: _is_connected(getattr(c, 'SRS860_3', 0)),
```

### Step 4: `procedures/__init__.py`

Add `SRS860_3` to imports + `__all__`.

### Step 5: `Transport measurements.py`

Add `cfg.SRS860_3` to `instrument_list` in `closeEvent`.

### Step 6: Procedure files (OPTIONAL)

```python
use_srs860_3 = BooleanParameter('Use srs860_3', group_by='devices', default=False)
# add 'use_srs860_3' to inputs list
```

### Step 7: Verify

```bash
python -m procedures.self_check_columns
python -m procedures.self_check_runtime
```

---

## Recipe 2: Keithley SMU (2450 or 2604B)

**Example: Adding `Gate_3`**

SMUs return voltage + current pairs and are selectable as sweep source via dropdown.

### Step 1: `config_prelaunch.py`

```python
use_gate3: bool = False
gate3_visa: str = ""
# _build_keithley_tab(): checkbox + combobox
# _fill_visa_comboboxes(), _apply_cfg_to_widgets(), accept()
```

### Step 2: `configuration.py` (Pattern A)

```python
Gate_3 = _maybe(Keithley2450,  # ← Keithley2604B if 2604B
    enabled=overrides.get("use_gate3", False),
    addr=overrides.get("gate3_visa", ""),
    name="Gate_3")
```

### Step 3: `procedures/base.py` (4 edits + SMU helpers)

**3a.** Binding + rebind (same as lock-in pattern).

**3b.** `_build_smu_columns()`:
```python
if _is_connected(Gate_3):
    cols += ['Gate_3_voltage(V)', 'Gate_3_Leakage(A)']
```

**3c.** `_read_smu_values()` (same order):
```python
if _is_connected(Gate_3):
    vals += [Gate_3.measure__voltage(), Gate_3.measure__current()] if self.use_keithley_3 else [math.nan] * 2
```

**3d.** Filter:
```python
'use_keithley_3': lambda c: _is_connected(getattr(c, 'Gate_3', 0)),
```

**3e.** SMU helpers (so it can be selected as sweep source):
```python
# smu_choice():
if name == 'Gate_3': return Gate_3

# smu_output():
if name in ['Gate_1', 'Gate_2', 'Gate_3']:  # add 'Gate_3'
```

### Step 4-5: Same as lock-in.

### Step 6: Procedure files (OPTIONAL + dropdown update)

```python
use_keithley_3 = BooleanParameter('Use k2450_3', group_by='devices', default=False)
# add 'use_keithley_3' to inputs list
# Update smu ListParameter choices: ['Gate_1', 'Gate_2', 'Gate_3', 'smua', 'smub']
```

### Step 7: Verify.

---

## Recipe 3: Second Magnet

Magnet uses **serial/COM** (Pattern B). Singleton currently — adding second means `magnet_2`.

### Step 1: `config_prelaunch.py`

```python
use_magnet_2: bool = False
magnet_2_com: str = ""
magnet_2_baud: int = 9600
magnet_2_timeout_s: float = 0.3
# _build_magnet_tab(): second block, _fill_com_ports(): register
```

### Step 2: `configuration.py` (Pattern B)

```python
if overrides.get("use_magnet_2") and overrides.get("magnet_2_com"):
    try:
        magnet_2 = Cryomagnetics_MPS4G(...)
        magnet_2.remote()
    except Exception as e:
        magnet_2 = None
else:
    magnet_2 = None
```

### Step 3: `procedures/base.py`

**3a.** Binding + rebind.

**3b.** `_build_magnet_columns()`:
```python
def _build_magnet_columns():
    cols = []
    if _is_connected(magnet):
        cols.append('field(T)')
    if _is_connected(magnet_2):
        cols.append('field_2(T)')
    return cols
```

**3c.** `_read_magnet()`:
```python
def _read_magnet(self):
    vals = []
    if _is_connected(magnet):
        vals.append(magnet.magnet_field_read_response() if self.use_magnet else math.nan)
    if _is_connected(magnet_2):
        vals.append(magnet_2.magnet_field_read_response() if self.use_magnet_2 else math.nan)
    return vals
```

**3d.** Filter:
```python
'use_magnet_2': lambda c: _is_connected(getattr(c, 'magnet_2', 0)),
```

### Step 4-7: Same pattern.

---

## Recipe 4: Fourth Zurich MFLI

MFLI uses **TCP/network** (Pattern C).

### Step 1: `config_prelaunch.py`

```python
use_mfli_4: bool = False
mfli_4_host: str = ""
mfli_4_port: int = 8004
mfli_4_dev: str = ""
# _build_mfli_tab(): copy MFLI_3 block, change to 4
# _scan_mfli_devices(): range(1,4) → range(1,5)
```

### Step 2: `configuration.py` (Pattern C)

```python
MFLI_4 = None
if overrides.get("use_mfli_4") and overrides.get("mfli_4_host") and overrides.get("mfli_4_dev"):
    try:
        MFLI_4 = MFLIController(overrides["mfli_4_host"],
            int(overrides.get("mfli_4_port", 8004)), 6, overrides["mfli_4_dev"])
    except Exception as e:
        MFLI_4 = None
```

### Step 3: `procedures/base.py` (same as lock-in pattern)

**3a.** Binding + rebind.

**3b.** `_build_lockin_columns()` — add `(MFLI_4, None, 4)` to `_lockin_specs`.

**3c.** `_read_lockin_values()`:
```python
if _is_connected(MFLI_4):
    vals += list(MFLI_4.read_demod()) if self.use_MFLI_4 else [math.nan] * 2
```

**3d.** Metadata + filter:
```python
# ICEProcedure class body:
MFLI_4_sine_voltage = Metadata("MFLI_4 sine voltage", default=math.nan)
MFLI_4_frequency    = Metadata("MFLI_4 frequency (Hz)", default=math.nan)

# _capture_metadata():
if self.use_MFLI_4 and _is_connected(MFLI_4):
    self.MFLI_4_sine_voltage = MFLI_4.sine_amplitude  # note: .sine_amplitude not .sine_voltage
    self.MFLI_4_frequency = MFLI_4.frequency

# _INPUT_CONNECTION_MAP:
'use_MFLI_4': lambda c: _is_connected(getattr(c, 'MFLI_4', 0)),
```

### Step 4-7: Same pattern.

> **API difference:** SRS uses `.snap("X", "Y")` + `.sine_voltage`. MFLI uses `.read_demod()` + `.sine_amplitude`. `.frequency` same for both.

---

## API Cheat Sheet

| Instrument Class | Read X,Y | Sine amplitude | Frequency | Voltage (SMU) | Current (SMU) |
|---|---|---|---|---|---|
| `SR860` / `SR830` | `.snap("X", "Y")` | `.sine_voltage` | `.frequency` | — | — |
| `MFLIController` | `.read_demod()` | `.sine_amplitude` | `.frequency` | — | — |
| `Keithley2450` | — | — | — | `.measure__voltage()` | `.measure__current()` |
| `Keithley2604B` | — | — | — | `.smua.measure__voltage()` | `.smua.measure__current()` |
| `Cryomagnetics_MPS4G` | — | — | — | `.magnet_field` | — |

> Keithley 2604B (Dual_gate) has two channels (`smua`, `smub`) → 4 values per reading.

---

## Verifying (Step 7)

```bash
cd "ICE version"
python -m procedures.self_check_columns
python -m procedures.self_check_runtime
```

Verifies `len(DATA_COLUMNS) == len(values from _read_standard())` across 8 connection scenarios. Add your own scenario in `self_check_columns.py`:
```python
{"name": "with new SRS860_3", "connected": {"SRS860_3": True, "magnet": True}},
```
