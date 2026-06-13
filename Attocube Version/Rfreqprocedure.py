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
import keithley6221_with_add_ons
from pymeasure.adapters import VISAAdapter, adapter
from PyANC350v4 import Positioner 
from PyattoDRY import Cryostat
from pymeasure.instruments.keithley import Keithley2450
from pymeasure.instruments.yokogawa import Yokogawa7651
from SR830_with_add_ons import SR830
from signalrecovery7265_with_add_ons import DSP7265
from pymeasure.experiment import Procedure, Results, Worker
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
from pymeasure.display import Plotter
from pymeasure.display.Qt import QtGui,QtCore
from re import match as re_match
from re import compile as re_compile



class RfreqProcedure(Procedure):
##    lockin1_RES = Parameter('SR830#1 Resistor (Ohm)', default= 1e7)
    freq_list1=Parameter('freq_list1 (Hz)')
    freq_list2=Parameter('freq_list2 (Hz)')
    lockins_VOLT = Parameter('SR830#1 Voltage Output (V)', default= 0.1)
    KE6221_Curr1 = Parameter('KE6221 Curr Amp (A)', default= 1e-4)
    KE6221_FRQ1 = Parameter('KE6221 Curr Frq (Hz)', default= 173.21)
    KE6221_Curr2 = Parameter('KE6221 Curr Amp (A)', default= 1e-4)
    KE6221_FRQ2 = Parameter('KE6221 Curr Frq (Hz)', default= 117.31)

    ##lockin1_frq = Parameter('SR830#1 Freq (Hz)', default = 11.568)
##    lockin2_RES = Parameter('SR830#2 Resistor (Ohm)', default= 10e6)
##    lockin2_VOLT = Parameter('SR830#2 Voltage Output (V)', default= 5)
##    lockin2_frq = Parameter('SR830#2 Freq (Hz)', default= 17.079)
    DATA_COLUMNS = ['time(s)','freq1','freq2','Tsample(K)','field(T)','theta(deg)','phi(deg)',
                    'Tmagnet(K)','mag0deg(V)','phase0deg(deg)',
                    'mag90deg(V)','phase90deg(deg)','mag30deg(V)','phase30deg(deg)','mag60deg(V)','phase60deg(deg)']
    acq_delay = Parameter ('Acquisition  Delay (s)', default = 0.5)


    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        self.sourcemeter1 = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.sourcemeter2 = keithley6221_with_add_ons.Keithley6221("GPIB::13")
        log.info("Setting the current")
        self.sourcemeter1.waveform_amplitude = 0.0001
        print("aaa")
        self.sourcemeter1.waveform_frequency = self.freq_list1[0]
        print("bbb")
        self.sourcemeter2.waveform_frequency = self.freq_list2[0]
        print("safsaas")
        self.sourcemeter2.waveform_amplitude = 0.0001
        self.sourcemeter1.waveform_arm()
        self.sourcemeter2.waveform_arm()
        time.sleep(0.5)
        self.sourcemeter1.waveform_start()
        self.sourcemeter2.waveform_start()
        time.sleep(0.5)
        log.info("Waiting for the lockin stabilitity")
        time.sleep(self.acq_delay)
        self.lockin1 = SR830("GPIB::8")
        log.info("lockin1")
        self.lockin2 = SR830("GPIB::9")
        log.info("lockin2")
        self.lockin3 = SR830("GPIB::10")
        log.info("lockin3")
        self.lockin4 = SR830("GPIB::11")
        log.info("lockin4")        
##        self.lockin2 = SR830("GPIB::8")
##        log.info("lockin2")
        self.attoDRY = Cryostat("COM4")
        log.info("attoDRY")
##        self.Keithley = Keithley2450("GPIB::18")
##        log.info("Connected to KE2450")
        log.info("Connected to devices!")

##        log.info("Configuring attoDRY log path")
##        log_path = os.path.dirname(os.path.realpath(__file__))
##        log_path = log_path + '\\'+ r'2022-09-07 cooldown with exchange.txt'
##        time_log = 2 #30 seconds attoDRY logging
##        append = 1
##        self.attoDRY.startLogging(log_path,time_log,append)
##        log.info("attoDRY logging started")


    
    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        freq1=self.sourcemeter1.waveform_frequency
        freq2=self.sourcemeter2.waveform_frequency
        field = self.attoDRY.getMagneticField()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        v1_phase1 = self.lockin1.snap("R","Theta")
        v2_phase2 = self.lockin2.snap("R","Theta")
        v3_phase3 = self.lockin3.snap("R","Theta")
        v4_phase4 = self.lockin4.snap("R","Theta")

        
##        v2_phase2 = self.lockin2.snap("R","Theta")
        return [tsec,freq1,freq2,Tsample,field,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],
                v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],v4_phase4[0],v4_phase4[1]]

    def execute(self):
        time_0 = time.time()
        current_time = 0
        print("fff")
        for i in range(0,min(len(self.freq_list1),len(self.freq_list2))):
            print("eee")
            self.sourcemeter1.waveform_frequency = self.freq_list1[i]
            self.sourcemeter2.waveform_frequency = self.freq_list2[i]
            self.sourcemeter1.waveform_arm()
            self.sourcemeter2.waveform_arm()
            time.sleep(0.5)
            self.sourcemeter1.waveform_start()
            self.sourcemeter2.waveform_start()
            time.sleep(0.5)
            log.info("Waiting for the lockin stabilitity")
            time.sleep(self.acq_delay)
            data=self.getmeas (time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            current_time = data[0]
        log.info("Condition Reached!")


           
    def shutdown(self):
##        sys.exit()
        self.sourcemeter1.waveform_abort()
        self.sourcemeter2.waveform_abort()
        self.anc.disconnect()
        log.info("ANC disconnected")
        self.attoDRY.Disconnect()
        log.info("attoDRY disconnected")
        log.info("Finished measuring")
        

new_logging = False
# avoiding double logging
def main(freq_list1,freq_list2,delay=60):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True

    
    log.info("Constructing an RtProcedure")
    procedure = RfreqProcedure()
    procedure.freq_list1 = freq_list1
    procedure.freq_list2 = freq_list2
    procedure.acq_delay=delay
    data_filename = 'Rfreq'  + str(int(time.time())) +'.csv'
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

##if __name__ == "__main__":
##    main(10)
