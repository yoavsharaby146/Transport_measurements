def generate_measurement_sequence(filename, target_voltages,voltage_step,sweep_mode, dc_bias_targets, aux_step_mv):
    sequence = []
    with open(filename, 'w') as f:
        for v_target in target_voltages:
            # RV Section
            f.write(f'- "Measurement Type", "[\'RV\']"\n')
            f.write(f'-- "Target Voltage(V)", "[{v_target}]"\n')
            f.write(f'-- "Step size(mV)", "[{voltage_step}]"\n')

            # dV_dI Section
            f.write(f'- "Measurement Type", "[\'dV_dI\']"\n')
            f.write(f'-- "Sweep Mode","[{sweep_mode}]"\n')
            # Formatting the bias list as a string without extra spaces
            bias_str = ",".join(map(str, dc_bias_targets))                                  # comment this line in case of Sweep and Return
            f.write(f'-- "Auxiliary DC Bias Target  (V)", "[{bias_str}]"\n')          # comment this line in case of Sweep and Return
            #f.write(f'-- "Auxiliary DC Bias Target  (V)", "[{dc_bias_targets}]"')  # uncomment this in case of Sweep and return
            f.write(f'-- "Target Voltage(V)", "[{v_target}]"\n')                      # this line is to document the voltage at the time of the bias sweep proply
            f.write(f'-- "Step size(mV)", "[{voltage_step}]"\n')
            f.write(f'--- "Auxiliary step (mV)", "[{aux_step_mv}]"\n')



# --- USER INPUTS ---
file_name = "sequence.txt"
voltages = [5,4,3,2,1.5,1,0.75,0.5,0.25,0,-0.25,-0.5,-0.75,-1,-1.5,-2,-3,-4,-5]     # Define your order and numbers here
#voltages = voltages[::-1]                                                            # in case the array needs reversal
voltage_step = 5                                                                    # voltage sweep step size mV

sweep_mode = "Sweep to setpoint"                                                    # Bias sweep type Sweep to setpoint/ Sweep and Return
biases = [0.5, -0.5, 0]                                                             # Define your DC bias targets in case of Sweep and Return use one value only
bias_step = 2                                                                       #Bias sweep step size mV

# Generate and Print
generate_measurement_sequence(file_name,
                              voltages, voltage_step,
                              sweep_mode, biases, bias_step
                              )
