import numpy as np
import os


def write_block(f, measurement_type, params):
    """
    Helper function to write a formatted block to the file
    to ensure strict indentation compliance.
    """
    # Level 1: Measurement Type
    f.write(f'- "Measurement Type", "[\'{measurement_type}\']"\n')

    # Level 2+: Parameters
    # params is a list of tuples: (Label, Value, Indentation_Level)
    for label, value, level in params:
        dashes = '-' * (level + 1)  # Level 1 has 1 dash, Level 2 has 2, etc.
        f.write(f'{dashes} "{label}", "[{value}]"\n')


def generate_universal_sequence(filename,
                                mode,
                                field_points,
                                voltage_points,
                                step_size_mv,
                                acquisition_length):
    """
    Generates sequence based on the selected mode.

    Modes:
    1. 'v_hyst_at_h': Voltage Hysteresis (Fwd+Bwd) at different fixed Magnetic Fields.
    2. 'h_hyst_at_v': Field Hysteresis (Fwd+Bwd) at different fixed Voltages.
    3. 'map_snake':   Snake Map (Field step -> V sweep up -> Field step -> V sweep down).
    4. 'map_fwdbwd':  Fwd/Bwd Map (Field step -> V sweep up -> V sweep down -> Next Field).
    """

    with open(filename, 'w') as f:

        # --- MODE 1: Voltage Hysteresis at Fixed Fields ---
        if mode == 'v_hyst_at_h':
            # voltage_points should be [V_min, V_max]
            v_min, v_max = voltage_points[0], voltage_points[-1]

            for h in field_points:
                # 1. Move Magnet (RH)
                write_block(f, 'RH', [
                    ('Target field (T)', h, 1),
                    ('Target Voltage(V)', v_min, 2),  # Hold at V_min while moving
                    ('Use Magnet', 'True', 3)
                ])

                # 2. Wait/Stabilize (Rt)
                write_block(f, 'Rt', [
                    ('Acquisition Length (s)', acquisition_length, 1),
                    ('Target Voltage(V)', v_min, 2),
                    ('Target field (T)', h, 3),
                    ('Use Magnet', 'True', 4)
                ])

                # 3. V Sweep Forward (RV)
                write_block(f, 'RV', [
                    ('Target Voltage(V)', v_max, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

                # 4. V Sweep Backward (RV)
                write_block(f, 'RV', [
                    ('Target Voltage(V)', v_min, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

        # --- MODE 2: Magnetic Field Hysteresis at Fixed Voltages ---
        elif mode == 'h_hyst_at_v':
            # field_points should be [H_min, H_max]
            # voltage_points is the list of fixed voltages to measure at
            h_min, h_max = field_points[0], field_points[-1]

            for v in voltage_points:
                # 1. Set Voltage (Using RV usually, or just holding during RH)
                # We start by doing an RH sweep, assuming the system holds V.

                # Sweep H Forward (H_min -> H_max)
                write_block(f, 'RH', [
                    ('Target field (T)', h_max, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Use Magnet', 'True', 3)
                ])

                # Sweep H Backward (H_max -> H_min)
                write_block(f, 'RH', [
                    ('Target field (T)', h_min, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Use Magnet', 'True', 3)
                ])

        # --- MODE 3.1: Snake Map (Field Step -> Toggle V direction) ---
        elif mode == 'map_snake':
            # voltage_points should be [V_start, V_end]
            v_start, v_end = voltage_points[0], voltage_points[-1]

            for i, h in enumerate(field_points):
                # Determine target V based on even/odd iteration
                current_v_target = v_end if (i % 2 == 0) else v_start
                # The "holding" voltage during magnet move is the *previous* target
                holding_v = v_start if (i % 2 == 0) else v_end

                # 1. Move Magnet
                write_block(f, 'RH', [
                    ('Target field (T)', h, 1),
                    ('Target Voltage(V)', holding_v, 2),
                    ('Use Magnet', 'True', 3)
                ])

                # 2. Sweep V to target
                write_block(f, 'RV', [
                    ('Target Voltage(V)', current_v_target, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

        # --- MODE 3.2: Forward/Backward Map (Field Step -> V Fwd -> V Bwd) ---
        elif mode == 'map_fwdbwd':
            v_min, v_max = voltage_points[0], voltage_points[-1]

            for h in field_points:
                # 1. Move Magnet
                write_block(f, 'RH', [
                    ('Target field (T)', h, 1),
                    ('Target Voltage(V)', v_min, 2),
                    ('Use Magnet', 'True', 3)
                ])

                # 2. Wait (Rt)
                write_block(f, 'Rt', [
                    ('Acquisition Length (s)', acquisition_length, 1),
                    ('Target Voltage(V)', v_min, 2),
                    ('Target field (T)', h, 3),
                    ('Use Magnet', 'True', 4)
                ])

                # 3. Sweep V Forward
                write_block(f, 'RV', [
                    ('Target Voltage(V)', v_max, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

                # 4. Sweep V Backward
                write_block(f, 'RV', [
                    ('Target Voltage(V)', v_min, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

    print(f"Sequence generated successfully: {filename}")
    print(f"Mode Used: {mode}")


# ==========================================
#              USER CONFIGURATION
# ==========================================

# 1. Setup File Path
#save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav\2026\Device 3\RHV by sequence"
save_dir = r"C:\Users\Yoav\Desktop\test"
# Ensure directory exists
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

filename = os.path.join(save_dir, "Generated_Sequence.txt")

# 2. Define Parameters
# ----------------------------------------
# For Modes 1, 3.1, 3.2: field_points is the list of STEPS.
# For Mode 2: field_points is [H_min, H_max] for the sweep.
fields_array = np.linspace(0, 1, 5)

# For Modes 1, 3.1, 3.2: voltage_points is [V_min, V_max].
# For Mode 2: voltage_points is the list of FIXED voltages.
voltages_array = [-5, 5]

step_mv = 10
acq_time = 30  # seconds

# 3. Select Mode
# Options: 'v_hyst_at_h', 'h_hyst_at_v', 'map_snake', 'map_fwdbwd'
current_mode = 'map_snake'

# 4. Run Generator
generate_universal_sequence(filename,
                            current_mode,
                            fields_array,
                            voltages_array,
                            step_mv,
                            acq_time)