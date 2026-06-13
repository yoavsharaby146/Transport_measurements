# Import necessary packages
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from pymeasure.log import console_log
import time
import numpy as np
import os
import pymeasure
from pymeasure.adapters import VISAAdapter, adapter
from PyANC350v4 import Positioner 
from PyattoDRY import Cryostat
from SR830_with_add_ons import SR830
from SR860_with_add_ons import SR860
from pymeasure.experiment import Procedure, Results, Worker
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
from pymeasure.display import Plotter
from pymeasure.display.Qt import QtGui,QtCore
from re import match as re_match
from re import compile as re_compile


# Eyal: look for breaking key press
import msvcrt
def key_pressed():
    if msvcrt.kbhit():
        return msvcrt.getch()
    return None


class RHProcedurePtbyPt(Procedure):
    lockin1_RES = Parameter('SR830#1 Resistor (Ohm)', default= 1e7)
    lockin1_VOLT = Parameter('SR830#1 Voltage Output (V)', default= 2.5)
    lockin1_FREQ = Parameter('SR830#1 Freq (Hz)', default= 92.08)
    lockin1_GAIN = Parameter('SR830#1 Gain (V/V)', default= 500)
    
##    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','theta(deg)','phi(deg)',
##                    'Tmagnet(K)','mag(V)','phase(deg)']
    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','theta(deg)','phi(deg)',
                    'Tmagnet(K)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)']
    acq_delay = Parameter ('Acquisition  Delay (s)', default = 0.3)
    dwell_time = Parameter ('Dwell  Time (s)', default = 10)
    start_field = Parameter ('Field Start (T)', default = 0)
    end_field = Parameter ('Field End (T)', default = 1)
    field_tol = Parameter('Field Tolerance(T)',default = 0.0005)
    data_points = Parameter('Data Points', default = 10)

    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(0.5)
        self.lockin = SR860("GPIB::14")
        self.lockin2 = SR830("GPIB::11")
        log.info("lockin1")       
##        self.attoDRY = Cryostat("COM4")
        log.info("attoDRY")
        log.info("Connected to devices!")

    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        field = self.attoDRY.getMagneticField()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        v1_phase1 = self.lockin.snap("R", "Theta")
        v2_phase2 = self.lockin2.snap("R", "Theta")
##        return [tsec,Tsample,field,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1]]
        return [tsec,Tsample,field,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],v2_phase2[0],v2_phase2[1]]



    def sleep_get_h(self):
        h = self.attoDRY.getMagneticField()
        time.sleep(0.2)
        return h
    
    def wait_for_field(self,H,back_avg = 10,tol = 0.001):
        avg = np.sum([np.abs(H-self.sleep_get_h()) for i in range(back_avg)]) / back_avg
        while avg > tol:
            log.info("Going to %fT, %fT away...  ", H, avg)
            avg = np.sum([np.abs(H-self.sleep_get_h()) for i in range(back_avg)]) / back_avg
            
    def go_to_field(self,H):
        self.attoDRY.setUserMagneticField(H)
        time.sleep(.5)
        self.wait_for_field(H)
               
    def execute(self):
        time_0 = time.time()
        log.info("Going to %f T...", self.start_field)
        if self.attoDRY.isControllingField() == 0:
            time.sleep(0.5)
            self.attoDRY.toggleMagneticFieldControl()
            
        self.go_to_field(self.start_field)
           
        for field in np.linspace(self.start_field,self.end_field,self.data_points + 1)[1:]:
            log.info("Going to %f T...", field)
            self.go_to_field(field)
            
            # Eyal: pressing 'Esc' breaks the loop
            if key_pressed() == b'\x1b':
                log.info("Exit key pressed.")
                self.attoDRY.setUserMagneticField(self.attoDRY.getMagneticField())
                break
                
            time_in_field = time.time()
##            while (time.time() - time_in_field < self.dwell_time): #dwell
##                data = self.getmeas(time_0)
##                self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
##                time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
        log.info("Condition Reached!")
        
    def shutdown(self):
        self.anc.disconnect()
        log.info("ANC disconnected")
##        self.attoDRY.Disconnect()
        log.info("attoDRY disconnected")
        log.info("Finished measuring")

new_logging = False
# avoiding double logging
def main(attoDRY, folder_path, start_field,end_field,data_points=10,dwell_time=10, field_tol = 0.0005):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True

    log.info("Constructing an RHProcedure")
    procedure = RHProcedurePtbyPt()
    
    # Eyal: use the Cryostat that is given as a parameter
    procedure.attoDRY = attoDRY
    
    procedure.start_field = start_field
    procedure.end_field = end_field
    procedure.data_points = data_points
    procedure.dwell_time = dwell_time
    procedure.field_tol = field_tol
    data_filename = 'RH'  + str(int(time.time())) +'.csv'
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
    
    

