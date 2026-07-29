# Import necessary packages
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import time
import numpy as np
import os
from PyANC350v4 import Positioner
from DynacoolPPMSClient import Cryostat
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


class IVProcedure(Procedure):

    data_points = IntegerParameter('Data points', default=50)
    max_current = FloatParameter('Maximum Current', units='A', default=10e-6)
    min_current = FloatParameter('Minimum Current', units='A', default=-10e-6)
    DATA_COLUMNS = ['Current_PEAK(A)', 'time(s)','Tsample(K)','field(T)',
                    'gate(V)','theta(deg)','phi(deg)','Tmagnet(K)','mag1(V)','phase1(deg)',
                    'mag2(V)','phase2(deg)','mag3(V)','phase3(deg)',
                    'mag4(V)','phase4(deg)','overflow indicator1','overflow indicator2']

    def startup(self):
        log.info("Connecting and configuring the instrument")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(1)
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.lockin1 = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        self.lockin3 = SR860("GPIB::3")
        #self.lockin3 = SR830("GPIB::3")
        self.lockin4 = SR860("GPIB::4")
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Yokogawa")
        time.sleep(0.1) # wait here to give the instrument time to react
        while self.ppms.getSampleTemperature() == 0:
            time.sleep(0.5)
            print(".",end='')

    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])

    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        Tsample = self.ppms.getSampleTemperature()
        field = self.ppms.getMagneticField()
        gate = self.get_gate()
        Tmagnet = self.ppms.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        Current_PEAK = self.sourcemeter.waveform_amplitude
        while True:
            try:
                v1_phase1 = self.lockin1.snap("R","Theta")
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
                if overflow1!=4.0 and overflow2!=4.0:
                    break
            except:
                time.sleep(1)
                print("error with lockins")
        return [Current_PEAK,tsec,Tsample,field,gate,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],v4_phase4[0],v4_phase4[1],overflow1,overflow2]

    def execute(self):
        log.info("starting to sweep currents")
        ## checking the phase of the current
##        self.sourcemeter.waveform_use_phasemarker = 1
##        time.sleep(0.4)
##        self.sourcemeter.waveform_phasemarker_phase = 0
##        time.sleep(0.4)
        time_0 = time.time()
        currents = np.linspace(
            self.min_current,
            self.max_current,
            num=self.data_points
        )

##        ## define costum current array
##        currents1 = 1e-6*np.arange(0.1,3,0.3)
##        currents2 = 1e-6*np.arange(3,6,0.5)
##        currents3 = 1e-6*np.arange(6,20,1)
##        currents4 = 1e-6*np.arange(20,30,2)
##        currents5 = 1e-6*np.arange(30,60,4)
##        currents6 = 1e-6*np.arange(60,100+8,8)
##        currents = np.concatenate((currents1, currents2, currents3,
##                                   currents4, currents5, currents6))


##        self.sourcemeter.waveform_abort()
##        time.sleep(0.5)

##        self.sourcemeter.source_range = 10*self.max_current

##        self.sourcemeter.source_auto_range = True
##        time.sleep(1)
##        self.sourcemeter.waveform_ranging = "best"
##        self.sourcemeter.waveform_ranging = "fixed"

##        self.sourcemeter.waveform_amplitude = self.min_current
##        self.sourcemeter.waveform_arm()
##        time.sleep(0.5)
##        self.sourcemeter.waveform_start()

        # Loop through each current point, measure and record the voltage
        for current in currents:
            log.info("Setting the current to %g A" % current)
            self.sourcemeter.waveform_abort()
            time.sleep(0.4)
            self.sourcemeter.source_range = 10*current
            time.sleep(0.4)
            self.sourcemeter.waveform_amplitude = current
            time.sleep(0.4)
            self.sourcemeter.waveform_arm()
            time.sleep(0.4)
            self.sourcemeter.waveform_start()
            time.sleep(10) # wait for current to rise
            try:
                self.lockin1.auto_range_1w()
                time.sleep(0.4)
                rng1 = self.lockin1.ask("IRNG?")
            except:
                print("lck1 (1w) auto range failed")
                time.sleep(5)
            try:
                self.lockin2.auto_range(rng1)
            except:
                print("lck2 (2w) auto range failed")
                time.sleep(5)
            try:
                self.lockin3.auto_range_1w()
                time.sleep(0.4)
                rng2 = self.lockin3.ask("IRNG?")
            except:
                print("lck3 (1w) auto range failed")
                time.sleep(5)
            try:
                self.lockin4.auto_range(rng2)
            except:
                print("lck2 (2w) auto range failed")
                time.sleep(5)
            #try:
            #    self.lockin3.auto_range_advanced()
            #    time.sleep(0.4)
##          #      rng2 = float(self.lockin3.snap("R")[0])
            #except:
            #    print("lck3 (1w) auto range failed")
            #    time.sleep(5)
            #try:
            #    self.lockin4.auto_range_1w()
            #except:
            #    print("lck4 (2w) auto range failed")
            #    time.sleep(5)

            log.info("Waiting for the lockin stabilitity")
##            time.sleep(15)
            time.sleep(10)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))

##            sleep(0.01)
##            if self.should_stop():
##                log.info("User aborted the procedure")
##                break

    def shutdown(self):
##        self.sourcemeter.waveform_abort()
        log.info("Finished measuring")

def main(ppms, folder_path, min_current, max_current, data_points):
    console_log(log)

    log.info("Constructing an IVProcedure")
    procedure = IVProcedure()
    procedure.data_points = data_points

    procedure.max_current = np.sqrt(2)*max_current # this is the peak current
    procedure.min_current = np.sqrt(2)*min_current
    procedure.ppms = ppms

    data_filename = 'IV'  + str(int(time.time())) +'.csv'
    log.info("Constructing the Results with a data file: %s" % data_filename)
    data_filename = f"{folder_path}\\{data_filename}"
    results = Results(procedure, data_filename)

    log.info("Constructing the Plotter")
    plotter = Plotter(results)
    plotter.start()
    log.info("Started the Plotter")


    log.info("Constructing the Worker")
    worker = Worker(results)
    worker.start()
    log.info("Started the Worker")

    log.info("Joining with the worker in at most 1 hr")
    worker.join(timeout=10800) # wait at most 3 hr
    plotter.should_stop()
    plotter.stop()
    time.sleep(0.1)
    log.info("Closing the plotter")
    log.info("Finished the measurement")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: IVprocedure.py [filepath] [min_current] [max_current] [data_points]")
        exit()
    ppms = Cryostat()
    fldr = sys.argv[1]
    mnc = float(sys.argv[2])
    mxc = float(sys.argv[3])
    dp = int(sys.argv[4])
    main(ppms,fldr,mnc,mxc,dp)

