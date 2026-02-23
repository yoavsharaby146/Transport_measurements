==================================================
        KEITHLEY 2450 IV SWEEPER & SEQUENCER
                  USER GUIDE
==================================================

1. INSTRUMENT CONNECTION
--------------------------------------------------
This section manages the communication with your Keithley instruments.

- Gate Instrument / Bias Instrument: 
  Dropdown lists showing all detected VISA resource addresses.
  (e.g., USB0::... or TCPIP::...)

- Refresh: 
  Scans the computer for connected instruments and updates the dropdowns.

- Connect: 
  Initializes the connection to the selected instruments.
  *Note:* You must select a Bias instrument to run any sweep.
  The Gate instrument is optional only for "Run Single Sweep (NO Gate Info)".

2. GATE CONTROL
--------------------------------------------------
Direct manual control over the Gate Source Measure Unit (SMU).

- Verify V/I
    Check Gate status and print the voltage and current in the messageboard

- Setup Voltage Source: 
  Opens a popup to configure safety limits.
  * Current Limit: Max current the Gate can source/sink.
  * Compliance: Safety limit to protect the device.
  * NPLC: Integration time. Higher = slower, less noise.

- Ramp Gate Voltage: 
  Smoothly moves the gate voltage to a target value.
  * Target: Final Voltage.
  * Step: Voltage change per step (mV).
  * Pause: Wait time between steps (seconds).

- Gate Toggle Button: 
  A large colored button indicating status.
  * RED: Gate is OFF. Click to turn ON.
  * GREEN: Gate is ON. Click to turn OFF.

3. MEASUREMENT OPERATIONS
--------------------------------------------------
Standard measurement modes.

- Run Single Sweep (WITH Gate Info):
  * Performs one IV sweep on the Bias instrument.
  * Reads the current voltage from the Gate instrument.
  * Saves Gate Voltage in the filename and file header.
  * Requires: Both instruments connected.
  * A second file (_GateLog.csv) is saved containing real-time
      Gate V and I data taken during the Bias sweep.


- Run Single Sweep (NO Gate Info):
  * Performs one IV sweep on the Bias instrument.
  * IGNORES the Gate instrument completely.
  * Useful for 2-terminal devices or when Gate is disconnected.

- RUN MULTI-GATE IV LOOP:
  * Automatically changes the Gate voltage in steps (Start -> End).
  * At each Gate step, it performs a full Bias IV sweep.
  * *Loop Settings:* You can control the Gate Ramping speed (Step/Delay) inside the popup.

4. SEQUENCER (ADVANCED)
--------------------------------------------------
This allows you to run a custom list of measurements defined in a text file.
Useful for complex experiments, jumping between random voltages, or changing
compliance dynamically.

HOW TO USE:
1. Click "OPEN SEQUENCER CONFIG".
2. Load your text/CSV file using the "Load Sequence File" button.
3. Configure Global Settings:
   * Gate Ramp Step (mV): The voltage step size when moving the gate
     between sequence lines.
   * Gate Ramp Delay (s): The pause time between those steps (speed control).
4. Select a Save Directory.
5. Click "RUN SEQUENCE".

FILE FORMAT:
Create a standard text file or CSV. Each line is one measurement step.
The columns must be in this exact order (comma-separated):
Gate_Voltage, Bias_Start, Bias_End, Bias_Step, Compliance

* Gate_Voltage: The voltage the Gate will ramp to before the sweep.
* Bias_Start/End: The range for the IV sweep (mV).
* Bias_Step: Step size for the IV sweep (mV).
* Compliance: Current limit for the Bias instrument (Amps).

EXAMPLE FILE CONTENT:
---------------------
# Lines starting with # are comments and ignored
# Format: Gate(V), Start(mV), End(mV), Step(mV), Comp(A)

0.0, 0, 1000, 10, 1e-6
1.5, 0, -1000, 10, 1e-6
5.0, 0, 2000, 20, 1e-8
0.0, 0, 100, 10, 1e-6
---------------------