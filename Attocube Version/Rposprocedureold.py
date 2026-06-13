# Import necessary packages
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
from SR830_with_add_ons import SR830
from signalrecovery7265_with_add_ons import DSP7265
from pymeasure.experiment import Procedure, Results, Worker
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
from pymeasure.display import Plotter

class RposProcedure(Procedure):
    
    data_points = IntegerParameter('Data points', default=50)
    final_pos = FloatParameter('Final Positions', units='deg', default=90)
    lockins_VOLT = Parameter('SR830#1 Voltage Output (V)', default= 0.1)
    #KE6221_Curr1 = Parameter('KE6221 Curr Amp (A)', default= 1e-4)
    #KE6221_FRQ1 = Parameter('KE6221 Curr Frq (Hz)', default= 173.21)
    #KE6221_Curr2 = Parameter('KE6221 Curr Amp (A)', default= 1e-4)
    #KE6221_FRQ2 = Parameter('KE6221 Curr Frq (Hz)', default= 163.31)


##    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','theta(deg)','phi(deg)',
##                    'Tmagnet(K)','mag1(V)','phase1(deg)','mag2(V)','phase2(deg)',
##                    'mag1st7265(V)','phase1st7265(deg)','mag2nd7265(V)','phase2nd7265(deg)']
    DATA_COLUMNS = ['time(s)','Tsample(K)','field(T)','theta(deg)','phi(deg)',
                    'Tmagnet(K)','magDXX(V)','phaseDXX(deg)',
                    'magCXY(V)','phaseCXY(deg)','magDXY(V)','phaseDXY(deg)',]
##     axisNo = Parameter ('AxisNo', default = 0)
##    KE6221_Curr = Parameter('KE6221 Curr Amp (A)', default= 20e-6)
##    KE6221_FRQ = Parameter('KE6221 Curr Frq (Hz)', default= 17.310)
##    lockin2_RES = Parameter('SR830#2 Resistor (Ohm)', default= 1e6)
##    lockin2_VOLT = Parameter('SR830#2 Voltage Output (V)', default= 5)
##    lockin2_frq = Parameter('SR830#2 Freq (Hz)', default= 17.126)
##    SR7265_RES = Parameter('SR7265 Resistor (Ohm)', default= 1e6)
##    SR7265_VOLT = Parameter('SR7265 Voltage Output (V)', default = 1)
##    SR7265_FREQ = Parameter('SR7265 Frequency (Hz)', default = 17.1)
    pos_delay = Parameter ('Position Delay', default = 15)
##    mag_field = Parameter ('Field (T)', default = 9)
    
    def startup(self):
        log.info("Connecting and configuring the piezo, attoDRY and devices")
        self.anc = Positioner()
        log.info("ANC")
        #self.sourcemeter1 = keithley6221_with_add_ons.Keithley6221("GPIB::12")
        #self.sourcemeter2 = keithley6221_with_add_ons.Keithley6221("GPIB::13")
        log.info("Setting the current")
        #self.sourcemeter1.waveform_amplitude = 0.000001
        #self.sourcemeter1.waveform_frequency = 17.321
        #self.sourcemeter2.waveform_amplitude = 0.000001
        #self.sourcemeter2.waveform_frequency = 16.331
        #self.sourcemeter1.waveform_arm()
        #self.sourcemeter2.waveform_arm()
        #time.sleep(0.5)
        #self.sourcemeter1.waveform_start()
        #self.sourcemeter2.waveform_start()
        #time.sleep(0.5)
        log.info("Waiting for the lockin stabilitity")
        time.sleep(60)
        self.lockin1 = SR830("GPIB::9")
        log.info("lockin1")
        self.lockin2 = SR830("GPIB::10")
        log.info("lockin2")
        self.lockin3 = SR830("GPIB::11")
        log.info("lockin3")
        #self.lockin4 = SR830("GPIB::11")
        #log.info("lockin4")         
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
        tsec = time.time() - time_0
        field = self.attoDRY.getMagneticField()
        Tsample = self.attoDRY.getSampleTemperature()
        Tmagnet = self.attoDRY.get4KStageTemperature()
        theta = self.anc.getPosition(0)
        phi = self.anc.getPosition(1)
        v1_phase1 = self.lockin1.snap("R","Theta")
        v2_phase2 = self.lockin2.snap("R","Theta")
        v3_phase3 = self.lockin3.snap("R","Theta")
        #v4_phase4 = self.lockin4.snap("R","Theta")
##        v2_phase2 = self.lockin2.snap("R","Theta")
        return [tsec,Tsample,field,theta,phi,Tmagnet,v1_phase1[0],v1_phase1[1],
                v2_phase2[0],v2_phase2[1],v3_phase3[0],v3_phase3[1]]

    def gotopos(self,axisNo,pos, printFlag = False):
        self.anc.setTargetPosition(axisNo,pos)
        self.anc.setTargetGround(axisNo,0)
        self.anc.startAutoMove(axisNo, 1, 0)
        ##check what's happening
        moving = 1
        target = 0
        while target == 0:
            connected, enabled, moving, target, eotFwd, eotBwd, error = self.anc.getAxisStatus(self.axisNo) #find bitmask of status
            if target == 0:
                if printFlag:
                    print('axis moving, currently at',self.anc.getPosition(axisNo))
            elif target == 1:
                if printFlag:
                    print('axis arrived at',self.anc.getPosition(axisNo))
            time.sleep(0.1)
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
##        print(positions)
        # Loop through each current point, measure and record the voltage
        for position in positions:
            data = self.getmeas(time_0)
            self.emit('results',dict(zip(self.DATA_COLUMNS, data)))
            log.info("Setting the positions to %g deg" % position)
            self.gotopos(self.axisNo,position)
            log.info("Waiting for position delay")
            time.sleep(self.pos_delay)
##            data = self.getmeas(time_0)
##            print('help get data')

##            sleep(0.01)
##            if self.should_stop():
##                log.info("User aborted the procedure")
##                break

    def shutdown(self):
##        self.sourcemeter.waveform_abort()
       # self.sourcemeter1.waveform_abort()
       # self.sourcemeter2.waveform_abort()
        self.anc.disconnect()
        log.info("ANC disconnected")
        self.attoDRY.Disconnect()
        log.info("attoDRY disconnected")
        log.info("Finished measuring")

new_logging = False
# avoiding double logging
def main(ax_str = 'theta',final_pos = 0, data_points = 10, pos_delay=15):
    global new_logging
    if new_logging == False:
        console_log(log)
        new_logging = True
    ax = {'theta':0, 'phi':1}
    log.info("Constructing an RposProcedure")
    procedure = RposProcedure()
    procedure.data_points = data_points
    procedure.final_pos = final_pos
    procedure.axisNo = ax[ax_str]
    procedure.pos_delay = pos_delay
    data_filename = 'Rpos'  + str(int(time.time())) +'.csv'
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
    log.info("Joining with the worker in at most 10 hr")
    #worker.join(timeout=36000) # wait at most 10 hr
    plotter.should_stop()
    plotter.stop()
    time.sleep(0.1)
    log.info("Closing the plotter")
    log.info("Finished the measurement")
