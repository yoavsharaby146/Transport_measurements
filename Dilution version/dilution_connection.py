import socket
import time
import numpy as np

class DilutionInstrument:
    """Wrapper for the dilution refrigerator TCP interface.

    The original ``dilution_connection`` class only handled the socket.
    This new class behaves like an "instrument" with helper methods for
    temperature control and magnet commands that were previously scattered
    across ``TemperatureControl.py``, ``Heater.py`` and ``Magnet.py``.

    Usage example::

        instr = DilutionInstrument()
        instr.connect()
        t = instr.get_temperature(8)
        instr.set_temperature(8, rate=0.1, setpoint=0.05)
        instr.close()
    """

    def __init__(self, ip: str = '132.66.132.173', port: int = 33576,
                 timeout: float = 10):
        # connection parameters
        self.timeout_connection = timeout
        self.dilution_address = (ip, port)
        self.dilution_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dilution_socket.settimeout(self.timeout_connection)

    # --- connection management ------------------------------------------------
    def connect(self):
        """Open the TCP connection to the dilution refrigerator."""
        self.dilution_socket.connect(self.dilution_address)

    def send(self, command: str):
        """Send an ASCII command to the instrument.

        The instrument expects newline-terminated strings so callers may omit
        the trailing ``\n``.  ``send`` automatically encodes to UTF-8.
        """
        if not command.endswith("\n"):
            command = command + "\n"
        self.dilution_socket.send(command.encode())

    def recv(self, size: int = 5000) -> bytes:
        """Receive up to ``size`` bytes from the instrument."""
        return self.dilution_socket.recv(size)

    def close(self):
        """Close the connection cleanly."""
        try:
            self.dilution_socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self.dilution_socket.close()

    # -------------------------------------------------------------------------
    # temperature control helpers (originally in TemperatureControl.py)
    # -------------------------------------------------------------------------
    def get_temperature(self, thermometer_num: int) -> float:
        """Read the temperature from a channel.

        Returns ``0.0`` if the response is invalid (text, NOT_FOUN, etc.).
        """
        command = f'READ:DEV:T{thermometer_num}:TEMP:SIG:TEMP'
        while True:
            try:
                self.send(command)
                time.sleep(.06)
                response = self.recv()
                if response:
                    break
            except socket.timeout:
                continue
        text = response.decode().split(":")[-1].strip()
        # the device sometimes appends an extra character
        text = text[:-1] if len(text) and text[-1] not in '0123456789.' else text
        if text.isalpha() or text == 'NOT_FOUN':
            return 0.0
        return float(text)

    def find_range(self, setpoint: float) -> float:
        """Pick a heater range appropriate for a requested temperature."""
        s = float(setpoint)
        if s < 0.03:
            return 1
        if 0.03 <= s <= 0.1:
            return 3.16
        if 0.1 < s < 0.2:
            return 3.16
        if 0.2 <= s <= 1:
            return 10
        if 1 < s <= 3.6:
            return 31.6
        if 3.6 < s < 10:
            return 100
        if 100 < s:
            return 10
        return 10

    def set_heater_range(self, thermometer_num: int, hrange: float):
        """Set the heater range for a given thermometer."""
        command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RANGE:{hrange}'
        self.send(command)

    def init_thermometers(self, thermometer_num: int):
        """Enable only a single thermometer channel; disable all others."""
        for t in range(1, 9):
            if t != thermometer_num:
                self.send(f'SET:DEV:T{t}:TEMP:MEAS:ENAB:OFF')
                time.sleep(.1)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:MEAS:ENAB:ON')
        time.sleep(.1)

    def init_thermometers_and_heaters(self, thermometer_num: int):
        """Turn off any active loops and prepare a single channel for PID."""
        for t in range(1, 9):
            self.send(f'READ:DEV:T{t}:TEMP:LOOP:MODE')
            time.sleep(.1)
            resp = self.recv()
            status = resp.decode().split(":")[-1].strip()
            if status == 'ON':
                self.send(f'SET:DEV:T{t}:TEMP:LOOP:MODE:OFF')
                time.sleep(5)
            if t != thermometer_num:
                self.send(f'SET:DEV:T{t}:TEMP:MEAS:ENAB:OFF')
        time.sleep(.1)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:MEAS:ENAB:ON')
        self.send(f'SET:DEV:TEMP:LOOP:CHAN:T{thermometer_num}')
        time.sleep(.1)
        P, I, D = 10, 10, 10
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:P:{P}:I:{I}:D:{D}')
        time.sleep(.1)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:MODE:ON')
        time.sleep(.1)

    def set_temperature(self, thermometer_num: int, rate: float, setpoint: float):
        """Initiate a PID ramp to ``setpoint`` at the specified ``rate``.

        This roughly mirrors the behavior of the standalone
        ``SetTemperature`` function.
        """
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:ENAB:OFF')
        time.sleep(.03)
        current = self.get_temperature(thermometer_num)
        while current == 0:
            current = self.get_temperature(thermometer_num)
            if current > 300:
                current = 1.3
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:TSET:{current}')
        time.sleep(.03)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:RATE:{rate}')
        time.sleep(.03)
        hrange = self.find_range(current)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RANGE:{hrange}')
        time.sleep(.03)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:ENAB:ON')
        time.sleep(.03)
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:TSET:{setpoint}')
        time.sleep(.03)

    def stop_heater(self, thermometer_num: int):
        """Turn off the PID loop for a thermometer."""
        self.send(f'SET:DEV:T{thermometer_num}:TEMP:LOOP:MODE:OFF')

    # -------------------------------------------------------------------------
    # magnet control helpers (from Magnet.py)
    # -------------------------------------------------------------------------
    def read_magnet(self) -> tuple[float, float, float]:
        """Return the current field vector (Bx, By, Bz) in tesla."""
        self.send('READ:SYS:VRM:VECT')
        time.sleep(1)
        data = self.recv()
        import re
        matches = re.search(r'\[(-?\d+\.\d+)T (-?\d+\.\d+)T (-?\d+\.\d+)T\]', data.decode())
        while matches is None:
            time.sleep(1)
            data = self.recv()
            matches = re.search(r'\[(-?\d+\.\d+)T (-?\d+\.\d+)T (-?\d+\.\d+)T\]', data.decode())
        return tuple(float(x) for x in matches.groups())

    def ramp_magnet_to(self, rate: float, bx: float, by: float, bz: float):
        """Sweep the magnet to a new vector at ``rate`` (T/min)."""
        self.send('SET:SYS:VRM:ACTN:HOLD')
        self.send('SET:SYS:VRM:COO:CART')
        self.send(f'SET:SYS:VRM:RVST:MODE:RATE:RATE:{rate}:VSET:[{bx} {by} {bz}]')
        # read initial field to compute approximate sweep time
        fx, fy, fz = self.read_magnet()
        self.send('SET:SYS:VRM:ACTN:RTOS')
        # blocking wait until stable
        t_x = abs(fx - bx) / (rate / 60)
        t_y = abs(fy - by) / (rate / 60)
        t_z = abs(fz - bz) / (rate / 60)
        stable_time = max(t_x, t_y, t_z)
        time.sleep(stable_time + 2)
        threshold = 0.002
        while True:
            fx, fy, fz = self.read_magnet()
            if (abs(fx - bx) <= threshold and
                abs(fy - by) <= threshold and
                abs(fz - bz) <= threshold):
                break
            time.sleep(1)
        self.send('SET:SYS:VRM:ACTN:HOLD')

    def ramp_magnet_zero(self):
        """Return the magnet to zero field and hold it there."""
        self.send('SET:SYS:VRM:ACTN:RTOZ')
        time.sleep(2)
        threshold = 0.002
        while True:
            fx, fy, fz = self.read_magnet()
            if abs(fx) <= threshold and abs(fy) <= threshold and abs(fz) <= threshold:
                break
            time.sleep(1)
        self.send('SET:SYS:VRM:ACTN:HOLD')

