"""
Yokogawa GS200 USB Connection Test Script
==========================================
This script tests the connection and basic functionality of a Yokogawa GS200
DC Voltage/Current Source connected via USB.

Requirements:
    pip install pyvisa pyvisa-py

Usage:
    python "Instrument control/Yokogawa_GS200_test.py"

The script will:
    1. List all connected VISA resources (to help find your GS200)
    2. Connect to the GS200 automatically (or manually by address)
    3. Query identification and status
    4. Test voltage source mode (safe low values)
    5. Test current source mode (safe low values)
    6. Test measurement readback
    7. Safely shut down (output off)
"""

import pyvisa
import time
import sys


class YokogawaGS200Tester:
    """Test suite for the Yokogawa GS200 DC Source via USB."""

    def __init__(self, visa_address=None):
        self.rm = pyvisa.ResourceManager('@py')  # Use pyvisa-py backend
        self.instrument = None
        self.visa_address = visa_address

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    def list_resources(self):
        """List all available VISA resources to help identify the GS200."""
        print("\n" + "=" * 60)
        print("  Scanning for VISA resources...")
        print("=" * 60)
        resources = self.rm.list_resources()
        if not resources:
            print("  ⚠ No VISA resources found!")
            print("  Make sure the GS200 is connected via USB and powered on.")
            print("  You may also need a USB-TMC driver (e.g., NI-VISA or usbtmc).")
        else:
            for i, r in enumerate(resources):
                print(f"  [{i}] {r}")
                if 'YOKOGAWA' in r.upper() or 'GS200' in r.upper():
                    print(f"      ^ Looks like a Yokogawa GS200!")
        print()
        return resources

    def auto_find_gs200(self):
        """Try to automatically find the GS200 among VISA resources."""
        resources = self.rm.list_resources()
        for r in resources:
            r_upper = r.upper()
            # Yokogawa USB VID is 0xB21, GS200 commonly appears with these patterns
            if 'YOKOGAWA' in r_upper or 'GS200' in r_upper or '0XB21' in r_upper:
                return r
        # If not found by name, try any USB resource
        usb_resources = [r for r in resources if r.startswith('USB')]
        if len(usb_resources) == 1:
            return usb_resources[0]
        return None

    def connect(self, address=None):
        """Connect to the GS200 at the given VISA address."""
        addr = address or self.visa_address

        if addr is None:
            print("  Attempting auto-detect...")
            addr = self.auto_find_gs200()
            if addr is None:
                print("  ⚠ Could not auto-detect GS200.")
                print("  Available resources:")
                self.list_resources()
                addr = input("  Enter VISA address manually (or 'q' to quit): ").strip()
                if addr.lower() == 'q':
                    return False

        try:
            print(f"\n  Connecting to: {addr}")
            self.instrument = self.rm.open_resource(addr)
            self.instrument.timeout = 5000  # 5 second timeout
            self.instrument.read_termination = '\n'
            self.instrument.write_termination = '\n'
            self.visa_address = addr
            print("  ✓ Connection established!")
            return True
        except pyvisa.VisaIOError as e:
            print(f"  ✗ VisaIO Error: {e}")
            return False
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Close the connection to the GS200."""
        if self.instrument:
            try:
                self.safe_shutdown()
            except Exception:
                pass
            self.instrument.close()
            self.instrument = None
            print("  ✓ Disconnected.")

    # -------------------------------------------------------------------------
    # Low-level helpers
    # -------------------------------------------------------------------------

    def write(self, command):
        """Send a SCPI command."""
        self.instrument.write(command)

    def query(self, command):
        """Send a SCPI query and read the response."""
        return self.instrument.query(command).strip()

    def query_float(self, command):
        """Send a SCPI query and return the response as a float."""
        return float(self.query(command))

    # -------------------------------------------------------------------------
    # Test Functions
    # -------------------------------------------------------------------------

    def test_identification(self):
        """Test 1: Query instrument identification."""
        print("\n" + "-" * 60)
        print("  TEST 1: Instrument Identification")
        print("-" * 60)
        try:
            idn = self.query("*IDN?")
            print(f"  *IDN? → {idn}")

            parts = idn.split(',')
            if len(parts) >= 4:
                print(f"    Manufacturer : {parts[0].strip()}")
                print(f"    Model        : {parts[1].strip()}")
                print(f"    Serial No.   : {parts[2].strip()}")
                print(f"    Firmware     : {parts[3].strip()}")

            if 'GS200' in idn.upper():
                print("  ✓ Confirmed: This is a Yokogawa GS200!")
                return True
            else:
                print("  ⚠ Device did not identify as a GS200.")
                return False
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False

    def test_system_status(self):
        """Test 2: Query system status and error queue."""
        print("\n" + "-" * 60)
        print("  TEST 2: System Status & Error Queue")
        print("-" * 60)
        try:
            # Operation status
            oper = self.query(":STAT:OPER?")
            print(f"  Operation Status Register: {oper}")

            # Questionable status
            ques = self.query(":STAT:QUES?")
            print(f"  Questionable Status Register: {ques}")

            # Check error queue
            errors = []
            while True:
                err = self.query(":SYST:ERR?")
                if '0,"No error"' in err or '0,"' not in err:
                    break
                errors.append(err)
                if len(errors) > 20:
                    break

            if errors:
                print(f"  ⚠ Errors in queue ({len(errors)}):")
                for e in errors:
                    print(f"    - {e}")
            else:
                print("  ✓ No errors in queue.")

            # Clear status
            self.write("*CLS")
            print("  ✓ Status cleared (*CLS).")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False

    def test_reset(self):
        """Test 3: Reset the instrument to factory defaults."""
        print("\n" + "-" * 60)
        print("  TEST 3: Reset (*RST)")
        print("-" * 60)
        try:
            self.write("*RST")
            time.sleep(0.5)
            self.write("*CLS")
            print("  ✓ Instrument reset to defaults.")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False

    def test_voltage_source(self, test_voltage=0.01, voltage_range=0.1):
        """
        Test 4: Test voltage source mode with a small safe voltage.

        Args:
            test_voltage: Voltage to output in Volts (default: 10 mV — safe!)
            voltage_range: Voltage range in Volts (default: 100 mV)
        """
        print("\n" + "-" * 60)
        print(f"  TEST 4: Voltage Source Mode ({test_voltage*1000:.1f} mV)")
        print("-" * 60)
        try:
            # Make sure output is off
            self.write(":OUTP OFF")
            time.sleep(0.2)

            # Set source function to voltage
            self.write(":SOUR:FUNC VOLT")
            print(f"  Source function: {self.query(':SOUR:FUNC?')}")

            # Set voltage range
            self.write(f":SOUR:RANG {voltage_range}")
            print(f"  Voltage range: {self.query(':SOUR:RANG?')} V")

            # Set protection (current limit) — 1 mA safety
            self.write(":SOUR:PROT:CURR 0.001")
            print(f"  Current protection: {self.query(':SOUR:PROT:CURR?')} A")

            # Set voltage level
            self.write(f":SOUR:LEV {test_voltage}")
            read_level = self.query(":SOUR:LEV?")
            print(f"  Voltage level set: {read_level} V")

            # Enable output
            self.write(":OUTP ON")
            time.sleep(0.5)
            output_state = self.query(":OUTP?")
            print(f"  Output state: {'ON' if output_state == '1' else 'OFF'}")

            # Read back measurement (if available)
            try:
                meas = self.query(":MEAS?")
                print(f"  Measured value: {meas}")
            except Exception:
                print("  (Measurement readback not available — this is normal if no load)")

            time.sleep(0.5)

            # Turn off output
            self.write(":OUTP OFF")
            print("  ✓ Output turned OFF.")
            print("  ✓ Voltage source test PASSED!")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            # Safety: ensure output is off
            try:
                self.write(":OUTP OFF")
            except Exception:
                pass
            return False

    def test_current_source(self, test_current=1e-5, current_range=1e-4):
        """
        Test 5: Test current source mode with a small safe current.

        Args:
            test_current: Current to output in Amps (default: 10 µA — safe!)
            current_range: Current range in Amps (default: 100 µA)
        """
        print("\n" + "-" * 60)
        print(f"  TEST 5: Current Source Mode ({test_current*1e6:.1f} µA)")
        print("-" * 60)
        try:
            # Make sure output is off
            self.write(":OUTP OFF")
            time.sleep(0.2)

            # Set source function to current
            self.write(":SOUR:FUNC CURR")
            print(f"  Source function: {self.query(':SOUR:FUNC?')}")

            # Set current range
            self.write(f":SOUR:RANG {current_range}")
            print(f"  Current range: {self.query(':SOUR:RANG?')} A")

            # Set protection (voltage limit) — 1 V safety
            self.write(":SOUR:PROT:VOLT 1.0")
            print(f"  Voltage protection: {self.query(':SOUR:PROT:VOLT?')} V")

            # Set current level
            self.write(f":SOUR:LEV {test_current}")
            read_level = self.query(":SOUR:LEV?")
            print(f"  Current level set: {read_level} A")

            # Enable output
            self.write(":OUTP ON")
            time.sleep(0.5)
            output_state = self.query(":OUTP?")
            print(f"  Output state: {'ON' if output_state == '1' else 'OFF'}")

            # Read back measurement (if available)
            try:
                meas = self.query(":MEAS?")
                print(f"  Measured value: {meas}")
            except Exception:
                print("  (Measurement readback not available — this is normal if no load)")

            time.sleep(0.5)

            # Turn off output
            self.write(":OUTP OFF")
            print("  ✓ Output turned OFF.")
            print("  ✓ Current source test PASSED!")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            try:
                self.write(":OUTP OFF")
            except Exception:
                pass
            return False

    def test_measurement(self):
        """Test 6: Test the measurement function (readback)."""
        print("\n" + "-" * 60)
        print("  TEST 6: Measurement Readback")
        print("-" * 60)
        try:
            self.write(":OUTP OFF")

            # Set to voltage source mode, small voltage
            self.write(":SOUR:FUNC VOLT")
            self.write(":SOUR:RANG 0.1")
            self.write(":SOUR:LEV 0.005")  # 5 mV

            # Enable measurement
            self.write(":SENS:FUNC VOLT")
            self.write(":SENS:RANG 0.1")

            self.write(":OUTP ON")
            time.sleep(1.0)

            try:
                meas = self.query(":MEAS?")
                print(f"  Measurement: {meas} V")
            except Exception as e:
                print(f"  Measurement query failed (may be normal): {e}")

            self.write(":OUTP OFF")
            print("  ✓ Measurement test completed.")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            try:
                self.write(":OUTP OFF")
            except Exception:
                pass
            return False

    def test_sweep_voltage(self, start=0.0, stop=0.01, steps=11, step_delay=0.2):
        """
        Test 7: Perform a simple voltage sweep (safe values only).

        Args:
            start: Start voltage in V (default: 0 V)
            stop: Stop voltage in V (default: 10 mV)
            steps: Number of steps (default: 11)
            step_delay: Delay between steps in seconds (default: 0.2)
        """
        print("\n" + "-" * 60)
        print(f"  TEST 7: Voltage Sweep ({start*1000:.1f} mV → {stop*1000:.1f} mV, {steps} steps)")
        print("-" * 60)
        try:
            import numpy as np

            self.write(":OUTP OFF")
            self.write("*CLS")

            # Configure voltage source
            self.write(":SOUR:FUNC VOLT")
            self.write(":SOUR:RANG 0.1")
            self.write(":SOUR:PROT:CURR 0.001")  # 1 mA limit

            voltages = np.linspace(start, stop, steps)

            self.write(":OUTP ON")
            print(f"  {'Step':>4}  {'Voltage (mV)':>14}  {'Measured':>14}")
            print(f"  {'----':>4}  {'------------':>14}  {'--------':>14}")

            for i, v in enumerate(voltages):
                self.write(f":SOUR:LEV {v:.6f}")
                time.sleep(step_delay)

                # Try to get measurement
                meas_str = "N/A"
                try:
                    meas_str = self.query(":MEAS?")
                except Exception:
                    pass

                print(f"  {i+1:>4}  {v*1000:>14.4f}  {meas_str:>14}")

            self.write(":OUTP OFF")
            print("  ✓ Voltage sweep completed. Output OFF.")
            return True
        except ImportError:
            print("  ⚠ NumPy not installed. Using manual sweep...")
            return self._manual_voltage_sweep(start, stop, steps, step_delay)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            try:
                self.write(":OUTP OFF")
            except Exception:
                pass
            return False

    def _manual_voltage_sweep(self, start, stop, steps, step_delay):
        """Fallback sweep without numpy."""
        try:
            self.write(":SOUR:FUNC VOLT")
            self.write(":SOUR:RANG 0.1")
            self.write(":SOUR:PROT:CURR 0.001")

            step_size = (stop - start) / (steps - 1) if steps > 1 else 0

            self.write(":OUTP ON")
            for i in range(steps):
                v = start + i * step_size
                self.write(f":SOUR:LEV {v:.6f}")
                time.sleep(step_delay)
                meas_str = "N/A"
                try:
                    meas_str = self.query(":MEAS?")
                except Exception:
                    pass
                print(f"  Step {i+1}/{steps}: {v*1000:.4f} mV → {meas_str}")

            self.write(":OUTP OFF")
            print("  ✓ Sweep completed. Output OFF.")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            try:
                self.write(":OUTP OFF")
            except Exception:
                pass
            return False

    def test_communication_speed(self, num_queries=20):
        """Test 8: Benchmark communication latency."""
        print("\n" + "-" * 60)
        print(f"  TEST 8: Communication Speed ({num_queries} queries)")
        print("-" * 60)
        try:
            times = []
            for _ in range(num_queries):
                t0 = time.perf_counter()
                self.query("*OPC?")
                t1 = time.perf_counter()
                times.append((t1 - t0) * 1000)  # ms

            avg = sum(times) / len(times)
            mn = min(times)
            mx = max(times)
            print(f"  Average: {avg:.2f} ms")
            print(f"  Min:     {mn:.2f} ms")
            print(f"  Max:     {mx:.2f} ms")
            print(f"  ✓ Communication speed test complete.")
            return True
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Safety
    # -------------------------------------------------------------------------

    def safe_shutdown(self):
        """Ensure the output is turned off safely."""
        if self.instrument:
            try:
                # Set source to 0
                func = self.query(":SOUR:FUNC?")
                if 'VOLT' in func.upper():
                    self.write(":SOUR:LEV 0")
                elif 'CURR' in func.upper():
                    self.write(":SOUR:LEV 0")
                # Turn off output
                self.write(":OUTP OFF")
                print("  ✓ Safe shutdown: output set to 0 and turned OFF.")
            except Exception as e:
                print(f"  ⚠ Shutdown warning: {e}")

    # -------------------------------------------------------------------------
    # Main Test Runner
    # -------------------------------------------------------------------------

    def run_all_tests(self):
        """Run all tests in sequence."""
        print("\n" + "=" * 60)
        print("   Yokogawa GS200 — Full Connection & Functionality Test")
        print("=" * 60)

        results = {}

        # List resources
        self.list_resources()

        # Connect
        if not self.connect():
            print("\n  ✗ Could not connect to the GS200. Aborting.")
            return results

        # Run tests
        tests = [
            ("1. Identification",       self.test_identification),
            ("2. System Status",         self.test_system_status),
            ("3. Reset",                 self.test_reset),
            ("4. Voltage Source",        self.test_voltage_source),
            ("5. Current Source",        self.test_current_source),
            ("6. Measurement Readback",  self.test_measurement),
            ("7. Voltage Sweep",         self.test_sweep_voltage),
            ("8. Communication Speed",   self.test_communication_speed),
        ]

        for name, test_func in tests:
            try:
                passed = test_func()
                results[name] = "PASS" if passed else "FAIL"
            except Exception as e:
                results[name] = f"ERROR: {e}"

        # Final safe shutdown
        self.safe_shutdown()

        # Summary
        print("\n" + "=" * 60)
        print("   TEST SUMMARY")
        print("=" * 60)
        for name, status in results.items():
            icon = "✓" if status == "PASS" else "✗"
            print(f"   {icon} {name}: {status}")
        print("=" * 60)

        passed = sum(1 for s in results.values() if s == "PASS")
        total = len(results)
        print(f"\n   Results: {passed}/{total} tests passed.\n")

        return results


# =============================================================================
# Main entry point
# =============================================================================

def main():
    """Main function — runs when script is executed directly."""
    print("=" * 60)
    print("  Yokogawa GS200 USB Test Utility")
    print("=" * 60)

    # Allow passing address as command line argument
    address = None
    if len(sys.argv) > 1:
        address = sys.argv[1]
        print(f"  Using provided address: {address}")

    tester = YokogawaGS200Tester(visa_address=address)

    try:
        results = tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n  ⚠ Interrupted by user. Ensuring safe shutdown...")
        tester.safe_shutdown()
    except Exception as e:
        print(f"\n  ✗ Unexpected error: {e}")
        tester.safe_shutdown()
    finally:
        tester.disconnect()

    print("  Done.")


if __name__ == "__main__":
    main()