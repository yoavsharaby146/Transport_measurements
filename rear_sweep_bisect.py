# Rear-terminal sweep bisect for Keithley 2470 (2450-family SCPI).
# Run from repo root:  python rear_sweep_bisect.py <VISA_ADDRESS>
# Paste full output back.
import sys, time
sys.path.insert(0, ".")
from Instruments.keithley2450_with_add_ons import Keithley2450

k = Keithley2450(sys.argv[1])
k.adapter.connection.timeout = 10000
k.adapter.connection.read_termination = "\n"
k.adapter.connection.write_termination = "\n"

print("IDN:", k.ask("*IDN?"))
print("terminals now:", k.check_terminals())
k.use_rear_terminals()
print("terminals after set:", k.check_terminals())

# replicate the sweep configuration, minimal 2-point clist
k.reset()
k.use_rear_terminals()
k.write(':SOUR:CONF:LIST:CRE "sourceVclist"')
k.source_mode = "voltage"
k.measure_current(1, 1e-6, False)
k.disable_source()
k.source_voltage = 0.001
k.write(':SOUR:CONF:LIST:STORE "sourceVclist";')
k.write('TRAC:MAKE "sweepBuffer", 2;')
k.write(':SOUR:SWE:VOLT:LIST 1, 0.1, 1, ON, "sweepBuffer", "sourceVclist"')
print("sweep armed, sending INIT...")
k.write("INIT")

for i in range(10):
    print(f"t={i}s output:", k.source_enabled, "| err:", k.ask(":SYST:ERR?"))
    time.sleep(1)

print("buffer:", k.ask('TRAC:DATA? 1, 2, "sweepBuffer", READ, SOUR, REL;'))
print("done")
