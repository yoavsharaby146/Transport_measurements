import subprocess
import time
import numpy as np
import RPCPyattoDRYClient
import keithley6221_with_add_ons
from PyANC350v4 import Positioner
import multiprocessing
import psutil
c = RPCPyattoDRYClient.Cryostat()

base = r"C:\Users\attocube\Desktop\Data\eyal\AttoCubePython_eyal"

python_path = r"C:\Users\attocube\AppData\Local\Programs\Python\Python310-32\python.exe"

folder_path = base + "\\Shilo_Eyal_data_files\\KTO 111 20022025 cooldown on 07.04.26\\New cooldown 13.05.26\\hallbar 0\\RH vs T"

rtproc = base + "\\Rtprocedure.py"
rvproc = base + "\\RVprocedure.py"
ivproc = base + "\\IVprocedure.py"
ivprocrange = base + "\\IVprocedureRange.py"
ivprocsetrange = base + "\\IVprocedureSetRange.py"
rposproc = base + "\\Rposprocedure.py"
rhproc = base + "\\RHprocedure.py"
rtemproc = base + "\\Rtemprocedure.py"
rposwfproc = base + "\\Rposprocedure_wobblefix.py"


def run_py(proc,params):
    subprocess.run([python_path,proc] + params)

def Rtproc(acq_time, path = folder_path):
    run_py(rtproc, [path,str(int(acq_time))])
    
def RVproc(final_voltage, data_points, voltage_delay, path = folder_path):
    run_py(rvproc, [path,str(final_voltage),str(int(data_points)),str(voltage_delay)])
def IVproc(min_current, max_current, data_points, path = folder_path):
    run_py(ivproc, [path,str(min_current),str(max_current),str(int(data_points))])
def IVprocRange(min_current, max_current, data_points, path = folder_path):
    run_py(ivprocrange, [path,str(min_current),str(max_current),str(int(data_points))])
def IVprocSetRange(min_current, max_current, data_points, path = folder_path):
    run_py(ivprocsetrange, [path,str(min_current),str(max_current),str(int(data_points))])
def Rposproc(ax_str, final_pos, data_points, pos_delay, dwell_time, path = folder_path):
    run_py(rposproc,[path,str(ax_str), str(final_pos),str(int(data_points)),
                     str(pos_delay),str(dwell_time)])
def Rposwfproc(ax_str, ax_str2, final_pos, data_points, pos_delay, dwell_time, path = folder_path):
    run_py(rposwfproc,[path, str(ax_str), str(ax_str2), str(final_pos),str(int(data_points)),
                     str(pos_delay),str(dwell_time)])  
def RHproc(field_setpoint, path = folder_path):
    run_py(rhproc, [path,str(field_setpoint)])
def Rtemproc(temperature_setpoint, temperature_delay, temperature_step, path = folder_path):
    run_py(rtemproc, [path, str(temperature_setpoint), str(temperature_delay), str(temperature_step)])


def kill_process_tree(pid):
    """Kills a process and all of its descendant processes."""
    try:
        parent = psutil.Process(pid)
        # Grab all child processes recursively
        children = parent.children(recursive=True)
        
        # Terminate children first
        for child in children:
            child.kill()
            
        # Finally, kill the parent
        parent.kill()
    except psutil.NoSuchProcess:
        # The process might have naturally died just before we tried to kill it
        pass

def run_with_timer(function, args_tuple, timer_seconds):
    while True:
        process = multiprocessing.Process(target=function, args=args_tuple)
        process.start()
        
        # Returns after the process is done or the timer is up
        process.join(timeout=timer_seconds) 
        
        if process.is_alive():
            print('Your function timed out, killing process tree and rebooting...')
            
            # Use psutil to kill the main process AND any children it spawned
            kill_process_tree(process.pid)
            
            # Wait for the OS to finalize the termination
            process.join() 
            
            # Optional: Free up resources associated with the process object (Python 3.7+)
            if hasattr(process, 'close'):
                process.close()
                
            time.sleep(1 * 60) # Let it rest for 1 min
            continue
        else:
            # Process finished on its own
            break

