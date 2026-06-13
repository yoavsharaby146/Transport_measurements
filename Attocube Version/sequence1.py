import Rtprocedure_old, IVprocedure, RVprocedure,Rtemprocedure,Rtprocedure,RHprocedure,Rposprocedure,Rposprocedure_wobblefix
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import time
import numpy as np
import os
from RPCPyattoDRYClient import Cryostat

folder_path = r"C:\Users\attocube\Desktop\Data\eyal\AttoCubePython - eyal\Shilo and Eyal data files"
attoDRY = Cryostat(port=1818)


##a=89.17
##b=0.803
##anglefix_x = np.linspace(-180, 180, 500)
##anglefix_y = a + b * np.sin(np.deg2rad(anglefix_x)) 
####    Phis = np.arange(90, -120, -30)
##Phis = [90, -60, -90]
##N_Thetas = 200
##Theta_min = -100
##Theta_max = 100
####    anglefix_phi = Phi * np.ones_like(anglefix_x)

fields = [-9, 9]
Gates = [-30, 30, -30, 30]
# Sweep gate from -30V to 30V a few times
for Gate in Gates:
    RVprocedure.main(attoDRY, folder_path, Gate, 90, 3) # final gate, points, delay
    time.sleep(5)
# Fix phi=90, scan H from -9 to 9T, theta = [0, 90]
Phi = 90
Thetas = [-90, 0]
Rposprocedure.main(attoDRY, folder_path, ax_str ='phi',
    final_pos = Phi, data_points = 10, pos_delay=5, dwell_time = 5)
time.sleep(5)
Gates = np.arange(30, -40, -10)
RHprocedure.main(attoDRY, folder_path, 9)
time.sleep(5)
# let the system cooldown
time.sleep(120)
for Gate in Gates:
    RVprocedure.main(attoDRY, folder_path, Gate, 30, 3) # final gate, points, delay
    time.sleep(5)
    idx = 0
    for Theta in Thetas:
        Rposprocedure.main(attoDRY, folder_path, ax_str ='theta',
                           final_pos = Theta, data_points = 30, pos_delay=5, dwell_time = 5)
        time.sleep(5)
        for field in fields:
            RHprocedure.main(attoDRY, folder_path, field)
            time.sleep(5)
            # let the system cooldown
            time.sleep(120)
RHprocedure.main(attoDRY, folder_path, 0)

        

        
    
    
##    for field in fields:
##    time.sleep(3)
##    RHprocedure.main(attoDRY, field)
##    # let the system cooldown
##    print("waiting 4 mins after field sweep...")
##    time.sleep(4*60)
##    for Phi in Phis:
##        #make sure we are at phi 
##        time.sleep(3)
##        Rposprocedure.main(attoDRY, ax_str ='phi',
##                           final_pos = Phi, data_points = 20, pos_delay=5, dwell_time = 5)
##        #make sure we are at Theta min 
##        time.sleep(3)
##        Rposprocedure.main(attoDRY, ax_str ='theta',
##                           final_pos = Theta_min, data_points = 10, pos_delay=5, dwell_time = 5)
##        #let the system cooldown, then scan up to Theta_max
##        time.sleep(120)
##        print("waiting 2 mins before start scannig...")
##        Rposprocedure_wobblefix.main(attoDRY, 'theta' ,'phi', Theta_max, N_Thetas, 7, [-360, 360], [Phi, Phi], 5)
##        #go to Theta_min
##        time.sleep(3)
##        Rposprocedure.main(attoDRY, ax_str ='theta',
##                           final_pos = Theta_min, data_points = 50, pos_delay=5, dwell_time = 5)


##            Rposprocedure_wobblefix.main(attoDRY, ax_str ='theta' ,ax_str2 = 'phi',final_pos = -80,
##                                         data_points = 10, pos_delay=4, anglefix_x=[-360,360],
##                                         anglefix_y=[0,0], dwell_time = 5)
##            Rposprocedure_wobblefix.main(attoDRY, ax_str ='theta' ,ax_str2 = 'phi',
##                                         final_pos = -95, data_points = 40, pos_delay=4,
##                                         anglefix_x=[-360,360],anglefix_y=[0,0], dwell_time = 5)
##RHprocedure.main(attoDRY, folder_path, 9) # target field (T)
##Rposprocedure_wobblefix.main(attoDRY, folder_path, ax_str ='theta' ,ax_str2 = 'phi',final_pos = -90, data_points = 3, pos_delay=10, anglefix_x=[-360,360],anglefix_y=[0,0], dwell_time = 5)
##Rposprocedure_wobblefix.main(attoDRY, folder_path, ax_str = 'phi',ax_str2 = 'theta',final_pos = -90, data_points = 10, pos_delay=15, anglefix_x=[-360,360],anglefix_y=[90,90], dwell_time = 5)
##RHprocedurePtbyPt.main(attoDRY, folder_path, start_field=0,end_field=0.04,data_points=5,dwell_time=10, field_tol = 0.0005)
##RVprocedure.main(attoDRY, folder_path, 0.5, 10, 2) # gate_start, points, delay
##IVprocedure.main(attoDRY, folder_path, 1e-6, 5e-6, 5) # Istart(rms), Istop(rms), points
##Rposprocedure.main(attoDRY, folder_path, ax_str ='theta',final_pos = -100, data_points = 3, pos_delay=5, dwell_time = 5)
##RVprocedure.main(attoDRY, folder_path, 35, 700, 1) # final gate, points, delay
##Rtprocedure.main(attoDRY, folder_path, 10)
##sequence1.seq(attoDRY)





