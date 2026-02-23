# Copilot Instructions for QLMG Research Codebase

## Overview
This codebase is for controlling and automating measurements with Keithley 2450 and related instruments, including IV sweeps, gate control, and advanced sequencing. The main workflow is through GUIs and scripts that interface with lab hardware using VISA and custom drivers.

## Key Components
- **Keithley2450_GUI.py**: Main GUI for IV sweeps and instrument control.
- **Instruments/**: Instrument drivers and helpers (e.g., `keithley2450_with_add_ons.py`, `SR830_with_add_ons.py`).
- **Scripts/**: Data analysis, plotting, and utility scripts.
- **Sequencer**: Advanced measurement automation via sequence files (see README for format).

## Developer Workflows
- **Instrument Communication**: Uses VISA addresses (USB/TCPIP). Instrument selection and connection logic is in the GUI and drivers.
- **Measurement Modes**: Single sweep (with/without gate), multi-gate loop, and custom sequence. See `README.txt` for user-facing details.
- **Sequencer Files**: CSV/text files define measurement steps. Format: `Gate_Voltage, Bias_Start, Bias_End, Bias_Step, Compliance`.
- **Data Output**: Measurement data and logs are saved as CSV, with filenames including key parameters (e.g., gate voltage).

## Project Conventions
- **Instrument drivers**: All drivers are in `Instruments/`, with submodules for specific models.
- **GUI logic**: Centralized in `Keithley2450_GUI.py` and `Instruments/keithleygui/`.
- **No formal build/test system**: Scripts are run directly. Testing is manual via the GUI and instrument feedback.
- **Configuration**: Some scripts use `configuration.py` or `instrument_overrides.json` for settings.
- **Comments**: Sequence files and config files support `#` for comments.

## Integration & Patterns
- **VISA/pyVISA**: For instrument communication (not always explicit in code, but required for hardware control).
- **PyQt**: Used for GUI components (see `.ui` files and `pyqt_labutils`).
- **Data Flow**: GUI triggers driver actions, which perform measurements and save results.

## Examples
- To add a new instrument, create a driver in `Instruments/` and update the GUI logic.
- To automate a new measurement, add a script or extend the sequencer logic.
- For plotting, use scripts in `Scripts/` (e.g., `csv_plotter.py`).

## References
- See `README.txt` for user workflows and sequence file format.
- Key files: `Keithley2450_GUI.py`, `Instruments/`, `Scripts/`, `configuration.py`, `instrument_overrides.json`.

---
For new features, follow the structure and patterns in the main GUI and instrument driver files. When in doubt, reference the README and existing scripts for conventions.