##RVproc(-2, 5, 1)



##currents = 1e-6*np.array([0.15, 0.5, 1.15, 3, 10])
##currents = 1e-6*np.array([0.5, 1.15, 3, 10])
##currents = 1e-6*np.array([10, 70, 100, 130])
##min_current = 10e-6
##IVproc(0.75*min_current, min_current, 3)
##time.sleep(10)
##N_Thetas = 200
##Theta_min = -100
##Theta_max = 100
##Phi = 0







##Rtemproc(1.8, 2, 0.015) 
##print("measurement finished")


##RVproc(22, 8, 1)
##IVprocRange(current,current,1)
##RVproc(30, 80, 1)
##RVproc(22, 80, 1)
##print("measurement is over")




##time.sleep(10)
##print("measurement is over")
##
##RHproc(9)
##print("let the system cooldown 5 mins...")
##time.sleep(5*60)
##RHproc(9)



##time.sleep(3*60)
##RVproc(-30,3,1)
##IVproc(0.75*current, current, 2)
##RHproc(9)
##time.sleep(3*60)
##RHproc(-9)
##time.sleep(3*60)
##RHproc(9)
##time.sleep(3*60)
##RHproc(-9)
##time.sleep(3*60)
##RHproc(9)
##time.sleep(3*60)
##RHproc(-9)


##Vgs = np.linspace(-30,30,13)
##
##for Vg in Vgs:
##    RVproc(Vg, 3, 1)
##    IVproc(0.75*current, current, 2)
##    RHproc(9)
##    print("let the system cooldown 3 min...")
##    time.sleep(3*60)
##    RHproc(-9)
##    print("let the system cooldown 3 min...")
##    time.sleep(3*60)
##

##c.setUserTemperature(2.0)
##current_temperature = c.getSampleTemperature()
##while np.abs(current_temperature - 1.7) >= 0.05:
##    time.sleep(1)
##    current_temperature = c.getSampleTemperature()
##print("let the system cooldown 1 min...")
##time.sleep(1*60)
##current_temperature = c.getSampleTemperature()
##while np.abs(current_temperature - 1.7) >= 0.05:
##    time.sleep(1)
##    current_temperature = c.getSampleTemperature()
##print("let the system cooldown 2 min...")
##time.sleep(2*60)
##RVproc(-21.5,10,2)
##RHproc(9)
##IVproc(current, current, 1)
##RHproc(-9)
##time.sleep(3*60)
##RHproc(9)
##time.sleep(3*60)
##print("going to phi=90")
##Rposproc('phi',90,5,5,5)
##IVproc(current, current, 1)
##RHproc(-9)
##time.sleep(3*60)
##RHproc(9)
##time.sleep(3*60)
##print("going to phi=0")
##Rposproc('phi',0,5,5,5)
##print("waiting 3 mins before scanning")
##Rposproc('phi',90,1800,5,5)
##Rposproc('theta',90, 360, 10, 5)



##Vgs = [-30,-18,-10,-5,0,5,10,24,30]
##for Vg in Vgs:
##    RVproc(Vg,5,2)
##    IVprocRange(90e-6,90e-6,1)
##    IVproc(10e-6,90e-6,40)
##RVproc(24,5,2)
##RHproc(0)




##angles = np.linspace(0,90,10)
##for angle in angles:
##    Rposproc('theta', angle, 5, 5, 5)
##    time.sleep(5*60)
##    IVprocRange(current,current,1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)


##Vgs = np.linspace(0,26,14)
##for Vg in Vgs:
##    RVproc(Vg,5,2)
##    time.sleep(10)
##    IVprocRange(current,current,1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)



##Currents = np.linspace(80e-6,90e-6,2)
##for Current in Currents:
##    IVprocRange(Current,Current,1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)




