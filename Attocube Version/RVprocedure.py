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


class RVProcedure(Procedure):
    Current1_RMS = Parameter('KE6221 Curr Amp1 (A)', default= 100e-6)
    Current2_RMS = Parameter('KE6221 Curr Amp2 (A)', default= 100e-6)
    Current1_FREQ = Parameter('KE6221 Curr Freq1 (Hz)', default= 17.321)
    Current2_FREQ = Parameter('KE6221 Curr Freq2 (Hz)', default= 16.331) 
    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','theta(deg)','phi(deg)',
                    'Tmagnet(K)', 'gate(V)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)','mag3(V)',
                    'phase3(deg)','mag4(V)','phase4(deg)','Current_PEAK(A)','overflow indicator1','overflow indicator2']
    manual_phase = Parameter ('Manual Lockins Phase (deg)', default = -90)

    data_points = Parameter('Data points', default=50)
    final_voltage = Parameter ('Final Voltage (V)', default = 1.0)
    voltage_delay = Parameter ('Voltage Delay (s)', default = 3)
    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(0.5)
        self.lockin = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        #self.lockin3 = SR830("GPIB::3")
        self.lockin3 = SR860("GPIB::3")
        self.lockin4 = SR860("GPIB::4")
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        log.info("lockins")       
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Yokogawa")
        log.info("Connected to devices!")
##        self.yoko.enable_source() # set gate output on

    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])

    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        field = self.attoDRY.getMagneticField()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        gate = self.get_gate()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        Current_PEAK = self.sourcemeter.waveform_amplitude
        while True:
            try:
                time.sleep(0.2)
                v1_phase1 = self.lockin.snap("R","Theta")
                time.sleep(0.2)
                v2_phase2 = self.lockin2.snap("R","Theta")
                time.sleep(0.2)
                v3_phase3 = self.lockin3.snap("R","Theta")
                time.sleep(0.2)
                v4_phase4 = self.lockin4.snap("R","Theta")
                time.sleep(0.2)
                overflow1 = float(self.lockin2.ask("ILVL?"))
                time.sleep(0.2)
                overflow2 = float(self.lockin4.ask("ILVL?"))
                break
##                if overflow1!=4.0 and overflow2!=4.0:
##                    break
            except:
                print("error with lockins")
                time.sleep(1)
        
##        v1_phase1 = self.lockin.snap("R","Theta")
##        v2_phase2 = self.lockin2.snap("R","Theta")
##        v3_phase3 = self.lockin3.snap("R","Theta")
##        v4_phase4 = self.lockin4.snap("R","Theta")
##            return [tsec,Tsample,field,theta,phi,Tmagnet,gate,
##               v1_phase1[0],v1_phase1[1],v2_phase2[0],v2_phase2[1],
##               v3_phase3[0],v3_phase3[1],v4_phase4[0],v4_phase4[1]]
        output = [tsec,Tsample,field,theta,phi,Tmagnet,gate,v1_phase1[0],v1_phase1[1], v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],
                      v4_phase4[0],v4_phase4[1],Current_PEAK,overflow1,overflow2]
        return output
        

    def execute(self):
        time_0 = time.time()
        log.info("starting to sweep to %f voltage",self.final_voltage)
        voltages = np.linspace(self.get_gate(),self.final_voltage, num=self.data_points)
        range_val = np.max(np.abs(voltages))
        self.yoko.source_voltage_range = range_val # change range to maximum in range
        time.sleep(1.0)
        for voltage in voltages: #looping for all voltages from current gate to final gate
            self.yoko.ramp_to_voltage(voltage,25,1)
            time.sleep(self.voltage_delay)
##            self.lockin.auto_range()
##            self.lockin2.auto_range()
            time.sleep(6)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
        log.info("Condition Reached!")
           
    def shutdown(self):
##        sys.exit()
##        self.anc.disconnect()
##        log.info("ANC disconnected")
##        self.attoDRY.Disconnect()
##        log.info("attoDRY disconnected")
        log.info("Finished measuring")
        

new_logging = False
# avoiding double logging

def main(attoDRY, folder_path, final_voltage, data_points, voltage_delay):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True
    log.info("Constructing an RVProcedure")
    procedure = RVProcedure()
    procedure.data_points = data_points
    procedure.final_voltage = final_voltage
    procedure.voltage_delay = voltage_delay
    # Eyal: use the Cryostat that is given as a parameter
    procedure.attoDRY = attoDRY
    data_filename = 'RV'  + str(int(time.time())) +'.csv'
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
##    log.info("Joining with the worker in at most 2 acqusition lengths")
    #worker.join(timeout=14400) #wait at most 24 hr
    plotter.should_stop()
    plotter.stop()
    time.sleep(0.1)
    log.info("Closing the plotter")
    log.info("Finished the measurement")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: RVprocedure.py [filepath] [final_voltage] [data_points] [voltage_delay]")
        exit()
    attoDRY = Cryostat(port=1818)
    fldr = sys.argv[1]
    fv = float(sys.argv[2])
    dp = int(sys.argv[3])
    vd = float(sys.argv[4])
    main(attoDRY,fldr,fv,dp,vd)
