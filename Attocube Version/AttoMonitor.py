import ctypes, math, time
import RPCPyattoDRYClient
import curses
import datetime
c = RPCPyattoDRYClient.Cryostat()
stdscr = curses.initscr()
while True:
    stdscr.addstr(0, 0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    stdscr.addstr(1, 0, "4K temp - %f" % (c.get4KStageTemperature(),))
    stdscr.addstr(2, 0, "VTI temp - %f" % (c.getVtiTemperature(),))
    stdscr.addstr(3, 0, "Reservoir temp - %f" % (c.getReservoirTemperature(),))
    stdscr.addstr(4, 0, "Sample temp - %f" % (c.getSampleTemperature(),))


    stdscr.addstr(5, 0, "Is Connected - %d" % (c.isDeviceConnected(),))
    stdscr.addstr(6, 0, "Is Initialized - %d" % (c.isDeviceInitialised(),))
    stdscr.addstr(7, 0, "Is Persistent - %d" % (c.isPersistentModeSet(),))
    stdscr.addstr(8, 0, "Is Controlling Temperature - %d" % (c.isControllingTemperature(),))
    stdscr.addstr(9, 0, "Is Going to Base - %d" % (c.isGoingToBaseTemperature(),))

    stdscr.addstr(10, 0, "Megnetic Field - %f" % (c.getMagneticField(),))
    stdscr.addstr(11, 0, "Megnetic Field Setpoint - %f" % (c.getMagneticFieldSetPoint(),))
    stdscr.addstr(12, 0, "Is Controlling Field - %d" % (c.isControllingField(),))
        
    stdscr.refresh()
    time.sleep(1)
