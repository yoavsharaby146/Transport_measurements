 #
#  PyattoDRY is a control scheme suitable for the Python coding style
#    for the attocube AttoDry2100 cryostat system.
#
#  It implements attoDRYlib.py, which in turn depends on attoDRYLib.dll, which are provided by attocube in the
#     Place all of these in the same folder as this module.
#
#  Unlike attoDRYlib which is effectively a re-imagining of the
#    C++ header, PyattoDRY is intended to behave as one might expect
#    Python to. This means: returning values; behaving as an object.
#
#
#  Usage:
#   instantiate Cryostat() class to begin, eg. attoDRY = Cryostat(). Profit!
#
#   attoDRY is written by Elad Mileikowsky, Asaf Yagoda and Itai Silber, Tel Aviv University, Israel
#   https://yoramdagan.wordpress.com/


import attoDRYlib as attoDRY
import ctypes, math, time

class Cryostat:
    
    def __init__(self,port): ##consider adding automatic logging and request for filepath
        self.begin()
        self.Connect(port)
        if(self.isDeviceConnected() == 1):
           print("Connected successfully to attoDRY!")
        else:
            print ('Failed connection to attoDRY')
        while (self.isDeviceInitialised() != 1):
            time.sleep(0.05)
            self.isDeviceInitialised()
        print("AttoDry initialised!")

    def begin(self):
        '''
        * Starts the server that communicates with the attoDRY and loads the software 
        * for the device specified by Device . This VI needs to be run before 
        * commands can be sent or received. The <B>UI Queue</B> is an event queue for 
        * updating the GUI. It should not be used when calling the function from a 
        * DLL.
        '''
        attoDRY.begin(ctypes.c_int(1)) ### 1 is attoDRY2100
        
    def Connect(self,port):
        '''
        Connects to the attoDRY using the specified COM Port.
        '''
        port = port.encode('utf-8')
        attoDRY.Connect(ctypes.c_char_p(port))

    def Disconnect(self):
        '''
        Disconnects from the attoDRY, if already connected. This should be run 
         before the end.vi
        '''
        attoDRY.Disconnect()
    
    def isDeviceConnected(self):
        '''
        * Checks to see if the attoDRY is connected. Returns 1 if connected.
        '''
        connected = ctypes.c_int()
        attoDRY.isDeviceConnected(ctypes.byref(connected))
        return connected.value
    
    def isDeviceInitialised(self):
        '''
         * Checks to see if the attoDRY has initialised. Use this after you have 
         * connected and before sending any commands or getting any data from the 
         * attoDRY. Return 1 if connected
        '''
        initialised = ctypes.c_int()
        attoDRY.isDeviceInitialised(ctypes.byref(initialised))
        return initialised.value

    def startLogging(self,log_path, TimeSelection,append): 
        '''
         * Starts logging data to the file specifed by log_Path. 
         * If the file does not exist, it will be created.
         * log_path - should end explicilty with .txt
         * TimeSelection - 0 (1Second), 1 (5seconds), 2 (30seconds)
         * TimeSelection - 3 (60seconds), 4 (300seconds)
         * append - if 1 then append, if 0 overwrites
        '''
        log_path = ctypes.c_char_p(log_path.encode('utf-8'))
        TimeSelection = ctypes.c_uint16(TimeSelection)
        append = ctypes.c_int(append)
        attoDRY.startLogging(log_path, TimeSelection, append)

    def stopLogging(self):
        '''
         * Stops logging data
         '''
        attoDRY.stopLogging()
        
    def get4KStageTemperature(self):
        '''
        Returns the temperature of the Stage4KTemperature
        '''
        Stage4KTemperature = ctypes.c_float()
        attoDRY.get4KStageTemperature(ctypes.byref(Stage4KTemperature))
        return Stage4KTemperature.value

    def getSampleTemperature(self):
        '''
        Returns the temperature sample
        '''
        SampleTemperature = ctypes.c_float()
        attoDRY.getSampleTemperature(ctypes.byref(SampleTemperature))
        return SampleTemperature.value
    
    def getVtiTemperature(self):
        '''
        Returns the VTI temprature
        '''
        VtiTemperature = ctypes.c_float()
        attoDRY.getVtiTemperature(ctypes.byref(VtiTemperature))
        return VtiTemperature.value
    
    def getReservoirTemperature(self):
        '''
        Returns the temperature of the Reservoir
        '''
        ReservoirTemperature = ctypes.c_float()
        attoDRY.getReservoirTemperature(ctypes.byref(ReservoirTemperature))
        return ReservoirTemperature.value

    def toggleFullTemperatureControl(self):
        '''
        toggles the status of the temprature control.
        Takes a few moments to actually change the status
        '''
        attoDRY.toggleFullTemperatureControl()

    def goToBaseTemperature(self):
        '''
         * Initiates the "Base Temperature" command, as on the touch screen
        '''
        attoDRY.goToBaseTemperature()

    def isGoingToBaseTemperature(self):
        '''
         * Returns 'True' if the base temperature process is active. This is true when 
         * the base temperature button on the touch screen is orange, and false when 
         * the button is white
        '''
        GoingToBaseTemperature =   ctypes.c_int()
        attoDRY.isGoingToBaseTemperature(ctypes.byref(GoingToBaseTemperature))
        return GoingToBaseTemperature.value

    def isControllingTemperature(self):
        '''
         * Returns 'True' if temperature control is active. This is true when the 
         * temperature control icon on the touch screen is orange, and false when the 
         * icon is white.
        '''
        controlling =   ctypes.c_int()
        attoDRY.isControllingTemperature(ctypes.byref(controlling))
        return controlling.value

    def setUserTemperature(self,desiredT):
        '''
         * Sets the user temperature. This is the temperature used when temperature 
         * control is enabled.
        '''
        attoDRY.setUserTemperature(ctypes.c_float(desiredT))

    def getMagneticField(self):
        '''
        Gets the current magnetic field
        '''
        magneticfield = ctypes.c_float()
        attoDRY.getMagneticField(ctypes.byref(magneticfield))
        return magneticfield.value

    def getMagneticFieldSetPoint(self):
        '''
        Gets the current magnetic field setpoint
        '''
        MagneticFieldSetPoint = ctypes.c_float()
        attoDRY.getMagneticFieldSetPoint(ctypes.byref(MagneticFieldSetPoint))
        return MagneticFieldSetPoint.value   

    def setUserMagneticField(self,desiredH):
        '''
         * Sets the user magntic field. This is used as the set point when field 
         * control is active
        '''
        attoDRY.setUserMagneticField(ctypes.c_float(desiredH))

    def toggleMagneticFieldControl(self):
        '''
         * Toggle magnetic field control, just as the magnet icon on the touch screen
        '''
        attoDRY.toggleMagneticFieldControl()

    def isControllingField(self):
        '''
         * Returns 'True' if magnetic filed control is active. This is true when the 
         * magnetic field control icon on the touch screen is orange, and false when 
         * the icon is white.
        '''
        controlling =  ctypes.c_int()
        attoDRY.isControllingField(ctypes.byref(controlling))
        return controlling.value

    def togglePersistentMode(self):
        '''
         * Toggles persistant mode for magnet control. If it is enabled, the switch 
         * heater will be turned off once the desired field is reached. If it is not, 
         * the switch heater will be left on
         '''
        attoDRY.togglePersistentMode()

    def isPersistentModeSet(self):
        '''
         * Checks to see if persistant mode is set for the magnet. Note: this shows if 
         * persistant mode is set, it does not show if the persistant switch heater is 
         * on. The heater may be on during persistant mode when, for example, changing 
         * the field.
        '''
        PersistentMode =  ctypes.c_int()
        attoDRY.isPersistentModeSet(ctypes.byref(PersistentMode))
        return PersistentMode.value


    # Eyal: allow for remote confirmation of air sealing
    def Confirm(self):
        attoDRY.Confirm()
        
        


