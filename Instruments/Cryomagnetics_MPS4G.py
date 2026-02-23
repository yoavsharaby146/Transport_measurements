# This bit of code uses the Cyromagnetics_4GMPS  manual providing all the commands used from the computer interface Command summery

# The commands are listed and explained in the magnet power supply manual

# https://cryomagnetics.com/wp-content/uploads/2022/05/4G-Rev-9_3.pdf


# The functions that are mostly used are the
# get_magnet_field and go_to_target_field
# all other functions are mainly for programming the power supply

# Writen by YOAV SHARABY



# Each set function in this file ends with a read command because of traces of previous commands
# have been shown when quarry commands are used

# necessary imports
import serial

# maybe not necessary
import time


class Cryomagnetics_MPS4G:
    # connect to magnet with relevant comport, baudrate, timeout ...
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)


    # utilaze the serial commands for open, close, write and read from instrument
    def open(self):
        if not self.serial.is_open:
            self.serial.open()

    def close(self):
        if self.serial.is_open:
            self.serial.close()

    def write(self, data):
        self.serial.write(data)

    def read(self, bytes_to_read):
        return self.serial.read(bytes_to_read)

    # set and get error response mode, (0 - disable error reporting, 1 - enable error reporting)
    def set_error_response(self, error_code):
        set_error_mode = f'ERROR {error_code}\n'
        self.write(set_error_mode.encode('utf-8'))
        response = self.read(1000)

    def get_error_response(self):
        get_error_mode = b'ERROR?\n'
        self.write(get_error_mode)
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        error = int(response_str[8:])
        return error

    # get and set magnetic field values in Tesla(T)
    # set_magnet_field is not used

    def set_magnet_field(self, magnet_field):
        current = 1.0375 * magnet_field * 10
        set_magnet_current = f'IMAG {current}\n'
        self.write(set_magnet_current.encode('utf-8'))
        response = self.read(1000)

    def get_magnet_field(self):
        get_magnet_current = b'IMAG?\n'
        self.write(get_magnet_current)
        time.sleep(0.1)
        response = self.read(512)
        response_str = response.decode().strip()
        current = float(response_str[7:-1])
        magnet_field = 0.96385 * current / 10
        return magnet_field
    
    # Trying to separate the write and the read to two different functions
    def get_magnet_field_write(self):
        get_magnet_current = b'IMAG?\n'
        self.write(get_magnet_current)

    def get_magnet_field_read(self):
        response = self.read(512)
        response_str = response.decode().strip()
        current = float(response_str[7:-1])
        magnet_field = 0.96385 * current / 10
        return magnet_field
    
    # get the output current from the power supply
    def get_ps_output(self):
        get_power_supply_current = b'IOUT?\n'
        self.write(get_power_supply_current)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    # set and get the current limit for lower limit and upper limit
    # when sweeping field Up goes to upper limit and down field goes to lower limit
    def set_low_current_sweep_limit(self, magnet_field):
        current = 1.0375 * magnet_field * 10
        set_low_limit_sweep = f'LLIM {current}\n'
        self.write(set_low_limit_sweep.encode('utf-8'))
        response = self.read(1000)

    def get_low_current_sweep_limit(self):
        get_low_limit_sweep = b'LLIM?\n'
        self.write(get_low_limit_sweep)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    def set_high_current_sweep_limit(self, magnet_field):
        current = 1.0375 * magnet_field * 10
        set_upper_limit_sweep = f'ULIM {current}\n'
        self.write(set_upper_limit_sweep.encode('utf-8'))
        response = self.read(1000)

    def get_high_current_sweep_limit(self):
        get_high_limit_sweep = b'ULIM?\n'
        self.write(get_high_limit_sweep)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    # get the operating mode that is selected (Manual or SHIM)
    # SHIM is not used
    def get_operating_mode(self):
        get_mode = b'MODE?\n'
        self.write(get_mode)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = response_str[7:]
        return answer

    # get and set the coil name
    def set_coil_name(self, coil_name):
        change_name = f'NAME {coil_name}\n'
        self.write(change_name.encode('utf-8'))
        response = self.read(1000)

    def get_coil_name(self):
        read_name = b'NAME?\n'
        self.write(read_name)
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        name = response_str[7:]
        return name

    # get and set the persistent heater state (ON or OFF)
    # Normally the heater is always ON when magnet current is controlled
    # The heater must be on before using the magnet !!!
    def set_persistent_switch_heater(self, pshtr):
        set_magnet_current = f'PSHTR {pshtr}\n'
        self.write(set_magnet_current.encode('utf-8'))
        response = self.read(1000)
    def get_persistent_switch_heater(self):
        heater_state = b'PSHTR?\n'
        self.write(heater_state)
        time.sleep(0.1)
        response = self.read(2000)
        response_str = response.decode('utf-8', errors='ignore').strip()
        status = response_str[8:]
        return status

    # The QRESET command resets a power supply quench condition and returns the
    # supply to STANDBY
    def reset_quench_condition(self):
        quench_reset = f'QRESET\n'
        self.write(quench_reset.encode('utf-8'))
        response = self.read(1000)

    # set and get the upper limit for a charge rate range in amps.
    # Range 0 starts at 0A and ends at the limit provided.
    # Range 1 starts at the Range 0 limit and ends at the Range 1 limit.
    # Range 2 starts at the Range 1 limit and ends at the Range 2 limit.
    # Range 3 starts at the Range 2 limit and ends at the Range 3 limit.
    # Range 4 starts at the Range 3 limit and ends at the supply output capacity
    def set_current_range0(self, range0):
        set_range0 = f'RANGE 0 {range0}\n'
        self.write(set_range0.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_range1(self, range1):
        set_range1 = f'RANGE 1 {range1}\n'
        self.write(set_range1.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_range2(self, range2):
        set_range2 = f'RANGE 2 {range2}\n'
        self.write(set_range2.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_range3(self, range3):
        set_range3 = f'RANGE 3 {range3}\n'
        self.write(set_range3.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_range4(self, range4):
        set_range4 = f'RANGE 4 {range4}\n'
        self.write(set_range4.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def get_current_range0(self):
        range0 = b'RANGE? 0\n'
        self.write(range0)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[10:])
        return answer
    def get_current_range1(self):
        range1 = b'RANGE? 1\n'
        self.write(range1)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[10:])
        return answer
    def get_current_range2(self):
        range2 = b'RANGE? 2\n'
        self.write(range2)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[10:])
        return answer
    def get_current_range3(self):
        range3 = b'RANGE? 3\n'
        self.write(range3)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[10:])
        return answer
    def get_current_range4(self):
        range4 = b'RANGE? 4\n'
        self.write(range4)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[10:])
        return answer

    # set and get  the charge rate in amps/second for a selected range.
    # A range parameter of 0, 1, 2, 3, and 4 will select Range 1, 2, 3, 4, or 5 sweep
    # rates as displayed in the Rates Menu.
    # A range parameter of 5 selects the Fast mode sweep rate.
    def set_current_rate0(self, rate0):
        set_rate0 = f'RATE 0 {rate0}\n'
        self.write(set_rate0.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_rate1(self, rate1):
        set_rate1 = f'RATE 1 {rate1}\n'
        self.write(set_rate1.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_rate2(self, rate2):
        set_rate2 = f'RATE 2 {rate2}\n'
        self.write(set_rate2.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_rate3(self, rate3):
        set_rate3 = f'RATE 3 {rate3}\n'
        self.write(set_rate3.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_rate4(self, rate4):
        set_rate4 = f'RATE 4  {rate4}\n'
        self.write(set_rate4.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def set_current_rate5(self, rate5):
        set_rate5 = f'RATE 5  {rate5}\n'
        self.write(set_rate5.encode('utf-8'))
        time.sleep(0.1)
        response = self.read(1000)
    def get_current_rate0(self):
        rate0 = b'RATE? 0\n'
        self.write(rate0)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer
    def get_current_rate1(self):
        rate1 = b'RATE? 1\n'
        self.write(rate1)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer
    def get_current_rate2(self):
        rate2 = b'RATE? 2\n'
        self.write(rate2)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer
    def get_current_rate3(self):
        rate3 = b'RATE? 3\n'
        self.write(rate3)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer
    def get_current_rate4(self):
        rate4 = b'RATE? 4\n'
        self.write(rate4)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer
    def get_current_rate5(self):
        rate5 = b'RATE? 5\n'
        self.write(rate5)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[9:])
        return answer

    # set the device to remote mode disabling the buttons on the power supply (except LOCAL)
    def remote(self):
        remote = f'REMOTE\n'
        self.write(remote.encode('utf-8'))
        response = self.read(1000)

    # The SWEEP command causes the power supply to sweep the output current
    # from the present current to the specified limit at the applicable charge rate set
    # by the range and rate commands.
    # If the FAST parameter is given, the fast mode rate will be used instead of a rate
    # selected from the output current range.
    # SLOW is required to change from fast sweep.
    # SWEEP UP sweeps to the Upper limit, SWEEP DOWN sweeps to the Lower limit, and SWEEP ZERO
    # discharges the supply.
    # If in Shim Mode, SWEEP LIMIT sweeps to the shim target current.
    def set_sweep_mode(self, sweep_mode):
        set_sweep = f'SWEEP {sweep_mode}\n'
        self.write(set_sweep.encode('utf-8'))
        response = self.read(1000)
    def get_sweep_mode(self):
        get_sweep_mode = b'SWEEP?\n'
        self.write(get_sweep_mode)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = response_str[8:]
        return answer

    # gets and set the units used in the power supply (A - Amps or G - Gauss)
    # the convention is to use Amps at all times
    def set_units(self, units):
        set_units = f'UNITS {units}\n'
        self.write(set_units.encode('utf-8'))
        response = self.read(1000)
    def get_units(self):
        get_unit = b'UNITS?\n'
        self.write(get_unit)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = response_str[8:]
        return answer

    # set and get the power supply output voltage limit to the voltage
    # provided.
    def set_voltage_limit(self, voltage_limit):
        set_voltage_limit = f'VLIM {voltage_limit}\n'
        self.write(set_voltage_limit.encode('utf-8'))
        response = self.read(1000)
    def get_voltage_limit(self):
        get_voltage_limit = b'VLIM?\n'
        self.write(get_voltage_limit)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    # get the present magnet voltage
    def get_magnet_voltage(self):
        get_magnet_voltage = b'VMAG?\n'
        self.write(get_magnet_voltage)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    # get the present power supply output voltage
    def get_output_voltage(self):
        get_output_voltage = b'VOUT?\n'
        self.write(get_output_voltage)
        time.sleep(0.1)
        response = self.read(1000)
        response_str = response.decode().strip()
        answer = float(response_str[7:-1])
        return answer

    # go_to_target_field gets as a variable the magnetic field the user wants to sweep to
    # and compares with present magnetic field
    # if zero, sweep is changed to ZERO
    # if above present field, high limit is changed to target and SWEEP to UP
    # if below present field, low limit is changed to target and SWEEP to DOWN
    def go_to_target_field(self, target_field):
        current_field = self.get_magnet_field()

        if target_field == 0:
            self.set_sweep_mode("ZERO")

        elif target_field > current_field:
            self.set_high_current_sweep_limit(target_field)
            self.set_sweep_mode("UP")

        elif target_field < current_field:
            self.set_low_current_sweep_limit(target_field)
            self.set_sweep_mode("DOWN")
