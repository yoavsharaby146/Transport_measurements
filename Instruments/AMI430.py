# AMI (American Magnetics) Model 430 Magnet Power Supply Controller
#
# This module provides a Python interface for controlling the AMI 430 series
# magnet power supply via VISA (Ethernet socket on port 7180 or RS-232).
#
# Command reference: AMI Model 430 Programmer's Reference Manual
#
# Key properties/methods for typical use:
#   - magnet_field: Get the current magnetic field in Tesla (FIELD:MEAS?)
#   - target_field: Get/set the ramp target field in Tesla (FIELD:TAR)
#   - go_to_target_field(): Set target and start the ramp, wait until done
#   - ramp_rate: Get/set the field ramp rate in Tesla/s
#   - ps_heater: Control the persistent switch heater (PS:EN ON/OFF)
#   - ramp(): / pause(): / zero_field(): ramp control
#
# Written by YOAV SHARABY

import time

import pyvisa


class AMI430:
    """Controller for the AMI Model 430 magnet power supply.

    This class provides a high-level interface for controlling the magnet power
    supply, including magnetic field control, ramp operations, and the
    persistent switch heater.

    The AMI430 communicates over Ethernet (raw TCP socket, port 7180) or
    RS-232. Pass the matching VISA resource address:
        Ethernet: 'TCPIP0::192.168.0.10::7180::SOCKET'
        Serial:   'ASRL3::INSTR'

    Attributes:
        visa_address: VISA resource address of the instrument
        field_units: Field units used by the supply ('TESLA' by default)
    """

    #: RAMPSTATE? return codes -> meaning
    RAMP_STATES = {
        1: 'RAMPING',
        2: 'RAMP HOLD',
        3: 'PAUSING',
        4: 'PAUSED',
        5: 'QUENCH',
        6: 'AT ZERO',
        7: 'HOLDING ERROR',
        8: 'AT TARGET',
    }

    def __init__(self, visa_address, field_units='TESLA', **kwargs):
        """Initialize connection to the magnet power supply.

        Args:
            visa_address: VISA resource address, e.g.
                'TCPIP0::192.168.0.10::7180::SOCKET' or 'ASRL3::INSTR'
            field_units: Field units to configure on connect
                ('TESLA', 'KG', 'OERSTED', or 'AMPERE'). Default 'TESLA'.
            **kwargs: Extra keyword args passed to pyvisa open_resource()
                (e.g. baud_rate=115200 for serial).
        """
        self.visa_address = visa_address
        rm = pyvisa.ResourceManager()
        self.instrument = rm.open_resource(
            visa_address,
            read_termination='\n',
            write_termination='\n',
            **kwargs,
        )
        self.instrument.timeout = 5000
        self.field_units = field_units

    # =========================================================================
    # Communication Methods
    # =========================================================================

    def open(self):
        """Open the connection to the instrument."""
        if not self.instrument.session:
            self.instrument.open()

    def close(self):
        """Close the connection to the instrument."""
        self.instrument.close()

    def write(self, command):
        """Send a command to the instrument.

        Args:
            command: Command string (no terminator needed)
        """
        self.instrument.write(command)

    def read(self):
        """Read a response line from the instrument.

        Returns:
            str: Response string with terminator stripped
        """
        return self.instrument.read()

    def query(self, command):
        """Send a query command and return the response.

        Args:
            command: Query string (should end in '?')

        Returns:
            str: Response string stripped of whitespace
        """
        return self.instrument.query(command).strip()

    def wait_operation_complete(self):
        """Block until all pending operations complete (*OPC?)."""
        self.query('*OPC?')

    # =========================================================================
    # Identification / System
    # =========================================================================

    @property
    def idn(self):
        """Get the instrument identification string (*IDN?).

        Returns:
            str: e.g. 'AMI430,12345,0,1.00'
        """
        return self.query('*IDN?')

    def reset(self):
        """Reset the instrument to power-up defaults (*RST)."""
        self.write('*RST')

    # =========================================================================
    # Configuration Properties
    # =========================================================================

    @property
    def field_units(self):
        """Get the configured field units.

        Returns:
            str: 'TESLA', 'KG', 'OERSTED', or 'AMPERE'
        """
        response = self.query('CONF:FIELD:UNITS?')
        return response.split()[-1]

    @field_units.setter
    def field_units(self, units):
        """Set the field units used by the supply.

        Convention is to use 'TESLA' at all times.

        Args:
            units: 'TESLA', 'KG', 'OERSTED', or 'AMPERE'
        """
        units = units.upper()
        if units not in ('TESLA', 'KG', 'OERSTED', 'AMPERE'):
            raise ValueError(
                f"Invalid units '{units}'. Use 'TESLA', 'KG', 'OERSTED' or 'AMPERE'"
            )
        self.write(f'CONF:FIELD:UNITS {units}')
        self.wait_operation_complete()

    @property
    def coil_constant(self):
        """Get the magnet coil constant (COIL?).

        Returns:
            float: Coil constant in Tesla per Ampere
        """
        response = self.query('COIL?')
        return float(response.split()[-1])

    @property
    def magnet_current_limit(self):
        """Get the magnet current limit in Amperes.

        Returns:
            float: Current limit in Amps
        """
        response = self.query('CONF:CURR:LIM?')
        return float(response.split()[-1])

    @property
    def voltage_limit(self):
        """Get the power supply voltage limit in Volts.

        Returns:
            float: Voltage limit in Volts
        """
        response = self.query('CONF:VOLT:LIM?')
    # =========================================================================
    # Field Ramp Properties
    # =========================================================================

    @property
    def ramp_rate(self):
        """Get the field ramp rate of the first ramp segment.

        Returns:
            float: Ramp rate in Tesla per second
        """
        # Response: 'CONF:RAMP:RATE:FIELD <rate>,<units code>'
        # units code: 0=A/s, 1=T/s, 2=kG/s, 3=Oe/s
        response = self.query('CONF:RAMP:RATE:FIELD?')
        value = float(response.split()[-1].split(',')[0])
        return value

    @ramp_rate.setter
    def ramp_rate(self, rate):
        """Set a single-segment field ramp rate.

        This rewrites the ramp table with a single segment.

        Args:
            rate: Ramp rate in Tesla per second
        """
        self.write(f'CONF:RAMP:RATE:FIELD {rate},T/S')
        self.wait_operation_complete()

    @property
    def target_field(self):
        """Get the programmed target field.

        Returns:
            float: Target field in Tesla
        """
        response = self.query('FIELD:TAR?')
        return float(response.split()[-1])

    @target_field.setter
    def target_field(self, field):
        """Set the target field for the next ramp.

        Does not start the ramp; call ramp() or go_to_target_field().

        Args:
            field: Target field in Tesla
        """
        self.write(f'FIELD:TAR {field}')
        self.wait_operation_complete()

    # =========================================================================
    # Measurement Properties
    # =========================================================================

    @property
    def magnet_field(self):
        """Get the present measured magnetic field.

        Returns:
            float: Field in Tesla
        """
        response = self.query('FIELD:MEAS?')
        return float(response.split()[-1])

    @property
    def setpoint_field(self):
        """Get the programmed setpoint the supply is ramping to (FIELD:MAG:SET?).

        Returns:
            float: Programmed field setpoint in Tesla
        """
        response = self.query('FIELD:MAG:SET?')
        return float(response.split()[-1])

    @property
    def magnet_current(self):
        """Get the present magnet current (CURR:MEAS?).

        Returns:
            float: Current in Amps
        """
        response = self.query('CURR:MEAS?')
        return float(response.split()[-1])

    @property
    def magnet_voltage(self):
        """Get the present magnet voltage (VOLT:MEAS?).

        Returns:
            float: Voltage in Volts
        """
        response = self.query('VOLT:MEAS?')
        return float(response.split()[-1])

    # =========================================================================
    # Ramp State
    # =========================================================================

    @property
    def ramp_state_code(self):
        """Get the raw ramp state code (RAMPSTATE?).

        Returns:
            int: 1=RAMPING, 2=RAMP HOLD, 3=PAUSING, 4=PAUSED, 5=QUENCH,
                 6=AT ZERO, 7=HOLDING ERROR, 8=AT TARGET
        """
        response = self.query('RAMPSTATE?')
        return int(response.split()[-1])

    @property
    def ramp_state(self):
        """Get the ramp state as a human readable string.

        Returns:
            str: e.g. 'RAMPING', 'AT TARGET', 'PAUSED'
        """
        return self.RAMP_STATES.get(
            self.ramp_state_code, f'UNKNOWN ({self.ramp_state_code})'
        )

    @property
    def is_ramping(self):
        """Check whether the supply is currently ramping.

        Returns:
            bool: True if RAMPSTATE? returns 1 (RAMPING)
        """
        return self.ramp_state_code == 1

    # =========================================================================
    # Persistent Switch Heater
    # =========================================================================

    @property
    def ps_heater(self):
        """Get the persistent switch heater state (PS:EN?).

        Returns:
            bool: True if the switch heater is ON
        """
        response = self.query('PS:EN?')
        return bool(int(response.split()[-1]))

    @ps_heater.setter
    def ps_heater(self, state):
        """Turn the persistent switch heater ON or OFF.

        Convention when changing field: heater ON, wait for it to warm up,
        ramp, then optionally go persistent.

        Args:
            state: True/False or 'ON'/'OFF'
        """
        if isinstance(state, bool):
            value = 'ON' if state else 'OFF'
        else:
            value = str(state).upper()
        if value not in ('ON', 'OFF'):
            raise ValueError(f"Invalid state '{state}'. Use True/False or 'ON'/'OFF'")
        self.write(f'PS:EN {value}')
        self.wait_operation_complete()

    @property
    def is_persistent(self):
        """Check whether the magnet is in persistent mode (PERS:SW?).

        Returns:
            bool: True if the magnet is persistent
        """
        response = self.query('PERS:SW?')
        return bool(int(response.split()[-1]))

    def go_persistent(self):
        """Ramp the supply current to zero and turn the switch heater off
        (PS:PERS), leaving the magnet stored in persistent mode."""
        self.write('PS:PERS')
        self.wait_operation_complete()

    def go_normal(self):
        """Turn the switch heater on and match the supply current to the
        magnet current (PS:NORM)."""
        self.write('PS:NORM')
        self.wait_operation_complete()

    # =========================================================================
    # Quench Detection
    # =========================================================================

    @property
    def quench_detection(self):
        """Get the quench detection enable state (QU:EN?).

        Returns:
            bool: True if quench detection is enabled
        """
        response = self.query('QU:EN?')
        return bool(int(response.split()[-1]))

    @quench_detection.setter
    def quench_detection(self, state):
        """Enable or disable quench detection.

        Args:
            state: True/False or 'ON'/'OFF'
        """
        if isinstance(state, bool):
            value = 'ON' if state else 'OFF'
        else:
            value = str(state).upper()
        if value not in ('ON', 'OFF'):
            raise ValueError(f"Invalid state '{state}'. Use True/False or 'ON'/'OFF'")
        self.write(f'QU:EN {value}')
        self.wait_operation_complete()

    # =========================================================================
    # High-Level Control Methods
    # =========================================================================

    def ramp(self):
        """Start ramping to the programmed target field (FIELD:RAMP)."""
        self.write('FIELD:RAMP')
        self.wait_operation_complete()

    def pause(self):
        """Pause the ramp and hold the field (FIELD:PAUSE)."""
        self.write('FIELD:PAUSE')
        self.wait_operation_complete()

    def zero_field(self):
        """Ramp the field to zero (FIELD:ZERO)."""
        self.write('FIELD:ZERO')
        self.wait_operation_complete()

    def wait_for_ramp(self, poll_interval=0.5, timeout=3600):
        """Block until the ramp completes or fails.

        Args:
            poll_interval: Seconds between RAMPSTATE? polls
            timeout: Maximum seconds to wait before raising TimeoutError

        Raises:
            TimeoutError: If the ramp does not finish within timeout
            RuntimeError: If the supply reports QUENCH or HOLDING ERROR
        """
        start = time.time()
        while True:
            code = self.ramp_state_code
            if code == 5:
                raise RuntimeError('Magnet quench detected during ramp')
            if code == 7:
                raise RuntimeError('Ramp failed: HOLDING ERROR state')
            if code in (2, 4, 8):
                # RAMP HOLD / PAUSED / AT TARGET
                return
            if time.time() - start > timeout:
                raise TimeoutError(
                    f'Ramp did not complete within {timeout} s '
                    f'(state: {self.ramp_state})'
                )
            time.sleep(poll_interval)

    def go_to_target_field(self, target_field, wait=True, poll_interval=0.5,
                           timeout=3600):
        """Ramp the magnetic field to a target value.

        Sets the target field, starts the ramp, and optionally blocks until
        the supply reports AT TARGET.

        Args:
            target_field: Target magnetic field in Tesla
            wait: If True, block until the ramp completes
            poll_interval: Seconds between state polls while waiting
            timeout: Maximum seconds to wait before raising TimeoutError
        """
        self.target_field = target_field
        self.ramp()
        if wait:
            self.wait_for_ramp(poll_interval=poll_interval, timeout=timeout)


if __name__ == '__main__':
    print(__doc__)
    print('Connect with e.g.:')
    print("  ami = AMI430('TCPIP0::192.168.0.10::7180::SOCKET')")
    print("  ami.go_to_target_field(1.0)   # ramp to 1 T and wait")
    print('  print(ami.magnet_field)       # read field in Tesla')

