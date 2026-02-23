import numpy as np
import os

def generate_measurement_sequence(filename,
                                  target_fields,
                                  target_voltages,step_size,
                                  acquisition_length
                                  ):

    forward_backward= True
    snake = False

    with open(filename, 'w') as f:
        for h_target in target_fields:
            if forward_backward == True:
                # RH Section
                f.write(f'- "Measurement Type", "[\'RH\']"\n')
                f.write(f'-- "Target field (T)", "[{h_target}]"\n')
                f.write(f'--- "Target Voltage(V)", "[{target_voltages[-1]}]"\n')
                f.write(f'---- "Use Magnet", "[\'True\']"\n')

                # # Rt in case some waiting time is need after magnet sweep
                f.write(f'- "Measurement Type", "[\'Rt\']"\n')
                f.write(f'-- "Acquisition Length (s)", "[{acquisition_length}]"\n')
                f.write(f'--- "Target Voltage(V)", "[{target_voltages[-1]}]"\n')
                f.write(f'---- "Target field (T)", "[{h_target}]"\n')
                f.write(f'----- "Use Magnet", "[\'True\']"\n')

                # RV Sweep back and forth
                f.write(f'- "Measurement Type", "[\'RV\']"\n')
                f.write(f'-- "Target Voltage(V)", "[{target_voltages[0]}]"\n')
                f.write(f'--- "Target field (T)", "[{h_target}]"\n')
                f.write(f'----"Step size(mV)","[{step_size}]"\n')
                f.write(f'----- "Use Magnet", "[\'False\']"\n')

                f.write(f'- "Measurement Type", "[\'RV\']"\n')
                f.write(f'-- "Target Voltage(V)", "[{target_voltages[-1]}]"\n')
                f.write(f'--- "Target field (T)", "[{h_target}]"\n')
                f.write(f'----"Step size(mV)","[{step_size}]"\n')
                f.write(f'----- "Use Magnet", "[\'False\']"\n')

            elif snake == True:
                # RH Section
                f.write(f'- "Measurement Type", "[\'RH\']"\n')
                f.write(f'-- "Target field (T)", "[{h_target}]"\n')
                f.write(f'--- "Target Voltage(V)", "[{target_voltages[-1]}]"\n')
                f.write(f'---- "Use Magnet", "[\'True\']"\n')

                # # Rt in case some waiting time is need after magnet sweep
                f.write(f'- "Measurement Type", "[\'Rt\']"\n')
                f.write(f'-- "Acquisition Length (s)", "[{acquisition_length}]"\n')
                f.write(f'--- "Target Voltage(V)", "[{target_voltages[-1]}]"\n')
                f.write(f'---- "Target field (T)", "[{h_target}]"\n')
                f.write(f'----- "Use Magnet", "[\'True\']"\n')

                # RV Sweep back and forth
                f.write(f'- "Measurement Type", "[\'RV\']"\n')
                f.write(f'-- "Target Voltage(V)", "[{target_voltages[0]}]"\n')
                f.write(f'--- "Target field (T)", "[{h_target}]"\n')
                f.write(f'---- "Use Magnet", "[\'False\']"\n')

                f.write(f'- "Measurement Type", "[\'RV\']"\n')
                f.write(f'-- "Target Voltage(V)", "[{-target_voltages[0]}]"\n')
                f.write(f'--- "Target field (T)", "[{h_target}]"\n')
                f.write(f'---- "Use Magnet", "[\'False\']"\n')


# --- USER INPUTS ---
name = "RH_RV_Rt_sequence.txt"
save_dir = r"C:\Users\ICE\Desktop\ICE Measurements\Yoav\2026\Device 3\RHV by sequence"
file_name =os.path.join(save_dir, name)
target_fields = np.linspace(0.6,3,25)               # decide on magnetic field range of measurements

target_voltages = [5,-5]                            # decide on forward and backward sweep for voltage
step_size = 10

acquisition_length = 30                             # wait time after magnet sweep

# file name for measurement  {Measurement Type} sweep to {Target field (T)} T and {Target Voltage(V)} V
# Generate and Print
generate_measurement_sequence(file_name,
                              target_fields,
                              target_voltages, step_size,
                              acquisition_length
                              )
