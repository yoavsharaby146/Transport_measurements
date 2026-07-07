"""
Simulated serial port for the Cryomagnetics MPS 4G magnet power supply.

This module provides :class:`MockSerialPort`, a drop-in replacement for
``serial.Serial`` that emulates the 4G's text command/response protocol. It is
used by ``Cryomagnetics_MPS4G GUI`` in "Simulation Mode" so the GUI can run with
no hardware connected.

The mock keeps an in-memory model of the instrument state and, on every
``write()``, prepares the byte-for-byte response that the real
:class:`Instruments.Cryomagnetics_MPS4G.Cryomagnetics_MPS4G` driver expects to
parse (including the exact ``[7:-1]`` / ``[7:]`` / ``[8:]`` / ``[9:]`` /
``[10:]`` slicing the driver performs).

Usage from the GUI::

    import Instruments.Cryomagnetics_MPS4G as cryo_module
    from mock_instrument import MockSerialPort
    cryo_module.serial.Serial = MockSerialPort
    inst = cryo_module.Cryomagnetics_MPS4G(port='SIM', baudrate=9600, timeout=1)
"""

import random


class MockSerialPort:
    """A minimal, in-process stand-in for ``serial.Serial``.

    The public surface mirrors what the Cryomagnetics driver actually uses:
    ``write``, ``read``, ``close`` and the ``is_open`` flag. Construction
    accepts the same keyword arguments the driver passes
    (``port``, ``baudrate``, ``timeout``) plus arbitrary extras for safety.
    """

    def __init__(self, port=None, baudrate=9600, timeout=None, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True

        # --- Internal instrument model -----------------------------------
        # Currents/voltages are stored in the same "wire" units the driver
        # echoes back (Amperes / Volts). Field-related limits are stored as
        # the magnet-current values the driver sends with ULIM/LLIM.
        self._imag = 0.0           # magnet current reported by IMAG? (A)
        self._iout = 0.0           # power-supply output current (A)
        self._llim = -90.0         # low sweep limit (magnet-current units)
        self._ulim = 90.0          # high sweep limit (magnet-current units)
        self._mode = 'Manual'
        self._name = 'MOCK_COIL'
        self._pshtr = 'ON'
        self._ranges = [1.0, 5.0, 10.0, 20.0, 40.0]   # RANGE 0..4 (A)
        self._rates = [0.1, 0.2, 0.3, 0.4, 0.5, 1.0]  # RATE 0..5 (A/s)
        self._sweep = 'HOLDING'    # SWEEP? state string
        self._units = 'A'
        self._vlim = 2.5           # voltage limit (V)
        self._vmag = 0.0           # magnet voltage (V)
        self._vout = 0.0           # output voltage (V)
        self._error = 0

        self._buffer = b''

    # ------------------------------------------------------------------
    # serial.Serial-compatible API
    # ------------------------------------------------------------------
    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def write(self, data):
        """Accept a command (bytes or str), update state, queue a response."""
        if isinstance(data, (bytes, bytearray)):
            cmd = bytes(data).decode('utf-8', errors='ignore').strip()
        else:
            cmd = str(data).strip()
        self._buffer = self._handle(cmd).encode('utf-8')
        return len(data) if data is not None else 0

    def read(self, size=1000):
        """Return the response queued by the most recent ``write``."""
        data = self._buffer
        self._buffer = b''
        return data

    # Convenience no-ops for compatibility with code that flushes buffers.
    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    @property
    def in_waiting(self):
        return len(self._buffer)

    # ------------------------------------------------------------------
    # Response formatting
    # ------------------------------------------------------------------
    @staticmethod
    def _fmt(prefix, value, prefix_len, trailing=''):
        """Build a response whose payload begins at index ``prefix_len``.

        The driver slices responses like ``response_str[7:-1]`` or
        ``response_str[8:]``; this helper left-pads ``prefix`` with spaces so
        the payload lands exactly where the parser expects it.
        """
        pad = ' ' * max(0, prefix_len - len(prefix))
        return f'{prefix}{pad}{value}{trailing}'

    # ------------------------------------------------------------------
    # Command interpreter
    # ------------------------------------------------------------------
    def _handle(self, cmd):
        upper = cmd.upper()

        # --- Magnet current / field ------------------------------------
        if upper == 'IMAG?':
            self._tick_sweep()
            return self._fmt('IMAG:', f'{self._imag + random.gauss(0, 1e-3):.4f}', 7, 'A')
        if upper.startswith('IMAG '):
            self._imag = float(cmd[5:])
            return ''

        # --- Power supply output current -------------------------------
        if upper == 'IOUT?':
            return self._fmt('IOUT:', f'{self._iout + random.gauss(0, 1e-3):.4f}', 7, 'A')
        if upper.startswith('IOUT '):
            self._iout = float(cmd[5:])
            return ''

        # --- Sweep limits ----------------------------------------------
        if upper == 'LLIM?':
            return self._fmt('LLIM:', f'{self._llim:.4f}', 7, 'A')
        if upper.startswith('LLIM '):
            self._llim = float(cmd[5:])
            return ''

        if upper == 'ULIM?':
            return self._fmt('ULIM:', f'{self._ulim:.4f}', 7, 'A')
        if upper.startswith('ULIM '):
            self._ulim = float(cmd[5:])
            return ''

        # --- Operating mode / coil name --------------------------------
        if upper == 'MODE?':
            return self._fmt('MODE:', self._mode, 7)
        if upper.startswith('MODE '):
            self._mode = cmd[5:].strip()
            return ''

        if upper == 'NAME?':
            return self._fmt('NAME:', self._name, 7)
        if upper.startswith('NAME '):
            self._name = cmd[5:].strip()
            return ''

        # --- Persistent switch heater ----------------------------------
        if upper == 'PSHTR?':
            return self._fmt('PSHTR:', self._pshtr, 8)
        if upper.startswith('PSHTR '):
            self._pshtr = cmd[6:].strip().upper()
            return ''

        # --- Quench reset ----------------------------------------------
        if upper == 'QRESET':
            self._mode = 'Standby'
            return ''

        # --- Current ranges (RANGE 0..4) -------------------------------
        if upper.startswith('RANGE?'):
            i = int(cmd.split()[1])
            i = max(0, min(i, len(self._ranges) - 1))
            return self._fmt(f'RANGE {i}', f'{self._ranges[i]:.4f}', 10)
        if upper.startswith('RANGE '):
            parts = cmd.split()
            i = int(parts[1])
            if 0 <= i < len(self._ranges):
                self._ranges[i] = float(parts[2])
            return ''

        # --- Current rates (RATE 0..5) ---------------------------------
        if upper.startswith('RATE?'):
            i = int(cmd.split()[1])
            i = max(0, min(i, len(self._rates) - 1))
            return self._fmt(f'RATE {i}', f'{self._rates[i]:.4f}', 9)
        if upper.startswith('RATE '):
            parts = cmd.split()
            i = int(parts[1])
            if 0 <= i < len(self._rates):
                self._rates[i] = float(parts[2])
            return ''

        # --- Remote / local --------------------------------------------
        if upper == 'REMOTE':
            return ''
        if upper == 'LOCAL':
            return ''

        # --- Sweep mode ------------------------------------------------
        if upper == 'SWEEP?':
            return self._fmt('SWEEP:', self._sweep, 8)
        if upper.startswith('SWEEP '):
            mode = cmd[6:].strip().upper()
            self._sweep = mode if mode in ('UP', 'DOWN', 'ZERO', 'FAST', 'SLOW', 'PAUSE', 'HALT') else 'HOLDING'
            return ''

        # --- Units -----------------------------------------------------
        if upper == 'UNITS?':
            return self._fmt('UNITS:', self._units, 8)
        if upper.startswith('UNITS '):
            self._units = cmd[6:].strip()
            return ''

        # --- Voltages --------------------------------------------------
        if upper == 'VLIM?':
            return self._fmt('VLIM:', f'{self._vlim:.4f}', 7, 'V')
        if upper.startswith('VLIM '):
            self._vlim = float(cmd[5:])
            return ''

        if upper == 'VMAG?':
            return self._fmt('VMAG:', f'{self._vmag + random.gauss(0, 1e-3):.4f}', 7, 'V')
        if upper == 'VOUT?':
            return self._fmt('VOUT:', f'{self._vout + random.gauss(0, 1e-3):.4f}', 7, 'V')

        # --- Error reporting -------------------------------------------
        if upper == 'ERROR?':
            return self._fmt('ERROR:', str(self._error), 8)
        if upper.startswith('ERROR '):
            self._error = int(float(cmd[6:]))
            return ''

        # Unknown command -> empty acknowledgement
        return ''

    # ------------------------------------------------------------------
    # Sweep simulation
    # ------------------------------------------------------------------
    def _tick_sweep(self):
        """Advance the simulated magnet current toward the active sweep target.

        Called on each ``IMAG?`` poll so that sweeps initiated from the GUI
        visibly move on the live plot, then settle once the target is reached.
        """
        sweep = self._sweep
        if sweep == 'UP':
            target = self._ulim
        elif sweep == 'DOWN':
            target = self._llim
        elif sweep == 'ZERO':
            target = 0.0
        else:
            return  # FAST / SLOW / HOLDING / ... -> no motion

        # Move a fraction of the remaining distance each poll (smooth approach).
        self._imag += (target - self._imag) * 0.08
        self._iout = self._imag
        if abs(target - self._imag) < 1e-3:
            self._imag = target
            self._iout = target
            self._sweep = 'CLAMPED AT ' + ('ZERO' if target == 0 else 'LIMIT')