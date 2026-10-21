"""
Sequencer for RV and R_AUX measurements (Generic Version).

Type switch between a gate-voltage sweep (RV) and a lock-in AUX output
voltage sweep (R_AUX) — the same AUX-source machinery as "Resistance aux
voltage sweep" (any connected lock-in), inherited by subclassing.
"""

from .base import *
from . import base
from .resistance_aux_sweep import (Resistance_aux_voltage_measurement,
                                   _make_aux_source_parameter,
                                   _connected_aux_sources)


def _requires_aux_source(cfg):
    return len(_connected_aux_sources()) > 0


class RV_R_AUX_sequencer_measurement(Resistance_aux_voltage_measurement):
    Title = Parameter('Measurement type', default='RV and R_AUX in sequence')
    Resistor = Parameter('Resistance/Gain', default='insert resistor size/gain')
    Contacts = Parameter('Contacts ', default='insert contact numbers')
    Gate_contacts = Parameter('Gate contacts', default='insert gate contacts')

    # --- Type-dependent parameters ---
    Type = ListParameter('Measurement Type', choices=['RV', 'R_AUX'], default='RV')

    # RV branch (gate sweep)
    Target_voltage = FloatParameter('Target Voltage(V)', group_by='Type',
                                    group_condition='RV', default=0)
    step_size = FloatParameter('Step size(mV)', group_by='Type',
                               group_condition='RV', default=1)
    smu = base._make_smu_parameter('User defined SMU', default='Gate_1',
                                   group_by='Type', group_condition='RV')

    # R_AUX branch (AUX sweep) — parent parameters regrouped under Type
    target_AUX_voltage = FloatParameter('Target Aux Voltage(V)', group_by='Type',
                                        group_condition='R_AUX', default=0)
    aux_step = FloatParameter('Auxiliary step (mV)', group_by='Type',
                              group_condition='R_AUX', default=1)

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

    def run_R_AUX(self):
        # Parent's execute() does the AUX sweep from its present level to
        # target_AUX_voltage using self.step_size as the step. In this
        # sequencer the step parameter for the R_AUX branch is aux_step.
        self.step_size = self.aux_step
        self.execute()

    def execute(self):
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'R_AUX':
            super().execute()

    def shutdown(self):
        log.info("Finished measuring")


proc_RV_R_AUX_sequencer = {
    "RV R_AUX sequencer measurement": dict(
        cls=RV_R_AUX_sequencer_measurement,
        category=["Aux Sweep", "Gate Sweep"],
        description="Sequencer for RV (gate sweep) and R_AUX (lock-in AUX output "
                    "voltage sweep) measurements.\n"
                    "R_AUX branch: any connected lock-in (SRS830 / SRS860 / MFLI — "
                    "connected units only) as AUX source.",
        requires=_requires_aux_source,
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'acq_delay', 'Type',
                'Target_voltage', 'step_size', 'smu',
                'target_AUX_voltage', 'aux_step', 'aux_source', 'aux',
                'devices', 'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2', 'use_k6221'],
        displays=['Type', 'Target_voltage', 'target_AUX_voltage', 'aux_source', 'smu'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu',
                          'target_AUX_voltage', 'aux_step', 'aux_source', 'aux'],
    ),
}

