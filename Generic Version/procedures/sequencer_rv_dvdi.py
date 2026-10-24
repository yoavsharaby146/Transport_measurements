"""
Sequencer for RV and dV/dI measurements (Generic Version).

Type switch between a gate-voltage sweep (RV) and a dV/dI DC-current sweep —
the same dV/dI machinery as "Differential Resistance 6221" (DC bias on the
K6221 current source, compliance/range set manually on the instrument, AC
from a lock-in sine output assumed pre-configured), inherited by
subclassing.
"""

from .base import *
from . import base
from .differential_resistance_6221 import Differential_Resistance_6221


def _requires_k6221(cfg):
    return base._is_connected(getattr(cfg, 'K6221', 0))


class RV_dV_dI_sequencer_measurement(Differential_Resistance_6221):
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

    # dV/dI branch (K6221 DC current sweep) — parent parameters regrouped
    # under Type. dc_step fills the parent's step_size inside run_dV_dI/
    # execute (RV owns the step_size name for its mV gate step).
    target_current = FloatParameter('DC target current (A)', group_by='Type',
                                    group_condition='dV/dI', default=1e-6)
    dc_step = FloatParameter('DC step size (A)', group_by='Type',
                             group_condition='dV/dI', default=1e-8)

    @classmethod
    def _rebuild_parameters(cls):
        """Refresh the SMU dropdown to the connected instruments."""
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
        # Parent's execute() sweeps the K6221 DC current from its present
        # level to target_current using self.step_size (A) as the step —
        # in this sequencer the dV/dI step parameter is dc_step.
        self.step_size = self.dc_step
        self.execute()

    def execute(self):
        if self.Type == 'RV':
            self.run_RV()
        elif self.Type == 'dV/dI':
            self.step_size = self.dc_step
            super().execute()

    def shutdown(self):
        log.info("Finished measuring")


proc_RV_dV_dI_sequencer = {
    "RV dV/dI sequencer measurement": dict(
        cls=RV_dV_dI_sequencer_measurement,
        category=["Differential Resistance", "Gate Sweep"],
        description="Sequencer for RV (gate sweep) and dV/dI (K6221 DC bias "
                    "current sweep) measurements.\n"
                    "dV/dI branch: DC bias on the K6221 current source; K6221 "
                    "compliance and current range are set manually on the "
                    "instrument; AC excitation from a lock-in sine output assumed "
                    "pre-configured.\n"
                    "Sources are NOT turned off at the end.",
        requires=_requires_k6221,
        inputs=['Title', 'Resistor', 'Contacts', 'Gate_contacts', 'acq_delay', 'Type',
                'Target_voltage', 'step_size', 'smu',
                'target_current', 'dc_step',
                'devices', 'use_MFLI_1', 'use_MFLI_2', 'use_MFLI_3',
                'use_srs860_1', 'use_srs860_2', 'use_srs860_3', 'use_srs860_4',
                'use_srs830_1', 'use_srs830_2', 'use_srs830_3',
                'use_dual_gate', 'use_keithley_1', 'use_keithley_2',
                'use_yoko_gs200_1', 'use_yoko_gs200_2',
                'use_yoko7651_1', 'use_yoko7651_2'],
        displays=['Type', 'Target_voltage', 'target_current', 'smu'],
        x=['time(s)'],
        y=['time(s)', 'time(s)'],
        sequencer=True,
        sequencer_inputs=['Type', 'Target_voltage', 'step_size', 'smu',
                          'target_current', 'dc_step'],
    ),
}