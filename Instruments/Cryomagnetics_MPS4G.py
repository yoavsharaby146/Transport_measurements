# Cryomagnetics MPS 4G Magnet Power Supply Controller
#
# This module provides a Python interface for controlling the Cryromagnetics 4GMPS
# magnet power supply via serial communication.
#
# Command reference: https://cryomagnetics.com/wp-content/uploads/2022/05/4G-Rev-9_3.pdf
#
# Key properties/methods for typical use:
#   - magnet_field: Get/set the current magnetic field in Tesla
#   - go_to_target_field(): Sweep to a target field value
#   - sweep_mode: Set sweep direction (UP, DOWN, ZERO, FAST, SLOW)
#   - persistent_switch_heater: Control the persistent switch heater (ON/OFF)
#
# Written by YOAV SHARABY

import serial
import time


class Cryomagnetics_MPS4G:
    """Controller for the Cryomagnetics MPS 4G magnet power supply.
    
    This class provides a high-level interface for controlling the magnet power supply,
    including magnetic field control, sweep operations, and configuration settings.
    
    Attributes:
        port: Serial port identifier (e.g., 'COM3' or '/dev/ttyUSB0')
        baudrate: Communication baud rate
        timeout: Serial read timeout in seconds
    """
    
    def __init__(self, port, baudrate, timeout):
        """Initialize connection to the magnet power supply.
        
        Args:
            port: Serial port identifier (e.g., 'COM3' or '/dev/ttyUSB0')
            baudrate: Communication baud rate
            timeout: Serial read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

    # =========================================================================
    # Serial Communication Methods
    # =========================================================================
    
    def open(self):
        """Open the serial connection to the instrument."""
        if not self.serial.is_open:
            self.serial.open()

    def close(self):
        """Close the serial connection to the instrument."""
        if self.serial.is_open:
            self.serial.close()

    def write(self, data):
        """Write data to the instrument.
        
        Args:
            data: Bytes or string to send
        """
        self.serial.write(data)

    def read(self, bytes_to_read):
        """Read data from the instrument.
        
        Args:
            bytes_to_read: Number of bytes to read
            
        Returns:
            Bytes read from the instrument
        """
        return self.serial.read(bytes_to_read)

    # =========================================================================
    # Error Response Property
    # =========================================================================
    
    @property
    def error_response(self):
        """Get the current error response mode.
        
        Returns:
            int: 0 if error reporting is disabled, 1 if enabled
        """
        self.write(b'ERROR?\n')
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        return int(response_str[8:])
    
    @error_response.setter
    def error_response(self, error_code):
        """Set the error response mode.
        
        Args:
            error_code: 0 to disable error reporting, 1 to enable
        """
        set_error_mode = f'ERROR {error_code}\n'
        self.write(set_error_mode.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Magnetic Field Properties
    # =========================================================================
    
    @property
    def magnet_field(self):
        """Get the current magnetic field in Tesla (T).
        
        The field is calculated from the magnet current using the calibration factor.
        
        Returns:
            float: Current magnetic field in Tesla
        """
        self.write(b'IMAG?\n')
        time.sleep(0.1)
        response = self.read(512)
        response_str = response.decode().strip()
        current = float(response_str[7:-1])
        return 0.96385 * current / 10
    
    @magnet_field.setter
    def magnet_field(self, magnet_field):
        """Set the magnet current based on the desired field in Tesla.
        
        Note: This sets the current directly. For sweeping to a target field,
        use go_to_target_field() instead.
        
        Args:
            magnet_field: Desired magnetic field in Tesla
        """
        current = 1.0375 * magnet_field * 10
        set_magnet_current = f'IMAG {current}\n'
        self.write(set_magnet_current.encode('utf-8'))
        self.read(1000)

    @property
    def ps_output(self):
        """Get the output current from the power supply in Amps.
        
        Returns:
            float: Power supply output current in Amps
        """
        self.write(b'IOUT?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])

    # =========================================================================
    # Split Read/Write Methods for Advanced Use
    # =========================================================================
    
    def magnet_field_write_query(self):
        """Send the magnet field query command without reading response.
        
        Use magnet_field_read_response() to retrieve the result.
        Useful for timing-sensitive operations.
        """
        self.write(b'IMAG?\n')

    def magnet_field_read_response(self):
        """Read the response from a previous magnet field query.
        
        Must be called after magnet_field_write_query().
        
        Returns:
            float: Current magnetic field in Tesla
        """
        response = self.read(512)
        response_str = response.decode().strip()
        current = float(response_str[7:-1])
        return 0.96385 * current / 10

    # =========================================================================
    # Sweep Limit Properties
    # =========================================================================
    
    @property
    def low_current_sweep_limit(self):
        """Get the lower sweep current limit in Tesla equivalent.
        
        When sweeping DOWN, the magnet will sweep to this limit.
        
        Returns:
            float: Lower sweep limit in Tesla
        """
        self.write(b'LLIM?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])
    
    @low_current_sweep_limit.setter
    def low_current_sweep_limit(self, magnet_field):
        """Set the lower sweep current limit.
        
        Args:
            magnet_field: Lower sweep limit in Tesla
        """
        current = 1.0375 * magnet_field * 10
        set_low_limit_sweep = f'LLIM {current}\n'
        self.write(set_low_limit_sweep.encode('utf-8'))
        self.read(1000)

    @property
    def high_current_sweep_limit(self):
        """Get the upper sweep current limit in Tesla equivalent.
        
        When sweeping UP, the magnet will sweep to this limit.
        
        Returns:
            float: Upper sweep limit in Tesla
        """
        self.write(b'ULIM?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])
    
    @high_current_sweep_limit.setter
    def high_current_sweep_limit(self, magnet_field):
        """Set the upper sweep current limit.
        
        Args:
            magnet_field: Upper sweep limit in Tesla
        """
        current = 1.0375 * magnet_field * 10
        set_upper_limit_sweep = f'ULIM {current}\n'
        self.write(set_upper_limit_sweep.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Operating Mode Property
    # =========================================================================
    
    @property
    def operating_mode(self):
        """Get the current operating mode.
        
        Returns:
            str: Operating mode (e.g., 'Manual' or 'SHIM')
        """
        self.write(b'MODE?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return response_str[7:]

    # =========================================================================
    # Coil Name Property
    # =========================================================================
    
    @property
    def coil_name(self):
        """Get the coil name identifier.
        
        Returns:
            str: Name of the coil
        """
        self.write(b'NAME?\n')
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        return response_str[7:]
    
    @coil_name.setter
    def coil_name(self, coil_name):
        """Set the coil name identifier.
        
        Args:
            coil_name: Name to assign to the coil
        """
        change_name = f'NAME {coil_name}\n'
        self.write(change_name.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Persistent Switch Heater Property
    # =========================================================================
    
    @property
    def persistent_switch_heater(self):
        """Get the persistent switch heater state.
        
        WARNING: The heater must be ON before using the magnet!
        
        Returns:
            str: Heater state ('ON' or 'OFF')
        """
        self.write(b'PSHTR?\n')
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        return response_str[8:]
    
    @persistent_switch_heater.setter
    def persistent_switch_heater(self, state):
        """Set the persistent switch heater state.
        
        WARNING: The heater must be ON before using the magnet!
        Normally the heater is always ON when magnet current is controlled.
        
        Args:
            state: 'ON' or 'OFF'
        """
        set_heater = f'PSHTR {state}\n'
        self.write(set_heater.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Quench Reset
    # =========================================================================
    
    def reset_quench_condition(self):
        """Reset a power supply quench condition.
        
        After a quench event, this command returns the supply to STANDBY mode.
        """
        self.write(b'QRESET\n')
        self.read(1000)

    # =========================================================================
    # Current Range Properties (0-4)
    # =========================================================================
    
    @property
    def current_range0(self):
        """Get the upper limit for charge rate Range 0 in Amps.
        
        Range 0 starts at 0A and ends at this limit.
        
        Returns:
            float: Range 0 upper limit in Amps
        """
        self.write(b'RANGE? 0\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[10:])
    
    @current_range0.setter
    def current_range0(self, range0):
        """Set the upper limit for charge rate Range 0.
        
        Args:
            range0: Upper limit in Amps
        """
        self.write(f'RANGE 0 {range0}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_range1(self):
        """Get the upper limit for charge rate Range 1 in Amps.
        
        Range 1 starts at Range 0 limit and ends at this limit.
        
        Returns:
            float: Range 1 upper limit in Amps
        """
        self.write(b'RANGE? 1\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[10:])
    
    @current_range1.setter
    def current_range1(self, range1):
        """Set the upper limit for charge rate Range 1.
        
        Args:
            range1: Upper limit in Amps
        """
        self.write(f'RANGE 1 {range1}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_range2(self):
        """Get the upper limit for charge rate Range 2 in Amps.
        
        Range 2 starts at Range 1 limit and ends at this limit.
        
        Returns:
            float: Range 2 upper limit in Amps
        """
        self.write(b'RANGE? 2\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[10:])
    
    @current_range2.setter
    def current_range2(self, range2):
        """Set the upper limit for charge rate Range 2.
        
        Args:
            range2: Upper limit in Amps
        """
        self.write(f'RANGE 2 {range2}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_range3(self):
        """Get the upper limit for charge rate Range 3 in Amps.
        
        Range 3 starts at Range 2 limit and ends at this limit.
        
        Returns:
            float: Range 3 upper limit in Amps
        """
        self.write(b'RANGE? 3\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[10:])
    
    @current_range3.setter
    def current_range3(self, range3):
        """Set the upper limit for charge rate Range 3.
        
        Args:
            range3: Upper limit in Amps
        """
        self.write(f'RANGE 3 {range3}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_range4(self):
        """Get the upper limit for charge rate Range 4 in Amps.
        
        Range 4 starts at Range 3 limit and ends at supply output capacity.
        
        Returns:
            float: Range 4 upper limit in Amps
        """
        self.write(b'RANGE? 4\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[10:])
    
    @current_range4.setter
    def current_range4(self, range4):
        """Set the upper limit for charge rate Range 4.
        
        Args:
            range4: Upper limit in Amps
        """
        self.write(f'RANGE 4 {range4}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    # =========================================================================
    # Current Rate Properties (0-5)
    # =========================================================================
    
    @property
    def current_rate0(self):
        """Get the charge rate for Range 0 in Amps/second.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 0\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate0.setter
    def current_rate0(self, rate0):
        """Set the charge rate for Range 0.
        
        Args:
            rate0: Charge rate in Amps/second
        """
        self.write(f'RATE 0 {rate0}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_rate1(self):
        """Get the charge rate for Range 1 in Amps/second.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 1\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate1.setter
    def current_rate1(self, rate1):
        """Set the charge rate for Range 1.
        
        Args:
            rate1: Charge rate in Amps/second
        """
        self.write(f'RATE 1 {rate1}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_rate2(self):
        """Get the charge rate for Range 2 in Amps/second.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 2\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate2.setter
    def current_rate2(self, rate2):
        """Set the charge rate for Range 2.
        
        Args:
            rate2: Charge rate in Amps/second
        """
        self.write(f'RATE 2 {rate2}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_rate3(self):
        """Get the charge rate for Range 3 in Amps/second.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 3\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate3.setter
    def current_rate3(self, rate3):
        """Set the charge rate for Range 3.
        
        Args:
            rate3: Charge rate in Amps/second
        """
        self.write(f'RATE 3 {rate3}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_rate4(self):
        """Get the charge rate for Range 4 in Amps/second.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 4\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate4.setter
    def current_rate4(self, rate4):
        """Set the charge rate for Range 4.
        
        Args:
            rate4: Charge rate in Amps/second
        """
        self.write(f'RATE 4 {rate4}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    @property
    def current_rate5(self):
        """Get the charge rate for Fast mode in Amps/second.
        
        Range 5 corresponds to the Fast mode sweep rate.
        
        Returns:
            float: Charge rate in A/s
        """
        self.write(b'RATE? 5\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[9:])
    
    @current_rate5.setter
    def current_rate5(self, rate5):
        """Set the charge rate for Fast mode.
        
        Args:
            rate5: Charge rate in Amps/second
        """
        self.write(f'RATE 5 {rate5}\n'.encode('utf-8'))
        time.sleep(0.1)
        self.read(1000)

    # =========================================================================
    # Remote Mode
    # =========================================================================
    
    def remote(self):
        """Enable remote control mode.
        
        This disables buttons on the power supply front panel except LOCAL.
        Required before sending sweep commands.
        """
        self.write(b'REMOTE\n')
        self.read(1000)

    # =========================================================================
    # Sweep Mode Property
    # =========================================================================
    
    @property
    def sweep_mode(self):
        """Get the current sweep mode status.
        
        Returns:
            str: Current sweep mode/status
        """
        self.write(b'SWEEP?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return response_str[8:]
    
    @sweep_mode.setter
    def sweep_mode(self, sweep_mode):
        """Set the sweep mode to control output current.
        
        The SWEEP command causes the power supply to sweep the output current
        from the present current to the specified limit at the applicable charge rate.
        
        Valid modes:
            - 'UP': Sweep to upper limit (ULIM)
            - 'DOWN': Sweep to lower limit (LLIM)
            - 'ZERO': Discharge the supply (sweep to zero)
            - 'FAST': Use fast mode rate
            - 'SLOW': Return to normal rate mode
        
        Args:
            sweep_mode: Sweep direction/mode string
        """
        self.write(f'SWEEP {sweep_mode}\n'.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Units Property
    # =========================================================================
    
    @property
    def units(self):
        """Get the current units setting.
        
        Returns:
            str: 'A' for Amps or 'G' for Gauss
        """
        self.write(b'UNITS?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return response_str[8:]
    
    @units.setter
    def units(self, units):
        """Set the units for the power supply.
        
        Convention is to use Amps ('A') at all times.
        
        Args:
            units: 'A' for Amps or 'G' for Gauss
        """
        self.write(f'UNITS {units}\n'.encode('utf-8'))
        self.read(1000)

    # =========================================================================
    # Voltage Properties
    # =========================================================================
    
    @property
    def voltage_limit(self):
        """Get the power supply output voltage limit.
        
        Returns:
            float: Voltage limit in Volts
        """
        self.write(b'VLIM?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])
    
    @voltage_limit.setter
    def voltage_limit(self, voltage_limit):
        """Set the power supply output voltage limit.
        
        Args:
            voltage_limit: Voltage limit in Volts
        """
        self.write(f'VLIM {voltage_limit}\n'.encode('utf-8'))
        self.read(1000)

    @property
    def magnet_voltage(self):
        """Get the present magnet voltage.
        
        Returns:
            float: Magnet voltage in Volts
        """
        self.write(b'VMAG?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])

    @property
    def output_voltage(self):
        """Get the present power supply output voltage.
        
        Returns:
            float: Output voltage in Volts
        """
        self.write(b'VOUT?\n')
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        return float(response_str[7:-1])

    # =========================================================================
    # High-Level Control Methods
    # =========================================================================
    
    def go_to_target_field(self, target_field):
        """Sweep the magnetic field to a target value.
        
        This method automatically determines the sweep direction based on the
        current field and target field values, sets the appropriate limit,
        and initiates the sweep.
        
        Args:
            target_field: Target magnetic field in Tesla
        """
        current_field = self.magnet_field

        if target_field == 0:
            self.sweep_mode = "ZERO"
        elif target_field > current_field:
            self.high_current_sweep_limit = target_field
            self.sweep_mode = "UP"
        elif target_field < current_field:
            self.low_current_sweep_limit = target_field
            self.sweep_mode = "DOWN"