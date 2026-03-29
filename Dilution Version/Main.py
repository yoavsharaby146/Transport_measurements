import os
import sys
import time
import math
import numpy as np

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from pymeasure.log import console_log


import Rt_procedure
import RV_procedure
import R_AUX_procedure
import RH_procedure

"""
Comment and uncomment the different procedures depending on the measurement
Change the directory according to your needs
"""
folder_name = fr'C:\Users\USER\Desktop\Data\YoavSharaby\2026\Device 3\500mT'


###----- RH procedure -----
##RH_procedure.main(
##        title='RH',
##        target_field = 0.5, step_size = 5,ramp_rate = 0.01 ,axis = 'bz',
##        acq_delay = 15,
##        Resistor='Gain 3', Contacts='SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49_50',
##        save_dir = folder_name
##        ).run()

target_gate_voltage = 4
#time.sleep(60)
## ----- Timed measurement for wait and simple tracking -----

##Rt_procedure.main(
##                  title='Waiting for 2 hours',
##                  acq_delay=1,acq_length=7200,
##                  resistor='Gain 3',
##                  contacts='SRS_830_1 18-38,SRS_830_2 1-2, SRS_860_1 49-50',
##                  save_dir = folder_name).run()
##


## ----- Example of Gate Hyst sequence
folder_name = fr'C:\Users\USER\Desktop\Data\YoavSharaby\2026\Device 3\500mT\Hyst pm{target_gate_voltage}'
RV_procedure.main(
                 title='RV',
                 target_voltage=target_gate_voltage, step_size=5,
                 acq_delay=1,
                 smu = 'Gate_1',
                 Resistor='Gain 3',
                 Contacts='SRS830_1 18-38,SRS830_2 1-2, SRS860_1 49-50',
                 save_dir = folder_name
                 ).run()
##time.sleep(2)
RV_procedure.main(
                 title='RV',
                 target_voltage=-target_gate_voltage, step_size=5,
                 acq_delay=1,
                 smu = 'Gate_1',
                 Resistor='Gain 3',
                 Contacts='SRS_1 24-38,SRS_2 1-2, SRS_3 49-50',
                 save_dir = folder_name).run()
time.sleep(3)
RV_procedure.main(
                 title='RV',
                 target_voltage=0.0, step_size=8,
                 acq_delay=1,
                 smu = 'Gate_1',
                 Resistor='Gain 3',
                 Contacts='SRS_1 24-38,SRS_2 1-2, SRS_3 49-50',
                 save_dir = folder_name).run()

time.sleep(3)

## ----- Example for AUX hyst while changing Gate voltage between steps -----
'''

Folder name changes with each step to create a new directory for measurements

values determins the different gate steps

'''
values = np.linspace(0.5,-0.5,11)
for target_gate_voltage in values:
    folder_name = fr'C:\Users\USER\Desktop\Data\YoavSharaby\2026\Device 3\500mT\AUX_hyst {target_gate_voltage}V'
    
    RV_procedure.main(
                 title='RV',
                 target_voltage=target_gate_voltage, step_size=5,
                 acq_delay=1,
                 smu = 'Gate_1',
                 Resistor='Gain 3', Contacts='SRS830_1 18-38,SRS830_2 1-2, SRS860_1 49-50',
                 save_dir = folder_name
                 ).run()
    time.sleep(2)
    
    R_AUX_procedure.main(
                 title='AUX sweep',
                 target_AUX_voltage = 4, step_size = 20 ,
                 acq_delay = 4,
                 aux = 1,
                 Resistor='Gain 3', Contacts='SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49_50',
                 save_dir = folder_name
                 ).run()
    time.sleep(2)
    
    R_AUX_procedure.main(
                 title='AUX sweep',
                 target_AUX_voltage = -4, step_size = 20 ,
                 acq_delay = 4,
                 aux = 1,
                 Resistor='Gain 3', Contacts='SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49_50',
                 save_dir = folder_name
                 ).run()
    time.sleep(2)
    
    R_AUX_procedure.main(
                 title='AUX sweep',
                 target_AUX_voltage = 0.0, step_size = 20 ,
                 acq_delay = 4,
                 aux = 1,
                 Resistor='Gain 3', Contacts='SRS830_1 18-38, SRS830_2 1-2, SRS860_1 49_50',
                 save_dir = folder_name
                 ).run()
    time.sleep(2)


## ----- Timed measurement for wait and simple tracking -----

folder_name = fr'C:\Users\USER\Desktop\Data\YoavSharaby\2026\Device 3\500mT'
Rt_procedure.main(
                  title='Waiting for 2 hours',
                  acq_delay=1, acq_length=14400,
                  Resistor='Gain 3', Contacts='SRS_830_1 18-38,SRS_830_2 1-2, SRS_860_1 49-50',
                  save_dir = folder_name
                  ).run()


    
