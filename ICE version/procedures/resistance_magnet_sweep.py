"""
Resistance magnet sweep measurement procedure.
"""

from .base import *
from . import base


class Resistance_magnet_sweep_measurement(ICEProcedure):
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
    use_dual_gate = BooleanParameter('Use dual gate', group_by='devices', default=False)
    use_keithley_1 = BooleanParameter('Use k2450_1', group_by='devices', default=False)
    use_keithley_2 = BooleanParameter('Use k2450_2', group_by='devices', default=False)

    def startup(self):
        self._capture_metadata()

    def getmeas(self, t0):
        if self.use_magnet and base._is_connected(base.magnet):
            base.magnet.magnet_field_write_query()
        return self._read_standard(t0)

    def execute(self):
        magnet = base.magnet
        if self.use_magnet == False:
            log.warning("Magnet was not chosen measurement aborted")
            return
        original_rates = {i: getattr(magnet, f"current_rate{i}") for i in range(5)}
        SAFETY_MAX_RATE_PER_RANGE = {0: 0.20,1: 0.10,2: 0.05,3: 0.03,4: 0.001}

        try:
            for i in range(5):
                max_rate = SAFETY_MAX_RATE_PER_RANGE[i]
                if self.sweep_rate <= max_rate:
                    applied_rate = self.sweep_rate
                else:
                    applied_rate = original_rates[i]
                    log.warning(
                    "Requested rate %g T/min exceeds safety limit %g T/min for range %d — "
                    "ignored, default rate %g T/min retained.",
                    self.sweep_rate, max_rate, i, original_rates[i]
                    )
                rate_A_s = (applied_rate * 10.375) / 60
                setattr(magnet, f'current_rate{i}', rate_A_s)
                log.info("Range %d rate set to %g T/min (%g A/s)", i, applied_rate, rate_A_s)
            
            time_0 = time.time()
            log.info("starting to sweep field to %g Tesla", self.Target_field)
            # --- 1. Persistent Heater Logic ---
            current_field = magnet.magnet_field
            persistent_heater_status = magnet.persistent_switch_heater
            print('Persistent switch heater mode: %s' % persistent_heater_status)
            # Test if the magnet heater is on, in case the persistent heater is off
            # turn it on and wait 10 min
            if persistent_heater_status == '0':
                log.info("Heater is OFF. Turning ON and waiting 600s...")
                magnet.persistent_switch_heater = 'ON'
                time.sleep(600)
                log.info("Heater warm-up complete.")

            # --- 2. Setup Sweep ---
            origin_field = magnet.magnet_field
            magnet.go_to_target_field(self.Target_field)

            total_sweep_range = abs(self.Target_field - origin_field)
            if total_sweep_range == 0: total_sweep_range = 1.0  # Avoid division by zero

            # --- 3. Monitoring Loop ---
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
        finally:
            for i in range(5):
                setattr(magnet, f'current_rate{i}', original_rates[i])

    def shutdown(self):
        magnet = base.magnet
        if self.use_magnet == True:
            current_field = magnet.magnet_field
            if abs(current_field-self.Target_field) > 0.003:
                magnet.sweep_mode = 'PAUSE'
                log.info("Measurement stopped before reaching target field")
        log.info("Finished measuring")


proc_resistance_magnet = {
"Resistance magnet sweep measurement": dict(
        cls=Resistance_magnet_sweep_measurement,
        category="Magnetic Field",
        description="Measurement of resistance vs magnetic field sweep.",
        inputs=[
                'Title','Resistor','Contacts','Gate_contacts',
                'devices',
                'use_magnet','Target_field','sweep_rate',
                'use_MFLI_1','use_MFLI_2' ,'use_MFLI_3',
                'use_srs860_1','use_srs860_2',
                'use_srs830_1','use_srs830_2','use_srs830_3',
                'use_dual_gate','use_keithley_1','use_keithley_2',
                'acq_delay',
        ],
        displays=[
            'Title',
            'Target_field'],
        x=['time(s)'],
        y=['probe_temp(K)','field(T)'],
    ),
}
