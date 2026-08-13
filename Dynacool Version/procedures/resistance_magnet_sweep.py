"""
Resistance magnet sweep measurement procedure.
"""
from .base import *
from . import base


class Resistance_magnet_sweep_measurement(DynacoolProcedure):
    # --- Parameters ---
    Title = Parameter('RH measurement', default='RH')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate', default='Insert gate contacts')
    Target_field = FloatParameter('Target field (T)', group_by='use_magnet', default=0)
    sweep_rate = FloatParameter('Sweep rate (T/min)', group_by='use_magnet', default=0.1)
    acq_delay = FloatParameter('Acquisition Delay (s)', default=0.5)

    # --- Hardware Selection ---
    devices = BooleanParameter("Device in use", default=False)
    use_magnet = BooleanParameter('Use Magnet', group_by='devices', default=False)
    use_MFLI_1 = BooleanParameter('use_MFLI_1', group_by='devices', default=False)
    use_MFLI_2 = BooleanParameter('use_MFLI_2', group_by='devices', default=False)
    use_MFLI_3 = BooleanParameter('use_MFLI_3', group_by='devices', default=False)
    use_srs860_1 = BooleanParameter('Use srs860_1', group_by='devices', default=False)
    use_srs860_2 = BooleanParameter('Use srs860_2', group_by='devices', default=False)
    use_srs830_1 = BooleanParameter('Use srs830_1', group_by='devices', default=False)
    use_srs830_2 = BooleanParameter('Use srs830_2', group_by='devices', default=False)
    use_srs830_3 = BooleanParameter('Use srs830_3', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)
    use_keithley_3 = BooleanParameter('Use k2450_3', group_by='devices', default=False)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.getMagneticField()
        return self._read_standard(t0)

    def execute(self):
        magnet = base.magnet
        if self.use_magnet == False:
            log.warning("Magnet was not chosen measurement aborted")
            return
        # PPMS firmware manages ramp safety; no per-range limits or persistent
        # switch heater like the Cryomagnetics supply.
        time_0 = time.time()
        log.info("starting to sweep field to %g Tesla at %g T/min",
                 self.Target_field, self.sweep_rate)
        origin_field = magnet.getMagneticField()
        magnet.go_to_target_field(self.Target_field, self.sweep_rate)
        total_sweep_range = abs(self.Target_field - origin_field)
        if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero
        current_field = origin_field
        # --- Monitoring Loop ---
        while abs(current_field - self.Target_field) > 0.003:
            data = self.getmeas(time_0)
            current_field = data[-1]
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            progress_percent = 100 * (abs(current_field - origin_field) / total_sweep_range)
            self.emit('progress', min(100, max(0, progress_percent)))
            time.sleep(self.acq_delay)
            if self.should_stop():
                log.warning("Magnet sweep stopped by user.")
                return
        log.info("Magnetic field Reached!")

    def shutdown(self):
        magnet = base.magnet
        if self.use_magnet == True:
            current_field = magnet.getMagneticField()
            if abs(current_field - self.Target_field) > 0.003:
                magnet.pause_field()
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")


proc_resistance_magnet = {
"Resistance magnet sweep measurement": dict(
        cls=Resistance_magnet_sweep_measurement,
        category="Magnetic Field",
        description="Measurement of resistance vs magnetic field sweep.",
        inputs=[
                'Title', 'Resistor', 'Contacts', 'Gate_contacts',
                'devices',
                'use_magnet', 'Target_field', 'sweep_rate',
                'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_keithley_1', 'use_keithley_2', 'use_keithley_3',
                'acq_delay',
        ],
        displays=[
            'Title',
            'Target_field'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
    ),
}