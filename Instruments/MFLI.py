# This module is written as various functions to operate some of the functions
# that the MFLI has. For any additional and specific functions the Lab ONe Data server will be usefull
# to write this functions

# Written by YOAV SHARABY

import time
from zhinst.core import ziDAQServer
import numpy as np


class MFLIController:
    """Controller class for Zurich Instruments MFLI lock-in amplifier."""

    def __init__(self, host: str = 'localhost', port: int = 8004, api_level: int = 6, device: str = 'MFLI1'):
        """Initialize connection to LabOne Data Server and connect to the specified MFLI device."""
        self.daq = ziDAQServer(host, port, api_level)
        self.device = device
        self._amplitude = None

    def turn_voltage(self, enable: bool):
        """Turn the built-in oscillator output on (True) or off (False)."""
        self.daq.setInt(f"/{self.device}/sigouts/0/on", int(enable))


    def enable_amplitude(self):
        self.daq.setInt(f'/{self.device}/sigouts/0/enables/1', 1)

    def disable_amplitude(self):
        """Disable the amplitude by setting it to zero."""
        self.daq.setInt(f'/{self.device}/sigouts/0/enables/1', 0)



    @property
    def frequency(self) -> float:
        """Get the lock-in reference frequency (Hz)."""
        return self.daq.getDouble(f'/{self.device}/oscs/0/freq')
    @frequency.setter
    def frequency(self, freq: float):
        """Set the lock-in reference frequency (Hz)."""
        self.daq.setDouble(f'/{self.device}/oscs/0/freq', freq)



    @property
    def sine_amplitude(self) -> float:
        """Get the current output amplitude (V)."""
        return self.daq.getDouble(f"/{self.device}/sigouts/0/amplitudes/1") / (2 ** 0.5)
    @sine_amplitude.setter
    def amplitude(self, amplitude: float):
        """Set the output amplitude (V)."""
        self.daq.setDouble(f"/{self.device}/sigouts/0/amplitudes/1", amplitude * (2 ** 0.5))
        # self._amplitude = amplitude



    @property
    def dc_offset(self):
        """Get the current output dc offset (V)."""
        return self.daq.getDouble(f"/{self.device}/sigouts/0/offset")
    @dc_offset.setter
    def dc_offset(self, dcoffset: float):
        self.daq.setDouble(f"/{self.device}/sigouts/0/offset", dcoffset)

    def dc_offset_ramp(self, dc_offset, steps: int =5, delay: float = 0.1):
        origin = self.dc_offset
        for a in np.linspace(origin, dc_offset,steps):
            self.dc_offset = a
            time.sleep(delay)

    def dc_offset_ramping(self, dc_offset, step_size: float =2, delay: float = 0.1):
        origin = self.dc_offset
        m_step = step_size /1000
        points = int(round(abs(dc_offset - origin) / m_step)) + 1

        for a in np.linspace(origin, dc_offset, points):
            self.dc_offset = a
            time.sleep(delay)


    @property
    def diffrential(self):
       return self.daq.getInt(f'/{self.device}/sigins/0/diff')
    @diffrential.setter
    def diffrential(self, diff):
        self.daq.setInt(f'/{self.device}/sigins/0/diff', diff)



    @property
    def timeconstant(self) -> float:
        return self.daq.getDouble(f"/{self.device}/demods/0/timeconstant")
    @timeconstant.setter
    def time_constant(self, time_constant: float):
        self.daq.setDouble(f"/{self.device}/demods/0/timeconstant", time_constant)



    @property
    def voltage_output_range(self) -> float:
        """Get the current output voltage range (V)."""
        return self.daq.getDouble(f"/{self.device}/sigouts/0/range")
    @voltage_output_range.setter
    def  voltage_output_range(self, v_range: float):
        """Set the output voltage range (V)."""
        self.daq.setDouble(f"/{self.device}/sigouts/0/range", v_range)



    ##### AUX output signal
    #   Signal is the AUX output 0,1,2,3 for the AUx BNC cables 1,2,3,4
    #   Select is for the mode for each signal
    # Manual -              -1
    # Demod X -             0
    # Demod Y -             1
    # Demode R -            2
    # Demode theta -        3
    # TU filtered value -   11
    # TU output value -     13


    def get_auxout(self,signal: int = 0) -> float:
        """Get the auxout DC offset"""
        return self.daq.getDouble(f'/{self.device}/auxouts/{signal}/offset')

    def set_auxout(self,signal: int =0 , select: int=-1, demod_select: int=0):
        self.daq.set(f'/{self.device}/auxouts/{signal}/outputselect', select)
        if select == 11 or select == 13:
            self.daq.set(f'/{self.device}/auxouts/{signal}/demodselect', demod_select)

    def set_aux_offset(self,offset: float=0, signal: int =0):
        self.daq.setDouble(f'/{self.device}/auxouts/{signal}/offset', offset)

    def aux_ramp(self,signal: int = 0, aux: float =0 , steps: int=3, delay: float = 0.1):
        origin = self.get_auxout(signal)
        for a in np.linspace(origin, aux, steps):
            self.set_aux_offset(a,signal)
            time.sleep(delay)

    def aux_ramping(self,signal: int = 0, aux: float =0 , step_size: float=2, delay: float = 0.1):
        origin = self.get_auxout(signal)
        m_step = step_size /1000
        points = int(round(abs(aux - origin) / m_step)) + 1
        for a in np.linspace(origin, aux, points):
            self.set_aux_offset(offset = a)
            time.sleep(delay)


    @property
    def phase(self):
        return self.daq.getDouble(f'/{self.device}/demods/0/phaseshift')
    @phase.setter
    def phase(self, phase):
        self.daq.setDouble(f'/{self.device}/demods/0/phaseshift', phase)
    @property
    def auto_phase(self):
        self.daq.setInt('/dev5985/demods/0/phaseadjust', 1)

    def read_demod(self) -> np.ndarray:
        """
        Read a single sample from the demodulator: returns an array [R, phi].
        """
        data = self.daq.getSample(f'/{self.device}/demods/0/sample')
        x = data["x"][0]
        y = data["y"][0]
        return np.array([x, y], dtype=float)

