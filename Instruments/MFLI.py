"""
MFLI Lock-in Amplifier Controller Module
=========================================

This module provides a controller class for the Zurich Instruments MFLI lock-in amplifier.
It wraps the zhinst.core library to provide a simplified interface for common operations.

Features
--------
- Connection management to LabOne Data Server
- Oscillator and output signal control (frequency, amplitude, DC offset)
- Demodulator configuration (time constant, phase)
- AUX output control with ramping capabilities
- Signal input configuration (differential mode)
- Data acquisition from demodulators

Requirements
------------
- zhinst.core package (Zurich Instruments LabOne API)
- numpy for numerical operations

Example Usage
-------------
>>> from Instruments.MFLI import MFLIController
>>> 
>>> # Initialize connection
>>> mfli = MFLIController(host='localhost', port=8004, device='MFLI1')
>>> 
>>> # Configure output signal
>>> mfli.turn_voltage(True)          # Enable output
>>> mfli.frequency = 1000            # Set frequency to 1 kHz
>>> mfli.sine_amplitude = 0.1        # Set amplitude to 100 mV (RMS)
>>> 
>>> # Read demodulated signal
>>> x, y = mfli.read_demod()

Notes
-----
For additional and specific functions, refer to the LabOne Data Server documentation.
The device path format is: /{device}/{module}/{index}/{parameter}

Written by: YOAV SHARABY
"""

import time
from typing import Tuple, Optional
import numpy as np
from zhinst.core import ziDAQServer


