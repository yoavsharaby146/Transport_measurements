# Transport Measurements

A Python toolkit for **automated transport measurements** on quantum devices (tunnel junctions, Hall bars, 2DEGs, etc.) across multiple cryostat platforms. Sweeps gate voltage, magnetic field, temperature, and angular position; supports lock-in amplifiers, DC SMUs, and superconducting magnets with live plotting and CSV data output.

Developed by **Yoav Sharaby**.

---

## Table of Contents

- [Overview](#overview)
- [Repository Layout](#repository-layout)
- [Platform Versions](#platform-versions)
  - [ICE version](#ice-version)
  - [Dynacool Version](#dynacool-version)
  - [Dilution Version](#dilution-version)
  - [Attocube Version](#attocube-version)
- [Shared Components](#shared-components)
  - [Instruments](#instruments)
  - [Instrument control](#instrument-control)
  - [Plotter](#plotter)
  - [Data analysis](#data-analysis)
  - [Scripts](#scripts)
- [Supported Instruments](#supported-instruments)
- [Dependencies](#dependencies)
- [Quick Start](#quick-start)
- [Data Output](#data-output)

---

## Overview

This monorepo unifies four cryostat-specific measurement suites plus a shared set of instrument drivers, analysis tools, and plotting utilities. Each cryostat version targets a specific physical platform but shares the same underlying instrument drivers and measurement concepts:

- **Resistance vs. Time (Rt)** — monitor device resistance over time
- **Resistance vs. Gate Voltage (RV)** — sweep gate voltage and measure
- **Resistance vs. Magnetic Field (RH)** — sweep magnetic field and measure
- **Resistance vs. Temperature (Rtem)** — sweep temperature and measure *(Attocube)*
- **Resistance vs. Angular Position (Rpos)** — rotate sample and measure *(Attocube)*
- **2D Mapping** — gate × field, gate × gate, and differential-conductance maps *(ICE / Dynacool)*
- **Differential Conductance (dI/dV)** — via SRS860 or Zurich MFLI
- **Differential Resistance (dV/dI)** — via Zurich MFLI aux output
- **Sequenced Measurements** — automated Rt → RV → RH or RV → dV/dI sequences

---

## Repository Layout

```
Transport_measurements/
├── ICE version/            # GUI suite for the ICE measurement workstation
├── Dynacool Version/       # GUI suite for the Quantum Design Dynacool PPMS
├── Dilution Version/       # Script suite for a dilution refrigerator (3D vector magnet)
├── Attocube Version/       # Script suite for the Attocube attoDRY cryostat (rotation)
├── Instruments/            # Shared instrument drivers (VISA / serial / TCP-IP)
├── Instrument control/     # Standalone GUI controllers for individual instruments
├── Plotter/                # Interactive plotting application (CSV / Excel)
├── Data analysis/          # CSV merging, splitting, reversing, and column math
├── Scripts/                # Measurement-sequence generators and research calculators
├── .gitignore
└── README.md               # This file
```

---

## Platform Versions

### ICE version

A **PyMeasure-based GUI application** for the ICE measurement workstation. A PyQt5 launcher lets you select and run measurement procedures, each opening its own managed window with real-time plotting.

- **Cryostat:** ICE cryostat (temperature read from log files)
- **Magnet:** single-axis superconducting magnet (Cryomagnetics MPS4G, serial COM)
- **Procedures:** 13 (Rt, RV, RH, two-gate sweep/map, magnet–gate maps, dI/dV, dV/dI, sequencers)
- **Configuration:** pre-launch dialog writes `instrument_overrides.json`
- **Entry point:** `python "Transport measurements.py"`

→ See [`ICE version/README.md`](ICE%20version/README.md)

---

### Dynacool Version

A **PyMeasure-based GUI application** for the Quantum Design **Dynacool PPMS**. Shares the same procedure architecture and launcher design as the ICE version, adapted for the Dynacool platform.

- **Cryostat:** Quantum Design Dynacool PPMS
- **Client:** `DynacoolPPMSClient.py`
- **Procedures:** same 13-procedure set as ICE (Rt, RV, RH, maps, dI/dV, dV/dI, sequencers)
- **Entry point:** `python "Transport measurements.py"`

→ See [`Dynacool Version/README.md`](Dynacool%20Version/README.md)

---

### Dilution Version

A **script-based suite** for a **dilution refrigerator** with a 3D vector magnet. You compose measurement sequences by editing `Main.py` directly — commenting/uncommenting procedure blocks and chaining them with `time.sleep()` delays.

- **Cryostat:** dilution refrigerator (TCP/IP, default `132.66.132.173:33576`)
- **Magnet:** 3D vector magnet (Bx, By, Bz) with enforced safety limits
- **Procedures:** 4 core (Rt, RV, RH, R AUX)
- **Entry point:** `python Main.py` (or `Run main.bat`)

→ See [`Dilution Version/README.md`](Dilution%20Version/README.md)

---

### Attocube Version

A **script-based suite** for the **Attocube attoDRY** cryostat. Adds angular-position scans (theta/phi rotation) and temperature sweeps on top of the standard Rt/RV/RH procedures.

- **Cryostat:** Attocube attoDRY (TCP/IP server client on port 1818)
- **Positioner:** ANC350 piezo rotator (theta + phi axes, with wobble-fix variant)
- **Procedures:** Rt, RV, RH, RH point-by-point, Rtem (temperature), Rpos (angular position), Rpos wobblefix
- **Entry point:** `python Main.py` (or `Run main.bat`)

→ `Main.py` documents the full procedure API and example sequences (gate hysteresis, field sweeps at multiple gates, rotation scans, temperature sweeps).

---

## Shared Components

### Instruments

Low-level Python drivers for all supported laboratory instruments. Imported by every cryostat version and the standalone controllers.

| Driver | Instrument | Connection |
|---|---|---|
| `keithley2450_with_add_ons.py` | Keithley 2450 SourceMeter | VISA (USB/GPIB) |
| `keithley2604B.py` | Keithley 2604B dual-channel SMU | VISA (USB/GPIB) |
| `SR830_with_add_ons.py` | SRS SR830 lock-in amplifier | VISA (GPIB) |
| `SR860_with_add_ons.py` | SRS SR860 lock-in amplifier | VISA (USB) |
| `MFLI.py` | Zurich Instruments MFLI | TCP/IP (`zhinst`) |
| `Cryomagnetics_MPS4G.py` | Cryomagnetics MPS4G magnet controller | Serial (COM) |

Bundled packages: `keithley2600/`, `keithleygui/`, `srsinst/` (installed wheel distributions).

---

### Instrument control

Standalone Tkinter GUI tools for controlling individual instruments outside the measurement suites:

| Script | Controls |
|---|---|
| `SRS Control.py` | SR830 / SR860 lock-in amplifiers |
| `Keithley2450_GUI.py` | Keithley 2450 SourceMeters (multi-tab) |
| `Keithley2604B_GUI.py` | Keithley 2604B dual-channel SMUs |
| `IV_VI_Sweeper.py` | Hysteresis IV/VI sweeps with independent gate voltage |

→ See [`Instrument control/README.md`](Instrument%20control/README.md)

---

### Plotter

An Origin Pro-inspired interactive plotting application (Tkinter + matplotlib). Loads CSV/Excel, supports line/scatter/colormap/dual-axis plots, axis breaks, custom ticks/fonts, session save/load, and color-map line profiling.

```bash
python "Plotter/Plot data.py"
```

→ See [`Plotter/README.md`](Plotter/README.md)

---

### Data analysis

A suite of GUI tools for post-measurement CSV processing:

| Script | Purpose |
|---|---|
| `csv_merger.py` | Merge multiple CSV files into one sorted file |
| `smart orginizer.py` | Split a scan into Forward / Backward sweep files (5 modes) |
| `reverser.py` | Reverse measurement blocks in a CSV |
| `map_splitter.py` | Split a map CSV into one file per slow-axis setpoint |
| `csv_operations.py` | Cross-file column math with formula expressions |

→ See [`Data analysis/README.md`](Data%20analysis/README.md)

---

### Scripts

Sequence generators and calculators that produce measurement-sequence files (`.txt`) consumed by the GUI sequencers:

| Script | Output |
|---|---|
| `RH RV Rt sequence generator.py` | Generates RH → Rt → RV forward/backward sequences at multiple fields |
| `RV_dV_dI_sequence generator.py` | Generates RV → dV/dI sequences |
| `*_interactive.py` variants | Prompted (interactive) versions of the generators |
| `Calculator.py` | Research calculations |
| `Conversions for research.ipynb` | Unit / physics conversions notebook |

---

## Supported Instruments

| Instrument | Driver | Connection |
|---|---|---|
| Cryomagnetics MPS4G | `Cryomagnetics_MPS4G.py` | Serial (COM) |
| Keithley 2450 (×2) | `keithley2450_with_add_ons.py` | VISA (USB/GPIB) |
| Keithley 2604B | `keithley2604B.py` | VISA (USB/GPIB) |
| SRS SR860 | `SR860_with_add_ons.py` | VISA (USB) |
| SRS SR830 (×2) | `SR830_with_add_ons.py` | VISA (GPIB) |
| Zurich Instruments MFLI (×3) | `MFLI.py` | TCP/IP (`zhinst`) |
| Attocube ANC350 | `ANC350libv4.py` / `PyANC350v4.py` | USB (DLL) |
| attoDRY cryostat | `attoDRYlib.py` / `PyattoDRY.py` | TCP/IP |
| Dynacool PPMS | `DynacoolPPMSClient.py` | TCP/IP |

---

## Dependencies

- **Python** 3.8+
- **PyMeasure** — experiment procedure framework with Qt GUI
- **PyQt5** — GUI toolkit
- **PyVISA** (`pyvisa`) — VISA instrument communication
- **PySerial** (`pyserial`) — serial port communication (magnet controller)
- **NumPy** — numerical arrays
- **SciPy** — physical constants
- **pyqtgraph** — real-time plotting
- **matplotlib** — static plotting (Plotter, Instrument control)
- **polars** — DataFrame CSV processing (Data analysis, Plotter)
- **zhinst** (optional) — Zurich Instruments MFLI drivers
- **openpyxl** (optional) — Excel file support in Plotter
- **tkinter** — included with standard Python

A VISA backend (e.g., [NI-VISA](https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html) or `pyvisa-py`) is required for VISA instrument communication.

```bash
pip install pymeasure PyQt5 pyvisa pyserial numpy scipy pyqtgraph matplotlib polars
```

---

## Quick Start

1. **Install dependencies** (see above).
2. **Connect instruments** and ensure the cryostat is reachable.
3. **Pick your platform folder** and follow its README:
   - ICE / Dynacool → run `Transport measurements.py`, configure via pre-launch dialog, select a procedure.
   - Dilution / Attocube → edit `Main.py`, set `folder_name`, uncomment procedure blocks, run `python Main.py`.
4. **Live plots** appear during measurement; data is saved as timestamped CSVs.
5. **Analyze & plot** using the tools in `Data analysis/` and `Plotter/`.

---

## Data Output

Measurements are saved as timestamped CSV files in the configured output directory. Each CSV contains columns for elapsed time, temperature, gate voltage(s) and leakage, lock-in X/Y readings, and magnetic field, depending on the instruments enabled.

Example filenames:

```
Rt_Procedure_2026-01-15_14-30-00.csv
RV_Procedure_sweep_to_4.0V_2026-01-15_14-35-00.csv
RH_Procedure_sweeping_bz_to_0.5T_2026-01-15_15-00-00.csv
```
