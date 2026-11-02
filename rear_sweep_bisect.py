# Rear-terminal sweep bisect round 2 - Keithley 2470.
# Run from repo root:  python rear_sweep_bisect.py <VISA_ADDRESS> [front]
import sys, time
sys.path.insert(0, ".")
from Instruments.keithley2450_with_add_ons import Keithley2450

k = Keithley2450(sys.argv[1])
k.adapter.connection.timeout = 10000
k.adapter.connection.read_termination = "\n"
k.adapter.connection.write_termination = "\n"

front = "front" in sys.argv[2:]
print("IDN:", k.ask("*IDN?"))
if not front and k.check_terminals() != "REAR":
    k.use_rear_terminals()   # only if actually needed - redundant write poisons 2470 sweeps
print("terminals now:", k.check_terminals())

# replicate the real GUI sweep config: >=10 points (21 pts, 100mV step)
k.reset()
if not front and k.check_terminals() != "REAR":
    k.use_rear_terminals()
k.write(':SOUR:CONF:LIST:CRE "sourceVclist"')
k.source_mode = "voltage"
k.measure_current(1, 1e-6, False)
k.disable_source()
for v in [i * 0.1 for i in range(21)]:         # 0.0 .. 2.0 V, 21 points
    k.source_voltage = v
    k.write(':SOUR:CONF:LIST:STORE "sourceVclist";')
k.write('TRAC:MAKE "sweepBuffer", 21;')
print("clist stored. errors:", k.ask(":SYST:ERR?"))
k.write(':SOUR:SWE:VOLT:LIST 1, 0.1, 1, ON, "sweepBuffer", "sourceVclist"')
print("sweep armed, sending INIT...")
k.write("INIT")

on_seen = False
for i in range(75):                            # 15 s, poll every 0.2 s
    try:
        on = k.source_enabled
    except Exception as e:
        on = f"query-error: {e}"
    if on is True:
        on_seen = True
    if i % 5 == 0:                             # print every 1 s
        print(f"t={i*0.2:.1f}s output:", on)
    time.sleep(0.2)
print("output EVER turned on:", on_seen)
print("errors:", k.ask(":SYST:ERR?"))
try:
    print("buffer:", k.ask('TRAC:DATA? 1, 21, "sweepBuffer", READ, SOUR, REL;'))
except Exception as e:
    print("buffer read failed:", e)
print("done")
