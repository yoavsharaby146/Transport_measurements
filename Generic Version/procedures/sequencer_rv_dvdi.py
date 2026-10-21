"""
Sequencer for RV and dV/dI measurements (Generic Version).

Type switch between a gate-voltage sweep (RV) and a dV/dI AUX sweep — the
same dV/dI AUX machinery as "Differential Resistance AUX" (any connected
lock-in as AUX source, AC from a lock-in sine output or the K6221),
inherited by subclassing. Port of the ICE RV/dV/dI sequencer.
"""

from .base import *
from . import base
from .differential_resistance import (Differential_Resistance_AUX,
                                      _make_aux_source_parameter,
                                      _requires_aux_source)


class RV_dV_dI_sequencer_measurement(Differential_Resistance_AUX):
    Title = Parameter('Measurement type', default='RV and dV/dI in sequence')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Type-dependent parameters ---
    Type = ListParameter('Measurement Type', choices=['RV', 'dV/dI'], default='RV')

    # RV branch (gate sweep)
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type',
                                    group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type',
                               group_condition='RV', default=1)
    smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                   group_by='Type', group_condition='RV')

    # dV/dI branch (AUX sweep) — parent parameters regrouped under Type
    scan_mode = ListParameter('Sweep Mode', choices=['Sweep to setpoint', 'Sweep and Return'],
                              group_by='Type', group_condition='dV/dI',
                              default='Sweep to setpoint')
    aux_Target = FloatParameter('Auxiliary DC Bias Target (V)', group_by='Type',
                                group_condition='dV/dI', default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='Type',
                              group_condition='dV/dI', default=2)

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh aux_source and SMU dropdowns to connected instruments."""
        cls.aux_source = _make_aux_source_parameter()
        cls.smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                           group_by='Type', group_condition='RV')

    def run_RV(self):
        time_0 = time.time()
        log.info(f"starting voltage sweep to {self.Target_voltage} V")
        Gate = self.smu_choice(self.smu)
        self.smu_output(Gate, self.smu)
        start_volts = Gate.measure__voltage()
        gate_ranges = self.generate_range(start_volts, self.Target_voltage, self.step_size)
        log.info(f"Sweeping {self.smu} from {start_volts:.4f}V to {self.Target_voltage:.4f}V")
        iteration = 1
        for gate_volt in gate_ranges:
            Gate.ramp_voltage(gate_volt, 2, 0.001)
            time.sleep(self.acq_delay)
            data = self.getmeas(time_0)
            self.emit('results', dict(zip(self.DATA_COLUMNS, data)))
            self.emit('progress', 100 * iteration / len(gate_ranges))
            iteration += 1
            if self.should_stop():
                log.warning("Caught the stop flag in the procedure")
                return
        if self.Target_voltage == 0:
            log.info(f"Target reached 0V.  {self.smu} is still ON.")

    def run_dV_dI(self):
        # Same as the parent's execute(), packaged as a branch method.
        self.execute()

    def execute(self):
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'dV/dI':
            super().execute()

    def shutdown(self):
        log.info("Finished measuring")


proc_RV_dV_dI_sequencer = {
    "RV dV/dI sequencer measurement": dict(
        cls=RV_dV_dI_sequencer_measurement,
        category=["Differential Resistance", "Gate Sweep"],
        description="Sequencer for RV (gate sweep) and dV/dI (lock-in AUX DC bias "
                    "sweep) measurements.\n"
                    "dV/dI branch: any connected lock-in as AUX source; AC excitation "
                    "selectable (lock-in sine output or K6221 waveform).\n"
                    "Sources are NOT turned off at the end.",
        requires=_requires_aux_source,
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'acq_delay', 'Type',
                'Target_voltage', 'step_size', 'smu',
                'scan_mode', 'aux_source', 'aux_signal', 'aux_Target', 'aux_step',
                'ac_source', 'ac_running', 'waveform', 'frequency',
                'ac_current', 'ac_compliance',
                'devices', 'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221'],
        displays=['Type', 'Target_voltage', 'scan_mode', 'aux_Target', 'aux_source', 'smu'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu',
                          'scan_mode', 'aux_Target', 'aux_step', 'aux_source', 'aux_signal'],
    ),
}