##RHproc(0)
##time.sleep(3*60)
##RVproc(-30,5,2)
##time.sleep(10)
##IVprocRange(current,current,1)
##IVproc(current,current,1)
##RVproc(30,60,2)
##time.sleep(10)
##RVproc(-30,60,2)
##time.sleep(10)
##RVproc(30,60,2)
##time.sleep(10)
##RVproc(-30,60,2)
##time.sleep(10)
##RVproc(30,100,2)
##time.sleep(10)
##RVproc(-30,100,2)
##time.sleep(10)
##RVproc(0,5,2) #find optimal gate
##RHproc(9)
##time.sleep(3*60)


##IVprocRange(current, current, 1)
##RVproc(30, 30, 2)
##time.sleep(10)
##RVproc(-30, 60, 2)
##IVprocRange(current, current, 1)
##for i in range(3):
##    RVproc(30, 60, 2)
##    RVproc(-30, 60, 2)
##
##RVproc(0, 30, 2)
##time.sleep(10)
##IVprocRange(90e-6, 90e-6, 1)
##time.sleep(10)
##IVproc(10e-6, 90e-6, 40)
##time.sleep(10)
##IVprocRange(current, current, 1)

##RHproc(-9)
##time.sleep(2*60)
##IVprocRange(current, current, 1)
##RHproc(9)
##time.sleep(2*60)
##RHproc(-9)

## first data set
##Temps = [15, 20, 25, 30, 35, 40, 45, 50, 70, 100, 150]

## seoncd dataset
##Temps = [2.5, 3.5, 5.5, 8.5, 10, 11, 14, 20]
##Temps = [25, 27.5, 30, 32.5, 35, 37.5, 40, 42.5,
##         45, 47.5, 50, 55, 60, 65, 70, 80, 90,
##         100, 115, 130, 150, 200, 250, 300]


##Temps = [42.5, 45, 47.5, 50, 55, 60, 65, 70, 80, 90,
##         100, 115, 130, 150, 200, 250, 300]

##RHproc(9)
##time.sleep(2*60)
##RHproc(-9)
##
##for temp in Temps:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 5 min...")
##    time.sleep(5*60)
##    
##    c.setUserTemperature(2.5)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)


##gates = [30, 20, 10, 0, -10, -20, -30]
##RVproc(30, 30, 2)
##for gate in gates:
##    RVproc(gate, 10, 2)
##    time.sleep(10)
##    IVprocRange(current, current, 1)
##    time.sleep(10)
##    RHproc(9)
##    print("let the system cooldown 3 min...")
##    time.sleep(3*60)
##    RHproc(-9)



##for temp in Temps:
##    Rtemproc(temp, 0.5, 0.05)
##    time.sleep(5*60)
##    Rtemproc(2.5, 0.5, 0.05)
##    time.sleep(20)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)



##IVprocRange(90e-6,90e-6,1)
##IVproc(10e-6,90e-6, 10)
##
##IVprocRange(current,current, 1)
##RVproc(-30,20,2)
##IVprocRange(current, current, 1)
##RVproc(30,20,2)
##RVproc(-30,20,2)
##RVproc(30,150,2)
##RVproc(-30,150,2)
##IVprocRange(current, current, 1)



##Temps1 = [7.5, 8.25, 8.5, 8.75, 9.5]
##
##RHproc(-9)
#RVproc(-30, 20, 2)
#IVprocRange(current, current, 1)
#RVproc(30, 150, 2)
#time.sleep(10)
#RVproc(-30, 150, 2)
#IVprocRange(current, current, 1)



##for temp in Temps1:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##
##    IVprocRange(current, current, 1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)
##    time.sleep(3*60)



    
##Temps2 = [7, 7.5, 8, 8.25, 8.5, 8.75, 9, 9.5]
##RVproc(30,20,2)

##for temp in Temps2:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##
##    IVprocRange(current, current, 1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)
##    time.sleep(3*60)
##
##RHproc(0)



