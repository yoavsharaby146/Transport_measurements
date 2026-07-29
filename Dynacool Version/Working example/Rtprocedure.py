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





class RtProcedure(Procedure):
    class Rt_RV_RH_sequencer_measurement(Procedure):
        Title = Parameter('Combination sequence measurement', default='measurement type')
        Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
        Contacts = Parameter('Contacts ', default='insert contact numbers')
        Gate_contacts = Parameter('Gate', default='Insert gate contacts')
        Type = ListParameter('Measurement Type', choices=['Rt', 'RV', 'RH'], default='Rt')

        Target_field = FloatParameter('Target field (T)', group_by='Type', group_condition='RH', default=0)
        sweep_rate = FloatParameter('Sweep rate (T/min)', group_by='Type', group_condition='RH', default=0.1)

        Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type', group_condition='RV', default=0)
        step_size = FloatParameter('Step size(mV)', group_by='Type', group_condition='RV', default=1)
        smu = ListParameter('User defined SMU', choices=['Gate_1', 'Gate_2', 'smua', 'smub'], group_by='Type',
                            group_condition='RV', default='Gate_1')

        acq_length = IntegerParameter('Acquisition Length (s)', group_by='Type', group_condition='Rt', default=3600)
        acq_delay = FloatParameter('Acquisition Delay (s)', default=1)
        devices = BooleanParameter("Device in use", default=False)
        use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
        use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
        use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
        use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
        use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
        use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

        srs860_1_sine_voltage = Metadata("SRS860_1 sine voltage", default=math.nan)
        srs860_1_frequency = Metadata("SRS860_1 frequency (Hz)", default=math.nan)
        srs830_1_sine_voltage = Metadata("SRS830_1 sine voltage", default=math.nan)
        srs830_1_frequency = Metadata("SRS830_1 frequency (Hz)", default=math.nan)
        srs830_2_sine_voltage = Metadata("SRS830_2 sine voltage", default=math.nan)
        srs830_2_frequency = Metadata("SRS830_2 frequency (Hz)", default=math.nan)

        DATA_COLUMNS = BASE_DATA_COLUMNS + LOCKIN_VOLTAGE_COLUMNS + MAGNET_COLUMNS


    def startup(self):
        log.info("Connecting and configuring the piezo, Dynacool PPMS and devices")
        self.anc = Positioner()
        log.info("ANC")
        time.sleep(0.5)
        self.sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        self.lockin = SR860("GPIB::1")
        self.lockin2 = SR860("GPIB::2")
        #self.lockin3 = SR830("GPIB::3")
        self.lockin3 = SR860("GPIB::3")
        self.lockin4 = SR860("GPIB::4")
        self.yoko = Yokogawa7651("GPIB::17")
        log.info("Connected to devices!")
        log.info("waiting for temperature readings")
        while self.ppms.getSampleTemperature() == 0:
            time.sleep(0.5)
            print(".",end='')
        log.info("Connected to devices!")
##        self.Current_PEAK = self.sourcemeter.waveform_amplitude
##        self.Current_FREQ = self.sourcemeter.waveform_frequency
##        self.SR830_GAIN = self.lockin.sensitivity
##        self.SR860_GAIN = self.lockin2.sensitivity

    def get_gate(self):
        return float(self.yoko.ask("OD").split('\r\n')[0])

    def getmeas(self,time_0 = 0):
        log.info("measuring")
        tsec = time.time() - time_0
        field = self.ppms.getMagneticField()
        gate = self.get_gate()
        Tsample = self.ppms.getSampleTemperature()
        Tmagnet = self.ppms.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
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
        Current_PEAK = self.sourcemeter.waveform_amplitude
        output = [tsec,Tsample,field,theta,phi,Tmagnet,gate,v1_phase1[0],v1_phase1[1], v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1],
                      v4_phase4[0],v4_phase4[1],Current_PEAK,overflow1,overflow2]
        return output


    def execute(self):
        time_0 = time.time()
        log.info("starting to measure for %d seconds", self.acq_length)
        # While Loop through until acquisition length is done
        current_time = 0
        counter = 1
        #self.ppms.goToBaseTemperature()
        while (current_time < self.acq_length):
##            print("trying sr860 arange")
##            time.sleep(1)
##            self.lockin.auto_range()
##            time.sleep(1)
##            print("trying sr830 arange")
##            time.sleep(1)
##            self.lockin2.auto_range()
##            time.sleep(1)
##            print("trying to take data")
##            time.sleep(1)
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            current_time = data[0]
            time.sleep(self.acq_delay)


    def shutdown(self):
        log.info("Finished measuring")


new_logging = False
# avoiding double logging
def main(ppms, folder_path, acq_length=24*60*60):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True

    log.info("Constructing an RtProcedure")
    procedure = RtProcedure()
    procedure.acq_length = acq_length

    # Eyal: use the Cryostat that is given as a parameter
    procedure.ppms = ppms

    data_filename = 'Rt'  + str(int(time.time())) +'.csv'
    log.info("Constructing the Results with a data file: %s" % data_filename)
    data_filename = f"{folder_path}\\{data_filename}"
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
    time.sleep(0.5)
    log.info("Closing the plotter")
    log.info("Finished the measurement")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: Rtprocedure.py [filepath] [acqlen]")
        exit()
    ppms = Cryostat()
    fldr = sys.argv[1]
    acqlen = int(sys.argv[2])
    main(ppms, fldr, acqlen)
