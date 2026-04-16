from __future__ import annotations

import numpy as np
import os
from enum import Enum
from typing import Sequence, Union


class Mode(Enum):
    """Supported measurement sequence modes."""
    V_HYST_AT_H = 'v_hyst_at_h'   # Voltage Hysteresis (Fwd+Bwd) at different fixed Magnetic Fields
    H_HYST_AT_V = 'h_hyst_at_v'   # Field Hysteresis (Fwd+Bwd) at different fixed Voltages
    MAP_SNAKE = 'map_snake'        # Snake Map (Field step -> V sweep up -> Field step -> V sweep down)
    MAP_FWDBWD = 'map_fwdbwd'     # Fwd/Bwd Map (Field step -> V sweep up -> V sweep down -> Next Field)


# Shorthand access: Mode.V_HYST_AT_H, etc.
# Can also be used as strings: Mode.V_HYST_AT_H.value == 'v_hyst_at_h'
VALID_MODES = {m.value for m in Mode}


def _format_value(value: Union[int, float, str]) -> str:
    """Format a value for clean file output. Strings pass through; numbers get 'g' formatting."""
    if isinstance(value, str):
        return value
    # Use 'g' format: removes trailing zeros, keeps integers clean, limits decimal noise
    return f"{value:g}"


def write_block(f, measurement_type: str, params: list[tuple[str, Union[int, float, str], int]]) -> None:
    """
    Helper function to write a formatted block to the file
    to ensure strict indentation compliance.

    Args:
        f: File handle to write to.
        measurement_type: String like 'RH', 'RV', 'Rt'.
        params: List of tuples (Label, Value, Indentation_Level).
                Value can be a number or string; numbers are formatted cleanly.
    """
    # Level 1: Measurement Type
    f.write(f'- "Measurement Type", "[\'{measurement_type}\']"\n')

    # Level 2+: Parameters
    for label, value, level in params:
        dashes = '-' * (level + 1)  # Level 1 has 1 dash, Level 2 has 2, etc.
        formatted = _format_value(value)
        f.write(f'{dashes} "{label}", "[{formatted}]"\n')


def _count_blocks(mode_str: str, n_fields: int, n_voltages: int) -> dict[str, int]:
    """Calculate the number of each measurement block type for the preview summary."""
    counts = {'RH': 0, 'Rt': 0, 'RV': 0}
    if mode_str == Mode.V_HYST_AT_H.value:
        # Per field: 1 RH + 1 Rt + 2 RV
        counts['RH'] = n_fields
        counts['Rt'] = n_fields
        counts['RV'] = n_fields * 2
    elif mode_str == Mode.H_HYST_AT_V.value:
        # Per voltage: 2 RH + 2 Rt
        counts['RH'] = n_voltages * 2
        counts['Rt'] = n_voltages * 2
        counts['RV'] = 0
    elif mode_str == Mode.MAP_SNAKE.value:
        # Per field: 1 RH + 1 Rt + 1 RV
        counts['RH'] = n_fields
        counts['Rt'] = n_fields
        counts['RV'] = n_fields
    elif mode_str == Mode.MAP_FWDBWD.value:
        # Per field: 1 RH + 1 Rt + 2 RV
        counts['RH'] = n_fields
        counts['Rt'] = n_fields
        counts['RV'] = n_fields * 2
    return counts


def generate_descriptive_filename(
    mode: Union[str, Mode],
    field_points: Sequence[Union[int, float]],
    voltage_points: Sequence[Union[int, float]],
    step_size_mv: Union[int, float],
    acquisition_length: Union[int, float],
    save_dir: str | None = None
) -> str:
    """
    Generate a descriptive filename from the measurement parameters.

    Example output: 'map_snake_H0to1T_V-5to5V_step10mV_acq30s.txt'

    Args:
        mode: Measurement mode (string or Mode enum).
        field_points: Array of magnetic field values (T).
        voltage_points: Array of voltage values (V).
        step_size_mv: Voltage step size in mV.
        acquisition_length: Rt wait time in seconds.
        save_dir: If provided, prepends the directory to the filename.

    Returns:
        Full file path (if save_dir given) or just the filename.
    """
    mode_str = mode.value if isinstance(mode, Mode) else mode

    h_min = _format_value(field_points[0])
    h_max = _format_value(field_points[-1])
    v_min = _format_value(voltage_points[0])
    v_max = _format_value(voltage_points[-1])

    filename = f"{mode_str}_H{h_min}to{h_max}T_V{v_min}to{v_max}V_step{_format_value(step_size_mv)}mV_acq{_format_value(acquisition_length)}s.txt"

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        return os.path.join(save_dir, filename)
    return filename


