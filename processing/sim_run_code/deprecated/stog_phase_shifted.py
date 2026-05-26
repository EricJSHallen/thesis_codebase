"""
stog_phase_shifted.py

Spike-train output generator for Cadence/Spectre PWL inputs.

This script follows the directory convention used by stog_v2.py:

    processing/sim_run_code/
        stog_phase_shifted.py
        spike_train_output/
            st_1/<frequency>_hz/trial_<n>.pwl
            st_2/<frequency>_hz/trial_<n>.pwl
            ...
        spike_train_output_csv/
            st_1/<frequency>_hz/trial_<n>.csv
            st_2/<frequency>_hz/trial_<n>.csv
            ...

Difference from stog_v2.py:
    For each (frequency, trial), only st_1 is randomly generated. st_2, st_3,
    ... st_n are deterministic copies of st_1 shifted later in time by

        (st_index - 1) * phase_shift_fraction_of_pulse_width * pulse_width

    With the default value phase_shift_fraction_of_pulse_width = 0.1:
        st_1 shift = 0.0 * pulse_width
        st_2 shift = 0.1 * pulse_width
        st_3 shift = 0.2 * pulse_width
        st_4 shift = 0.3 * pulse_width
        etc.

The base train is generated with enough end-of-simulation margin that all shifted
copies fit inside total_time without silently dropping late spikes.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import numpy as np

# -----------------------------------------------------------------------------
# User variables
# -----------------------------------------------------------------------------

# Keep these folders beside this script, as in the reference repo structure.
output_root = Path(__file__).resolve().parent / "spike_train_output"
csv_output_root = Path(__file__).resolve().parent / "spike_train_output_csv"

num_spike_train_sets = 4          # Creates st_1, st_2, ..., st_n
max_frequency_hz = 600            # Highest frequency directory to create
step_size = 30                    # 1, 31, 61, ... if step_size = 30
trials_per_frequency = 5          # Creates trial_1.pwl, ..., trial_j.pwl
total_time = 0.5                  # seconds

pulse_height = 1.8                # volts
pulse_width = 10e-6               # seconds
rise_time = 1e-8                  # seconds
fall_time = 1e-8                  # seconds

# Core requested behaviour: each later spike train is the same train as st_1,
# shifted by 0.1*pulse_width per train index.
phase_shift_fraction_of_pulse_width = 0.1

random_seed: int | None = 12345   # Set to None for non-reproducible output
overwrite_output_directory = True # If True, delete and recreate output folders


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def get_pulse_width() -> float:
    """Return the pulse width used for every generated spike."""
    return pulse_width


def get_phase_shift(st_index: int) -> float:
    """
    Return the deterministic phase shift for a spike-train index.

    st_index is one-based:
        st_1 -> 0.0
        st_2 -> 0.1*pulse_width by default
        st_3 -> 0.2*pulse_width by default
    """
    if st_index < 1:
        raise ValueError("st_index must be one-based and positive.")
    return (st_index - 1) * phase_shift_fraction_of_pulse_width * get_pulse_width()


def get_max_phase_shift() -> float:
    """Return the largest phase shift used by the last spike train."""
    return get_phase_shift(num_spike_train_sets)


def validate_user_variables() -> None:
    """Validate user-editable settings before generating any output."""
    if num_spike_train_sets <= 0:
        raise ValueError("num_spike_train_sets must be positive.")
    if max_frequency_hz <= 0:
        raise ValueError("max_frequency_hz must be positive.")
    if step_size <= 0:
        raise ValueError("step_size must be positive.")
    if not isinstance(step_size, int):
        raise TypeError("step_size must be an integer.")
    if trials_per_frequency <= 0:
        raise ValueError("trials_per_frequency must be positive.")
    if total_time <= 0:
        raise ValueError("total_time must be positive.")
    if pulse_height <= 0:
        raise ValueError("pulse_height must be positive.")
    if get_pulse_width() <= 0:
        raise ValueError("pulse_width must be positive.")
    if rise_time <= 0 or fall_time <= 0:
        raise ValueError("rise_time and fall_time must be positive.")
    if get_pulse_width() <= rise_time + fall_time:
        raise ValueError("pulse_width must be larger than rise_time + fall_time.")
    if phase_shift_fraction_of_pulse_width < 0:
        raise ValueError("phase_shift_fraction_of_pulse_width must be non-negative.")

    latest_allowed_base_start = (
        total_time - get_pulse_width() - fall_time - get_max_phase_shift()
    )
    if latest_allowed_base_start <= 0:
        raise ValueError(
            "The final shifted pulse would not fit inside total_time. Increase total_time, "
            "reduce num_spike_train_sets, reduce phase_shift_fraction_of_pulse_width, "
            "or reduce pulse_width/fall_time."
        )

    requested_max_spikes = int(round(max_frequency_hz * total_time))
    # Conservative packing bound: spike starts must be at least one pulse_width apart.
    max_possible_spikes = int(np.floor(latest_allowed_base_start / get_pulse_width())) + 1
    if requested_max_spikes > max_possible_spikes:
        raise ValueError(
            "The requested maximum frequency is too high for the chosen total_time, "
            "pulse_width, and phase-shift margin. Reduce max_frequency_hz or pulse_width, "
            "or increase total_time."
        )


def generate_base_spike_times_exact_rate(
    mean_frequency_hz: int,
    duration_s: float,
    width_s: float,
    max_phase_shift_s: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate the random base spike start times for st_1.

    The realised spike count is round(mean_frequency_hz * duration_s), matching
    the original stog_v2.py convention. The latest allowed start is reduced by
    max_phase_shift_s and fall_time, so that all phase-shifted copies remain
    within the simulation window.
    """
    spike_count = int(round(mean_frequency_hz * duration_s))
    if spike_count == 0:
        return np.array([], dtype=float)

    latest_start = duration_s - width_s - fall_time - max_phase_shift_s
    if latest_start <= 0:
        raise ValueError("duration_s is too short for the pulse width and phase shifts.")

    max_attempts = 10_000
    for _ in range(max_attempts):
        starts = np.sort(rng.uniform(0.0, latest_start, size=spike_count))
        if spike_count == 1 or np.all(np.diff(starts) >= width_s):
            return starts

    raise RuntimeError(
        "Could not place non-overlapping base spikes after many attempts. "
        "Try reducing max_frequency_hz or pulse_width, or increasing total_time."
    )


