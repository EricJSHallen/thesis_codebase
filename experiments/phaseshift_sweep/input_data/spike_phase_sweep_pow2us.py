"""
spike_phase_sweep_pow2us.py

Single-spike interspike-interval generator for Cadence/Spectre PWL inputs.

Directory structure produced beside this script:

    single_spike_phase_sweep_output/
        st_1/
            base.pwl
        st_2/
            1e-6_phase_shift/base.pwl
            2e-6_phase_shift/base.pwl
            4e-6_phase_shift/base.pwl
            ...
            1.6e-5_phase_shift/base.pwl

    single_spike_phase_sweep_output_csv/
        st_1/
            base.csv
        st_2/
            1e-6_phase_shift/base.csv
            2e-6_phase_shift/base.csv
            4e-6_phase_shift/base.csv
            ...
            1.6e-5_phase_shift/base.csv

Behaviour:
    - st_1 is always the same single spike.
    - st_2 contains one spike starting after st_1 ends.
    - The st_2 directory sweeps interspike intervals from 1 us to 16 us
      in powers of two. Directory names retain the "_phase_shift" suffix
      for compatibility with downstream scripts.
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

# Interspike interval sweep for st_2, in microseconds. Each value is the
# temporal distance between the end of the st_1 spike and start of the st_2 spike.
interspike_interval_values_us = (1, 2, 4, 8, 16)

# Output behaviour.
overwrite_output_directory = True
base_filename_stem = "base"


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------

def format_scientific_for_dir(value: float) -> str:
    """
    Format values like 1e-6, 2e-6, ..., 1.6e-5 for folder names.

    Python's default scientific notation gives strings such as 1e-06. This
    function removes redundant exponent zeros so the folders are easier to read.
    """
    mantissa, exponent = f"{value:.12e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exponent_int = int(exponent)
    return f"{mantissa}e{exponent_int}"


def phase_shift_directory_name(interspike_interval_s: float) -> str:
    """Return the compatible folder name used for one st_2 interval case."""
    return f"{format_scientific_for_dir(interspike_interval_s)}_phase_shift"


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
    if not interspike_interval_values_us:
        raise ValueError("interspike_interval_values_us must contain at least one interval.")
    if any(interval_us <= 0 for interval_us in interspike_interval_values_us):
        raise ValueError("interspike_interval_values_us must contain only positive values.")

    interspike_intervals = get_interspike_intervals()
    max_interspike_interval = max(interspike_intervals)
    st1_end_time = get_st1_end_time()
    latest_st2_end = st1_end_time + max_interspike_interval + pulse_width + fall_time
    if latest_st2_end > total_time:
        raise ValueError(
            "The st_2 pulse with the largest interspike interval would exceed total_time. "
            "Increase total_time, move base_spike_start_time earlier, reduce the maximum "
            "interspike interval, or reduce pulse_width/fall_time."
        )

    base_end = get_st1_end_time()
    if base_end > total_time:
        raise ValueError(
            "The st_1 base pulse would exceed total_time. Increase total_time, "
            "move base_spike_start_time earlier, or reduce pulse_width/fall_time."
        )


def get_interspike_intervals() -> list[float]:
    """
    Return the st_1-end to st_2-start intervals.

    The default values are:
        1 us, 2 us, 4 us, 8 us, 16 us
    """
    return [interval_us * 1.0e-6 for interval_us in interspike_interval_values_us]


def get_st1_end_time() -> float:
    """Return the time where the st_1 pulse has fallen back to 0 V."""
    return base_spike_start_time + pulse_width + fall_time


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

    # st_2: one pulse after st_1, separated by each interspike interval value.
    st2_root = output_root / "st_2"
    csv_st2_root = csv_output_root / "st_2"
    st2_root.mkdir(parents=True, exist_ok=True)
    csv_st2_root.mkdir(parents=True, exist_ok=True)

    st1_end_time = get_st1_end_time()
    interspike_intervals = get_interspike_intervals()
    for interspike_interval_s in interspike_intervals:
        st2_start_time = st1_end_time + interspike_interval_s
        st2_points = build_single_pulse_points(st2_start_time, total_time)

        phase_dir_name = phase_shift_directory_name(interspike_interval_s)
        st2_phase_dir = st2_root / phase_dir_name
        csv_st2_phase_dir = csv_st2_root / phase_dir_name
        st2_phase_dir.mkdir(parents=True, exist_ok=True)
        csv_st2_phase_dir.mkdir(parents=True, exist_ok=True)

        write_spike_train_pwl(st2_phase_dir / f"{base_filename_stem}.pwl", st2_points)
        write_spike_train_csv(csv_st2_phase_dir / f"{base_filename_stem}.csv", st2_points)

    print(f"PWL directory tree written to: {output_root.resolve()}")
    print(f"CSV directory tree written to: {csv_output_root.resolve()}")
    print(f"st_1 spike start time: {base_spike_start_time:.12e} s")
    print(f"st_1 spike end time: {st1_end_time:.12e} s")
    print(
        "st_2 interspike-interval sweep: "
        f"{', '.join(f'{interval_s:.12e} s' for interval_s in interspike_intervals)}"
    )
    print("Output directories retain the '_phase_shift' suffix for compatibility.")
    print(f"Pulse width: {pulse_width:.12e} s")
    print(f"Number of st_2 interspike-interval cases written: {len(interspike_intervals)}")
    print(f"Total PWL files written: {1 + len(interspike_intervals)}")
    print(f"Total CSV files written: {1 + len(interspike_intervals)}")


if __name__ == "__main__":
    main()