##Temps = [3.5, 5.5, 8, 10, 15, 25, 32.5, 37.5, 40, 42.5, 47.5, 55, 70, 150]
##Temps = [2.5, 3.5, 5.5, 8, 10, 12, 15, 20, 25, 27.5, 30, 32.5, 35, 37.5, 40, 42.5,
##         45, 47.5, 50, 55, 60, 70, 100, 150]
##
##RVproc(-30,10,2)
##for temp in Temps:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 5 min...")
##    time.sleep(5*60)
##    
##    c.setUserTemperature(2.5)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##
##    IVprocRange(current, current, 1)
##    RVproc(30,150,2)
##    time.sleep(20)
##    RVproc(-30,150,2)


##Rposproc('phi',-100, 20, 5, 5)
##Rposproc('phi',100, 200, 5, 5)

##Rposwfproc('phi', 'theta', 100, 20, 5, 5)

##Fields = [9,8,6]
##
##for field in Fields:
##    
##    RHproc(field)
##    time.sleep(3*60)
##
##    Rposwfproc('phi', 'theta', -94, 195, 5, 5)
##    
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##
##    Rposwfproc('phi', 'theta', 100, 195, 5, 5)
##
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 2.5) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##
##Rposwfproc('phi', 'theta', 90, 5, 5, 5)
##
##current_temperature = c.getSampleTemperature()
##while np.abs(current_temperature - 2.5) >= 0.05:
##    time.sleep(1)
##    current_temperature = c.getSampleTemperature()
##print("let the system cooldown 1 min...")
##time.sleep(1*60)
##
##current_temperature = c.getSampleTemperature()
##while np.abs(current_temperature - 2.5) >= 0.05:
##    time.sleep(1)
##    current_temperature = c.getSampleTemperature()
##print("let the system cooldown 1 min...")
##time.sleep(1*60)

    
##Rposwfproc('phi', 'theta', 0, 91, 5, 5)



##Rposwfproc('phi', 'theta', 100, 11, 5, 5)

##Fields = [-0.14, -0.08, -0.04, -0.02, -0.01, 0.01, 0.02, 0.04, 0.08, 0.14]

##for field in Fields:
##    RHproc(field)
##    time.sleep(3*60)
##    Rposwfproc('phi', 'theta', 95, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 85, 101, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 80, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -80, 161, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -85, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -95, 101, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -100, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -95, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -85, 101, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', -80, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 80, 161, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 85, 11, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 95, 101, 5, 5)
##    time.sleep(20)
##    Rposwfproc('phi', 'theta', 100, 11, 5, 5)
##    time.sleep(20)
##
##Rposwfproc('phi', 'theta', 90, 11, 5, 5)
##time.sleep(3*60)
##Rposproc('theta', 100, 11, 5, 5)
##time.sleep(3*60)

##Fields = [-0.01, -0.02, -0.08, -0.14]
##
##for field in Fields:
##    RHproc(field)
##    time.sleep(3*60)
##    Rposproc('theta', 95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -100, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 100, 11, 5, 5)
##    time.sleep(20)
##
##Fields2 = [0.04, -0.04, 0.11, -0.11]
##
##IVproc(2.5e-6, 2.5e-6, 1)
##
##for field in Fields2:
##    RHproc(field)
##    time.sleep(3*60)
##    Rposproc('theta', 95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -100, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 100, 11, 5, 5)
##    time.sleep(20)
##
##RVproc(30,60,2)
##time.sleep(20)
##
##for field in Fields2:
##    RHproc(field)
##    time.sleep(3*60)
##    Rposproc('theta', 95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -100, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 100, 11, 5, 5)
##    time.sleep(20)
##
##IVproc(0.75e-6, 0.75e-6, 1)
##Fields3 = [0.04, -0.04, 0.13, -0.13]
##
##for field in Fields3:
##    RHproc(field)
##    time.sleep(3*60)
##    Rposproc('theta', 95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -100, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -95, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -85, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', -80, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 80, 161, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 85, 11, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 95, 101, 5, 5)
##    time.sleep(20)
##    Rposproc('theta', 100, 11, 5, 5)
##    time.sleep(20)


