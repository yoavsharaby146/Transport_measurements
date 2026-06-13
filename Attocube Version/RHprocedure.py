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


# Eyal: look for breaking key press
import msvcrt
def key_pressed():
    if msvcrt.kbhit():
        return msvcrt.getch()
    return None


class RHProcedure(Procedure):
    Current_RMS = Parameter('KE6221 Curr RMS (A)', default= 150e-9)
    Current_FREQ = Parameter('KE6221 Curr Freq (Hz)', default= 36.235)
    SR830_GAIN = Parameter('SR830#1 Gain (V/V)', default= 100)
##    SR830_FREQ = Metadata('SR930 freq', default = 1)
    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','gate(V)','theta(deg)','phi(deg)',
                    'Tmagnet(K)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)','mag3(V)','phase3(deg)','mag4(V)','phase4(deg)','Current_PEAK(A)','overflow indicator1','overflow indicator2']
    
##    manual_phase = Parameter ('Manual Lockins  Phase (deg)', default = -90)
    acq_delay = Parameter ('Acquisition  Delay (s)', default = 0.3)
    acq_length = Parameter ('Acquisition  Length (s)', default = 10)
    
    
    def startup(self):
##        self.SR830_FREQ = 3
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(1)
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.lockin = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        #self.lockin3 = SR830("GPIB::3")
        self.lockin3 = SR860("GPIB::3")
        self.lockin4 = SR860("GPIB::4")
        log.info("lockin")
        time.sleep(1)
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Yokogawa")
        time.sleep(1)
        log.info("Connected to devices!")
        time.sleep(1)
        
    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])
    
    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        field = self.attoDRY.getMagneticField()
        gate = self.get_gate()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        Current_PEAK = self.sourcemeter.waveform_amplitude
        while True:
            try:
                v1_phase1 = self.lockin.snap("R","Theta")
                time.sleep(0.1)
                v2_phase2 = self.lockin2.snap("R","Theta")
                time.sleep(0.1)
                v3_phase3 = self.lockin3.snap("R","Theta")
                time.sleep(0.1)
                v4_phase4 = self.lockin4.snap("R","Theta")
                time.sleep(0.1)
                overflow1 = float(self.lockin2.ask("ILVL?"))
                time.sleep(0.1)
                overflow2 = float(self.lockin4.ask("ILVL?"))
                break
##                if overflow1!=4.0 and overflow2!=4.0:
##                    break
            except:
                time.sleep(1)
        return [tsec,Tsample,field,gate,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],
                v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],
                v4_phase4[0],v4_phase4[1],Current_PEAK,overflow1,overflow2]
    
    def execute(self):
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla", self.field_setpoint)
        current_field = self.attoDRY.getMagneticField()
##        current_field = 20
        time.sleep(0.3)
        try:
            self.attoDRY.setUserMagneticField(self.field_setpoint)
        except:
            print("failed setting magnetic field")
            time.sleep(10)
        if self.attoDRY.isControllingField() == 0:
            time.sleep(0.5)
            self.attoDRY.toggleMagneticFieldControl()
        
        # While Loop  until field setpoint is acheived
        while (abs(current_field - self.field_setpoint) > 0.002):
            
            # Eyal: pressing 'Esc' breaks the loop
            if key_pressed() == b'\x1b':
                log.info("Exit key pressed.")
                self.attoDRY.setUserMagneticField(self.attoDRY.getMagneticField())
                break
##            self.lockin.auto_range()
##            self.lockin2.auto_range()
            time.sleep(2)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            current_field = data[2]
            time.sleep(self.acq_delay)
        log.info("Condition Reached!")
        
    def shutdown(self):
        log.info("ANC disconnected")
        log.info("Finished measuring")


new_logging = False
# avoiding double logging        
def main(attoDRY, folder_path, field_setpoint = 0):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True
        
    log.info("Constructing an RHProcedure")
    procedure = RHProcedure()
    procedure.field_setpoint = field_setpoint
    # Eyal: use the Cryostat that is given as a parameter
    procedure.attoDRY = attoDRY
    

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
    time.sleep(0.5)
    log.info("Closing the plotter")
    log.info("Joining with the worker in at most 4 hours")
    #worker.join(timeout=14400) # wait at most 24 hr 
    log.info("Finished the measurement")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: RHprocedure.py [filepath] [field_setpoint]")
        exit()
    attoDRY = Cryostat(port=1818)
    fldr = sys.argv[1]
    sp = float(sys.argv[2])
    main(attoDRY,fldr,sp)
    

