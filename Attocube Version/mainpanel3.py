import subprocess
import time

base = r"C:\Users\attocube\Desktop\Data\eyal\AttoCubePython_eyal"

python_path = r"C:\Users\attocube\AppData\Local\Programs\Python\Python310-32\python.exe"

folder_path = base + "\\Shilo_Eyal_data_files\KTO100 12012025 cooldown on 04.01.26\hallbar 0\RT"

rtproc = base + "\\Rtprocedure.py"
rvproc = base + "\\RVprocedure.py"
ivproc = base + "\\IVprocedure.py"
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


Rtproc(1e9)



##RHproc(9)

##Rtemproc(1.77, 1, 0.01)
##Rtproc(30*60)

##IVproc(.4e-6,.5e-6,2)

##Rposproc('theta',-60, 50, 5, 5)


##RHproc(0)

##Rtemproc(5, 1, 0.05)
##for i in range(4):
##    time.sleep(3)#

##Rposproc('theta',95, 10, 5, 5)
##Rposprocedure.main(attoDRY, folder_path, ax_str ='phi',
##    final_pos = Phi, data_points = 10, pos_delay=5, dwell_time = 5)
##Rposproc('phi',88, 10, 5, 5)


##RVproc(1,5,1)

##time.sleep(3)
##IVproc(70e-6,100e-6,10)
##for i in range(4):
##    SeqStop()


##def key_pressed():
##    if msvcrt.kbhit():
##        return msvcrt.getch()
##    return None
##
##def SeqStop():
##    if key_pressed() == b'\x1b':
##        sys.exit("Exiting due to key pressed.")

    
