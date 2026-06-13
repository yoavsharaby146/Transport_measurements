import Rtprocedure_old,IVprocedure, RVprocedure,Rtemprocedure,Rtprocedure,RHprocedure,Rposprocedure,Rposprocedure_wobblefix
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
##attoDRY.goToBaseTemperature()
##time.sleep(5)
##attoDRY.Confirm()
##time.sleep(20)

##Rtprocedure.main(attoDRY, folder_path, 10)
##time.sleep(3)
##RVprocedure.main(attoDRY, folder_path, 2, 10, 3) # final gate, points, delay
time.sleep(3)
RVprocedure.main(attoDRY, folder_path, 2, 5, 3) # final gate, points, delay

##IVprocedure.main(attoDRY, folder_path, min_current=1e-6, max_current=100e-6, data_points = 10)
##time.sleep(3)
##Rtprocedure.main(attoDRY, folder_path, 20)
##time.sleep(3)
##RVprocedure.main(attoDRY, folder_path, 1, 10, 2)
##time.sleep(3)
##Rtprocedure.main(attoDRY, folder_path, 10)
##time.sleep(3)
##Rtprocedure.main(attoDRY, folder_path, 10)
##RVprocedure.main(attoDRY, folder_path, 0, 20, 2)
##time.sleep(3)
##RVprocedure.main(attoDRY, folder_path, 2, 20, 2)
    

