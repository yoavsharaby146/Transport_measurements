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


### Eyal: look for breaking key press
##import msvcrt
##def key_pressed():
##    if msvcrt.kbhit():
##        return msvcrt.getch()
##    return None

class RposProcedure(Procedure):
    
    data_points = Parameter('Data points', default=50)

    final_pos = Parameter('Final Positions (deg)', default = 90)
    
    Current_RMS = Parameter('KE6221 Curr RMS (A)', default= 400e-9)
    Current_FREQ = Parameter('KE6221 Curr Freq1 (Hz)', default= 64.835)
    SR830_GAIN = Parameter('SR830#1 Gain (V/V)', default= 100)
    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','gate(V)','theta(deg)','phi(deg)',
                'Tmagnet(K)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)','mag3(V)','phase3(deg)','mag4(V)','phase4(deg)','Current_PEAK(A)','overflow indicator1','overflow indicator2']
    pos_delay = Parameter ('Position Delay (s)', default = 10)
    dwell_time = Parameter ('Dwell Time (s)', default = 0.5)

    def releaseStuckPiezo(self, axisNo, pos):
        print("shake it, shake it, baby!")
        originalAmplitude = self.anc.getAmplitude(axisNo)
        originalFrequency = self.anc.getFrequency(axisNo)
        self.anc.setAmplitude(axisNo, 65)
##        self.anc.setFrequency(axisNo, 1000)
        time.sleep(3)
        self.anc.setAmplitude(axisNo, originalAmplitude)
        self.anc.setFrequency(axisNo, originalFrequency)
        time.sleep(5)
        self.anc.setTargetPosition(axisNo,pos)
        self.anc.setTargetGround(axisNo,0)
        self.anc.startAutoMove(axisNo, 1, 0)
        print("piezo released")
    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(0.5)
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.lockin = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        #self.lockin3 = SR830("GPIB::3")
        self.lockin3 = SR860("GPIB::3")
        self.lockin4 = SR860("GPIB::4")
        log.info("lockin")
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Yokogawa")
        log.info("Connected to devices!")

    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])
    
    def getmeas(self,time_0 = 0):
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
            except:
                time.sleep(1)
        return [tsec,Tsample,field,gate,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],
                v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],
                v4_phase4[0],v4_phase4[1],Current_PEAK,overflow1,overflow2]

        
    
    def gotopos(self,axisNo,pos, printFlag = False):
        self.anc.setTargetPosition(axisNo,pos)
        self.anc.setTargetGround(axisNo,0)
        self.anc.startAutoMove(axisNo, 1, 0)
        ##check what's happening
        moving = 1
        target = 0
        movementStartTime = time.time()
        while target == 0:
            connected, enabled, moving, target, eotFwd, eotBwd, error = self.anc.getAxisStatus(axisNo) #find bitmask of status
            if target == 0:
                if printFlag:
                    print('axis moving, currently at',self.anc.getPosition(axisNo))
            elif target == 1:
                if printFlag:
                    print('axis arrived at',self.anc.getPosition(axisNo))
            time.sleep(0.5)
            if time.time() - movementStartTime > 30:
                print("piezo stuck")
                self.releaseStuckPiezo(axisNo, pos)
                movementStartTime = time.time()
        self.anc.startAutoMove(axisNo, 0, 0)
        self.anc.setTargetGround(axisNo,1)
            

    def execute(self):
        time_0 = time.time()
        log.info("starting to rotate piezo from current position")
        positions = np.linspace(
            self.anc.getPosition(self.axisNo),
            self.final_pos,
            num=self.data_points
        )
        
##        ## costum angle array
##        if self.data_points>150:
##            positions1=np.arange(-100,-80,0.333)
##            positions2=np.arange(-80,-70,1)
##            positions3=np.arange(-70,70,2)
##            positions4=np.arange(70,80,1)
##            positions5=np.arange(80,100,0.333)
##            positions = np.concatenate((positions1, positions2,
##                                         positions3, positions4, positions5))
            
        # Loop through each current point, measure and record the voltage
        for position in positions:
            time_in_pos = time.time()
##            while (time.time() - time_in_pos < self.dwell_time):
##                data = self.getmeas(time_0)
##                self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
##                time.sleep(1.0)
            log.info("Waiting for position delay")
            time.sleep(self.pos_delay)
##            self.lockin.auto_range()
##            self.lockin2.auto_range()
            time.sleep(6)  
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            log.info("Setting the positions to %g deg" % position)
            self.gotopos(self.axisNo,position, printFlag=True)
            time.sleep(1.0)
            
    def shutdown(self):
        self.anc.disconnect()
        log.info("ANC disconnected")
        log.info("Finished measuring")

new_logging = False
# avoiding double logging
def main(attoDRY, folder_path, ax_str = 'phi', final_pos = 0,
         data_points = 10, pos_delay=10, dwell_time = 0.5):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True
    ax = {'theta':0, 'phi':1}
    log.info("Constructing an RposProcedure")
    procedure = RposProcedure()
    # Eyal: use the Cryostat that is given as a parameter
    procedure.attoDRY = attoDRY
    procedure.data_points = data_points
    procedure.final_pos = final_pos
    procedure.axisNo = ax[ax_str]
##    procedure.axisNo2 = ax[ax_str2]
    procedure.pos_delay = pos_delay
    procedure.dwell_time = dwell_time
    
    data_filename = 'Rpos'  + str(int(time.time())) +'.csv'
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
    log.info("Finished the measurement")
    
if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: Rposprocedure.py [filepath] [ax_str] [final_pos] [data_points] [pos_delay] [dwell_time]")
        exit()
    attoDRY = Cryostat(port=1818)
    fldr = sys.argv[1]
    ax = sys.argv[2]
    fp = float(sys.argv[3])
    dp = int(sys.argv[4])
    pd = float(sys.argv[5])
    dw = float(sys.argv[6])
    main(attoDRY,fldr,ax, fp, dp, pd, dw)


    
    
