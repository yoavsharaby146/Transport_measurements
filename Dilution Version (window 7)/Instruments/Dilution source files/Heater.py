from tkinter import *
import time
import numpy as np


class Heater:
    """GUI helper that uses a :class:`DilutionInstrument` instance.

    The previous version of ``Heater`` received a raw socket and called
    loosely-related free functions from ``TemperatureControl``.  The
    refactored class instead accepts the instrument object and invokes
    methods on it directly.
    """

    def __init__(self, win, createDefaultValue, instrument):
        # instrument is expected to be an instance of DilutionInstrument
        self.inst = instrument

        xLim = 680
        xSifh = 90
        yLim = 2
        c = 2
        yLocShift = 30
        self.HTRflag = False  # heater flag off
        # Box for temperature display
        self.entry_temp = StringVar()  # initialize temperature display
        self.t49 = Entry(textvariable=self.entry_temp, width=8)
        self.t49.place(x=500, y=22)
        self.lbl49 = Label(win, text='Temp. (K)')
        self.lbl49.place(x=500, y=yLim)
        self.b7 = Button(win, text='Heater ON', height=1, width=8,
                         command=self.startHTR, fg='green')
        self.b7.place(x=500, y=yLim + 3.5 * yLocShift)
        self.t54 = createDefaultValue(win, '8')     # choose thermometer channel.
        self.t54.place(x=500-xSifh, y=22)
        self.lbl54 = Label(win, text='Channel')
        self.lbl54.place(x=500-xSifh, y=yLim)
        self.t55 = createDefaultValue(win, '1')     # choose heater set point.
        self.t55.place(x=500, y=yLim + 2.5 * yLocShift)
        self.lbl55 = Label(win, text='Setpoint (K)')
        self.lbl55.place(x=500, y=yLim + 1.7 * yLocShift)
        self.t56 = createDefaultValue(win, '0.1')               # choose heater Rate.
        self.t56.place(x=500 - xSifh, y=yLim + 2.5 * yLocShift)
        self.lbl56 = Label(win, text='Rate (K/min)')
        self.lbl56.place(x=500 - xSifh, y=yLim + 1.7 * yLocShift)
        self.win = win
        self.thermometer_num = None

    def startHTR(self):
        self.HTRflag = True  # heater flag on.
        self.thermometer_num = int(self.t54.get())
        self.setpoint = float(self.t55.get())
        self.rate = float(self.t56.get())
        self.b7.config(text='Heater OFF', command=self.interStop, fg='red')
        self.inst.init_thermometers_and_heaters(self.thermometer_num)
        self.inst.set_temperature(self.thermometer_num, self.rate, self.setpoint)

    def updateRange(self, temp):
        hrange = self.inst.find_range(temp)
        self.inst.set_heater_range(self.thermometer_num, hrange)

    def stabilizeTemp(self):
        temp = self.inst.get_temperature(self.thermometer_num)
        threshold = 0.005
        while abs(temp - self.setpoint) > threshold:
            temp = self.inst.get_temperature(self.thermometer_num)
            if temp == 0:
                time.sleep(1)
            else:
                self.updateRange(temp)
                self.entry_temp.set(str(temp))
            self.win.update()
            time.sleep(1)
        time.sleep(10)

    def startAndStabilize(self):
        self.thermometer_num = int(self.t54.get())
        self.setpoint = float(self.t55.get())
        self.rate = float(self.t56.get())
        self.b7.config(text='Heater OFF', command=self.interStop, fg='red')
        self.inst.init_thermometers_and_heaters(self.thermometer_num)
        self.inst.set_temperature(self.thermometer_num, self.rate, self.setpoint)
        self.stabilizeTemp()

    def setTempStep(self, state, parameters, nextMeas):
        self.b7.config(text='Heater OFF', command=self.interStop, fg='red')
        self.thermometer_num = parameters[0]
        self.setpoint = float(parameters[1])
        self.rate = parameters[2]
        if nextMeas == "RT Delta":
            self.HTRflag = True
            self.inst.init_thermometers_and_heaters(self.thermometer_num)
            self.inst.set_temperature(self.thermometer_num, self.rate, self.setpoint)
        else:
            if state == 0:
                self.inst.init_thermometers_and_heaters(self.thermometer_num)
            self.inst.set_temperature(self.thermometer_num, self.rate, self.setpoint)
            self.stabilizeTemp()

    def interStop(self):
        self.inst.stop_heater(self.thermometer_num)
        self.HTRflag = False
        self.b7.config(text='Heater ON', command=self.startHTR, fg='green')
