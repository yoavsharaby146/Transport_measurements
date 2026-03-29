# This bit of code was written for the use of a dual gate source
# The functions are divided to two categories, instrument functions and SMU functions

# It is the users responsibility to verify the functions and use them properly
#

# You are welcome to add more functions for your own uses

# Due to some communication delay read function behave in such a way that
# the command to read is sent and than the function returns another sent command
# there are the measure functions.


# Written by YOAV SHARABY


# Refactored Keithley2604B module with SMUa and SMUb as subclasses
import pyvisa
import time
import numpy as np
from typing import List, Tuple

#from scipy.constants import micro


class Keithley2604B:
    def __init__(self, visa_address: str):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(visa_address)
        self.instrument.timeout = 5000
        self.smua = SMUChannel(self.instrument, "smua")
        self.smub = SMUChannel(self.instrument, "smub")

    def reset(self):
        self.instrument.write("reset()")
        time.sleep(1)

    def get_idn(self) -> str:
        return self.instrument.query("*IDN?").strip()

    def close(self):
        self.instrument.close()
        self.rm.close()

    def beeper (self, status: str ):
        self.instrument.write(f"beeper.enable=beeper.{status}")

    def beeper_beep (self, duration: float, frequency: float):
        self.instrument.write("beeper.enable=beeper.ON")
        self.instrument.write(f"beeper.beep({duration}, {frequency})")

class SMUChannel:
    def __init__(self, instrument, label: str):
        self.instrument = instrument
        self.label = label

    def _w(self, cmd: str):
        self.instrument.write(f"{self.label}.{cmd}")

    def _q(self, cmd: str) -> str:
        #self.instrument.query(f"print({self.label}.{cmd})").strip()
        return self.instrument.query(f"print({self.label}.{cmd})").strip()

    def configure_voltage_source(self, voltage: float, current_limit: float = 15e-9):
        self._w("source.func = " + self.label + ".OUTPUT_DCVOLTS")
        self._w(f"source.levelv = {voltage}")
        self._w(f"source.limiti = {current_limit}")
        self.instrument.write(f"display.{self.label}.measure.func = display.MEASURE_DCAMPS")

    def sense_mode (self, mode: str):
        self._w(self.label +" = "+self.label+".SENSE_"+mode)

    def configure_current_source(self, current: float, voltage_limit: float = 10.0):
        self._w("source.func = " + self.label + ".OUTPUT_DCAMPS")
        self._w(f"source.leveli = {current}")
        self._w(f"source.limitv = {voltage_limit}")
        self.instrument.write(f"display.{self.label}.measure.func = display.MEASURE_DCVOLTS")

    def voltage_ramping(self, voltage: float, step_size: int, delay: float = 0.001):
        start_voltage = float(self._q("measure.v()"))
        milli_step = step_size* 1e-3
        points = int(abs(voltage-start_voltage) / milli_step)+1
        for v in np.linspace(start_voltage, voltage, points):
            self._w(f"source.levelv = {v}")
            self._q("measure.i()")
            time.sleep(delay)

    def ramp_voltage(self, voltage: float, steps: int = 30, delay: float = 20e-3):
        start_voltage = float(self._q("measure.v()"))
        for v in np.linspace(start_voltage, voltage, steps):
            self._w(f"source.levelv = {v}")
            self._q("measure.i()")
            time.sleep(delay)

    def ramp_current(self, current: float, steps: int, delay: float = 0.001):
        start_current = float(self._q("measure.i()"))
        for i in np.linspace(start_current, current, steps):
            self._w(f"source.leveli = {i}")
            self._q("measure.v()")
            time.sleep(delay)

    def output_on(self):
        self._w("source.output = " + self.label + ".OUTPUT_ON")

    def output_off(self):
        self._w("source.output = " + self.label + ".OUTPUT_OFF")

    def is_output_on(self) -> bool:
        return float(self._q("source.output")) == 1.0

    def measure__current(self) -> float:
        #self._q("measure.i()")
        return float(self._q("measure.i()"))

    def measure__voltage(self) -> float:
        #self._q("measure.v()")
        return float(self._q("measure.v()"))

    def pulsed_measure_to_buffer(self, source_func="voltage", level=1.0, pulse_time=0.01,
                                 delay_time=0.1, num_pulses=10, compliance=0.01, buffer_name="defbuffer1") -> List[float]:
        func_map = {
            "voltage": ("OUTPUT_DCVOLTS", "levelv", "limiti", "pulsev", "measure.i()"),
            "current": ("OUTPUT_DCAMPS", "leveli", "limitv", "pulsei", "measure.v()")
        }

        if source_func not in func_map:
            raise ValueError("source_func must be 'voltage' or 'current'")

        mode, level_cmd, limit_cmd, pulse_func, measure_cmd = func_map[source_func]

        tsp_script = f"""
{self.label}.source.func = {self.label}.{mode}
{self.label}.source.{level_cmd} = {level}
{self.label}.source.{limit_cmd} = {compliance}
{buffer_name}.clear()
for i = 1, {num_pulses} do
    {buffer_name}.append({self.label}.{pulse_func}({level}, {pulse_time}))
    delay({delay_time})
end
printbuffer(1, {buffer_name}.n, {buffer_name})
"""
        output = self.instrument.query(tsp_script)
        return [float(val) for val in output.strip().split(',')]

    def pulsed_dual_buffer_measure(self, level=1.0, pulse_time=0.01, delay_time=0.1,
                                   num_pulses=10, compliance=0.01) -> Tuple[List[float], List[float]]:
        tsp_script = f"""
{self.label}.source.func = {self.label}.OUTPUT_DCVOLTS
{self.label}.source.levelv = {level}
{self.label}.source.limiti = {compliance}
defbuffer1.clear()
defbuffer2.clear()

for i = 1, {num_pulses} do
    {self.label}.source.output = {self.label}.OUTPUT_ON
    delay({pulse_time})
    defbuffer1.append({self.label}.measure.i())
    defbuffer2.append({self.label}.measure.v())
    {self.label}.source.output = {self.label}.OUTPUT_OFF
    delay({delay_time})
end

printbuffer(1, defbuffer1.n, defbuffer1)
print("split")
printbuffer(1, defbuffer2.n, defbuffer2)
"""
        response = self.instrument.query(tsp_script)

        if "split" not in response:
            raise RuntimeError("Unexpected response format from instrument")

        current_str, voltage_str = response.strip().split("split")
        currents = [float(val) for val in current_str.strip().split(',')]
        voltages = [float(val) for val in voltage_str.strip().split(',')]
        return currents, voltages

