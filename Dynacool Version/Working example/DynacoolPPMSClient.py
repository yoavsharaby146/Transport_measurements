"""
DynacoolPPMSClient.py

Drop-in replacement for the old RPCPyattoDRYClient.py (which talked to an
Attocube attoDRY cryostat over a custom RPC socket server). This module talks
to a Quantum Design Dynacool PPMS instead, using Quantum Design's official
"MultiPyVu" package.

MultiPyVu ships MultiPyVu.Server (runs alongside the MultiVu executable on
the PPMS control PC) and MultiPyVu.Client (used here to send commands to the
cryostat). Docs / install:

    pip install MultiPyVu
    https://pypi.org/project/MultiPyVu/

Before any script that imports this module is run, MultiVu must be running
on the Dynacool control PC, and the MultiPyVu server must be started there
with either:

    python -m MultiPyVu
    (or the bundled run_server.py / RunServer.cmd)

If this script and the server run on the same PC, host='127.0.0.1' (the
default below) is correct. If this script is run from a different computer,
pass the PPMS control PC's IP address instead (see the server GUI, or
`python -m MultiPyVu -get_ip` on the control PC).

This class exposes (most of) the same method names the lab's existing
measurement scripts (RHprocedure.py, Rtemprocedure.py, Rtprocedure.py, etc.)
used to call on the old `RPCPyattoDRYClient.Cryostat` object, so those
scripts only need their import line and instantiation line updated -- see
the "ppms = Cryostat()" pattern used in each procedure file's
`if __name__ == "__main__":` block.

NOTE on units / assumptions (please double check against your actual PPMS
setup before running unattended sequences):
  * MultiVu/MultiPyVu report and accept magnetic field in Oersted (Oe), not
    Tesla. The lab's existing scripts (sequence3.py, RHprocedure.py, ...)
    were written treating field values as Tesla (e.g. RHproc(9) for a 9 T
    magnet). To keep those scripts working unmodified, this wrapper converts
    Tesla <-> Oe internally (1 T = 10,000 Oe). Set field_units='Oe' at
    construction time if you'd rather work in Oe throughout.
  * Default temperature ramp rate (5 K/min) and field ramp rate (100 Oe/s)
    are reasonable generic defaults, not necessarily what your cooldown
    procedure wants -- override via setUserTemperature()/setUserMagneticField()
    rate arguments, or the constructor defaults, as needed.
  * The driven_mode enum member names (`driven`, `persistent`) are inferred
    from Quantum Design's published documentation for MultiPyVu; if your
    installed MultiPyVu version differs, check
    `dir(client.field.driven_mode)` and adjust setUserMagneticField()
    accordingly.
  * The Dynacool does not expose a separate "4K stage" / "VTI" / "reservoir"
    thermometer over MultiPyVu the way the attoDRY did -- those getters are
    kept for compatibility but simply report the sample/platform
    temperature. If your PPMS has the auxiliary-thermometer option
    (OptiCool) or resistivity-bridge thermometry, extend this class with
    client.get_aux_temperature() as needed.
"""

import atexit

import MultiPyVu as mpv


