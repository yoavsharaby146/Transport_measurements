===============================================================================
Measurement Automation & Procedure Suite
===============================================================================

This directory contains a suite of automation procedures built on PyMeasure 
for executing standard laboratory transport measurements. It offers automated 
sweeps for Magnetic Fields, Gate Voltages, Auxiliary Outputs, and Time-tracking.

Files Included:
  - Main.py             : The master script used to run measurements sequentially.
  - Rt_procedure.py     : Time-dependent resistance/measurement tracking.
  - RV_procedure.py     : Voltage-dependent resistance/measurement tracking (Gate sweeps).
  - R_AUX_procedure.py  : Auxiliary output voltage sweeps (e.g., using Lock-in DAC outputs).
  - RH_procedure.py     : Magnetic field sweeps (3D vector magnets with safety checks).

===============================================================================
1. HOW TO USE Main.py
===============================================================================

`Main.py` acts as the command hub. Instead of running individual procedure files, 
you define your experimental parameters inside `Main.py` and invoke the `.run()` 
method of the respective procedure module.

Quick-Start:
  1. Open `Main.py`.
  2. Modify the `folder_name` directory variable to determine where your data 
     is saved (e.g., fr'C:\Users\...\Data\YourSample').
  3. Locate the procedure block you want to run (e.g., `RH_procedure`, `Rt_procedure`, 
     `RV_procedure`, or `R_AUX_procedure`).
  4. Uncomment the desired `.main(...).run()` function block.
  5. Pass your experimental arguments (such as `target_voltage`, `step_size`, 
     `acq_delay`, `Resistor`, `Contacts`, etc.).
  6. Execute the `Main.py` file. It will spin up a Live Plotting window and 
     autonomously cycle through your steps.

===============================================================================
2. CHANGING THE MEASURED DATA COLUMNS (DATA_COLUMNS)
===============================================================================

If you modify your circuit or setup (e.g., you start recording a new lock-in amplifier 
or want to turn off gate leakages), you must edit the procedures themselves.

How to edit the output file columns:
  1. Open the specific procedure file (e.g., `RV_procedure.py` or `RH_procedure.py`).
  2. Locate the `DATA_COLUMNS = [...]` list variable inside the Procedure class.
  3. Add, remove, or comment-out (`##`) the column names as strings.
  4. Scroll down to the `getmeas(self, t0)` function inside the file.
  5. Locate the `vals = [...]` list construction. 
  6. Add or delete the corresponding hardware readings to ensure the number of 
     variables appended to `vals` perfectly matches the count of `DATA_COLUMNS`. 

     *Note for RH_procedure users: In `RH_procedure.py`, the magnetic field readings 
     ('B_x', 'B_y', 'B_z') must remain at the very end of the list to preserve 
     internal vector-safety calculations.*

===============================================================================
3. CHANGING INSTRUMENTS AND RESOURCE ADDRESSES (startup)
===============================================================================

If you are changing physical hardware, swapping GPIB/USB ports, or introducing 
new equipment, edit the `startup` segment of your procedure files.

How to change instrument ports/addresses:
  1. Open the specific procedure file.
  2. Find the `def startup(self):` method.
  3. Modify the VISA address strings (e.g., replace `"GPIB::17"` with `"GPIB::12"` 
     if you shifted a Lock-in, or change the USB resource identifier for your Keithley).

How to swap or add a new instrument type:
  1. Make sure the PyMeasure driver or wrapper for the instrument is imported at 
     the top of the file (e.g., `from Instruments.keithley2450_with_add_ons import Keithley2450`).
  2. Inside `startup()`, initialize your new instrument variable:
     `self.NewInstrument = InstrumentDriverClass("VISA_ADDRESS")`
  3. Inside the `getmeas(self, t0)` function, fetch your reading from the new 
     instrument:
     `new_val = self.NewInstrument.measure_property()`
  4. Append `new_val` into the `vals` list and remember to add its name to `DATA_COLUMNS`.
  5. Inside `shutdown(self):`, write clean-up behaviors (like `self.NewInstrument.close()`) 
     to ensure the software drops its hardware reservations gracefully.

===============================================================================
4. MISCELLANEOUS SETTINGS & TIPS
===============================================================================

  - Parameter Passing: Variables like `Resistor` or `Contacts` are metadata stored 
    in your CSV output. If you replace or upgrade samples, alter these strings 
    in your parameters so your archive remains intelligible.
  - Sleep Timers: If you want to run sequences where you sweep a gate, wait for 
    equilibrium, and sweep a field, you can do this by using standard Python 
    `time.sleep(...)` between procedure calls in `Main.py`.