##RHproc(-1.5)
##time.sleep(3*60)

##currents = np.linspace(1.9, 2, 3)
##currents2 = np.linspace(3.0, 5.0, 11)
##currents3 = np.linspace(7, 7.5, 2)
##currents = np.array(currents)
##currents2 = np.array(currents2)
##currents3 = np.array(currents3)
##currents = currents * 1e-6
##currents2 = currents2 * 1e-6
##currents3 = currents3 * 1e-6
##Gates = np.linspace(25,30,6)
##Gates = np.array(Gates)

##for current in currents:
##    IVproc(current, current, 1)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)

##for current in currents2:
##    IVproc(current, current, 1)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)

##for current in currents3:
##    IVproc(current, current, 1)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)

##IVproc(1.15e-6, 1.15e-6, 1)
##time.sleep(20)

##for gate in Gates:
##    RVproc(gate, 2, 2)
##    time.sleep(20)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)

##RVproc(-30,20,2)
##time.sleep(20)
##



    ##pos.setAxisOutput(0,1,1)

##    Thetas1 = np.linspace(88.6,88.5,2)
##    Thetas1 = np.array(Thetas1)
##    Thetas2 = np.linspace(88.4,87.8,7)
##    Thetas2 = np.array(Thetas2)
##    Thetas3 = np.linspace(87.7,87.5,3)
##    Thetas3 = np.array(Thetas3)
##    Thetas4 = np.linspace(87.4,86.8,7)
##    Thetas4 = np.array(Thetas4)
##
##    time.sleep(5*60)
##    RHproc(-6)
##    time.sleep(3*60)
##
##    for theta in Thetas1:
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,1,1)
##        time.sleep(1)
##        pos.disconnect()
##        time.sleep(1)
##        run_with_timer(Rposproc, ('theta', theta, 2, 5, 5), timer_seconds=300)
##    ##    Rposproc('theta', theta, 2, 5, 5)
##        time.sleep(1)
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,0,1)
##        time.sleep(0.2)
##        pos.disconnect()
##        time.sleep(0.2)
##        time.sleep(3*60)
##        RHproc(6)
##        time.sleep(3*60)
##        RHproc(-6)
##        time.sleep(3*60)
##
##    RHproc(-9)
##    time.sleep(3*60)
##
##    for theta in Thetas2:
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,1,1)
##        time.sleep(1)
##        pos.disconnect()
##        time.sleep(1)
##        run_with_timer(Rposproc, ('theta', theta, 2, 5, 5), timer_seconds=300)
##    ##    Rposproc('theta', theta, 2, 5, 5)
##        time.sleep(1)
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,0,1)
##        time.sleep(0.2)
##        pos.disconnect()
##        time.sleep(0.2)
##        time.sleep(3*60)
##        RHproc(9)
##        time.sleep(3*60)
##        RHproc(-9)
##        time.sleep(3*60)
##
##    RHproc(-6)
##    time.sleep(3*60)
##
##    for theta in Thetas3:
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,1,1)
##        time.sleep(1)
##        pos.disconnect()
##        time.sleep(1)
##        run_with_timer(Rposproc, ('theta', theta, 2, 5, 5), timer_seconds=300)
##    ##    Rposproc('theta', theta, 2, 5, 5)
##        time.sleep(1)
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,0,1)
##        time.sleep(0.2)
##        pos.disconnect()
##        time.sleep(0.2)
##        time.sleep(3*60)
##        RHproc(6)
##        time.sleep(3*60)
##        RHproc(-6)
##        time.sleep(3*60)
##
##    RHproc(-3)
##    time.sleep(3*60)
##
##    for theta in Thetas4:
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,1,1)
##        time.sleep(1)
##        pos.disconnect()
##        time.sleep(1)
##        run_with_timer(Rposproc, ('theta', theta, 2, 5, 5), timer_seconds=300)
##    ##    Rposproc('theta', theta, 2, 5, 5)
##        time.sleep(1)
##        pos = Positioner()
##        time.sleep(0.2)
##        pos.setAxisOutput(0,0,1)
##        time.sleep(0.2)
##        pos.disconnect()
##        time.sleep(0.2)
##        time.sleep(3*60)
##        RHproc(3)
##        time.sleep(3*60)
##        RHproc(-3)
##        time.sleep(3*60)