class MFLIController:
    """
    Controller class for Zurich Instruments MFLI lock-in amplifier.
    
    This class provides methods to control various functions of the MFLI including
    signal generation, demodulation, and auxiliary outputs.
    
    Attributes
    ----------
    daq : ziDAQServer
        The Zurich Instruments data server connection object.
    device : str
        The device identifier (e.g., 'MFLI1').
    
    Parameters
    ----------
    host : str, optional
        Host address of the LabOne Data Server (default: 'localhost').
    port : int, optional
        Port number for the LabOne Data Server (default: 8004).
    api_level : int, optional
        API level for the Zurich Instruments API (default: 6).
    device : str, optional
        Device identifier string (default: 'MFLI1').
    
    Example
    -------
    >>> mfli = MFLIController(host='192.168.1.100', device='dev5985')
    >>> mfli.frequency = 10000  # Set frequency to 10 kHz
    """
    
    # =========================================================================
    # Initialization and Connection
    # =========================================================================
    
    def __init__(self, host: str = 'localhost', port: int = 8004, 
                 api_level: int = 6, device: str = 'MFLI1'):
        """
        Initialize connection to LabOne Data Server and connect to the specified MFLI device.
        
        Parameters
        ----------
        host : str
            Host address of the LabOne Data Server.
        port : int
            Port number for the connection.
        api_level : int
            API level (determines available features).
        device : str
            Device identifier string.
        """
        self.daq = ziDAQServer(host, port, api_level)
        self.device = device
        self._amplitude: Optional[float] = None

    # =========================================================================
    # Signal Output Control
    # =========================================================================
    
    def turn_voltage(self, enable: bool) -> None:
        """
        Turn the built-in oscillator output on or off.
        
        Parameters
        ----------
        enable : bool
            True to enable the output, False to disable.
        
        Example
        -------
        >>> mfli.turn_voltage(True)   # Turn output on
        >>> mfli.turn_voltage(False)  # Turn output off
        """
        self.daq.setInt(f"/{self.device}/sigouts/0/on", int(enable))

    def enable_amplitude(self) -> None:
        """
        Enable the sine output amplitude on signal output 0.
        
        This enables the amplitude component for the oscillator signal
        on the output channel.
        """
        self.daq.setInt(f'/{self.device}/sigouts/0/enables/1', 1)

    def disable_amplitude(self) -> None:
        """
        Disable the sine output amplitude on signal output 0.
        
        This disables the amplitude component, effectively setting
        the AC output to zero.
        """
        self.daq.setInt(f'/{self.device}/sigouts/0/enables/1', 0)

    # =========================================================================
    # Frequency Properties
    # =========================================================================
    
    @property
    def frequency(self) -> float:
        """
        Get or set the lock-in reference frequency.
        
        The frequency is specified in Hertz (Hz) and determines the
        oscillator frequency used for demodulation and signal generation.
        
        Parameters
        ----------
        freq : float
            The frequency in Hz.
        
        Returns
        -------
        float
            The current frequency in Hz.
        
        Example
        -------
        >>> mfli.frequency = 1000     # Set to 1 kHz
        >>> print(mfli.frequency)     # Get current frequency
        1000.0
        """
        return self.daq.getDouble(f'/{self.device}/oscs/0/freq')
    
    @frequency.setter
    def frequency(self, freq: float) -> None:
        self.daq.setDouble(f'/{self.device}/oscs/0/freq', freq)

    # =========================================================================
    # Amplitude Properties
    # =========================================================================
    
    @property
    def sine_amplitude(self) -> float:
        """
        Get or set the output sine amplitude (RMS value in Volts).
        
        The getter returns the RMS amplitude (peak amplitude / sqrt(2)).
        The setter accepts RMS amplitude and converts to peak amplitude
        internally as required by the MFLI.
        
        Parameters
        ----------
        amplitude : float
            The RMS amplitude in Volts.
        
        Returns
        -------
        float
            The current RMS amplitude in Volts.
        
        Note
        ----
        The MFLI internally stores peak amplitudes. This property
        handles the RMS <-> peak conversion automatically.
        
        Example
        -------
        >>> mfli.sine_amplitude = 0.1   # Set 100 mV RMS
        >>> print(mfli.sine_amplitude)  # Read back (may have small rounding differences)
        0.1
        """
        return self.daq.getDouble(f"/{self.device}/sigouts/0/amplitudes/1") / np.sqrt(2)
    
    @sine_amplitude.setter
    def sine_amplitude(self, amplitude: float) -> None:
        self.daq.setDouble(f"/{self.device}/sigouts/0/amplitudes/1", amplitude * np.sqrt(2))

    # =========================================================================
    # DC Offset Properties
    # =========================================================================
    
    @property
    def dc_offset(self) -> float:
        """
        Get or set the DC offset of the signal output (in Volts).
        
        The DC offset is added to the AC signal on the output.
        
        Parameters
        ----------
        dcoffset : float
            The DC offset voltage in Volts.
        
        Returns
        -------
        float
            The current DC offset in Volts.
        
        Example
        -------
        >>> mfli.dc_offset = 0.5  # Set 500 mV DC offset
        """
        return self.daq.getDouble(f"/{self.device}/sigouts/0/offset")
    
    @dc_offset.setter
    def dc_offset(self, dcoffset: float) -> None:
        self.daq.setDouble(f"/{self.device}/sigouts/0/offset", dcoffset)

    def dc_offset_ramp(self, dc_offset: float, steps: int = 5, 
                       delay: float = 0.1) -> None:
        """
        Ramp the DC offset to a target value using a fixed number of steps.
        
        This method gradually changes the DC offset from its current value
        to the target value, which helps avoid sudden jumps that could
        affect sensitive measurements.
        
        Parameters
        ----------
        dc_offset : float
            Target DC offset voltage in Volts.
        steps : int, optional
            Number of steps in the ramp (default: 5).
        delay : float, optional
            Delay in seconds between each step (default: 0.1).
        
        Example
        -------
        >>> mfli.dc_offset_ramp(1.0, steps=10, delay=0.05)  # Ramp to 1V in 10 steps
        """
        origin = self.dc_offset
        for value in np.linspace(origin, dc_offset, steps):
            self.dc_offset = value
            time.sleep(delay)

    def dc_offset_ramping(self, dc_offset: float, step_size: float = 2, 
                          delay: float = 0.1) -> None:
        """
        Ramp the DC offset to a target value using a fixed step size.
        
        Unlike `dc_offset_ramp`, this method calculates the number of steps
        based on the desired step size in millivolts.
        
        Parameters
        ----------
        dc_offset : float
            Target DC offset voltage in Volts.
        step_size : float, optional
            Step size in millivolts (default: 2 mV).
        delay : float, optional
            Delay in seconds between each step (default: 0.1).
        
        Example
        -------
        >>> mfli.dc_offset_ramping(0.5, step_size=5, delay=0.02)  # 5 mV steps
        """
        origin = self.dc_offset
        m_step = step_size / 1000  # Convert mV to V
        points = int(round(abs(dc_offset - origin) / m_step)) + 1

        for value in np.linspace(origin, dc_offset, points):
            self.dc_offset = value
            time.sleep(delay)

    # =========================================================================
    # Output Range Properties
    # =========================================================================
    
    @property
    def voltage_output_range(self) -> float:
        """
        Get or set the output voltage range (in Volts).
        
        The output range determines the maximum output voltage.
        Choose the smallest range that accommodates your signal for
        best resolution.
        
        Parameters
        ----------
        v_range : float
            The output voltage range in Volts.
        
        Returns
        -------
        float
            The current output voltage range in Volts.
        
        Example
        -------
        >>> mfli.voltage_output_range = 1.0  # Set ±1V range
        """
        return self.daq.getDouble(f"/{self.device}/sigouts/0/range")
    
    @voltage_output_range.setter
    def voltage_output_range(self, v_range: float) -> None:
        self.daq.setDouble(f"/{self.device}/sigouts/0/range", v_range)

    # =========================================================================
    # Signal Input Properties
    # =========================================================================
    
    @property
    def differential(self) -> int:
        """
        Get or set the differential input mode for signal input 0.
        
        When enabled, the input measures the difference between the
        two input terminals rather than relative to ground.
        
        Parameters
        ----------
        diff : int
            0 for single-ended (ground referenced), 1 for differential.
        
        Returns
        -------
        int
            Current differential mode setting (0 or 1).
        """
        return self.daq.getInt(f'/{self.device}/sigins/0/diff')
    
    @differential.setter
    def differential(self, diff: int) -> None:
        self.daq.setInt(f'/{self.device}/sigins/0/diff', diff)

    # =========================================================================
    # Demodulator Properties
    # =========================================================================
    
    @property
    def timeconstant(self) -> float:
        """
        Get or set the demodulator time constant (in seconds).
        
        The time constant determines the low-pass filter bandwidth.
        Longer time constants give better noise rejection but slower
        response to signal changes.
        
        Parameters
        ----------
        time_constant : float
            The time constant in seconds.
        
        Returns
        -------
        float
            The current time constant in seconds.
        
        Example
        -------
        >>> mfli.timeconstant = 0.1  # 100 ms time constant
        """
        return self.daq.getDouble(f"/{self.device}/demods/0/timeconstant")
    
    @timeconstant.setter
    def timeconstant(self, time_constant: float) -> None:
        self.daq.setDouble(f"/{self.device}/demods/0/timeconstant", time_constant)

    @property
    def phase(self) -> float:
        """
        Get or set the demodulator phase shift (in degrees).
        
        The phase shift is applied to the reference signal before
        demodulation, allowing adjustment of the X/Y coordinate system.
        
        Parameters
        ----------
        phase : float
            The phase shift in degrees.
        
        Returns
        -------
        float
            The current phase shift in degrees.
        """
        return self.daq.getDouble(f'/{self.device}/demods/0/phaseshift')
    
    @phase.setter
    def phase(self, phase: float) -> None:
        self.daq.setDouble(f'/{self.device}/demods/0/phaseshift', phase)

    @property
    def auto_phase(self) -> None:
        """
        Automatically adjust the phase to align X with the signal.
        
        This triggers an automatic phase adjustment that sets the
        phase so that the Y component is minimized (all signal in X).
        
        Note
        ----
        This is a write-only property; reading it returns None.
        """
        self.daq.setInt(f'/{self.device}/demods/0/phaseadjust', 1)

    # =========================================================================
    # Data Acquisition
    # =========================================================================
    
    def read_demod(self) -> np.ndarray:
        """
        Read a single sample from the demodulator.
        
        Returns the X and Y components of the demodulated signal,
        which represent the in-phase and quadrature components.
        
        Returns
        -------
        np.ndarray
            Array containing [X, Y] components where:
            - X: In-phase component (real part)
            - Y: Quadrature component (imaginary part)
            
            The magnitude R and phase φ can be calculated as:
            - R = sqrt(X² + Y²)
            - φ = arctan2(Y, X)
        
        Example
        -------
        >>> x, y = mfli.read_demod()
        >>> r = np.sqrt(x**2 + y**2)  # Calculate magnitude
        >>> phase = np.degrees(np.arctan2(y, x))  # Calculate phase in degrees
        """
        data = self.daq.getSample(f'/{self.device}/demods/0/sample')
        x = data["x"][0]
        y = data["y"][0]
        return np.array([x, y], dtype=float)

    # =========================================================================
    # Auxiliary Output Control
    # =========================================================================
    
    # AUX Output Signal Selection Values
    # -----------------------------------
    # The 'select' parameter in set_auxout() determines what signal
    # is output on the AUX BNC connectors:
    #
    # -1  : Manual (fixed DC value set by offset)
    #  0  : Demod X (in-phase component)
    #  1  : Demod Y (quadrature component)
    #  2  : Demod R (magnitude)
    #  3  : Demod θ (phase angle)
    #  11 : TU filtered value
    #  13 : TU output value
    
    AUX_MANUAL = -1
    AUX_DEMOD_X = 0
    AUX_DEMOD_Y = 1
    AUX_DEMOD_R = 2
    AUX_DEMOD_THETA = 3
    AUX_TU_FILTERED = 11
    AUX_TU_OUTPUT = 13

    def get_auxout(self, signal: int = 0) -> float:
        """
        Get the AUX output DC offset value.
        
        Parameters
        ----------
        signal : int, optional
            AUX output channel number (0-3 for BNC outputs 1-4).
            Default is 0.
        
        Returns
        -------
        float
            The current DC offset value in Volts.
        """
        return self.daq.getDouble(f'/{self.device}/auxouts/{signal}/offset')

    def set_auxout(self, signal: int = 0, select: int = -1, 
                   demod_select: int = 0) -> None:
        """
        Configure the AUX output signal source.
        
        Parameters
        ----------
        signal : int, optional
            AUX output channel number (0-3 for BNC outputs 1-4).
            Default is 0.
        select : int, optional
            Signal source selection:
                -1  : Manual (DC offset mode)
                0   : Demod X
                1   : Demod Y
                2   : Demod R (magnitude)
                3   : Demod θ (phase)
                11  : TU filtered value
                13  : TU output value
            Default is -1 (manual mode).
        demod_select : int, optional
            Demodulator channel to use when select is 0-3.
            Default is 0.
        
        Example
        -------
        >>> mfli.set_auxout(signal=0, select=2)  # Output R magnitude on AUX 1
        >>> mfli.set_auxout(signal=1, select=-1)  # Manual mode on AUX 2
        """
        self.daq.set(f'/{self.device}/auxouts/{signal}/outputselect', select)
        if select in (11, 13):
            self.daq.set(f'/{self.device}/auxouts/{signal}/demodselect', demod_select)

    def set_aux_offset(self, offset: float = 0, signal: int = 0) -> None:
        """
        Set the AUX output DC offset (for manual mode).
        
        Parameters
        ----------
        offset : float, optional
            The DC offset voltage in Volts. Default is 0.
        signal : int, optional
            AUX output channel number (0-3). Default is 0.
        
        Example
        -------
        >>> mfli.set_aux_offset(offset=1.5, signal=0)  # Set 1.5V on AUX 1
        """
        self.daq.setDouble(f'/{self.device}/auxouts/{signal}/offset', offset)

    def aux_ramp(self, signal: int = 0, aux: float = 0, 
                 steps: int = 3, delay: float = 0.1) -> None:
        """
        Ramp the AUX output offset using a fixed number of steps.
        
        Gradually changes the AUX output from its current value to
        the target value to avoid sudden jumps.
        
        Parameters
        ----------
        signal : int, optional
            AUX output channel number (0-3). Default is 0.
        aux : float, optional
            Target offset voltage in Volts. Default is 0.
        steps : int, optional
            Number of steps in the ramp. Default is 3.
        delay : float, optional
            Delay in seconds between steps. Default is 0.1.
        
        Example
        -------
        >>> mfli.aux_ramp(signal=0, aux=2.0, steps=20, delay=0.05)
        """
        origin = self.get_auxout(signal)
        for value in np.linspace(origin, aux, steps):
            self.set_aux_offset(value, signal)
            time.sleep(delay)

    def aux_ramping(self, signal: int = 0, aux: float = 0, 
                    step_size: float = 2, delay: float = 0.1) -> None:
        """
        Ramp the AUX output offset using a fixed step size.
        
        Calculates the number of steps based on the step size in millivolts.
        
        Parameters
        ----------
        signal : int, optional
            AUX output channel number (0-3). Default is 0.
        aux : float, optional
            Target offset voltage in Volts. Default is 0.
        step_size : float, optional
            Step size in millivolts. Default is 2 mV.
        delay : float, optional
            Delay in seconds between steps. Default is 0.1.
        
        Example
        -------
        >>> mfli.aux_ramping(signal=0, aux=1.0, step_size=10, delay=0.02)
        """
        origin = self.get_auxout(signal)
        m_step = step_size / 1000
        points = int(round(abs(aux - origin) / m_step)) + 1
        for value in np.linspace(origin, aux, points):
            self.set_aux_offset(offset=value, signal=signal)
            time.sleep(delay)

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================
    # These properties/methods maintain backward compatibility with older code
    # that may use the misspelled versions.
    
    # Note: 'diffrential' is a typo kept for backward compatibility.
    # Prefer using 'differential' in new code.
    diffrential = differential


# =============================================================================
# Module-level constants for convenience
# =============================================================================

# Quick reference for AUX output signal selection
AUX_SIGNAL_MANUAL = -1      # Manual DC offset mode
AUX_SIGNAL_DEMOD_X = 0      # Demodulator X output
AUX_SIGNAL_DEMOD_Y = 1      # Demodulator Y output
AUX_SIGNAL_DEMOD_R = 2      # Demodulator R (magnitude)
AUX_SIGNAL_DEMOD_THETA = 3  # Demodulator θ (phase)
AUX_SIGNAL_TU_FILTERED = 11 # Threshold Unit filtered
AUX_SIGNAL_TU_OUTPUT = 13   # Threshold Unit output