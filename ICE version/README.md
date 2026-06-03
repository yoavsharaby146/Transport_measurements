# ICE Version — Transport Measurement Suite

A **PyMeasure-based** GUI application for automated transport measurements on quantum devices (tunnel junctions, Hall bars, etc.) using lock-in amplifiers, DC SMUs, and superconducting magnets.

Built for the **ICE measurement workstation** and developed by **Yoav Sharaby**.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [File Structure](#file-structure)
- [Configuration](#configuration)
  - [Pre-Launch Dialog (`config_prelaunch.py`)](#pre-launch-dialog-config_prelaunchpy)
  - [Instrument Configuration (`configuration.py`)](#instrument-configuration-configurationpy)
  - [Instrument Overrides (`instrument_overrides.json`)](#instrument-overrides-instrument_overridesjson)
- [Measurement Procedures](#measurement-procedures)
- [Scan Modes](#scan-modes)
- [Supported Instruments](#supported-instruments)
- [Dependencies](#dependencies)
- [Troubleshooting](#troubleshooting)

---

## Overview

This suite provides a PyQt5 GUI launcher that lets you select and run various measurement procedures for characterizing quantum devices. Each procedure opens its own managed window with real-time plotting, input parameters, and data logging.

Key capabilities:

- **Resistance vs. Time** — monitor device resistance over time
- **Gate Sweeps** — sweep one or two gate voltages
- **Magnetic Field Sweeps** — sweep superconducting magnet field
- **2D Mapping** — gate × bias, gate × magnetic field, and dual-gate maps
- **Differential Conductance (dI/dV)** — using SRS860 or Zurich MFLI
- **Differential Resistance (dV/dI)** — using Zurich MFLI aux output
- **Sequenced Measurements** — automated Rt → RV → RH or RV → dV/dI sequences

---

## Quick Start

1. Ensure all required instruments are connected and powered on.
2. Run the main entry point:
   ```bash
   python "Transport measurements.py"
   ```
3. The **Pre-Launch Configuration Dialog** will appear first — select which instruments to use and verify their addresses.
4. Click **Save & Launch** to open the **Procedure Launcher**.
5. Select a procedure from the dropdown, optionally filter by category, and click **Open window**.
6. Configure the procedure parameters and start the measurement.

---

## File Structure

```
ICE version/
├── Transport measurements.py       # Main entry point — GUI launcher
├── config_prelaunch.py             # Pre-launch instrument configuration dialog
├── configuration.py                # Instrument initialization & temperature reader
├── instrument_overrides.json       # Saved instrument settings (auto-generated)
├── PROCEDURE_README.txt            # Additional procedure documentation
├── README.md                       # This file
│
└── procedures/                     # Measurement procedure package
    ├── __init__.py                 # Package init — exports all procedures & registries
    ├── base.py                     # Common imports, instrument bindings, helpers
    │
    ├── resistance_time.py          # Resistance vs. time
    ├── resistance_gate_sweep.py    # Resistance vs. gate voltage
    ├── resistance_magnet_sweep.py  # Resistance vs. magnetic field
    ├── resistance_two_gate_sweep.py      # Two-gate vector sweep
    ├── resistance_two_gate_map.py        # Two-gate 2D mapping
    ├── resistance_magnet_gate_map.py     # Magnet × gate 2D map
    ├── resistance_magnet_2gate_map.py    # Magnet × dual-gate 2D map
    │
    ├── differential_conductance_srs860.py      # dI/dV via SRS860
    ├── differential_conductance_zurich.py      # dI/dV via Zurich MFLI
    ├── differential_resistance_zurich.py       # dV/dI via Zurich MFLI
    ├── differential_resistance_zurich_AUX_map.py  # dV/dI AUX output mapping
    │
    ├── sequencer_rt_rv_rh.py       # Automated Rt → RV → RH sequence
    └── sequencer_rv_dvdi.py        # Automated RV → dV/dI sequence
```

---

## Configuration

### Pre-Launch Dialog (`config_prelaunch.py`)

A PyQt5 dialog that opens **before** the main launcher. It allows you to:

- **Enable/disable** individual instruments with checkboxes
- **Select COM ports** for the magnet controller (auto-enumerated)
- **Select VISA addresses** for Keithley SMUs and SRS lock-ins (auto-enumerated)
- **Configure Zurich MFLI** connections (host, port, device ID) with scan & test buttons
- **Save** settings to `instrument_overrides.json`

When you click **Save & Launch**, the configuration is written to JSON and the main `configuration.py` reads it to initialize only the selected instruments.

### Instrument Configuration (`configuration.py`)

This module:

1. Reads `instrument_overrides.json` for user-selected settings.
2. Initializes each enabled instrument using the appropriate driver class from the `Instruments/` package.
3. Sets module-level variables (`magnet`, `Gate_1`, `Gate_2`, `Dual_gate`, `SRS860`, `SRS830_1`, `SRS830_2`, `MFLI_1`, `MFLI_2`, `MFLI_3`) — disabled instruments are set to `None`.
4. Provides `read_temperature()` to read cryostat temperature logs.
5. Provides `read_dilution_temp()` placeholder for dilution fridge temperature.

### Instrument Overrides (`instrument_overrides.json`)

Auto-generated by the pre-launch dialog. Example:

```json
{
  "use_magnet": true,
  "magnet_com": "COM5",
  "magnet_baud": 115200,
  "use_gate1": true,
  "gate1_visa": "USB0::0x05E6::0x2450::04416746::INSTR",
  "use_mfli_1": true,
  "mfli_1_host": "192.168.173.170",
  "mfli_1_dev": "Dev32114"
}
```

> **Note:** This file should not be manually edited unless you know what you're doing. Use the pre-launch dialog instead.

---

## Measurement Procedures

Each procedure is a PyMeasure `Procedure` subclass with defined parameters, data columns, and an `execute()` method. They are registered in the `PROCEDURES` dictionary with metadata (category, description, inputs, displays, plot axes).

| Procedure | Module | Category | Description |
|---|---|---|---|
| **Resistance time measurement** | `resistance_time.py` | Time-based, Keithley 2450 | Monitors resistance over time with temperature, magnetic field, and lock-in readings |
| **Resistance gate sweep** | `resistance_gate_sweep.py` | Gate Sweep, Keithley 2450 | Sweeps gate voltage and measures resistance |
| **Resistance magnet sweep** | `resistance_magnet_sweep.py` | Magnetic Field | Sweeps magnetic field and measures resistance |
| **Two gate sweep** | `resistance_two_gate_sweep.py` | Gate Sweep | Sweeps two gates simultaneously along a vector |
| **Two gate map** | `resistance_two_gate_map.py` | 2D Mapping | 2D mapping of two independent gate voltages |
| **Magnet & gate map** | `resistance_magnet_gate_map.py` | Magnetic Field, 2D Mapping | 2D map of magnetic field vs. gate voltage |
| **Magnet & 2-gate map** | `resistance_magnet_2gate_map.py` | Magnetic Field, 2D Mapping | 2D map of magnetic field vs. dual gate voltages |
| **Differential conductance (SRS860)** | `differential_conductance_srs860.py` | Tunneling junction | dI/dV measurement using SRS860 lock-in |
| **Differential conductance (Zurich)** | `differential_conductance_zurich.py` | Tunneling junction | dI/dV measurement using Zurich MFLI |
| **Differential resistance (Zurich)** | `differential_resistance_zurich.py` | Differential Resistance | dV/dI measurement using Zurich MFLI |
| **Differential resistance AUX map** | `differential_resistance_zurich_AUX_map.py` | Differential Resistance, 2D Mapping | Gate-dependent dV/dI mapping via MFLI aux output |
| **Rt/RV/RH sequencer** | `sequencer_rt_rv_rh.py` | Time-based, Gate Sweep, Magnetic Field | Automated sequence of Rt, RV, and RH measurements |
| **RV/dV/dI sequencer** | `sequencer_rv_dvdi.py` | Gate Sweep, Differential Resistance | Automated RV followed by dV/dI measurements |

### Category Colors

The launcher displays procedures with color-coded category chips:

| Category | Color |
|---|---|
| Time-based | Light Blue |
| Gate Sweep | Light Green |
| Magnetic Field | Light Yellow |
| 2D Mapping | Light Purple |
| Tunneling junction | Light Pink |
| Differential Resistance | Light Orange |
| Keithley 2450 | Pink |

---

## Scan Modes

Many procedures support configurable scan modes:

| Mode | Description |
|---|---|
| **Snake** | Alternates sweep direction on each row of a 2D map (even rows: forward, odd rows: backward). Minimizes voltage jumps and saves time. |
| **Forward/Backward** | Performs a full sweep loop (Start → End → Start) at every step. Useful for detecting hysteresis. |
| **Sweep and Return** | 1D sweep that ramps back to the starting value after measurement. Keeps the device in a known state. |

---

## Supported Instruments

| Instrument | Driver | Connection | Variable Name |
|---|---|---|---|
| Cryomagnetics MPS4G | `Instruments/Cryomagnetics_MPS4G.py` | Serial (COM) | `magnet` |
| Keithley 2450 (×2) | `Instruments/keithley2450_with_add_ons.py` | VISA (USB/GPIB) | `Gate_1`, `Gate_2` |
| Keithley 2604B | `Instruments/keithley2604B.py` | VISA (USB/GPIB) | `Dual_gate` |
| SRS SR860 | `Instruments/SR860_with_add_ons.py` | VISA (USB) | `SRS860` |
| SRS SR830 (×2) | `Instruments/SR830_with_add_ons.py` | VISA (GPIB) | `SRS830_1`, `SRS830_2` |
| Zurich Instruments MFLI (×3) | `Instruments/MFLI.py` | TCP/IP (zhinst) | `MFLI_1`, `MFLI_2`, `MFLI_3` |

---

## Dependencies

- **Python** 3.8+
- **PyMeasure** — experiment procedure framework with Qt GUI
- **PyQt5** — GUI toolkit
- **PyVISA** (`pyvisa`) — VISA instrument communication
- **PySerial** (`pyserial`) — serial port communication (magnet controller)
- **NumPy** — numerical arrays
- **SciPy** — physical constants
- **pyqtgraph** — real-time plotting (with OpenGL enabled)
- **zhinst** (optional) — Zurich Instruments drivers for MFLI discovery

Instrument drivers are located in the parent directory at `Instruments/`.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| "Instrument not found" | Open the pre-launch dialog and verify addresses. Check USB/GPIB cables. Click **Refresh lists**. |
| "Stop flag caught" | The measurement was manually stopped. This is normal. |
| NaN values in output | Ensure the relevant instrument is toggled **on** in the procedure's **Devices** parameter group. |
| Magnet COM port access denied | Another program may be using the port. Close other instrument software and retry. |
| MFLI connection failed | Verify the host IP, port (default 8004), and device ID. Use the **Test connection** button in the pre-launch dialog. |
| Configuration not updating | Delete `instrument_overrides.json` and re-run to start fresh. |

---

## Data Output

Measurements are saved as CSV files to:
```
C:\Users\ICE\Desktop\ICE Measurements\Yoav\
```

Each CSV includes timestamped columns for temperature, gate voltages, leakage currents, lock-in X/Y readings (voltage and current), and magnetic field, depending on the instruments enabled during the procedure.

---

*For additional procedure details, see [`PROCEDURE_README.txt`](./PROCEDURE_README.txt).*