def generate_universal_sequence(
    filename: str,
    mode: Union[str, Mode],
    field_points: Sequence[Union[int, float]],
    voltage_points: Sequence[Union[int, float]],
    step_size_mv: Union[int, float],
    acquisition_length: Union[int, float]
) -> None:
    """
    Generates sequence based on the selected mode.

    Modes:
    1. 'v_hyst_at_h': Voltage Hysteresis (Fwd+Bwd) at different fixed Magnetic Fields.
    2. 'h_hyst_at_v': Field Hysteresis (Fwd+Bwd) at different fixed Voltages.
    3. 'map_snake':   Snake Map (Field step -> V sweep up -> Field step -> V sweep down).
    4. 'map_fwdbwd':  Fwd/Bwd Map (Field step -> V sweep up -> V sweep down -> Next Field).

    Args:
        filename: Output file path.
        mode: One of Mode enum values or their string equivalents.
        field_points: Array of magnetic field values (T).
        voltage_points: Array of voltage values (V).
        step_size_mv: Voltage step size in mV (must be > 0).
        acquisition_length: Rt wait time in seconds (must be > 0).
    """

    # --- Input Validation ---
    # Accept both Mode enum and raw strings
    mode_str = mode.value if isinstance(mode, Mode) else mode

    if mode_str not in VALID_MODES:
        raise ValueError(
            f"Invalid mode '{mode_str}'. "
            f"Valid modes: {', '.join(sorted(VALID_MODES))}"
        )

    if len(field_points) == 0:
        raise ValueError("field_points must not be empty.")

    if len(voltage_points) == 0:
        raise ValueError("voltage_points must not be empty.")

    if step_size_mv <= 0:
        raise ValueError(f"step_size_mv must be > 0, got {step_size_mv}.")

    if acquisition_length <= 0:
        raise ValueError(f"acquisition_length must be > 0, got {acquisition_length}.")

    # Modes that need voltage_points as [V_min, V_max] (exactly 2 endpoints)
    sweep_modes = {Mode.V_HYST_AT_H.value, Mode.MAP_SNAKE.value, Mode.MAP_FWDBWD.value}
    if mode_str in sweep_modes and len(voltage_points) < 2:
        raise ValueError(
            f"Mode '{mode_str}' requires voltage_points with at least 2 elements "
            f"[V_min, V_max], got {len(voltage_points)}."
        )

    # Mode 2 needs field_points as [H_min, H_max] (exactly 2 endpoints)
    if mode_str == Mode.H_HYST_AT_V.value and len(field_points) < 2:
        raise ValueError(
            f"Mode '{mode_str}' requires field_points with at least 2 elements "
            f"[H_min, H_max], got {len(field_points)}."
        )

    # --- Print Preview Summary ---
    block_counts = _count_blocks(mode_str, len(field_points), len(voltage_points))
    total_blocks = sum(block_counts.values())

    print("=" * 50)
    print("SEQUENCE GENERATION PREVIEW")
    print("=" * 50)
    print(f"  Mode:              {mode_str}")
    print(f"  Field range:       {_format_value(field_points[0])}T → "
          f"{_format_value(field_points[-1])}T ({len(field_points)} points)")
    print(f"  Voltage range:     {_format_value(voltage_points[0])}V → "
          f"{_format_value(voltage_points[-1])}V ({len(voltage_points)} points)")
    print(f"  Step size:         {step_size_mv} mV")
    print(f"  Acquisition time:  {acquisition_length} s")
    print(f"  Output file:       {filename}")
    print(f"  Total blocks:      {total_blocks}  "
          f"(RH: {block_counts['RH']}, Rt: {block_counts['Rt']}, RV: {block_counts['RV']})")
    print("=" * 50)

    with open(filename, 'w') as f:

        # --- MODE 1: Voltage Hysteresis at Fixed Fields ---
        if mode_str == Mode.V_HYST_AT_H.value:
            v_min, v_max = voltage_points[0], voltage_points[-1]

            for h in field_points:
                # 1. Move Magnet (RH)
                write_block(f, 'RH', [
                    ('Target field (T)', h, 1),
                    ('Target Voltage(V)', v_min, 2),
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
        elif mode_str == Mode.H_HYST_AT_V.value:
            h_min, h_max = field_points[0], field_points[-1]

            for v in voltage_points:
                # 1. Sweep H Forward (H_min -> H_max)
                write_block(f, 'RH', [
                    ('Target field (T)', h_max, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Use Magnet', 'True', 3)
                ])

                # 2. Wait/Stabilize (Rt) after forward sweep
                write_block(f, 'Rt', [
                    ('Acquisition Length (s)', acquisition_length, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Target field (T)', h_max, 3),
                    ('Use Magnet', 'True', 4)
                ])

                # 3. Sweep H Backward (H_max -> H_min)
                write_block(f, 'RH', [
                    ('Target field (T)', h_min, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Use Magnet', 'True', 3)
                ])

                # 4. Wait/Stabilize (Rt) after backward sweep
                write_block(f, 'Rt', [
                    ('Acquisition Length (s)', acquisition_length, 1),
                    ('Target Voltage(V)', v, 2),
                    ('Target field (T)', h_min, 3),
                    ('Use Magnet', 'True', 4)
                ])

        # --- MODE 3.1: Snake Map (Field Step -> Toggle V direction) ---
        elif mode_str == Mode.MAP_SNAKE.value:
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

                # 2. Wait/Stabilize (Rt) after magnet move
                write_block(f, 'Rt', [
                    ('Acquisition Length (s)', acquisition_length, 1),
                    ('Target Voltage(V)', holding_v, 2),
                    ('Target field (T)', h, 3),
                    ('Use Magnet', 'True', 4)
                ])

                # 3. Sweep V to target
                write_block(f, 'RV', [
                    ('Target Voltage(V)', current_v_target, 1),
                    ('Target field (T)', h, 2),
                    ('Step size(mV)', step_size_mv, 3),
                    ('Use Magnet', 'False', 4)
                ])

        # --- MODE 3.2: Forward/Backward Map (Field Step -> V Fwd -> V Bwd) ---
        elif mode_str == Mode.MAP_FWDBWD.value:
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

    print(f"\n✓ Sequence generated successfully: {filename}")
    print(f"  Mode: {mode_str}")


# ==========================================
#              INTERACTIVE INPUT
# ==========================================

def _input_float(prompt: str, default: float | None = None) -> float:
    """Prompt for a float value with optional default. Re-prompts on invalid input."""
    while True:
        suffix = f" [{default}]: " if default is not None else ": "
        raw = input(prompt + suffix).strip()
        if not raw and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print(f"  ⚠ Invalid number '{raw}'. Please try again.")


def _input_int(prompt: str, default: int | None = None) -> int:
    """Prompt for an int value with optional default. Re-prompts on invalid input."""
    while True:
        suffix = f" [{default}]: " if default is not None else ": "
        raw = input(prompt + suffix).strip()
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print(f"  ⚠ Invalid integer '{raw}'. Please try again.")


def _input_int_in_range(prompt: str, min_val: int, max_val: int, default: int | None = None) -> int:
    """Prompt for an int within [min_val, max_val]. Re-prompts on invalid input."""
    while True:
        val = _input_int(prompt, default)
        if min_val <= val <= max_val:
            return val
        print(f"  ⚠ Please enter a number between {min_val} and {max_val}.")


def interactive_main():
    """Run the sequence generator with interactive user prompts."""

    print()
    print("=" * 55)
    print("   RH / RV / Rt  SEQUENCE GENERATOR  (interactive)")
    print("=" * 55)
    print()

    # --- 1. Select Mode ---
    print("Select measurement mode:")
    modes_list = list(Mode)
    for i, m in enumerate(modes_list, 1):
        print(f"  {i}. {m.value}")
    print()
    mode_choice = _input_int_in_range("Mode number", 1, len(modes_list))
    current_mode = modes_list[mode_choice - 1].value
    print(f"  → Selected: {current_mode}\n")

    # Determine what inputs we need based on mode
    is_hyst_mode = (current_mode == Mode.H_HYST_AT_V.value)

    # --- 2. Save Directory ---
    save_dir = input("Save directory [C:\\Users\\Yoav\\Desktop\\test]: ").strip()
    if not save_dir:
        save_dir = r"C:\Users\Yoav\Desktop\test"
    print()

    # --- 3. Field Parameters ---
    if is_hyst_mode:
        # Mode 2: field_points is [H_min, H_max]
        print("Field sweep range (for H hysteresis):")
        h_min = _input_float("  H_min (T)", default=0)
        h_max = _input_float("  H_max (T)", default=1)
        fields_array = [h_min, h_max]
        print(f"  → Field sweep: {h_min}T → {h_max}T\n")
    else:
        # Modes 1, 3.1, 3.2: field_points is a list of steps via linspace
        print("Field step points (via linspace):")
        h_start = _input_float("  Start field (T)", default=0)
        h_end = _input_float("  End field (T)", default=1)
        n_points = _input_int_in_range("  Number of points", 2, 10000, default=5)
        fields_array = np.linspace(h_start, h_end, n_points)
        print(f"  → Fields: {h_start}T → {h_end}T ({n_points} points)\n")

    # --- 4. Voltage Parameters ---
    if is_hyst_mode:
        # Mode 2: voltage_points is a list of fixed voltages
        print("Fixed voltages to measure at (comma-separated):")
        while True:
            raw = input("  Voltages (V) [e.g. -5, 0, 5]: ").strip()
            try:
                voltages_array = [float(v.strip()) for v in raw.split(',') if v.strip()]
                if len(voltages_array) == 0:
                    raise ValueError
                break
            except ValueError:
                print("  ⚠ Invalid input. Enter comma-separated numbers, e.g. -5, 0, 5")
        print(f"  → Voltages: {voltages_array}\n")
    else:
        # Modes 1, 3.1, 3.2: voltage_points is [V_min, V_max]
        print("Voltage sweep range:")
        v_min = _input_float("  V_min (V)", default=-5)
        v_max = _input_float("  V_max (V)", default=5)
        voltages_array = [v_min, v_max]
        print(f"  → Voltage sweep: {v_min}V ↔ {v_max}V\n")

    # --- 5. Step Size & Acquisition Time ---
    step_mv = _input_int("Voltage step size (mV)", default=10)
    acq_time = _input_int("Acquisition / wait time (s)", default=30)
    print()

    # --- 6. Generate filename and confirm ---
    filename = generate_descriptive_filename(
        current_mode, fields_array, voltages_array, step_mv, acq_time,
        save_dir=save_dir
    )

    # Preview
    block_counts = _count_blocks(current_mode, len(fields_array), len(voltages_array))
    total_blocks = sum(block_counts.values())

    print("=" * 55)
    print("CONFIRM GENERATION")
    print("=" * 55)
    print(f"  Mode:              {current_mode}")
    print(f"  Field range:       {_format_value(fields_array[0])}T → "
          f"{_format_value(fields_array[-1])}T ({len(fields_array)} points)")
    print(f"  Voltage range:     {_format_value(voltages_array[0])}V → "
          f"{_format_value(voltages_array[-1])}V ({len(voltages_array)} points)")
    print(f"  Step size:         {step_mv} mV")
    print(f"  Acquisition time:  {acq_time} s")
    print(f"  Output file:       {filename}")
    print(f"  Total blocks:      {total_blocks}  "
          f"(RH: {block_counts['RH']}, Rt: {block_counts['Rt']}, RV: {block_counts['RV']})")
    print("=" * 55)

    confirm = input("\nGenerate this sequence? (Y/n): ").strip().lower()
    if confirm in ('', 'y', 'yes'):
        generate_universal_sequence(filename,
                                    current_mode,
                                    fields_array,
                                    voltages_array,
                                    step_mv,
                                    acq_time)
    else:
        print("Cancelled.")


if __name__ == '__main__':
    interactive_main()