def apply_phase_shift(base_spike_starts: np.ndarray, st_index: int) -> np.ndarray:
    """Return the spike starts for st_index as a shifted copy of st_1."""
    return base_spike_starts + get_phase_shift(st_index)


def build_pulse_points(spike_starts: np.ndarray, duration_s: float) -> list[tuple[float, float]]:
    """Convert spike start times into a piecewise-linear voltage waveform."""
    points: list[tuple[float, float]] = [(0.0, 0.0)]

    for start in spike_starts:
        width = get_pulse_width()
        end_high = float(start + width)
        end_fall = float(end_high + fall_time)

        if end_fall > duration_s:
            raise ValueError(
                f"Pulse ending at {end_fall:.12e} s exceeds total_time={duration_s:.12e} s."
            )

        points.append((float(start), 0.0))
        points.append((float(start + rise_time), pulse_height))
        points.append((end_high, pulse_height))
        points.append((end_fall, 0.0))

    if points[-1][0] < duration_s:
        points.append((duration_s, 0.0))

    return points


def write_spike_train_pwl(output_path: Path, points: list[tuple[float, float]]) -> None:
    """Write one whitespace-separated PWL file without a header."""
    with output_path.open("w", newline="") as f:
        for time_s, voltage_v in points:
            f.write(f"{time_s:.12e} {voltage_v:.12e}\n")


def write_spike_train_csv(output_path: Path, points: list[tuple[float, float]]) -> None:
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
    rng = np.random.default_rng(random_seed)

    reset_output_directory(output_root)
    reset_output_directory(csv_output_root)

    pwl_files_written = 0
    csv_files_written = 0

    # Create all st_n folders first, matching the existing repo convention.
    for st_index in range(1, num_spike_train_sets + 1):
        (output_root / f"st_{st_index}").mkdir(parents=True, exist_ok=True)
        (csv_output_root / f"st_{st_index}").mkdir(parents=True, exist_ok=True)

    for frequency_hz in range(1, max_frequency_hz + 1, step_size):
        for trial_index in range(1, trials_per_frequency + 1):
            base_spike_starts = generate_base_spike_times_exact_rate(
                mean_frequency_hz=frequency_hz,
                duration_s=total_time,
                width_s=get_pulse_width(),
                max_phase_shift_s=get_max_phase_shift(),
                rng=rng,
            )

            for st_index in range(1, num_spike_train_sets + 1):
                st_dir = output_root / f"st_{st_index}" / f"{frequency_hz}_hz"
                csv_st_dir = csv_output_root / f"st_{st_index}" / f"{frequency_hz}_hz"
                st_dir.mkdir(parents=True, exist_ok=True)
                csv_st_dir.mkdir(parents=True, exist_ok=True)

                shifted_spike_starts = apply_phase_shift(base_spike_starts, st_index)
                points = build_pulse_points(shifted_spike_starts, total_time)

                pwl_output_path = st_dir / f"trial_{trial_index}.pwl"
                csv_output_path = csv_st_dir / f"trial_{trial_index}.csv"

                write_spike_train_pwl(pwl_output_path, points)
                pwl_files_written += 1

                write_spike_train_csv(csv_output_path, points)
                csv_files_written += 1

    print(f"PWL directory tree written to: {output_root.resolve()}")
    print(f"CSV directory tree written to: {csv_output_root.resolve()}")
    print(
        "Frequency sequence used: "
        f"1_hz, {1 + step_size}_hz, {1 + 2 * step_size}_hz, ... up to <= {max_frequency_hz}_hz"
    )
    print(
        "Phase-shift rule: st_k = st_1 shifted by "
        "(k - 1) * "
        f"{phase_shift_fraction_of_pulse_width} * pulse_width"
    )
    print(f"Maximum phase shift: {get_max_phase_shift():.12e} s")
    print(f"PWL files written: {pwl_files_written}")
    print(f"CSV files written: {csv_files_written}")


if __name__ == "__main__":
    main()
