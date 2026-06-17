"""
spike_phase_sweep_pow2us.py

Single-spike phase-shift generator for Cadence/Spectre PWL inputs.

Directory structure produced beside this script:

    single_spike_phase_sweep_output/
        st_1/
            base.pwl
        st_2/
            1e-6_phase_shift/base.pwl
            2e-6_phase_shift/base.pwl
            4e-6_phase_shift/base.pwl
            ...
            2.56e-4_phase_shift/base.pwl

    single_spike_phase_sweep_output_csv/
        st_1/
            base.csv
        st_2/
            1e-6_phase_shift/base.csv
            2e-6_phase_shift/base.csv
            4e-6_phase_shift/base.csv
            ...
            2.56e-4_phase_shift/base.csv

Behaviour:
    - st_1 is always the same single spike.
    - st_2 is a copy of st_1 shifted later in time.
    - The st_2 directory sweeps absolute phase shifts from 1 us to 256 us
      in powers of two.
    - There is no Poisson-distributed spike generation.
    - There is no frequency sweep.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterable


# -----------------------------------------------------------------------------
# User variables
# -----------------------------------------------------------------------------

# Keep these folders beside this script.
output_root = Path(__file__).resolve().parent / "single_spike_phase_sweep_output"
csv_output_root = Path(__file__).resolve().parent / "single_spike_phase_sweep_output_csv"

# Simulation timing, in seconds.
total_time = 3.0e-4
base_spike_start_time = 1.0e-6

# Pulse shape.
pulse_height = 1.8
pulse_width = 1.0e-6
rise_time = 1.0e-8
fall_time = 1.0e-8

# Absolute phase-shift sweep for st_2, in seconds.
phase_shift_values_us = (1, 2, 4, 8, 16)

# Output behaviour.
overwrite_output_directory = True
base_filename_stem = "base"


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------

def format_scientific_for_dir(value: float) -> str:
    """
    Format values like 1e-6, 2e-6, ..., 2.56e-4 for folder names.

    Python's default scientific notation gives strings such as 1e-06. This
    function removes redundant exponent zeros so the folders are easier to read.
    """
    mantissa, exponent = f"{value:.12e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exponent_int = int(exponent)
    return f"{mantissa}e{exponent_int}"


def phase_shift_directory_name(phase_shift_s: float) -> str:
    """Return the folder name used for one st_2 phase-shift case."""
    return f"{format_scientific_for_dir(phase_shift_s)}_phase_shift"


# -----------------------------------------------------------------------------
# Validation and generation helpers
# -----------------------------------------------------------------------------

def validate_user_variables() -> None:
    """Validate user-editable settings before generating any output."""
    if total_time <= 0:
        raise ValueError("total_time must be positive.")
    if base_spike_start_time < 0:
        raise ValueError("base_spike_start_time must be non-negative.")
    if pulse_height <= 0:
        raise ValueError("pulse_height must be positive.")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")
    if rise_time <= 0 or fall_time <= 0:
        raise ValueError("rise_time and fall_time must be positive.")
    if pulse_width <= rise_time:
        raise ValueError("pulse_width must be larger than rise_time.")
    if not phase_shift_values_us:
        raise ValueError("phase_shift_values_us must contain at least one phase shift.")
    if any(phase_shift_us <= 0 for phase_shift_us in phase_shift_values_us):
        raise ValueError("phase_shift_values_us must contain only positive values.")

    phase_shifts = get_phase_shifts()
    phase_shift_stop = max(phase_shifts)
    latest_shifted_end = base_spike_start_time + phase_shift_stop + pulse_width + fall_time
    if latest_shifted_end > total_time:
        raise ValueError(
            "The largest shifted st_2 pulse would exceed total_time. "
            "Increase total_time, move base_spike_start_time earlier, reduce the maximum "
            "phase shift, or reduce pulse_width/fall_time."
        )

    base_end = base_spike_start_time + pulse_width + fall_time
    if base_end > total_time:
        raise ValueError(
            "The st_1 base pulse would exceed total_time. Increase total_time, "
            "move base_spike_start_time earlier, or reduce pulse_width/fall_time."
        )


def get_phase_shifts() -> list[float]:
    """
    Return the absolute st_2 phase shifts.

    The default values are:
        1 us, 2 us, 4 us, 8 us, 16 us, 32 us, 64 us, 128 us, 256 us
    """
    return [phase_shift_us * 1.0e-6 for phase_shift_us in phase_shift_values_us]


def build_single_pulse_points(spike_start_time: float, duration_s: float) -> list[tuple[float, float]]:
    """Convert one spike start time into a PWL voltage waveform."""
    spike_end_high = spike_start_time + pulse_width
    spike_end_fall = spike_end_high + fall_time

    if spike_start_time < 0:
        raise ValueError("spike_start_time must be non-negative.")
    if spike_end_fall > duration_s:
        raise ValueError(
            f"Pulse ending at {spike_end_fall:.12e} s exceeds total_time={duration_s:.12e} s."
        )

    points = [
        (0.0, 0.0),
        (spike_start_time, 0.0),
        (spike_start_time + rise_time, pulse_height),
        (spike_end_high, pulse_height),
        (spike_end_fall, 0.0),
    ]

    if points[-1][0] < duration_s:
        points.append((duration_s, 0.0))

    return points


def write_spike_train_pwl(output_path: Path, points: Iterable[tuple[float, float]]) -> None:
    """Write one whitespace-separated PWL file without a header."""
    with output_path.open("w", newline="") as f:
        for time_s, voltage_v in points:
            f.write(f"{time_s:.12e} {voltage_v:.12e}\n")


def write_spike_train_csv(output_path: Path, points: Iterable[tuple[float, float]]) -> None:
    """Write one CSV file containing the same points as the PWL file."""
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "voltage_v"])
        for time_s, voltage_v in points:
            writer.writerow([f"{time_s:.12e}", f"{voltage_v:.12e}"])


def reset_output_directory(path: Path) -> None:
    """Remove and recreate an output directory, unless overwrite is disabled."""
    resolved_path = path.resolve()

    if resolved_path.exists():
        if not resolved_path.is_dir():
            raise NotADirectoryError(f"Output path exists but is not a directory: {resolved_path}")
        if overwrite_output_directory:
            shutil.rmtree(resolved_path)
            print(f"Deleted previous output directory: {resolved_path}")
        else:
            raise FileExistsError(
                f"Output directory already exists: {resolved_path}. "
                "Set overwrite_output_directory = True to replace it."
            )

    resolved_path.mkdir(parents=True, exist_ok=False)
    print(f"Created empty output directory: {resolved_path}")


# -----------------------------------------------------------------------------
# Main directory-tree generator
# -----------------------------------------------------------------------------

def main() -> None:
    validate_user_variables()

    reset_output_directory(output_root)
    reset_output_directory(csv_output_root)

    # st_1: one fixed base spike.
    st1_dir = output_root / "st_1"
    csv_st1_dir = csv_output_root / "st_1"
    st1_dir.mkdir(parents=True, exist_ok=True)
    csv_st1_dir.mkdir(parents=True, exist_ok=True)

    st1_points = build_single_pulse_points(base_spike_start_time, total_time)
    write_spike_train_pwl(st1_dir / f"{base_filename_stem}.pwl", st1_points)
    write_spike_train_csv(csv_st1_dir / f"{base_filename_stem}.csv", st1_points)

    # st_2: same pulse, shifted by each absolute phase-shift value.
    st2_root = output_root / "st_2"
    csv_st2_root = csv_output_root / "st_2"
    st2_root.mkdir(parents=True, exist_ok=True)
    csv_st2_root.mkdir(parents=True, exist_ok=True)

    phase_shifts = get_phase_shifts()
    for phase_shift_s in phase_shifts:
        shifted_start_time = base_spike_start_time + phase_shift_s
        shifted_points = build_single_pulse_points(shifted_start_time, total_time)

        phase_dir_name = phase_shift_directory_name(phase_shift_s)
        st2_phase_dir = st2_root / phase_dir_name
        csv_st2_phase_dir = csv_st2_root / phase_dir_name
        st2_phase_dir.mkdir(parents=True, exist_ok=True)
        csv_st2_phase_dir.mkdir(parents=True, exist_ok=True)

        write_spike_train_pwl(st2_phase_dir / f"{base_filename_stem}.pwl", shifted_points)
        write_spike_train_csv(csv_st2_phase_dir / f"{base_filename_stem}.csv", shifted_points)

    print(f"PWL directory tree written to: {output_root.resolve()}")
    print(f"CSV directory tree written to: {csv_output_root.resolve()}")
    print(f"st_1 spike start time: {base_spike_start_time:.12e} s")
    print(
        "st_2 phase-shift sweep: "
        f"{', '.join(f'{phase_shift_s:.12e} s' for phase_shift_s in phase_shifts)}"
    )
    print(f"Pulse width: {pulse_width:.12e} s")
    print(f"Number of st_2 phase-shift cases written: {len(phase_shifts)}")
    print(f"Total PWL files written: {1 + len(phase_shifts)}")
    print(f"Total CSV files written: {1 + len(phase_shifts)}")


if __name__ == "__main__":
    main()
