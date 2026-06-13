# Import necessary packages
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import time
import numpy as np
import os
from PyANC350v4 import Positioner 
from RPCPyattoDRYClient import Cryostat
import keithley6221_with_add_ons
from SR860_with_add_ons import SR860
from SR830_with_add_ons import SR830
import pymeasure
from pymeasure.log import console_log
from pymeasure.adapters import VISAAdapter, adapter
from pymeasure.instruments.yokogawa import Yokogawa7651
from pymeasure.display import Plotter
from pymeasure.experiment import Procedure, Results, Worker
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread

import pyqtgraph as pg
from re import match as re_match
from re import compile as re_compile


class RTProcedure(Procedure):
    Current_PEAK = Parameter('KE6221 Curr Peak (A)', default= 100e-6)
    Current_FREQ = Parameter('KE6221 Curr Freq (Hz)', default= 11.189)
    SR830_GAIN = Parameter('SR830#1 SENS (V)', default= 1)
    SR860_GAIN = Parameter('SR860#2 SENS (V)', default= 1)
    DATA_COLUMNS = ['time(s)','Tsample(K)','Field(T)','Gate(V)','Tmagnet(K)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)']
    acq_delay = Parameter ('Acquisition  Delay (s)', default = 0.5)
    acq_length = Parameter ('Acquisition  Length (s)', default = 10)


    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.lockin = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        log.info("lockin")
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Yokogawa")
        log.info("Connected to devices!")
        log.info("waiting for temperature readings")
        while self.attoDRY.getSampleTemperature() == 0:
            time.sleep(0.5)
            print(".",end='')
##        self.attoDRY.toggleFullTemperatureControl()
##        time.sleep(2)
##        self.attoDRY.toggleFullTemperatureControl()
##        log.info("Temperature control initialized")
        log.info("Connected to devices!")
        
    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])
    
    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        field = self.attoDRY.getMagneticField()
        gate = self.get_gate()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        v1_phase1 = self.lockin.snap("R","Theta")
        v2_phase2 = self.lockin2.snap("R","Theta")
        return [tsec,Tsample,field,gate,Tmagnet,v1_phase1[0],v1_phase1[1],
                v2_phase2[0],v2_phase2[1]]
    
    def execute(self):
        time_0 = time.time()
        log.info("starting to sweep Temperature to %g Kelvin", self.temperature_setpoint)
        log.info("waiting for temperature readings")
        while self.attoDRY.getSampleTemperature() == 0:
            time.sleep(0.5)
            print(".",end='')
        current_temperature = self.attoDRY.getSampleTemperature()
        # make sure that the temperature toggle is on
        time.sleep(1)
        ToggleFlag = self.attoDRY.isControllingTemperature()
        if ToggleFlag == 0:
##            print(ToggleFlag)
            time.sleep(1)
            self.attoDRY.toggleFullTemperatureControl()
        deltaT = self.temperature_setpoint - current_temperature
        Taccuracy = 0.005
##        while abs(deltaT) > Taccuracy:
        ntemp = int(np.abs(deltaT / self.temperature_step))
        temps = np.linspace(current_temperature,self.temperature_setpoint,ntemp)
        for temp in temps:
            self.attoDRY.setUserTemperature(temp)
            current_temperature = self.attoDRY.getSampleTemperature()
            deltaT = temp - current_temperature
            counter = 0
            while abs(deltaT) > Taccuracy:
                counter = counter + 1
##                if counter > 30:
##                    # make sure that the temperature toggle is on
##                    time.sleep(1)
##                    ToggleFlag = self.attoDRY.isControllingTemperature()
##                    if ToggleFlag == 0:
##                        time.sleep(1)
##                        self.attoDRY.toggleFullTemperatureControl()
##                    else:
##                        log.info("Initializing temperature control")
##                        self.attoDRY.toggleFullTemperatureControl()
##                        time.sleep(2)
##                        self.attoDRY.toggleFullTemperatureControl()
##                        self.attoDRY.setUserTemperature(temp)
##                        log.info("Waiting after initialization 60s")
##                        time.sleep(60)
##                    counter = 0
                    
    ##            self.lockin.auto_range()
    ##            self.lockin2.auto_range()
                time.sleep(self.temperature_delay)
                data = self.getmeas(time_0)
                self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
                current_temperature = data[1]
                deltaT = temp - current_temperature
##            current_temperature = self.attoDRY.getSampleTemperature()
##            deltaT = self.temperature_setpoint - current_temperature
        log.info("Condition Reached!")
        
    def shutdown(self):
        log.info("Finished measuring")

new_logging = False
# avoiding double logging        
def main(attoDRY, folder_path, temperature_setpoint, temperature_delay, temperature_step):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True
    log.info("Constructing an RTProcedure")
    procedure = RTProcedure()
    procedure.temperature_setpoint = temperature_setpoint
    procedure.temperature_delay = temperature_delay
    procedure.temperature_step = temperature_step
    # Eyal: use the Cryostat that is given as a parameter
    procedure.attoDRY = attoDRY
    data_filename = 'RT'  + str(int(time.time())) +'.csv'
    data_filename = f"{folder_path}\\{data_filename}"
    log.info("Constructing the Results with a data file: %s" % data_filename)
    results = Results(procedure, data_filename)
    log.info("Constructing the Plotter")
    plotter = Plotter(results)
    plotter.start()
    log.info("Started the Plotter")
    log.info("Constructing the Worker")
    worker = Worker(results)
    worker.run()
    log.info("Started the Worker")
    plotter.should_stop()
    plotter.stop()
    time.sleep(0.1)
    log.info("Closing the plotter")
    log.info("Joining with the worker in at most 4 hours")
    #worker.join(timeout=14400) # wait at most 24 hr 
    log.info("Finished the measurement")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: Rtemprocedure.py [filepath] [temperature_setpoint] [temperature_delay] [temperature_step]")
        exit()
    attoDRY = Cryostat(port=1818)
    fldr = sys.argv[1]
    Tsp = float(sys.argv[2])
    Tdel = float(sys.argv[3])
    Tstep = float(sys.argv[4])
    main(attoDRY, fldr, Tsp,Tdel,Tstep)
    


    


