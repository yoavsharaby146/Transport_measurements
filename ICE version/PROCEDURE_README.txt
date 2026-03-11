==============================================================================
MEASUREMENT SUITE: ZURICH MFLI & KEITHLEY TRANSPORT
==============================================================================

1. OVERVIEW
------------------------------------------------------------------------------
This program is a PyMeasure-based suite for characterizing quantum devices
(Tunnel Junctions, Hall Bars, etc.) using lock-in amplifiers and DC source
measure units (SMUs).

It supports:
- Temperature Monitoring
- Gate Sweeps
- Magnetic Field Sweeps
- 2 Gate Sweeps (Carrier density & Displacement field)
- 2D Mapping (Gate, Magnetic field)
- Differential Conductance (dI/dV)
- Differential Resistance (dV/dI)
- Gate dependent dI/dV or dV/dI



2. HARDWARE CONFIGURATION
------------------------------------------------------------------------------
Ensure the following instruments are configured in 'configuration.py' or the
Pre-Launch menu before starting:

* Zurich Instruments MFLI (Lock-in & DC Source)
* SRS 860 / 830 (Lock-ins)
* Keithley 2450 / Keithley 2604  Dual Gate SMUs (Gate Voltage Control)
* Superconducting Magnet (Field Control)

3. SCAN MODES & LOGIC
------------------------------------------------------------------------------
Many procedures offer a 'Scan Mode' or 'Sweep Type' toggle:

A. SNAKE MODE (Best for 2D Maps)
   - Alternates sweep direction to save time and reduce voltage jumps.
   - Even Rows: Forward (Start -> End)
   - Odd Rows:  Backward (End -> Start)

B. FORWARD/BACKWARD (Hysteresis Check)
   - Performs a full loop at every step.
   - Sweep: Start -> End -> Start.
   - Useful for detecting hysteresis in the device.

C. SWEEP AND RETURN
   - 1D Sweep that ramps back to the starting value after measuring.
   - Useful for keeping the device in a known state (e.g., zero bias).

4. AVAILABLE PROCEDURES
------------------------------------------------------------------------------

[A] DIFFERENTIAL CONDUCTANCE (dI/dV)
    - Uses MFLI DC Offset to sweep bias.
    - Measures AC current response (dI).
    - Output: Conductance vs Bias.

[B] DIFFERENTIAL RESISTANCE (dV/dI)
    - Uses MFLI Aux Output to sweep current bias.
    - Measures AC voltage response (dV).
    - Output: Resistance vs Bias.

[C] 2D GATE MAPS (Gate vs Bias)
    - Sweeps Gate Voltage (Slow Axis) and DC Bias (Fast Axis).
    - Can use Keithley for Gate and MFLI for Bias.
    - Supports 'Snake' scanning to minimize measurement time.

[D] MAGNET & GATE MAPPING
    - Sweeps Magnetic Field (Outer Loop) and Gate Voltage (Inner Loop).
    - Checks persistent switch heater state automatically.

[E] TWO-GATE SWEEP
    - Sweeps two independent gates simultaneously along a defined vector.
    - Useful for carrier density / displacement field scans.

5. TROUBLESHOOTING
------------------------------------------------------------------------------
- "Instrument not found": Check 'config_prelaunch' settings or USB connections.
- "Stop flag caught": The measurement was paused/stopped by the user.
- "NaN values": Ensure the specific instrument (e.g., MFLI_1) is toggled
  to 'True' in the 'Devices' list within the procedure inputs.

==============================================================================