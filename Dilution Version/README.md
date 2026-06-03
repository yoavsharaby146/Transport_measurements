# Dilution Version — Transport Measurement Suite

A **PyMeasure-based** measurement suite for automated transport measurements on quantum devices inside a **dilution refrigerator**. Uses lock-in amplifiers, DC SMUs, and a **3D vector magnet** controlled via TCP/IP.

Developed by **Yoav Sharaby**.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [File Structure](#file-structure)
- [How It Works](#how-it-works)
- [Measurement Procedures](#measurement-procedures)
  - [Rt — Resistance vs. Time](#rt--resistance-vs-time)
  - [RV — Resistance vs. Gate Voltage](#rv--resistance-vs-gate-voltage)
  - [RH — Resistance vs. Magnetic Field](#rh--resistance-vs-magnetic-field)
  - [R AUX — Resistance vs. Auxiliary Output](#r-aux--resistance-vs-auxiliary-output)
- [Instrument Drivers](#instrument-drivers)
- [Dilution Refrigerator Connection](#dilution-refrigerator-connection)
- [Customizing Measurements](#customizing-measurements)
  - [Changing Data Columns](#changing-data-columns)
  - [Changing Instrument Addresses](#changing-instrument-addresses)
  - [Adding New Instruments](#adding-new-instruments)
- [Data Output](#data-output)
- [Dependencies](#dependencies)
- [Differences from ICE Version](#differences-from-ice-version)

---

## Overview

This suite provides a **script-based** approach to running transport measurements. Unlike the ICE version's GUI launcher, you compose measurement sequences by editing `Main.py` directly — commenting/uncommenting procedure blocks and chaining them together with Python code.

Each procedure opens its own **live plotting window** with selectable X/Y axes and a stop button, powered by PyQt5 and pyqtgraph.

Key capabilities:

- **Resistance vs. Time (Rt)** — monitor resistance over a set duration
- **Resistance vs. Gate Voltage (RV)** — sweep a gate SMU and measure
- **Resistance vs. Magnetic Field (RH)** — sweep a 3D vector magnet axis with built-in safety limits
- **Resistance vs. Auxiliary Output (R AUX)** — sweep a lock-in DAC output and measure
- **Sequential measurements** — chain procedures in `Main.py` with `time.sleep()` delays

---

## Quick Start

1. Ensure all instruments are connected and powered on, and the dilution refrigerator is reachable over the network.
2. Open `Main.py` and set the `folder_name` variable to your desired data output directory.
3. **Uncomment** the procedure block(s) you want to run and configure the parameters.
4. Run the script:
   ```bash
   python Main.py
   ```
   Or double-click `Run main.bat`.
5. A live plotting window will appear for each procedure as it runs.

---

## File Structure

```
Dilution Version/
├── Main.py                         # Master script — compose & run measurement sequences
├── Run main.bat                    # Batch launcher (simply runs Main.py)
├── README.txt                      # Original documentation
├── README.md                       # This file
│
├── Rt_procedure.py                 # Resistance vs. Time measurement
├── RV_procedure.py                 # Resistance vs. Gate Voltage measurement
├── RH_procedure.py                 # Resistance vs. Magnetic Field measurement
├── R_AUX_procedure.py              # Resistance vs. Auxiliary Output measurement
│
└── Instruments/                    # Local instrument driver modules
    ├── __init__.py
    ├── dilution_connection.py      # Dilution refrigerator TCP/IP interface
    ├── keithley2450_with_add_ons.py        # Keithley 2450 driver
    ├── keithley2450_with_add_ons_ver_2.py  # Keithley 2450 driver (alternate version)
    ├── keithley2604B.py             # Keithley 2604B dual-channel SMU driver
    ├── SR830_with_add_ons.py        # SRS SR830 lock-in driver
    ├── SR860_with_add_ons.py        # SRS SR860 lock-in driver
    ├── MFLI.py                      # Zurich MFLI driver (limited support on Win7)
    ├── README.txt                   # Instrument folder notes
    ├── Dilution source files/       # Original dilution interface source code
    ├── keithley2600/                # Keithley 2600 package
    └── keithleygui/                 # Keithley GUI package
```

---

## How It Works

The workflow is **script-driven**:

1. **`Main.py`** is the entry point. You edit it to define your experiment.
2. Each procedure module (e.g., `RV_procedure.py`) exposes a `main(...)` class that accepts parameters and a `run()` method.
3. Calling `.main(...).run()` opens a PyQt5 live plot window and blocks until the measurement completes (or the window closes).
4. You can chain multiple procedures sequentially, with `time.sleep()` delays between them.

Example from `Main.py`:
```python
import RV_procedure

RV_procedure.main(
    title='RV',
    target_voltage=4.0, step_size=5,
    acq_delay=1,
    smu='Gate_1',
    Resistor='Gain 3',
    Contacts='SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49-50',
    save_dir=folder_name
).run()
```

---

## Measurement Procedures

### Rt — Resistance vs. Time

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | str | `'Rt'` | Measurement title |
| `acq_delay` | float | `0.5` | Delay between readings (seconds) |
| `acq_length` | int | `3600` | Total acquisition duration (seconds) |
| `resistor` | str | `'N/A'` | Metadata: resistor/gain info |
| `contacts` | str | `'N/A'` | Metadata: contact numbers |
| `save_dir` | str | — | Directory for CSV output |

**Data columns:** time, mixing chamber temperature, magnet temperature, gate voltage & leakage, lock-in X/Y readings (SRS860, SR830 ×2), magnetic field (Bx, By, Bz).

---

### RV — Resistance vs. Gate Voltage

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | str | `'RV'` | Measurement title |
| `target_voltage` | float | `0.5` | Target gate voltage (V) |
| `step_size` | float | `5` | Voltage step size (mV) |
| `acq_delay` | float | `1` | Delay between steps (seconds) |
| `smu` | str | `'Gate_1'` | SMU to use (`'Gate_1'`, `'Gate_2'`, `'smua'`, `'smub'`) |
| `Resistor` | str | `'N/A'` | Metadata: resistor/gain info |
| `Contacts` | str | `'N/A'` | Metadata: contact numbers |
| `save_dir` | str | — | Directory for CSV output |

Ramps the selected SMU from its current voltage to the target voltage in discrete steps, taking a measurement at each point.

---

### RH — Resistance vs. Magnetic Field

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | str | `'RH'` | Measurement title |
| `target_field` | float | `0.5` | Target magnetic field (T) |
| `step_size` | int | `1` | Field step size (mT) |
| `ramp_rate` | float | `0.001` | Ramp rate (T/min) |
| `axis` | str | `'bz'` | Magnet axis (`'bx'`, `'by'`, `'bz'`) |
| `acq_delay` | float | `10` | Delay between steps (seconds) |
| `Resistor` | str | `'N/A'` | Metadata: resistor/gain info |
| `Contacts` | str | `'N/A'` | Metadata: contact numbers |
| `save_dir` | str | — | Directory for CSV output |

**Safety limits** are enforced:
- **Bx, By**: ±1 T maximum
- **Bz**: ±8 T maximum
- If in-plane axes (Bx/By) are non-zero, total vector magnitude must not exceed 1 T

---

### R AUX — Resistance vs. Auxiliary Output

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | str | `'AUX sweep'` | Measurement title |
| `target_AUX_voltage` | float | `0` | Target auxiliary voltage (V) |
| `step_size` | float | `1` | Voltage step size (mV) |
| `acq_delay` | float | `1` | Delay between steps (seconds) |
| `aux` | int | `1` | SRS860 aux output channel (1–4) |
| `Resistor` | str | `'N/A'` | Metadata: resistor/gain info |
| `Contacts` | str | `'N/A'` | Metadata: contact numbers |
| `save_dir` | str | — | Directory for CSV output |

Sweeps the SRS860 auxiliary output voltage from its current value to the target, measuring at each step. Useful for bias-dependent measurements.

---

## Instrument Drivers

Local instrument drivers are located in the `Instruments/` subdirectory:

| Module | Instrument | Connection |
|---|---|---|
| `dilution_connection.py` | Dilution refrigerator (temperature + 3D vector magnet) | TCP/IP (socket) |
| `keithley2450_with_add_ons.py` | Keithley 2450 SMU | VISA (USB) |
| `keithley2450_with_add_ons_ver_2.py` | Keithley 2450 SMU (alternate version) | VISA (USB) |
| `keithley2604B.py` | Keithley 2604B dual SMU | VISA (USB) |
| `SR830_with_add_ons.py` | SRS SR830 lock-in amplifier | VISA (GPIB) |
| `SR860_with_add_ons.py` | SRS SR860 lock-in amplifier | VISA (USB) |
| `MFLI.py` | Zurich Instruments MFLI | TCP/IP (zhinst) |

> **Note:** Some drivers are custom wrappers around PyMeasure built-in drivers with added convenience methods (e.g., `ramp_voltage()`, `ramp_aux()`). The MFLI driver has limited support on older Windows 7 systems. The Keithley 2450 module exists in two versions that have not been merged.

---

## Dilution Refrigerator Connection

The `DilutionInstrument` class (`Instruments/dilution_connection.py`) provides a unified TCP/IP interface to the dilution refrigerator, combining:

- **Temperature control** — read thermometers, set PID temperature ramps, control heater ranges
- **3D vector magnet control** — read field vector (Bx, By, Bz), ramp to target field, zero all fields

Default connection: `IP 132.66.132.173`, port `33576`

Key methods:

| Method | Description |
|---|---|
| `connect()` | Open TCP connection |
| `close()` | Close connection cleanly |
| `get_temperature(thermometer_num)` | Read temperature from a specific channel (default: ch. 8 = mixing chamber) |
| `set_temperature(ch, rate, setpoint)` | Start a PID temperature ramp |
| `read_magnet()` | Read current field vector as `(Bx, By, Bz)` in tesla |
| `ramp_magnet_to(rate, bx, by, bz)` | Ramp magnet to a target vector at given rate (T/min) |
| `ramp_magnet_zero()` | Return magnet to zero field on all axes |

---

## Customizing Measurements

### Changing Data Columns

1. Open the procedure file (e.g., `RV_procedure.py`).
2. Find the `DATA_COLUMNS = [...]` list inside the Procedure class.
3. Add, remove, or comment out (`##`) column name strings.
4. Update the `getmeas(self, t0)` method to ensure the number of values appended to `vals` **exactly matches** the number of `DATA_COLUMNS`.

> **Important for RH:** The magnetic field columns (`B_x`, `B_y`, `B_z`) must remain at the **end** of the data list for internal vector-safety calculations.

### Changing Instrument Addresses

1. Open the procedure file.
2. Find the `def startup(self):` method.
3. Modify the VISA address strings (e.g., `"GPIB::17"` → `"GPIB::12"`).

### Adding New Instruments

1. Import the driver at the top of the procedure file.
2. Initialize it in `startup()`: `self.NewInst = DriverClass("ADDRESS")`
3. Read from it in `getmeas()`: `new_val = self.NewInst.measure_property()`
4. Append to `vals` and add the column name to `DATA_COLUMNS`.
5. Add cleanup in `shutdown()`: `self.NewInst.close()`

---

## Data Output

Measurements are saved as timestamped CSV files in the specified `save_dir`:

```
Rt_Procedure_2026-01-15_14-30-00.csv
RV_Procedure_sweep_to_4.0V_2026-01-15_14-35-00.csv
RH_Procedure_sweeping_bz_to_0.5T_2026-01-15_15-00-00.csv
R_AUX_Procedure_sweep_to_4V_2026-01-15_15-30-00.csv
```

Each CSV contains columns for:
- Elapsed time
- Mixing chamber & magnet temperatures
- Gate voltage & leakage current
- Lock-in X/Y voltages (SRS860, SR830 ×2)
- Magnetic field vector (Bx, By, Bz)

---

## Dependencies

- **Python** 3.8+
- **PyMeasure** — experiment procedure framework
- **PyQt5** — GUI for live plotting windows
- **PyVISA** (`pyvisa`) — VISA instrument communication
- **NumPy** — numerical arrays
- **pyqtgraph** — real-time plotting
- **zhinst** (optional) — Zurich Instruments drivers (limited support)

---

## Differences from ICE Version

| Feature | Dilution Version | ICE Version |
|---|---|---|
| **Workflow** | Script-based (edit `Main.py`) | GUI launcher with pre-launch dialog |
| **Cryostat** | Dilution refrigerator (TCP/IP) | ICE cryostat (log file temperature) |
| **Magnet** | 3D vector magnet (Bx, By, Bz) | Single-axis superconducting magnet |
| **Configuration** | Hard-coded in each procedure's `startup()` | Centralized via JSON + pre-launch dialog |
| **Procedures** | 4 core procedures | 13 procedures + sequencers |
| **Plotting** | Custom `LivePlotterWindow` per procedure | PyMeasure `ManagedDockWindow` |
| **Instrument selection** | Fixed per procedure (hard-coded addresses) | Dynamic (user selects at launch time) |
| **Live plot** | Auto-closes 3s after measurement ends | Persistent until user closes |

---

*For additional details, see [`README.txt`](./README.txt) and [`Instruments/README.txt`](./Instruments/README.txt).*