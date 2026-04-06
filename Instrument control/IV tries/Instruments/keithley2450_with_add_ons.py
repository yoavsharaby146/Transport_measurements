#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2024 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
import time
from warnings import warn

import numpy as np

from pymeasure.instruments import Instrument, SCPIMixin
from pymeasure.instruments.validators import truncated_range, strict_discrete_set
from pymeasure.instruments.keithley.buffer import KeithleyBuffer

# Setup logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class Keithley2450(KeithleyBuffer, SCPIMixin, Instrument):
    """ Represents the Keithley 2450 SourceMeter and provides a
    high-level interface for interacting with the instrument.

    .. code-block:: python

        keithley = Keithley2450("GPIB::1")

        keithley.apply_current()                # Sets up to source current
        keithley.source_current_range = 10e-3   # Sets the source current range to 10 mA
        keithley.compliance_voltage = 10        # Sets the compliance voltage to 10 V
        keithley.source_current = 0             # Sets the source current to 0 mA
        keithley.enable_source()                # Enables the source output

        keithley.measure_voltage()              # Sets up to measure voltage

        keithley.ramp_to_current(5e-3)          # Ramps the current to 5 mA
        print(keithley.voltage)                 # Prints the voltage in Volts

        keithley.shutdown()                     # Ramps the current to 0 mA and disables output

    """

    def __init__(self, adapter, name="Keithley 2450 SourceMeter", **kwargs):
        super().__init__(
            adapter,
            name,
            **kwargs
        )

    source_mode = Instrument.control(
        ":SOUR:FUNC?", ":SOUR:FUNC %s",
        """ A string property that controls the source mode, which can
        take the values 'current' or 'voltage'. The convenience methods
        :meth:`~.Keithley2450.apply_current` and :meth:`~.Keithley2450.apply_voltage`
        can also be used. """,
        validator=strict_discrete_set,
        values={'current': 'CURR', 'voltage': 'VOLT'},
        map_values=True
    )

    source_enabled = Instrument.measurement(
        "OUTPUT?",
        """ Reads a boolean value that is True if the source is enabled. """,
        cast=lambda x: str(x).strip() in ('1', 'ON', 'True', 'true')
    )

    ###############
    # Current (A) #
    ###############

    current = Instrument.measurement(
        ":READ?",
        """ Reads the current in Amps, if configured for this reading.
        """
    )

    current_range = Instrument.control(
        ":SENS:CURR:RANG?", ":SENS:CURR:RANG:AUTO 0;:SENS:CURR:RANG %g",
        """ A floating point property that controls the measurement current
        range in Amps, which can take values between -1.05 and +1.05 A.
        Auto-range is disabled when this property is set. """,
        validator=truncated_range,
        values=[-1.05, 1.05]
    )

    current_nplc = Instrument.control(
        ":SENS:CURR:NPLC?", ":SENS:CURR:NPLC %g",
        """ A floating point property that controls the number of power line cycles
        (NPLC) for the DC current measurements, which sets the integration period
        and measurement speed. Takes values from 0.01 to 10, where 0.1, 1, and 10 are
        Fast, Medium, and Slow respectively. """,
        values=[0.01, 10]
    )

    compliance_current = Instrument.control(
        ":SOUR:VOLT:ILIM?", ":SOUR:VOLT:ILIM %g",
        """ A floating point property that controls the compliance current
        in Amps. """,
        validator=truncated_range,
        values=[-1.05, 1.05]
    )

    source_current = Instrument.control(
        ":SOUR:CURR?", ":SOUR:CURR:LEV %g",
        """ A floating point property that controls the source current
        in Amps. """
    )

    source_current_range = Instrument.control(
        ":SOUR:CURR:RANG?", ":SOUR:CURR:RANG:AUTO 0;:SOUR:CURR:RANG %g",
        """ A floating point property that controls the source current
        range in Amps, which can take values between -1.05 and +1.05 A.
        Auto-range is disabled when this property is set. """,
        validator=truncated_range,
        values=[-1.05, 1.05]
    )

    source_current_delay = Instrument.control(
        ":SOUR:CURR:DEL?", ":SOUR:CURR:DEL %g",
        """ A floating point property that sets a manual delay for the source
        after the output is turned on before a measurement is taken. When this
        property is set, the auto delay is turned off. Valid values are
        between 0 [seconds] and 999.9999 [seconds].""",
        validator=truncated_range,
        values=[0, 999.9999],
    )

    source_current_delay_auto = Instrument.control(
        ":SOUR:CURR:DEL:AUTO?", ":SOUR:CURR:DEL:AUTO %d",
        """ A boolean property that enables or disables auto delay. Valid
        values are True and False. """,
        values={True: 1, False: 0},
        map_values=True,
    )

    ###############
    # Voltage (V) #
    ###############

    voltage = Instrument.measurement(
        ":READ?",
        """ Reads the voltage in Volts, if configured for this reading.
        """
    )

    voltage_range = Instrument.control(
        ":SENS:VOLT:RANG?", ":SENS:VOLT:RANG:AUTO 0;:SENS:VOLT:RANG %g",
        """ A floating point property that controls the measurement voltage
        range in Volts, which can take values from -210 to 210 V.
        Auto-range is disabled when this property is set. """,
        validator=truncated_range,
        values=[-210, 210]
    )

    voltage_nplc = Instrument.control(
        ":SENS:VOLT:NPLC?", ":SENS:VOLT:NPLC %g",
        """ A floating point property that controls the number of power line cycles
        (NPLC) for the DC voltage measurements, which sets the integration period
        and measurement speed. Takes values from 0.01 to 10, where 0.1, 1, and 10 are
        Fast, Medium, and Slow respectively. """
    )

    compliance_voltage = Instrument.control(
        ":SOUR:CURR:VLIM?", ":SOUR:CURR:VLIM %g",
        """ A floating point property that controls the compliance voltage
        in Volts. """,
        validator=truncated_range,
        values=[-210, 210]
    )

    source_voltage = Instrument.control(
        ":SOUR:VOLT?", ":SOUR:VOLT:LEV %g",
        """ A floating point property that controls the source voltage
        in Volts. """
    )

    source_voltage_range = Instrument.control(
        ":SOUR:VOLT:RANG?", ":SOUR:VOLT:RANG:AUTO 0;:SOUR:VOLT:RANG %g",
        """ A floating point property that controls the source voltage
        range in Volts, which can take values from -210 to 210 V.
        Auto-range is disabled when this property is set. """,
        validator=truncated_range,
        values=[-210, 210]
    )

    source_voltage_delay = Instrument.control(
        ":SOUR:VOLT:DEL?", ":SOUR:VOLT:DEL %g",
        """ A floating point property that sets a manual delay for the source
        after the output is turned on before a measurement is taken. When this
        property is set, the auto delay is turned off. Valid values are
        between 0 [seconds] and 999.9999 [seconds].""",
        validator=truncated_range,
        values=[0, 999.9999],
    )

    source_voltage_delay_auto = Instrument.control(
        ":SOUR:VOLT:DEL:AUTO?", ":SOUR:VOLT:DEL:AUTO %d",
        """ A boolean property that enables or disables auto delay. Valid
        values are True and False. """,
        values={True: 1, False: 0},
        map_values=True,
    )

    ####################
    # Resistance (Ohm) #
    ####################

    resistance = Instrument.measurement(
        ":READ?",
        """ Reads the resistance in Ohms, if configured for this reading.
        """
    )

    resistance_range = Instrument.control(
        ":SENS:RES:RANG?", ":SENS:RES:RANG:AUTO 0;:SENS:RES:RANG %g",
        """ A floating point property that controls the resistance range
        in Ohms, which can take values from 0 to 210 MOhms.
        Auto-range is disabled when this property is set. """,
        validator=truncated_range,
        values=[0, 210e6]
    )
    resistance_nplc = Instrument.control(
        ":SENS:RES:NPLC?", ":SENS:RES:NPLC %g",
        """ A floating point property that controls the number of power line cycles
        (NPLC) for the 2-wire resistance measurements, which sets the integration period
        and measurement speed. Takes values from 0.01 to 10, where 0.1, 1, and 10 are
        Fast, Medium, and Slow respectively. """
    )

    wires = Instrument.control(
        ":SENS:RES:RSENSE?", ":SENS:RES:RSENSE %d",
        """ An integer property that controls the number of wires in
        use for resistance measurements, which can take the value of
        2 or 4.
        """,
        validator=strict_discrete_set,
        values={4: 1, 2: 0},
        map_values=True
    )

    buffer_points = Instrument.control(
        ":TRAC:POIN?", ":TRAC:POIN %d",
        """ An integer property that controls the number of buffer points. This
        does not represent actual points in the buffer, but the configuration
        value instead. """,
        validator=truncated_range,
        values=[1, 6875000],
        cast=int
    )

    means = Instrument.measurement(
        ":TRACe:STATistics:AVERage?",
        """ Reads the calculated means (averages) for voltage,
        current, and resistance from the buffer data  as a list. """
    )

    maximums = Instrument.measurement(
        ":TRACe:STATistics:MAXimum?",
        """ Returns the calculated maximums for voltage, current, and
        resistance from the buffer data as a list. """
    )

    minimums = Instrument.measurement(
        ":TRACe:STATistics:MINimum?",
        """ Returns the calculated minimums for voltage, current, and
        resistance from the buffer data as a list. """
    )

    standard_devs = Instrument.measurement(
        ":TRACe:STATistics:STDDev?",
        """ Returns the calculated standard deviations for voltage,
        current, and resistance from the buffer data as a list. """
    )



    ###########
    # Filters #
    ###########

    current_filter_type = Instrument.control(
        ":SENS:CURR:AVER:TCON?", ":SENS:CURR:AVER:TCON %s",
        """ A String property that controls the filter's type for the current.
        REP : Repeating filter
        MOV : Moving filter""",
        validator=strict_discrete_set,
        values=['REP', 'MOV'],
        map_values=False)

    current_filter_count = Instrument.control(
        ":SENS:CURR:AVER:COUNT?", ":SENS:CURR:AVER:COUNT %d",
        """ A integer property that controls the number of readings that are
        acquired and stored in the filter buffer for the averaging""",
        validator=truncated_range,
        values=[1, 100],
        cast=int)

    current_filter_state = Instrument.control(
        ":SENS:CURR:AVER?", ":SENS:CURR:AVER %s",
        """ A string property that controls if the filter is active.""",
        validator=strict_discrete_set,
        values=['ON', 'OFF'],
        map_values=False)

    voltage_filter_type = Instrument.control(
        ":SENS:VOLT:AVER:TCON?", ":SENS:VOLT:AVER:TCON %s",
        """ A String property that controls the filter's type for the current.
        REP : Repeating filter
        MOV : Moving filter""",
        validator=strict_discrete_set,
        values=['REP', 'MOV'],
        map_values=False)

    voltage_filter_count = Instrument.control(
        ":SENS:VOLT:AVER:COUNT?", ":SENS:VOLT:AVER:COUNT %d",
        """ A integer property that controls the number of readings that are
        acquired and stored in the filter buffer for the averaging""",
        validator=truncated_range,
        values=[1, 100],
        cast=int)

    #####################
    # Output subsystem #
    #####################

    current_output_off_state = Instrument.control(
        ":OUTP:CURR:SMOD?", ":OUTP:CURR:SMOD %s",
        """ Select the output-off state of the SourceMeter.
        HIMP : output relay is open, disconnects external circuitry.
        NORM : V-Source is selected and set to 0V, Compliance is set to 0.5%
        full scale of the present current range.
        ZERO : V-Source is selected and set to 0V, compliance is set to the
        programmed Source I value or to 0.5% full scale of the present current
        range, whichever is greater.
        GUAR : I-Source is selected and set to 0A""",
        validator=strict_discrete_set,
        values=['HIMP', 'NORM', 'ZERO', 'GUAR'],
        map_values=False)

    voltage_output_off_state = Instrument.control(
        ":OUTP:VOLT:SMOD?", ":OUTP:VOLT:SMOD %s",
        """ Select the output-off state of the SourceMeter.
        HIMP : output relay is open, disconnects external circuitry.
        NORM : V-Source is selected and set to 0V, Compliance is set to 0.5%
        full scale of the present current range.
        ZERO : V-Source is selected and set to 0V, compliance is set to the
        programmed Source I value or to 0.5% full scale of the present current
        range, whichever is greater.
        GUAR : I-Source is selected and set to 0A""",
        validator=strict_discrete_set,
        values=['HIMP', 'NORM', 'ZERO', 'GUAR'],
        map_values=False)

    ####################
    # Methods        #
    ####################

    def enable_source(self):
        """ Enables the source of current or voltage depending on the
        configuration of the instrument. """
        self.write("OUTPUT ON")

    def disable_source(self):
        """ Disables the source of current or voltage depending on the
        configuration of the instrument. """
        self.write("OUTPUT OFF")

    def measure_resistance(self, nplc=1, resistance=2.1e5, auto_range=True):
        """ Configures the measurement of resistance.

        :param nplc: Number of power line cycles (NPLC) from 0.01 to 10
        :param resistance: Upper limit of resistance in Ohms, from -210 MOhms to 210 MOhms
        :param auto_range: Enables auto_range if True, else uses the set resistance
        """
        log.info("%s is measuring resistance.", self.name)
        self.write(":SENS:FUNC 'RES';"
                   ":SENS:RES:NPLC %f;" % nplc)
        if auto_range:
            self.write(":SENS:RES:RANG:AUTO 1;")
        else:
            self.resistance_range = resistance
        self.check_errors()

    def measure_voltage(self, nplc=1, voltage=21.0, auto_range=True):
        """ Configures the measurement of voltage.

        :param nplc: Number of power line cycles (NPLC) from 0.01 to 10
        :param voltage: Upper limit of voltage in Volts, from -210 V to 210 V
        :param auto_range: Enables auto_range if True, else uses the set voltage
        """
        log.info("%s is measuring voltage.", self.name)
        self.write(":SENS:FUNC 'VOLT';"
                   ":SENS:VOLT:NPLC %f;" % nplc)
        if auto_range:
            self.write(":SENS:VOLT:RANG:AUTO 1;")
        else:
            self.voltage_range = voltage
        self.check_errors()

    def measure_current(self, nplc=1, current=1.05e-4, auto_range=True):
        """ Configures the measurement of current.

        :param nplc: Number of power line cycles (NPLC) from 0.01 to 10
        :param current: Upper limit of current in Amps, from -1.05 A to 1.05 A
        :param auto_range: Enables auto_range if True, else uses the set current
        """
        log.info("%s is measuring current.", self.name)
        self.write(":SENS:FUNC 'CURR';"
                   ":SENS:CURR:NPLC %f;" % nplc)
        if auto_range:
            self.write(":SENS:CURR:RANG:AUTO 1;")
        else:
            self.current_range = current
        self.check_errors()

    def auto_range_source(self):
        """ Configures the source to use an automatic range.
        """
        if self.source_mode == 'current':
            self.write(":SOUR:CURR:RANG:AUTO 1")
        else:
            self.write(":SOUR:VOLT:RANG:AUTO 1")

    def apply_current(self, current_range=None,
                      compliance_voltage=0.1):
        """ Configures the instrument to apply a source current, and
        uses an auto range unless a current range is specified.
        The compliance voltage is also set.

        :param compliance_voltage: A float in the correct range for a
                                   :attr:`~.Keithley2450.compliance_voltage`
        :param current_range: A :attr:`~.Keithley2450.current_range` value or None
        """
        log.info("%s is sourcing current.", self.name)
        self.source_mode = 'current'
        if current_range is None:
            self.auto_range_source()
        else:
            self.source_current_range = current_range
        self.compliance_voltage = compliance_voltage
        self.check_errors()

    def apply_voltage(self, voltage_range=None,
                      compliance_current=0.1):
        """ Configures the instrument to apply a source voltage, and
        uses an auto range unless a voltage range is specified.
        The compliance current is also set.

        :param compliance_current: A float in the correct range for a
                                   :attr:`~.Keithley2450.compliance_current`
        :param voltage_range: A :attr:`~.Keithley2450.voltage_range` value or None
        """
        log.info("%s is sourcing voltage.", self.name)
        self.source_mode = 'voltage'
        if voltage_range is None:
            self.auto_range_source()
        else:
            self.source_voltage_range = voltage_range
        self.compliance_current = compliance_current
        self.check_errors()

    def beep(self, frequency, duration):
        """ Sounds a system beep.

        :param frequency: A frequency in Hz between 65 Hz and 2 MHz
        :param duration: A time in seconds between 0 and 7.9 seconds
        """
        self.write(f":SYST:BEEP {frequency:g}, {duration:g}")

    def triad(self, base_frequency, duration):
        """ Sounds a musical triad using the system beep.

        :param base_frequency: A frequency in Hz between 65 Hz and 1.3 MHz
        :param duration: A time in seconds between 0 and 7.9 seconds
        """
        self.beep(base_frequency, duration)
        time.sleep(duration)
        self.beep(base_frequency * 5.0 / 4.0, duration)
        time.sleep(duration)
        self.beep(base_frequency * 6.0 / 4.0, duration)

    @property
    def error(self):
        warn("Deprecated to use `error`, use `next_error` instead.", FutureWarning)
        return self.next_error

    def reset(self):
        """ Resets the instrument and clears the queue.  """
        self.write("*RST;:stat:pres;:*CLS;")

    def ramp_current(self, target_current, steps=30, pause=20e-3):
        """ Ramps to a target current from the set current value over
        a certain number of linear steps, each separated by a pause duration.

        :param target_current: A current in Amps
        :param steps: An integer number of steps
        :param pause: A pause duration in seconds to wait between steps
        """
        currents = np.linspace(
            self.source_current,
            target_current,
            steps
        )
        for current in currents:
            self.source_current = current
            time.sleep(pause)

    def ramp_voltage(self, target_voltage, steps=30, pause=20e-3):
        """ Ramps to a target voltage from the set voltage value over
        a certain number of linear steps, each separated by a pause duration.

        :param target_voltage: A voltage in Amps
        :param steps: An integer number of steps
        :param pause: A pause duration in seconds to wait between steps
        """
        voltages = np.linspace(
            self.source_voltage,
            target_voltage,
            steps
        )
        for voltage in voltages:
            self.source_voltage = voltage
            time.sleep(pause)

    def trigger(self):
        """ Executes a bus trigger.
        """
        return self.write("*TRG")

    @property
    def mean_voltage(self):
        """ Returns the mean voltage from the buffer """
        return self.means[0]

    @property
    def max_voltage(self):
        """ Returns the maximum voltage from the buffer """
        return self.maximums[0]

    @property
    def min_voltage(self):
        """ Returns the minimum voltage from the buffer """
        return self.minimums[0]

    @property
    def std_voltage(self):
        """ Returns the voltage standard deviation from the buffer """
        return self.standard_devs[0]

    @property
    def mean_current(self):
        """ Returns the mean current from the buffer """
        return self.means[1]

    @property
    def max_current(self):
        """ Returns the maximum current from the buffer """
        return self.maximums[1]

    @property
    def min_current(self):
        """ Returns the minimum current from the buffer """
        return self.minimums[1]

    @property
    def std_current(self):
        """ Returns the current standard deviation from the buffer """
        return self.standard_devs[1]

    @property
    def mean_resistance(self):
        """ Returns the mean resistance from the buffer """
        return self.means[2]

    @property
    def max_resistance(self):
        """ Returns the maximum resistance from the buffer """
        return self.maximums[2]

    @property
    def min_resistance(self):
        """ Returns the minimum resistance from the buffer """
        return self.minimums[2]

    @property
    def std_resistance(self):
        """ Returns the resistance standard deviation from the buffer """
        return self.standard_devs[2]

    def use_rear_terminals(self):
        """ Enables the rear terminals for measurement, and
        disables the front terminals. """
        self.write(":ROUT:TERM REAR")

    def use_front_terminals(self):
        """ Enables the front terminals for measurement, and
        disables the rear terminals. """
        self.write(":ROUT:TERM FRON")

    def check_terminals(self):
        """ Queries the instrument to see which terminals are active.
        Returns: 'FRON' or 'REAR'
        """
        return self.ask(":ROUT:TERM?")

    # The following fuctions for ramping both the voltage and the current
    # use the linspace meathod, the user sets the number of steps between origin and target
    def ramp_to_voltage(self, target_voltage, steps=30, pause=20e-3):
        voltages = np.linspace(self.source_voltage, target_voltage, steps)
        for voltage in voltages:
            self.source_voltage = voltage
            self.current
            time.sleep(pause)

    def ramp_to_current(self, target_current, steps=30, pause=20e-3):
        currents = np.linspace(self.source_current, target_current, steps)
        for current in currents:
            self.source_current = current
            self.voltage
            time.sleep(pause)

    # calculate the number of points from origin to target_voltage using the step_size
    # and set np.linspace array accordingly.
    # During ramping the voltage and current are set and measured

    def voltage_ramping(self, target_voltage, step_size: int = 1, pause=20e-3, callback = None):
        origin = float(self.source_voltage)
        milli_step = step_size * 1e-3
        points= int(abs(target_voltage - origin) / milli_step) + 1
        for volt in np.linspace(origin, target_voltage, points):
            self.source_voltage = volt
            self.current
            time.sleep(pause)
            if callback:
                callback(self.source_voltage, self.current)

    def voltage_ramping_with_monitor(self, target_volt, step, time_step, callback=None):
        """
        Ramps voltage using np.linspace for precision.
        Checks callback to allow user abort.
        """
        # 1. Get starting point
        try:
            origin = self.measure__voltage()
        except:
            origin = 0.0

        # 2. Calculate Number of Points (Fencepost logic)
        # We use abs() to handle both Up and Down ramps automatically
        if step == 0: step = 0.001  # Safety
        points = int(abs(target_volt - origin) / abs(step)) + 1

        # 3. Generate the array (Safe from floating point drift)
        ramp_array = np.linspace(origin, target_volt, points)

        # 4. Iterate
        for volt in ramp_array:
            self.write(f":SOUR:VOLT {volt:.4f}")

            # --- MONITOR & STOP LOGIC ---
            if callback:
                try:
                    # Measure real values
                    meas_v = volt
                    meas_i = float(self.ask(":MEAS:CURR?"))

                    # Call GUI function. If it returns True -> STOP
                    if callback(meas_v, meas_i):
                        print("Ramp Aborted by User.")
                        return  # Exit the function immediately
                except:
                    pass
            # ----------------------------

            time.sleep(time_step)

        # Ensure we landed exactly on target (linspace handles this, but good safety)
        self.write(f":SOUR:VOLT {target_volt}")

    def current_ramping_with_monitor(self, target_curr, step, time_step, callback=None):
        """
        Ramps current using np.linspace for precision.
        Measures voltage at each step.
        Checks callback to allow user abort.
        """
        # 1. Get starting point
        try:
            origin = self.source_current
        except:
            origin = 0.0

        # 2. Calculate Number of Points (Fencepost logic)
        if step == 0: step = 1e-9  # Safety (1 nA minimum step)
        points = int(abs(target_curr - origin) / abs(step)) + 1

        # 3. Generate the array (Safe from floating point drift)
        ramp_array = np.linspace(origin, target_curr, points)

        # 4. Iterate
        for curr in ramp_array:
            self.write(f":SOUR:CURR {curr:.6e}")

            # --- MONITOR & STOP LOGIC ---
            if callback:
                try:
                    # Measure real values
                    meas_i = curr
                    meas_v = float(self.ask(":MEAS:VOLT?"))

                    # Call GUI function. If it returns True -> STOP
                    if callback(meas_v, meas_i):
                        print("Ramp Aborted by User.")
                        return  # Exit the function immediately
                except:
                    pass
            # ----------------------------

            time.sleep(time_step)

        # Ensure we landed exactly on target
        self.write(f":SOUR:CURR {target_curr:.6e}")

    def configure_voltage_source(self, nplc=1, current=1e-6, auto_range=False, compliance_current=1.05e-8):
 
        self.apply_voltage()
        self.measure_current(nplc, current, auto_range)
        self.compliance_current = compliance_current

    def configure_voltage_source_auto(self, nplc=1, current=10e-6, auto_range=False, compliance_current=10e-6):
        """
        Configures the source with optional Auto Range.
        :param current: Fixed measurement range (ignored if auto_range is True)
        :param auto_range: Boolean to enable automatic measurement ranging
        :param compliance_current: The current limit (ILIM)
        """
        self.write("*RST")
        self.write(f":SENS:CURR:NPLC {nplc}")
        self.write(":SOUR:FUNC VOLT")

        # 1. Set Compliance (Source Limit)
        self.write(f":SOUR:VOLT:ILIM {compliance_current}")

        # 2. Configure Measurement Range
        self.write(":SENS:FUNC \"CURR\"")

        if auto_range:
            # Auto Range: Instrument selects best range for the Compliance
            self.write(":SENS:CURR:RANG:AUTO ON")
        else:
            # Fixed Range: Must be >= Compliance or instrument errors
            self.write(":SENS:CURR:RANG:AUTO OFF")
            self.write(f":SENS:CURR:RANG {current}")

        self.write(":SOUR:VOLT:RANG:AUTO ON")

    def configure_current_source(self, nplc=1, voltage = 20e-3, auto_range=False, compliance_voltage = 20e-3):
        self.apply_current()
        self.measure_voltage(nplc, voltage, auto_range)
        self.compliance_voltage = compliance_voltage

    def output_on(self):
        self.enable_source()

    def output_off(self):
        self.disable_source()

    def is_output_on(self) -> bool:
        return self.source_enabled

    def create_hysteresis_voltage_sweep_config_list(self, Sp1 = 1000, Sp2 = -1000, step = 10, curr_range = 1e-6):
        # Creates a voltage source configuration list for full hysteresis measurements. Minimum step size is 1 mV and VALUES ARE In mV!!!
        terminal = self.ask(":ROUT:TERM?")
        self.reset()
        if terminal != "REAR":
            self.write(":ROUT:TERM FRON")
        else:
            self.write(":ROUT:TERM REAR")
        # Delete and recreate configuration list
        #self.write(':SOUR:CONF:LIST:DEL "sourceVclist"')
        self.write(':SOUR:CONF:LIST:CRE "sourceVclist"')
        #self.write(':SENS:CONF:LIST:DEL "senseIclist"')
        #self.write(':SENS:CONF:LIST:CRE "senseIclist"')
        # Set to source voltage and measure current at a constant current measure range (can turn to auto with auto_range flag)
        self.source_mode = 'voltage'
        self.measure_current(1, curr_range, False)
        # Enable/disable 4-wire sensing
        self.disable_source()  # Make sure source is off
        if getattr(self, 'wires', 2) == 4:
            self.write(":SYST:RSEN ON")  # 4-wire
        else:
            self.write(":SYST:RSEN OFF")  # 2-wire

        # Build the voltages array
        # Convert step point and step size to Volts
        mV_Sp1 = Sp1 /1000
        mV_Sp2 = Sp2 / 1000
        mV_step = step / 1000

        # Calculate number of point for each direction
        points1 = int(abs(mV_Sp1 - 0)/mV_step) + 1
        points2 = int(abs(mV_Sp2 - mV_Sp1) / mV_step) + 1
        points3 = int(abs(0 - mV_Sp2 ) / mV_step) + 1
        # Create sweep arrays
        part1 = np.linspace(0, mV_Sp1, points1)
        part2 = np.linspace(mV_Sp1, mV_Sp2, points2)
        part3 = np.linspace(mV_Sp2, 0, points3)
        # without duplicate points
        # 0 to Sp1 to Sp2 to 0
        voltages =  np.concatenate((part1, part2[1:], part3[1:]))
        # With duplicate points
        # 0 to Sp1, Sp1 to Sp_2, Sp2 to 0
        voltages= np.concatenate((part1, part2, part3))


        for voltage in voltages:
            self.source_voltage = voltage
            self.write(':SOUR:CONF:LIST:STORE "sourceVclist";')
            #self.write(':SENS:CONF:LIST:STORE "senseIclist";')
        create_buffer_cmd = 'TRAC:MAKE "sweepBuffer", ' +str(voltages.size) + ";"
        self.write(create_buffer_cmd)
        self.buffer_size = voltages.size

    def create_hysteresis_current_sweep_config_list(self, Sp1=1e-6, Sp2=-1e-6, step=1e-7, volt_range=20e-3):
        # Creates a current source configuration list for full hysteresis measurements. Values are in Amps.
        terminal = self.ask(":ROUT:TERM?")
        self.reset()
        if terminal != "REAR":
            self.write(":ROUT:TERM FRON")
        else:
            self.write(":ROUT:TERM REAR")
        # Delete and recreate configuration list
        #self.write(':SOUR:CONF:LIST:DEL "sourceIclist"')
        self.write(':SOUR:CONF:LIST:CRE "sourceIclist"')
        # Set to source current and measure voltage at a constant voltage measure range
        self.source_mode = 'current'
        self.measure_voltage(1, volt_range, False)
        # Enable/disable 4-wire sensing
        self.disable_source()  # Make sure source is off
        if getattr(self, 'wires', 2) == 4:
            self.write(":SYST:RSEN ON")  # 4-wire
        else:
            self.write(":SYST:RSEN OFF")  # 2-wire

        # Build the currents array (values in Amps)
        # Calculate number of points for each direction
        points1 = int(abs(Sp1 - 0) / step) + 1
        points2 = int(abs(Sp2 - Sp1) / step) + 1
        points3 = int(abs(0 - Sp2) / step) + 1
        # Create sweep arrays
        part1 = np.linspace(0, Sp1, points1)
        part2 = np.linspace(Sp1, Sp2, points2)
        part3 = np.linspace(Sp2, 0, points3)
        # without duplicate points
        # 0 to Sp1 to Sp2 to 0
        currents = np.concatenate((part1, part2[1:], part3[1:]))
        # With duplicate points
        # 0 to Sp1, Sp1 to Sp_2, Sp2 to 0
        currents = np.concatenate((part1, part2, part3))

        for current in currents:
            self.source_current = current
            self.write(':SOUR:CONF:LIST:STORE "sourceIclist";')
        create_buffer_cmd = 'TRAC:MAKE "sweepBuffer", ' + str(currents.size) + ";"
        self.write(create_buffer_cmd)
        self.buffer_size = currents.size

    def run_clist_sweep(self, delay=0.0, sweep_type='voltage'):
        if sweep_type == 'voltage':
            sweep_run_cmd = ':SOUR:SWE:VOLT:LIST 1, ' + str(delay) + ', 1, ON, "sweepBuffer", "sourceVclist"'
        elif sweep_type == 'current':
            sweep_run_cmd = ':SOUR:SWE:CURR:LIST 1, ' + str(delay) + ', 1, ON, "sweepBuffer", "sourceIclist"'
        else:
            raise ValueError("sweep_type must be 'voltage' or 'current'")
        self.write(sweep_run_cmd)
        self.timeout = 20000
        self.write('INIT')
        counter = 0
        while counter < 3:
            if self.source_enabled == False:
                counter = counter + 1
            time.sleep(1)
        query_buffer_cmd = 'TRAC:DATA? 1, ' + str(self.buffer_size) + ', "sweepBuffer", READ, SOUR, REL;'
        self.write(query_buffer_cmd)
        output = self.read()
        #time.sleep(5)
        return output

    def measure__current(self) -> float:
        return self.current

    def measure__voltage(self) -> float:
        return self.source_voltage

    def shutdown(self):
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        log.info("Shutting down %s.", self.name)
        if self.source_mode == 'current':
            self.ramp_to_current(0.0)
        else:
            self.ramp_to_voltage(0.0)
        self.stop_buffer()
        self.disable_source()
        super().shutdown()
