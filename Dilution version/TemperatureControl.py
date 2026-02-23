"""Compatibility layer that exposes the old TemperatureControl
functions while directing all new work through ``DilutionInstrument``.

Existing scripts that import this module can keep using the same names.
"""

from __future__ import annotations

import time
from typing import Any

from dilution_connection import DilutionInstrument


def _ensure_inst(obj: Any) -> DilutionInstrument:
    """Return a DilutionInstrument instance from a socket or instrument.

    This mirrors the behaviour of the original free functions which accepted a
    raw socket object.  If an instrument is already passed, it is returned
    unchanged.
    """
    if isinstance(obj, DilutionInstrument):
        return obj
    inst = DilutionInstrument()
    inst.dilution_socket = obj
    return inst

def getTemperature(thermometer_num, dilution_socket):
    return _ensure_inst(dilution_socket).get_temperature(thermometer_num)

def FindRange(setpoint):
    return DilutionInstrument().find_range(setpoint)

def setHRange(thermometer_num, dilution_socket, hrange):
    _ensure_inst(dilution_socket).set_heater_range(thermometer_num, hrange)

def InitThermometers(thermometer_num, dilution_socket):
    _ensure_inst(dilution_socket).init_thermometers(thermometer_num)

def InitThermometersAndHeaters(thermometer_num, dilution_socket):
    _ensure_inst(dilution_socket).init_thermometers_and_heaters(thermometer_num)

def SetTemperature(thermometer_num, dilution_socket, rate, setpoint):
    _ensure_inst(dilution_socket).set_temperature(thermometer_num, rate, setpoint)




# dilution_ip = '132.66.132.173'  # Replace with the target IP address
# dilution_port = 33576  # Replace with the target port number
# timeout_connection = 10  # Timeout for connection opening in seconds
# dilution_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# dilution_socket.settimeout(timeout_connection)
# dilution_socket.connect((dilution_ip, dilution_port))  # Connect to dilution socket.
# # print("Connected to", dilution_ip, "on port", dilution_port)
#
# # thermometer_num = 8
# # command = f'READ:DEV:T{thermometer_num}:TEMP:SIG:TEMP\n' # read temperature.
# # dilution_socket.send(command.encode())
# # time.sleep(0.5)
# # try:

# #     response = dilution_socket.recv(5000)
# # except ConnectionResetError as e:
# #     print(f"Connection was forcibly closed by the remote host: {e}")
# # NewTemperature = response.decode().split(":")[-1][:-1]
# # NewTemperature = NewTemperature[:-1]
# # print(NewTemperature)
#
# # Close the dilution socket.
# dilution_socket.shutdown(socket.SHUT_RDWR)
# dilution_socket.close()
# print("Connection closed")



# # define parameters
# thermometer_num = 8
# thermometer_num = int(thermometer_num)
# thermometers = np.linspace(1,8,num=8)
# P = 10
# I = 10
# D = 10
# setpoint = 0.05
# rate = 0.1
# hrange = FindRange(setpoint)
#
# InitThermometersAndHeaters(thermometer_num,dilution_socket) # initialize thermometer.
# time.sleep(.5)
# # command = f'SET:DEV:TEMP:LOOP:CHAN:T{thermometer_num}\n' # define thermometer in the closed loop.
# # dilution_socket.send(command.encode())
# # time.sleep(1)
# command = f'READ:DEV:T{thermometer_num}:TEMP:SIG:TEMP\n' # check current temperature.
# dilution_socket.send(command.encode())
# time.sleep(3)
# response = dilution_socket.recv(5000)
# CurrentTemperature = response.decode().split(":")[-1][:-1]
# CurrentTemperature = CurrentTemperature[:-1]
# print(CurrentTemperature)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:ENAB:OFF\n' # turn off ramp.
# dilution_socket.send(command.encode())
# time.sleep(.5)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:TSET:{CurrentTemperature}\n' # define set-point as the current value.
# dilution_socket.send(command.encode())
# time.sleep(.5)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:RATE:{rate}\n' # set temperature rate.
# dilution_socket.send(command.encode())
# time.sleep(.5)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RANGE:{hrange}\n' # set heater range.
# dilution_socket.send(command.encode())
# time.sleep(.5)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:P:{P}:I:{I}:D:{D}\n' # set PID parameters.
# dilution_socket.send(command.encode())
# time.sleep(.5)
#
# # start PID.
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:MODE:ON\n'  # turn ON closed PID loop.
# dilution_socket.send(command.encode())
# time.sleep(10)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:RAMP:ENAB:ON\n' # turn on ramp.
# dilution_socket.send(command.encode())
# time.sleep(2)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:TSET:{setpoint}\n' # define set-point.
# dilution_socket.send(command.encode())
# time.sleep(2)
# SettleTime = abs(float(CurrentTemperature)-setpoint)/rate
# time.sleep(SettleTime+30)
# command = f'READ:DEV:T{thermometer_num}:TEMP:SIG:TEMP\n' # read temperature.
# dilution_socket.send(command.encode())
# time.sleep(.5)
# response = dilution_socket.recv(5000)
# NewTemperature = response.decode().split(":")[-1][:-1]
# NewTemperature = NewTemperature[:-1]
# print(NewTemperature)
# command = f'SET:DEV:T{thermometer_num}:TEMP:LOOP:MODE:OFF\n' # turn OFF closed PID loop.
# dilution_socket.send(command.encode())
# time.sleep(1)
#
#
#
#
# # Close the dilution socket.
# dilution_socket.close()
# print("Connection closed")
