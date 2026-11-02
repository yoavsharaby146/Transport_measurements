# Rear-terminal sweep bisect round 3 - Keithley 2470.
# Runs the SAME sweep twice in one session, polling the error queue
# continuously, to catch a silent abort at the moment it happens.
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
    k.use_rear_terminals()   # only if actually needed - see driver note
print("terminals now:", k.check_terminals())


def drain_errors():
    errs = []
    while True:
        e = k.ask(":SYST:ERR?").strip()
        if e.startswith("0,"):
            break
        errs.append(e)
    return errs


def run_sweep(tag):
    print(f"--- sweep {tag} ---")
    k.reset()
    if k.check_terminals() != "REAR":
        k.use_rear_terminals()
    k.write(':SOUR:CONF:LIST:CRE "sourceVclist"')
    k.source_mode = "voltage"
    k.measure_current(1, 1e-6, False)
    k.disable_source()
    for v in [i * 0.1 for i in range(21)]:         # 0.0 .. 2.0 V, 21 points
        k.source_voltage = v
        k.write(':SOUR:CONF:LIST:STORE "sourceVclist";')
    k.write('TRAC:MAKE "sweepBuffer", 21;')
    e = drain_errors()
    if e:
        print(f"{tag} config errors: {e}")
    k.write(':SOUR:SWE:VOLT:LIST 1, 0.1, 1, ON, "sweepBuffer", "sourceVclist"')
    k.write("INIT")

    prev = None
    on_seen = False
    for i in range(75):                            # 15 s, poll every 0.2 s
        try:
            on = k.source_enabled
        except Exception as ex:
            on = f"qerr:{ex}"
        errs = drain_errors()
        stamp = f"t={i*0.2:.1f}s"
        if on != prev:
            print(f"{stamp} {tag} output: {on}")
            prev = on
        if on is True:
            on_seen = True
        if errs:
            print(f"{stamp} {tag} errors: {errs}")
        time.sleep(0.2)
    print(f"{tag}: output EVER on: {on_seen}")
    # probe actual buffer count (read past actual data -> TMO, so step up)
    actual = None
    for n in (1, 2, 5, 10, 15, 18, 20, 21):
        try:
            data = k.ask(f'TRAC:DATA? 1, {n}, "sweepBuffer", READ, SOUR, REL;')
            actual = n
            last = data.split(',')[-1]
            print(f"{tag}: buffer read {n} OK (last REL={last})")
        except Exception:
            print(f"{tag}: buffer read {n} FAILED -> actual count < {n}")
            break
    print(f"{tag}: actual buffer count ~= {actual}")
    e = drain_errors()
    if e:
        print(f"{tag} end errors: {e}")


run_sweep("A")
run_sweep("B")
print("done")
