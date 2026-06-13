from pymeasure.display.Qt import QtCore, QtGui
from pymeasure.display import Plotter
from pymeasure.experiment import Procedure, Results, Worker
from pymeasure.experiment import IntegerParameter, FloatParameter, Parameter
import pymeasure
from pymeasure.adapters import VISAAdapter, adapter
from pymeasure.log import console_log
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import importlib
import matplotlib.pyplot as plt
import time
import numpy as np
import os
import math
import traceback
from PyattoDRY import Cryostat
from re import match as re_match
from re import compile as re_compile



module_names = ['Rtemprocedure','Rtprocedure','RHprocedure','RVprocedure','Rposprocedure',
        'Rposprocedure_wobblefix', 'RHprocedurePtbyPt', 'IVprocedure', 'sequence1']



# Eyal: establish connection with attocube
attoDRY = Cryostat("COM4")
time.sleep(40)
##print(attoDRY)
##<PyattoDRY.Cryostat object at 0x01A0B0D0>
attoDRY.goToBaseTemperature()
time.sleep(5)
attoDRY.Confirm()
while True:
    try:
        command = input("Select procedure and input parameters: ")
        if command == "break":
            break
        else:
            for name in module_names:
                globals()[name] = importlib.import_module(name)
            print(command)
            exec(command)
            for name in module_names:
                del sys.modules[name]
                del globals()[name]
            
    except:
        print("Invalid command.")
        print(traceback.format_exc())
attoDRY.Disconnect()

##import sys
##del sys.modules['mainpanel']
##del mainpanel

##Rtprocedure.main(attoDRY, 100e7)
##RHprocedure.main(attoDRY, 0.01)
##Rposprocedure_wobblefix.main(attoDRY, ax_str ='theta' ,ax_str2 = 'phi',final_pos = -90, data_points = 3, pos_delay=10, anglefix_x=[-360,360],anglefix_y=[0,0], dwell_time = 5)
##Rposprocedure_wobblefix.main(attoDRY, ax_str = 'phi',ax_str2 = 'theta',final_pos = 90, data_points = 10, pos_delay=15, anglefix_x=[-360,360],anglefix_y=[90,90], dwell_time = 5)
##RHprocedurePtbyPt.main(attoDRY, start_field=0,end_field=0.04,data_points=5,dwell_time=10, field_tol = 0.0005)
##RVprocedure.main(attoDRY, 0.5, 10, 2) # gate_start, points, delay
##IVprocdedure.main(1e-6, 5e-6, 5) # Istart(rms), Istop(rms), points
##sequence1.seq(attoDRY)



##Rtemprocedure.main(attoDRY,3,2,0.05) #T_setpoint,T_delay,T_step

####Rposprocedure.main('theta',theta_min,5,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
####Rposprocedure.main('theta',theta_max,100,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
####Rposprocedure.main('theta',theta_min,100,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time

##calibrate in-plane wobble 05.08.2023##
##RHprocedure.main(3.0)
##
##phi_list = np.linspace(-90,90,12)
##theta_min = 85
##theta_max = 95
##
##for phi in phi_list:
##    Rposprocedure.main('phi',phi,5,3,3) #ax_str,final_pos,data_points,pos_delay,dwell_time
##    Rposprocedure.main('theta',theta_min,5,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
##    time.sleep(60)
##    Rposprocedure.main('theta',theta_max,180,20,10) #ax_str,final_pos,data_points,pos_delay,dwell_time

##phi_calib = [-89.42747144, -72.25472222, -56.86619983, -39.37862789, -23.80954767, -7.71967167, 8.32205483,
##             24.65332667, 40.81124611,  57.08134656,  73.46093917,  89.69916094]
##
##theta_plane = [90.10221326, 90.09984617, 90.07796108, 90.11682216, 90.14451508, 90.12482941, 90.16514055,
##               90.16701571, 90.1359418, 90.11282471, 90.07767673, 90.07340202]

####theta_plane = 90 * np.ones_like(phi_calib)
##phi_min = -90
##phi_max = 90
##N_phis = 360
##Rposprocedure_wobblefix.main('phi','theta',phi_max,N_phis,30,phi_calib,theta_plane,5)

##fields = [2.5,2.6,2.7,2.8,2.9,3.0,3.1,3.2,3.4,4,5] # mid to start of SC transition in field
##for field in fields:
##    Rposprocedure.main('phi',phi_min,5,3,3) #go fast to phi_min
##    RHprocedure.main(field)
##    time.sleep(120) #wait for T stability after rotatin and field sweep
##    Rposprocedure_wobblefix.main('phi','theta',phi_max,N_phis,25,phi_calib,theta_plane,10)
##    #ax_str,ax_str,final_pos, data_points,anglefix_x,anglefix_y, dwell_time)
##    ## Rposprocedure.main('phi',phi_max,N_phis,25,7) #go slow to to phi_max
##
##    
    


##attoDRY = Cryostat("COM4")
##attoDRY.setUserTemperature(2.5)
##attoDRY.Disconnect()
##Rtemprocedure.main(50,2,0.1) #T_setpoint,T_delay,T_step
##time.sleep(10)
##N_phis = 20
##phi_list = np.linspace(90,-90,N_phis)
##
###25052023 morning : sequencing out of plane alignmet for many phis###
##phi_pos = phi_list[13:]
##theta_max = 90.5+2
##theta_min = 90.5-2
##N_thetas = 44
##
##for phi in phi_list[2:]:
##    #### for each phi, make sure we at theta_min and then slowly scan to theta_max
##    Rposprocedure.main('theta',theta_min,5,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
##    Rposprocedure.main('theta',theta_min,5,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
##    Rposprocedure.main('phi',phi,5,10,5) #ax_str,final_pos,data_points,pos_delay,dwell_time
##    time.sleep(30)
##    Rposprocedure.main('theta',theta_max,N_thetas,15,5) #ax_str,final_pos,data_points,pos_delay,dwell_time


##Rtemprocedure.main(2.5,10,0.05) #T_setpoint,T_delay,T_step
##time.sleep(5)
##RHprocedure.main(5)
#RHprocedure.main(0)
#attoDRY = Cryostat("COM4")
#attoDRY.setUserTemperature(2)
#attoDRY.Disconnect()
#RHprocedure.main(0)

#Rposprocedure.main('theta','phi',-90.25,25,10,x,y1)
#Rposprocedure.main('theta','phi',-90.25,5,10,x,y1)
#Rposprocedure.main('theta','phi',-89.5,5,10,x,y2)
#Rposprocedure.main('theta','phi',-89.5,5,10,x,y2)
#Rposprocedure.main('theta', 20, 81, 15,5)

##Rposprocedure.main('theta','phi',-90.25,25,10,x,y1)