##    Temps2 = [3 ,2.7, 2.5, 2.4, 2.35, 2.3, 2.25]
##    Temps2 = np.array(Temps2)
    
##    pos = Positioner()
##    time.sleep(0.2)
##    pos.setAxisOutput(0,1,1)
##    time.sleep(1)
##    pos.disconnect()
##    time.sleep(0.2)
##    Rposproc('theta', 90.8, 20, 5, 5)
##    time.sleep(1)
##    pos = Positioner()
##    time.sleep(0.2)
##    pos.setAxisOutput(0,0,1)
##    time.sleep(0.2)
##    pos.disconnect()
##    time.sleep(0.2)
##    time.sleep(3*60)
    
##    for temp in Temps2:
##        c.setUserTemperature(temp)
##        current_temperature = c.getSampleTemperature()
##        while np.abs(current_temperature - temp) >= 0.01:
##            time.sleep(1)
##            current_temperature = c.getSampleTemperature()
##        print("let the system cooldown 2 min...")
##        time.sleep(2*60)
##        RHproc(1.5)
##        time.sleep(3*60)
##        RHproc(-1.5)
##        time.sleep(3*60)
##    
##    Temps = np.linspace(1.73, 1.69, 5)
##    Temps = np.array(Temps)
##    
##    for temp in Temps:
##        c.setUserTemperature(temp)
##        current_temperature = c.getSampleTemperature()
##        while np.abs(current_temperature - temp) >= 0.003:
##            time.sleep(1)
##            current_temperature = c.getSampleTemperature()
##        print("let the system cooldown 2 min...")
##        time.sleep(2*60)
##        RHproc(1.5)
##        time.sleep(3*60)
##        RHproc(-1.5)
##        time.sleep(3*60)


##    Fields3 = [0.1]
##    c.setUserTemperature(1.6)
##    time.sleep(10*60)
##
##
##    for field in Fields3:
##        RHproc(field)
##        time.sleep(3*60)
##        Rposproc('theta', 95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -100, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 100, 11, 5, 5)
##        time.sleep(20)
##
##
##    c.setUserTemperature(1.86)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 1.86) >= 0.005:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 1.86) >= 0.005:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
    
##    for field in Fields3:
##        RHproc(field)
##        time.sleep(3*60)
##        Rposproc('theta', 95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -100, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 100, 11, 5, 5)
##        time.sleep(20)
##
##    c.setUserTemperature(1.6)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 1.7) >= 0.02:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - 1.7) >= 0.02:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##
##    IVproc(3e-6, 3e-6, 1)
##    time.sleep(2*60)
##
##    Fields4 = [0.1, -0.1]
##
##    for field in Fields4:
##        RHproc(field)
##        time.sleep(3*60)
##        Rposproc('theta', 95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -100, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -95, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -85, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', -80, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 80, 161, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 85, 11, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 95, 101, 5, 5)
##        time.sleep(20)
##        Rposproc('theta', 100, 11, 5, 5)
##        time.sleep(20)


