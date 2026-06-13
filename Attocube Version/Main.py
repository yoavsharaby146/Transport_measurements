"""
Main.py — Master script for the Attocube Version
================================================
Compose measurement sequences by editing this file directly.
Comment/uncomment the procedure blocks you want to run.

Usage:
    python Main.py

Each procedure opens its own live plot window (pymeasure Plotter)
and blocks until the measurement completes.  Procedures are chained
sequentially — you can add time.sleep() delays between them or wrap
them in for-loops to build complex sequences.
"""

import os
import sys
import time
import numpy as np

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from pymeasure.log import console_log

# ---------------------------------------------------------------------------
# Import all procedure modules
# ---------------------------------------------------------------------------
import Rtprocedure
import RVprocedure
import RHprocedure
import RHprocedurePtbyPt
import Rtemprocedure
import Rposprocedure
import Rposprocedure_wobblefix

# ---------------------------------------------------------------------------
# Cryostat connection (TCP/IP server client)
# ---------------------------------------------------------------------------
from RPCPyattoDRYClient import Cryostat

attoDRY = Cryostat(port=1818)


# ---------------------------------------------------------------------------
# Set your data output directory here
# ---------------------------------------------------------------------------
folder_name = r"C:\Users\attocube\Desktop\Data\eyal\AttoCubePython_eyal\Shilo_Eyal_data_files"

# Make sure the folder exists (optional — comment out if you create it manually)
if not os.path.exists(folder_name):
    os.makedirs(folder_name)


# ===========================================================================
#                       MEASUREMENT SEQUENCE BELOW
#         Comment / uncomment / edit the blocks you want to run
# ===========================================================================


###----- Rt: Resistance vs. Time (timed measurement) -----
##Rtprocedure.main(
##    attoDRY,
##    folder_path=folder_name,
##    acq_length=3600,          # acquisition length in seconds (default: 24 hr)
##)


###----- RV: Resistance vs. Gate Voltage -----
##RVprocedure.main(
##    attoDRY,
##    folder_path=folder_name,
##    final_voltage=4.0,        # target gate voltage (V)
##    data_points=50,           # number of steps
##    voltage_delay=3,          # delay between steps (s)
##)


###----- RH: Resistance vs. Magnetic Field -----
##RHprocedure.main(
##    attoDRY,
##    folder_path=folder_name,
##    field_setpoint=9.0,       # target field (T)
##)


###----- RH point-by-point variant -----
##RHprocedurePtbyPt.main(
##    attoDRY,
##    folder_path=folder_name,
##    start_field=0,
##    end_field=1.0,
##    data_points=10,
##    dwell_time=10,
##    field_tol=0.0005,
##)


###----- Rtem: Resistance vs. Temperature -----
##Rtemprocedure.main(
##    attoDRY,
##    folder_path=folder_name,
##    temperature_setpoint=2.5,
##    temperature_delay=2,
##    temperature_step=0.05,
##)


###----- Rpos: Resistance vs. Angular Position -----
##Rposprocedure.main(
##    attoDRY,
##    folder_path=folder_name,
##    ax_str='theta',           # 'theta' (axis 0) or 'phi' (axis 1)
##    final_pos=90,             # target angle (deg)
##    data_points=30,           # number of steps
##    pos_delay=10,             # delay between steps (s)
##    dwell_time=5,             # dwell time (s)
##)


###----- Rpos wobblefix: Resistance vs. Position with wobble correction -----
##Rposprocedure_wobblefix.main(
##    attoDRY,
##    folder_path=folder_name,
##    ax_str='phi',             # scan axis: 'theta' or 'phi'
##    ax_str2='theta',          # fix axis: 'theta' or 'phi'
##    final_pos=90,             # target angle (deg)
##    data_points=30,           # number of steps
##    pos_delay=10,             # delay between steps (s)
##    dwell_time=5,             # dwell time (s)
##)


## ===========================================================================
## Example: Gate hysteresis sequence
## ===========================================================================
##target_gate_voltage = 4
##
##RVprocedure.main(attoDRY, folder_path=folder_name,
##                  final_voltage=target_gate_voltage, data_points=30, voltage_delay=2)
##time.sleep(5)
##
##RVprocedure.main(attoDRY, folder_path=folder_name,
##                  final_voltage=-target_gate_voltage, data_points=30, voltage_delay=2)
##time.sleep(5)
##
##RVprocedure.main(attoDRY, folder_path=folder_name,
##                  final_voltage=0.0, data_points=30, voltage_delay=2)


## ===========================================================================
## Example: Field sweep at multiple gate voltages
## ===========================================================================
##gates = np.linspace(-30, 30, 13)
##
##for Vg in gates:
##    RVprocedure.main(attoDRY, folder_path=folder_name,
##                      final_voltage=Vg, data_points=10, voltage_delay=2)
##    time.sleep(5)
##    RHprocedure.main(attoDRY, folder_path=folder_name, field_setpoint=9)
##    time.sleep(3*60)   # let system stabilise 3 min
##    RHprocedure.main(attoDRY, folder_path=folder_name, field_setpoint=-9)
##    time.sleep(3*60)


## ===========================================================================
## Example: Rotation scan at multiple fields
## ===========================================================================
##fields = [9, -9]
##
##for field in fields:
##    RHprocedure.main(attoDRY, folder_path=folder_name, field_setpoint=field)
##    time.sleep(3*60)
##
##    Rposprocedure.main(attoDRY, folder_path=folder_name,
##                       ax_str='theta', final_pos=90, data_points=50,
##                       pos_delay=5, dwell_time=5)
##    time.sleep(10)
##    Rposprocedure.main(attoDRY, folder_path=folder_name,
##                       ax_str='theta', final_pos=-90, data_points=50,
##                       pos_delay=5, dwell_time=5)


## ===========================================================================
## Example: Temperature sweep with RH at each point
## ===========================================================================
##temperatures = [2.5, 3.5, 5, 8, 10, 15, 20, 30, 50]
##
##for T in temperatures:
##    Rtemprocedure.main(attoDRY, folder_path=folder_name,
##                       temperature_setpoint=T, temperature_delay=2, temperature_step=0.05)
##    time.sleep(3*60)
##    RHprocedure.main(attoDRY, folder_path=folder_name, field_setpoint=9)
##    time.sleep(3*60)
##    RHprocedure.main(attoDRY, folder_path=folder_name, field_setpoint=-9)
##    time.sleep(3*60)


# ---------------------------------------------------------------------------
# Disconnect from the cryostat when done
# ---------------------------------------------------------------------------
attoDRY.Disconnect()
print("Disconnected from attoDRY. All measurements finished.")