#
#  attoDRY is a Python implementation of the C++ header provided
#     with the attocube AttoDry2100 system.
#
#  It depends on attoDRYLib.dll which provided by attocube in the
#     attoDRY_Library folder on the driver disc. Place all
#     of these in the same folder as this module (and that of attoDRYlib).
#  It requires Labview runtime engine compatible with version 2016   
#
#   attoDRY is written by Elad Mileikowsky, Asaf Yagoda and Itai Silber, Tel Aviv University, Israel
#   https://yoramdagan.wordpress.com/

import ctypes, os, time
# List of error types???

#checks the errors - needs to write

##first part: load the DLL, assuming it is at the same folder##
directory_of_this_module_and_dlls = os.path.dirname(os.path.realpath(__file__))
os.chdir(directory_of_this_module_and_dlls)
os.add_dll_directory(directory_of_this_module_and_dlls)
dll_name = r'attoDRYLib.dll'
attoDRY = ctypes.CDLL(dll_name)


##aliases for the functions from the attoDRY dll
#device connection functions
begin = getattr(attoDRY,"AttoDRY_Interface_begin")
Connect = getattr(attoDRY,"AttoDRY_Interface_Connect")
Confirm = getattr(attoDRY,"AttoDRY_Interface_Confirm")
isDeviceConnected = getattr(attoDRY,"AttoDRY_Interface_isDeviceConnected")
isDeviceInitialised = getattr(attoDRY,"AttoDRY_Interface_isDeviceInitialised")
Disconnect = getattr(attoDRY,"AttoDRY_Interface_Disconnect")
end = getattr(attoDRY,"AttoDRY_Interface_end")
Cancel = getattr(attoDRY,"AttoDRY_Interface_Cancel")

#logging
startLogging = getattr(attoDRY,"AttoDRY_Interface_startLogging")
stopLogging = getattr(attoDRY,"AttoDRY_Interface_stopLogging")

#temperature functions
get4KStageTemperature = getattr(attoDRY,"AttoDRY_Interface_get4KStageTemperature")
getSampleTemperature = getattr(attoDRY,"AttoDRY_Interface_getSampleTemperature")
getUserTemperature= getattr(attoDRY,"AttoDRY_Interface_getUserTemperature")
getVtiTemperature = getattr(attoDRY,"AttoDRY_Interface_getVtiTemperature")
getReservoirTemperature = getattr(attoDRY,"AttoDRY_Interface_getReservoirTemperature")
goToBaseTemperature = getattr(attoDRY,"AttoDRY_Interface_goToBaseTemperature")
isGoingToBaseTemperature = getattr(attoDRY,"AttoDRY_Interface_isGoingToBaseTemperature")
toggleFullTemperatureControl = getattr(attoDRY,"AttoDRY_Interface_toggleFullTemperatureControl")
isControllingTemperature = getattr(attoDRY,"AttoDRY_Interface_isControllingTemperature")
setUserTemperature = getattr(attoDRY,"AttoDRY_Interface_setUserTemperature")

#magnetic field functions
getMagneticField = getattr(attoDRY,"AttoDRY_Interface_getMagneticField")
getMagneticFieldSetPoint = getattr(attoDRY,"AttoDRY_Interface_getMagneticFieldSetPoint")
setUserMagneticField = getattr(attoDRY,"AttoDRY_Interface_setUserMagneticField")
toggleMagneticFieldControl = getattr(attoDRY,"AttoDRY_Interface_toggleMagneticFieldControl")
isControllingField = getattr(attoDRY,"AttoDRY_Interface_isControllingField")
togglePersistentMode = getattr(attoDRY,"AttoDRY_Interface_togglePersistentMode")
isPersistentModeSet = getattr(attoDRY,"AttoDRY_Interface_isPersistentModeSet")


###set error checking & handling
##discover.errcheck = checkError
##connect.errcheck = checkError