if __name__ == "__main__":
    
    current = 50e-6
    
    c.setUserTemperature(2.5)
    current_temperature = c.getSampleTemperature()
    while np.abs(current_temperature - 2.5) >= 0.05:
        time.sleep(1)
        current_temperature = c.getSampleTemperature()
    print("let the system cooldown 2 min...")
    time.sleep(2*60)
    current_temperature = c.getSampleTemperature()
    while np.abs(current_temperature - 2.5) >= 0.05:
        time.sleep(1)
        current_temperature = c.getSampleTemperature()
    print("let the system cooldown 2 min...")
    time.sleep(2*60)

    IVprocRange(current,current, 1)
    
    RVproc(30,30,2)
    time.sleep(20)
    RVproc(-30,30,2)
    time.sleep(20)
    RVproc(30,30,2)
    time.sleep(20)
    RVproc(-30,30,2)
    time.sleep(20)
    RVproc(30,60,2)
    time.sleep(20)
    RVproc(-30,60,2)
    time.sleep(20)
    RVproc(24,60,2)
    time.sleep(20)

    RHproc(-9)
    time.sleep(3*60)
    IVprocRange(current,current, 1)

    temps = [2.5, 2.75, 3, 3.3, 3.7, 4, 4.3, 4.7, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.3, 8.7, 9, 9.3, 9.7, 10, 10.5, 11, 11.5, 12, 13, 15, 20]
    for temp in temps:
        c.setUserTemperature(temp)
        current_temperature = c.getSampleTemperature()
        while np.abs(current_temperature - temp) >= 0.05:
            time.sleep(1)
            current_temperature = c.getSampleTemperature()
        print("let the system cooldown 1 min...")
        time.sleep(1*60)
        current_temperature = c.getSampleTemperature()
        while np.abs(current_temperature - temp) >= 0.05:
            time.sleep(1)
            current_temperature = c.getSampleTemperature()
        print("let the system cooldown 1 min...")
        time.sleep(2*60)
        
        IVprocRange(current,current,1)
        RHproc(9)
        time.sleep(3*60)
        RHproc(-9)
        time.sleep(3*60)

    c.setUserTemperature(2.5)
    RHproc(0)
    RVproc(0,30,2)
    
    print("measurement finished")



##currents = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85, 1.9, 1.95, 2, 2.2, 2.4, 2.6, 2.8, 3.0, 3.4, 3.8, 4.2, 4.6, 5, 5.5, 6, 6.5, 7]
##currents = [1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85, 1.9, 1.95, 2, 2.2, 2.4, 2.6, 2.8, 3.0, 3.4, 3.8, 4.2, 4.6, 5, 5.5, 6, 6.5, 7]
##currents2 = [7.5, 8, 8.5, 9, 9.5, 10.0]
##currents = np.array(currents)
##currents2 = np.array(currents2)
##currents = currents * 1e-6
##currents2 = currents2 * 1e-6

##Gates = [-30, -26, -22, -18, -14, -10, -6, -2, 2, 6, 10, 14, 18, 22, 26, 30]

##Gates = np.linspace(-30, 30, 61)
##
##for gate in Gates:
##    RVproc(gate, 2, 2)
##    time.sleep(20)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)
##
##RVproc(-30,30,2)
##time.sleep(20)

##Temps2 = np.linspace(3, 2.1, 10)
##
##for temp in Temps2:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.01:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)
##
##Temps = np.linspace(2.0, 1.7, 31)
##
##for temp in Temps:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.003:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 2 min...")
##    time.sleep(2*60)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)


##for current in currents:
##    IVproc(current, current, 1)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)


##for current in currents2:
##    IVproc(current, current, 1)
##    RHproc(1.5)
##    time.sleep(3*60)
##    RHproc(-1.5)
##    time.sleep(3*60)
    



##Freqs = [11.189, 7.742, 17.592]
##for freq in Freqs:
##    sourcemeter = keithley6221_with_add_ons.Keithley6221("GPIB::12")
##    sourcemeter.waveform_frequency = freq
##    IVprocRange(current, current, 1)
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)
##    time.sleep(3*60)
    