class Cryostat:
    """Compatibility wrapper around MultiPyVu.Client for the Dynacool PPMS."""

    OE_PER_TESLA = 10000.0

    def __init__(self, host='10.0.0.10', port=5000,
                 temperature_rate_K_per_min=5.0,
                 field_rate_Oe_per_sec=100.0,
                 field_units='T'):
        '''
        Connects to the MultiPyVu.Server running on the Dynacool control PC.

        host, port  -- address of the MultiPyVu server (defaults match
                        MultiPyVu.Server's own defaults: localhost:5000).
        field_units -- 'T' (default, Tesla in/out, converted internally to
                        the Oe MultiPyVu actually speaks) or 'Oe' to pass
                        values straight through unconverted.
        '''
        self.field_units = field_units
        self._temperature_rate = temperature_rate_K_per_min
        self._field_rate = field_rate_Oe_per_sec
        self._persistent = False

        self.client = mpv.Client(host=host, port=port)
        self.client.open()
        print("Connected successfully to the Dynacool PPMS (MultiPyVu server)!")

        # Make sure the connection to the server (which only accepts one
        # client at a time) is released even if the script exits abnormally,
        # e.g. via run_with_timer()'s process-kill path in sequence3.py.
        atexit.register(self.disconnect)

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------
    def getSampleTemperature(self):
        '''Returns the sample-chamber temperature, in Kelvin.'''
        temperature, status = self.client.get_temperature()
        return temperature

    def get4KStageTemperature(self):
        '''
        The Dynacool does not expose a separate cold-stage sensor over
        MultiPyVu; report the sample/platform temperature instead so
        existing "Tmagnet" logging columns still get a sensible value.
        '''
        return self.getSampleTemperature()

    def getVtiTemperature(self):
        '''No separate VTI thermometer on the Dynacool; see get4KStageTemperature.'''
        return self.getSampleTemperature()

    def getReservoirTemperature(self):
        '''No separate reservoir thermometer on the Dynacool; see get4KStageTemperature.'''
        return self.getSampleTemperature()

    def setUserTemperature(self, desiredT, rate_K_per_min=None):
        '''Sets the temperature setpoint (K). Uses the constructor's default ramp rate unless overridden.'''
        rate = self._temperature_rate if rate_K_per_min is None else rate_K_per_min
        self.client.set_temperature(
            desiredT, rate,
            self.client.temperature.approach_mode.fast_settle)

    def isControllingTemperature(self):
        '''
        The PPMS temperature bridge is always actively regulating once a
        setpoint has been issued -- there's no separate "enable control"
        step like on the attoDRY. Always report True (1) so legacy call
        sites that gate a toggleFullTemperatureControl() call on this never
        actually call it.
        '''
        return 1

    def toggleFullTemperatureControl(self):
        '''No equivalent on the Dynacool; kept as a harmless no-op so old call sites don't need to be deleted.'''
        pass

    def goToBaseTemperature(self):
        '''Convenience: ramps to a nominal base temperature (1.8 K). Adjust to your system's real base T.'''
        self.setUserTemperature(1.8)

    def isGoingToBaseTemperature(self):
        '''Not tracked separately on the Dynacool; not used by any live code path in this codebase.'''
        return 0

    # ------------------------------------------------------------------
    # Magnetic field
    # ------------------------------------------------------------------
    def _toOe(self, value):
        return value * self.OE_PER_TESLA if self.field_units == 'T' else value

    def _fromOe(self, value_oe):
        return value_oe / self.OE_PER_TESLA if self.field_units == 'T' else value_oe

    def getMagneticField(self):
        '''Returns the current magnetic field (Tesla by default; see field_units).'''
        field_oe, status = self.client.get_field()
        return self._fromOe(field_oe)

    def getMagneticFieldSetPoint(self):
        '''Returns the current magnetic field setpoint (Tesla by default; see field_units).'''
        field_oe, rate, approach, driven = self.client.get_field_setpoints()
        return self._fromOe(field_oe)

    def setUserMagneticField(self, desiredH, rate_Oe_per_sec=None):
        '''Sets the field setpoint (Tesla by default; see field_units).'''
        rate = self._field_rate if rate_Oe_per_sec is None else rate_Oe_per_sec
        driven_mode = (self.client.field.driven_mode.persistent if self._persistent
                       else self.client.field.driven_mode.driven)
        self.client.set_field(
            self._toOe(desiredH), rate,
            self.client.field.approach_mode.linear,
            driven_mode)

    def isControllingField(self):
        '''The PPMS magnet is always under active control once a setpoint is issued; see isControllingTemperature.'''
        return 1

    def toggleMagneticFieldControl(self):
        '''No equivalent on the Dynacool; kept as a harmless no-op.'''
        pass

    def togglePersistentMode(self):
        '''Switches whether subsequent setUserMagneticField() calls drive the magnet in persistent or driven mode.'''
        self._persistent = not self._persistent

    def isPersistentModeSet(self):
        return int(self._persistent)

    # ------------------------------------------------------------------
    # Misc / legacy compatibility
    # ------------------------------------------------------------------
    def isDeviceConnected(self):
        return 1

    def isDeviceInitialised(self):
        return 1

    def Confirm(self):
        '''No chamber air-sealing confirmation step is needed on the PPMS; kept as a no-op.'''
        pass

    def disconnect(self):
        '''Releases the connection to the MultiPyVu server.'''
        try:
            self.client.close_client()
        except Exception:
            pass
