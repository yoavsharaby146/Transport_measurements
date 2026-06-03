# Instrument Control

GUI applications and sweep tools for controlling laboratory instruments over VISA (GPIB / USB / Ethernet).  
All scripts communicate through the instrument drivers located in [`../Instruments/`](../Instruments/).

---

## Scripts

| Script | Instrument(s) | Interface | Description |
|--------|--------------|-----------|-------------|
| `SRS Control.py` | Stanford Research SR830 / SR860 Lock-in Amplifiers | GUI (Tk) | Multi-tab lock-in controller with full parameter control and live measurements |
| `Keithley2450_GUI.py` | Keithley 2450 SourceMeter | GUI (Tk) | Multi-device controller with manual source/measure, ramping, and live I-V plotting |
| `Keithley2604B_GUI.py` | Keithley 2604B Dual-Channel SMU | GUI (Tk) | Dual-SMU controller (Channel A & B) with source/measure, ramping, and live plotting |
| `IV_VI_Sweeper.py` | Keithley 2450 (×2) | GUI (Tk) | Hysteresis IV/VI sweep tool with independent gate voltage control and CSV export |

---

## Script Details

### `SRS Control.py` — SRS Lock-in Amplifier Controller

A multi-tab GUI for controlling **SR830** and/or **SR860** lock-in amplifiers simultaneously.

**Features:**
- VISA resource scanning and model selection (SR830 / SR860)
- Real-time X, Y, R, Θ measurement display (single-shot or auto-refresh)
- Full instrument configuration:
  - **Source**: reference source, frequency, phase, amplitude, DC offset, harmonic
  - **Input**: voltage/current mode, coupling, range, shield, line filter
  - **Gain**: sensitivity (auto-switched by input mode), time constant, filter slope
- Auxiliary output control (4 channels, ±10.5 V) and auxiliary input readback
- Tab-based — connect to multiple lock-ins in one window

**Run:**
```bash
python "Instrument control/SRS Control.py"
```

---

### `Keithley2450_GUI.py` — Keithley 2450 Master Controller

A multi-tab GUI for controlling one or more **Keithley 2450** SourceMeters from a single window.

**Features:**
- Add/remove device tabs dynamically; each tab is an independent connection
- **Manual Control** tab — source voltage or current with configurable range, compliance, and measurement range (auto/manual)
- **Ramping & Sweep** tab — linear voltage or current ramp with configurable target, step size, and timing; live I-V curve plotting
- **System Config** tab — front/rear terminal selection, 2-wire / 4-wire (remote sense) mode
- Single-point measurement with live readout
- Background polling of output state and terminal status
- System log with timestamped entries

**Run:**
```bash
python "Instrument control/Keithley2450_GUI.py"
```

---

### `Keithley2604B_GUI.py` — Keithley 2604B Dual-SMU Controller

A multi-tab GUI for controlling one or more **Keithley 2604B** two-channel SMUs.

**Features:**
- Each connected device exposes two sub-tabs: **SMU A** and **SMU B**
- Per-channel controls:
  - Source voltage or current with configurable range and compliance
  - Measurement range (auto/manual)
  - Linear ramp with live plotting (I-V or V-I depending on mode)
  - Single-point measurement
  - Independent output on/off per channel
- Thread-safe VISA communication (shared lock per device)
- Add/remove multiple device tabs
- Background status polling for both SMU channels

**Run:**
```bash
python "Instrument control/Keithley2604B_GUI.py"
```

---

### `IV_VI_Sweeper.py` — IV/VI Hysteresis Sweeper with Gate

A dedicated sweep tool for performing **hysteresis IV/VI measurements** with an independent **gate voltage** source.

**Features:**
- Two-instrument setup: one Keithley 2450 as the bias sweeper, another as the gate source
- **IV Sweep** (source voltage → measure current) or **VI Sweep** (source current → measure voltage)
- Hysteresis sweep pattern: 0 → Sp1 → Sp2 → 0 (configurable endpoints, step size, delay, compliance)
- Gate voltage control with configurable target, step (mV), delay, and compliance
- Gate ramping with live voltage/current monitoring
- Automatic CSV export with gate voltage in filename (optional)
- Plot popup with matplotlib after each sweep
- Thread-safe execution with abort support for both sweep and gate ramp

**Run:**
```bash
python "Instrument control/IV_VI_Sweeper.py"
```

---

## Subfolder: `IV tries/`

Early/experimental versions of the IV/VI sweeper scripts:

| File | Description |
|------|-------------|
| `IV VI sweeper.py` | Original single-instrument IV/VI sweeper (no gate support) |
| `IV VI sweeper with gate.py` | Intermediate version with gate voltage support |
| `Instruments/` | Local copy of the Keithley 2450 driver for standalone use |

> **Note:** These are archived prototypes. For active use, prefer the main `IV_VI_Sweeper.py` in the parent folder.

---

## Prerequisites

```bash
pip install pyvisa numpy matplotlib
```

- **tkinter** — included with standard Python installations
- A VISA backend (e.g., [NI-VISA](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html) or `pyvisa-py`)
- Instrument drivers from the [`../Instruments/`](../Instruments/) folder

---

## Related

- **Instrument drivers** → [`../Instruments/`](../Instruments/) — low-level Python drivers for all supported instruments
- **Data analysis tools** → [`../Data analysis/`](../Data%20analysis/) — CSV processing and data organization
- **Plotting tools** → [`../Plotter/`](../Plotter/) — visualization scripts for measurement data