##temps = [200,190,180,170,160,150,140,130,120,110,100,90,84,80,76,72,68,64,60,56,52,50,48,46,44,42,40,38,36,34,32,30,28,26,24,22,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2.5,2]
##temps = temps[::-1]
##for temp in temps:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    IVprocRange(90e-6, 90e-6, 1)
##    IVproc(10e-6, 90e-6, 40)
##    RHproc(-1)
##    time.sleep(0.5*60)
##    IVprocRange(current,current,1)
##    RHproc(1)
##    time.sleep(0.5*60)
##    RHproc(-1)
##    RHproc(0)
##
##RHproc(0)



##for i in range(1):
##    RHproc(-9)
##    time.sleep(3*60)
##    RHproc(9)
##    time.sleep(3*60)
    
##IVprocRange(90e-6,90e-6,1)
##IVproc(10e-6,90e-6,20)

    
##RHproc(-9)
##IVprocRange(current,current,1)


##for i in range(4):
##    RHproc(9)
##    time.sleep(3*60)
##    RHproc(-9)
##    time.sleep(3*60)
##RHproc(0)

##print("measurement finished")





##temps = [2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5,8,8.5,9,9.5,10,10.5,11,11.5,12,13,14,15]
##RVproc(-30,5,2)
##for temp in temps:
##    c.setUserTemperature(temp)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    current_temperature = c.getSampleTemperature()
##    while np.abs(current_temperature - temp) >= 0.05:
##        time.sleep(1)
##        current_temperature = c.getSampleTemperature()
##    print("let the system cooldown 1 min...")
##    time.sleep(1*60)
##    IVprocRange(current,current,1)
##    RVproc(30,150,2)
##    time.sleep(10)
##    RVproc(-30,150,2)
##



##fields = np.linspace(9,-9,19)
##
##for field in fields:
##    RHproc(field)
##    print("let the system cooldown 3 min...")
##    time.sleep(3*60)
##    IVproc(current, current, 1)
##    RVproc(30, 300, 2) # final_gate, points, delay
##    print("let the system cooldown 10s...")
##    time.sleep(10)
##    RVproc(-30, 300, 2) # final_gate, points, delay
##    print("let the system cooldown 10s...")
##    time.sleep(10)



##RHproc(9)
##time.sleep(3*60)
##RVproc(-3.6, 3, 1)
##IVproc(0.75*current, current, 2)
##


##
##
##RHproc(0)
##RVproc(0,5,1)
##Rtemproc(1.7,2,0.05)
##print("measurement finished")



##RVproc(-30, 10, 2)
##IVproc(0.75*current, current, 2)
##RHproc(9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##RHproc(-9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##RHproc(9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##RHproc(-9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##RHproc(9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##RHproc(-9)
##print("let the system cooldown 3 min...")
##time.sleep(3*60)
##

    
##for current in currents:
##IVproc(0.75*current, current, 3)
##time.sleep(10)

##for field in fields:
##field = 9
##RHproc(field)
##print("let the system cooldown 0.5 min...")
##time.sleep(0.5*60)
####make sure we are at Theta min 
##Rposproc('theta',Theta_min, 10, 5, 5)
##time.sleep(10)
####make sure we are at Phi 
##Rposproc('phi',Phi, 5, 5, 5)
##print("waiting 4 mins before start scannig...")
##time.sleep(4*60)
##Rposproc('theta',Theta_max, N_Thetas, 5, 5)
###go to Theta_min
##time.sleep(10)
##Rposproc('theta',Theta_min, 50, 5, 5)




##Rtemproc(1.7, 2, 0.05)


        
## examples of procedures
##RHproc(0)
##Rposproc(ax_str ='theta',
##         final_pos = Theta, data_points = 30, pos_delay=5, dwell_time = 5)
##RVproc(Gate, 90, 3) # final gate, points, delay




##anglefix_x=[-360,360],anglefix_y=[0,0], dwell_time = 5)
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





