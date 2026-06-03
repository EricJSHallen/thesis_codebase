#!/usr/bin/env python3
"""
stog_v3_strict_time_fixed.py

Spike-train output generator with deterministic non-overlap enforcement.

The original stog_v3_strict_time.py used rejection sampling: draw all spike
starts independently, sort them, and retry until every adjacent pair is far
enough apart. That becomes pathologically inefficient near dense packing even
when many valid non-overlapping layouts still exist.

This version samples in a compressed time coordinate and then expands the starts
by the required pulse spacing. Therefore every sampled train is valid on the
first attempt, provided the requested spike count is physically feasible.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterable

import numpy as np

# -----------------------------
# User variables
# -----------------------------

output_root = Path(__file__).resolve().parent / "spike_train_output"
csv_output_root = Path(__file__).resolve().parent / "spike_train_output_csv"

num_spike_train_sets = 2
max_frequency_hz = 9000
step_size = 1000
trials_per_frequency = 1
total_time = 0.1

pulse_height = 1.8
pulse_width = 1e-6
rise_time = 1e-8
fall_time = 1e-8
minimum_time_step = 1e-12

random_seed: int | None = 12345
overwrite_output_directory = True

# Use True to create a 1_hz directory first, matching the original script.
# With step_size=1000 this gives 1, 1001, 2001, ...
start_at_one_hz = True

# -----------------------------
# Pulse-width function
# -----------------------------


def get_pulse_width() -> float:
    """Return the width of each spike pulse."""
    return pulse_width


# -----------------------------
# Validation and packing geometry
# -----------------------------


def required_start_spacing(width_s: float) -> float:
    """Minimum allowed separation between adjacent pulse start times."""
    return width_s + fall_time + minimum_time_step


def valid_start_window(duration_s: float, width_s: float) -> tuple[float, float]:
    """Return inclusive earliest/latest pulse start times."""
    earliest_start = minimum_time_step
    latest_start = duration_s - width_s - fall_time
    if latest_start <= earliest_start:
        raise ValueError(
            "duration_s must be larger than pulse_width + fall_time + "
            "minimum_time_step."
        )
    return earliest_start, latest_start


def max_nonoverlapping_spike_count(duration_s: float, width_s: float) -> int:
    """Maximum number of full, non-overlapping pulses that fit in duration_s."""
    earliest_start, latest_start = valid_start_window(duration_s, width_s)
    spacing = required_start_spacing(width_s)
    return int(np.floor((latest_start - earliest_start) / spacing)) + 1


def validate_user_variables() -> None:
    if num_spike_train_sets <= 0:
        raise ValueError("num_spike_train_sets must be positive.")
    if max_frequency_hz <= 0:
        raise ValueError("max_frequency_hz must be positive.")
    if not isinstance(step_size, int) or step_size <= 0:
        raise ValueError("step_size must be a positive integer.")
    if trials_per_frequency <= 0:
        raise ValueError("trials_per_frequency must be positive.")
    if total_time <= 0:
        raise ValueError("total_time must be positive.")
    if pulse_height <= 0:
        raise ValueError("pulse_height must be positive.")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")
    if rise_time <= 0 or fall_time <= 0:
        raise ValueError("rise_time and fall_time must be positive.")
    if pulse_width <= rise_time + fall_time:
        raise ValueError("pulse_width must be larger than rise_time + fall_time.")
    if minimum_time_step <= 0:
        raise ValueError("minimum_time_step must be positive.")

    requested_max_spikes = int(round(max_frequency_hz * total_time))
    capacity = max_nonoverlapping_spike_count(total_time, get_pulse_width())
    if requested_max_spikes > capacity:
        max_feasible_frequency = capacity / total_time
        raise ValueError(
            "The requested maximum frequency is physically infeasible for the "
            "chosen total_time, pulse_width, fall_time, and minimum_time_step. "
            f"Requested {requested_max_spikes} spikes, but capacity is "
            f"{capacity} spikes, i.e. about {max_feasible_frequency:.6g} Hz "
            "for this duration."
        )


# -----------------------------
# Spike-train generation
# -----------------------------


def generate_spike_times_exact_rate(
    mean_frequency_hz: int | float,
    duration_s: float,
    width_s: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate non-overlapping spike start times.

    The realised spike count is round(mean_frequency_hz * duration_s). Instead
    of rejection sampling, this samples n sorted points in a compressed interval
    and expands them by i * required_spacing:

        y_i in [earliest, latest - (n - 1) spacing]
        t_i = y_i + i spacing

    Consequently t_{i+1} - t_i >= spacing by construction.
    """
    spike_count = int(round(float(mean_frequency_hz) * duration_s))
    if spike_count == 0:
        return np.array([], dtype=float)

    earliest_start, latest_start = valid_start_window(duration_s, width_s)
    spacing = required_start_spacing(width_s)
    compressed_latest = latest_start - (spike_count - 1) * spacing

    if compressed_latest < earliest_start:
        capacity = max_nonoverlapping_spike_count(duration_s, width_s)
        raise ValueError(
            "Cannot place the requested number of strictly non-overlapping "
            f"spikes. Requested {spike_count}; capacity is {capacity}."
        )

    compressed = np.sort(
        rng.uniform(earliest_start, compressed_latest, size=spike_count)
    )
    starts = compressed + np.arange(spike_count, dtype=float) * spacing

    # Guard against numerical roundoff at the boundary.
    starts = np.clip(starts, earliest_start, latest_start)
    assert_nonoverlapping_starts(starts, width_s, duration_s)
    return starts


def assert_nonoverlapping_starts(
    spike_starts: np.ndarray,
    width_s: float,
    duration_s: float,
) -> None:
    """Validate start ordering, pulse containment, and adjacent separation."""
    if len(spike_starts) == 0:
        return

    earliest_start, latest_start = valid_start_window(duration_s, width_s)
    spacing = required_start_spacing(width_s)

    if spike_starts[0] < earliest_start - 1e-15:
        raise AssertionError("First spike starts before the valid start window.")
    if spike_starts[-1] > latest_start + 1e-15:
        raise AssertionError("Last spike extends beyond the valid duration.")
    if len(spike_starts) > 1 and np.any(np.diff(spike_starts) < spacing - 1e-15):
        raise AssertionError("Generated spike starts overlap.")


def build_pulse_points(spike_starts: np.ndarray, duration_s: float) -> list[tuple[float, float]]:
    """Convert spike starts into strictly increasing PWL voltage points."""
    points: list[tuple[float, float]] = [(0.0, 0.0)]

    def append_strict(time_s: float, voltage_v: float) -> None:
        time_s = float(time_s)
        if time_s <= points[-1][0]:
            raise ValueError(
                f"Non-increasing timestamp generated: {time_s:.12e} <= "
                f"{points[-1][0]:.12e}."
            )
        points.append((time_s, float(voltage_v)))

    for start in spike_starts:
        width = get_pulse_width()
        start = float(start)
        rise_end = start + rise_time
        end_high = start + width
        end_fall = end_high + fall_time
        if end_fall > duration_s + 1e-15:
            raise ValueError("Generated pulse extends beyond duration_s.")

        append_strict(start, 0.0)
        append_strict(rise_end, pulse_height)
        append_strict(end_high, pulse_height)
        append_strict(end_fall, 0.0)

    if points[-1][0] < duration_s:
        append_strict(duration_s, 0.0)
    return points


def assert_strictly_increasing_time(points: list[tuple[float, float]]) -> None:
    """Raise an error if neighbouring PWL points have non-increasing time."""
    times = np.array([time for time, _ in points], dtype=float)
    if len(times) > 1 and not np.all(np.diff(times) > 0.0):
        bad_index = int(np.where(np.diff(times) <= 0.0)[0][0])
        raise ValueError(
            "Generated waveform has non-increasing time at rows "
            f"{bad_index + 1} and {bad_index + 2}: "
            f"{times[bad_index]:.12e}, {times[bad_index + 1]:.12e}"
        )


# -----------------------------
# PWL and CSV writing
# -----------------------------


def write_spike_train_pwl(output_path: Path, points: Iterable[tuple[float, float]]) -> None:
    with output_path.open("w", newline="") as f:
        for time, voltage in points:
            f.write(f"{time:.12e} {voltage:.12e}\n")


def write_spike_train_csv(output_path: Path, points: Iterable[tuple[float, float]]) -> None:
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "voltage_v"])
        for time, voltage in points:
            writer.writerow([f"{time:.12e}", f"{voltage:.12e}"])


# -----------------------------
# Output-directory reset
# -----------------------------


def reset_output_directory(path: Path) -> None:
    resolved_path = path.resolve()
    if resolved_path.exists():
        if not resolved_path.is_dir():
            raise NotADirectoryError(
                f"Output path exists but is not a directory: {resolved_path}"
            )
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


def frequency_sequence() -> range:
    start = 1 if start_at_one_hz else step_size
    return range(start, max_frequency_hz + 1, step_size)


# -----------------------------
# Main directory-tree generator
# -----------------------------


def main() -> None:
    validate_user_variables()
    rng = np.random.default_rng(random_seed)

    reset_output_directory(output_root)
    reset_output_directory(csv_output_root)

    pwl_files_written = 0
    csv_files_written = 0

    for st_index in range(1, num_spike_train_sets + 1):
        st_dir = output_root / f"st_{st_index}"
        csv_st_dir = csv_output_root / f"st_{st_index}"
        st_dir.mkdir(parents=True, exist_ok=True)
        csv_st_dir.mkdir(parents=True, exist_ok=True)

        for frequency_hz in frequency_sequence():
            frequency_dir = st_dir / f"{frequency_hz}_hz"
            csv_frequency_dir = csv_st_dir / f"{frequency_hz}_hz"
            frequency_dir.mkdir(parents=True, exist_ok=True)
            csv_frequency_dir.mkdir(parents=True, exist_ok=True)

            for trial_index in range(1, trials_per_frequency + 1):
                spike_starts = generate_spike_times_exact_rate(
                    mean_frequency_hz=frequency_hz,
                    duration_s=total_time,
                    width_s=get_pulse_width(),
                    rng=rng,
                )
                points = build_pulse_points(spike_starts, total_time)
                assert_strictly_increasing_time(points)

                pwl_output_path = frequency_dir / f"trial_{trial_index}.pwl"
                csv_output_path = csv_frequency_dir / f"trial_{trial_index}.csv"

                write_spike_train_pwl(pwl_output_path, points)
                pwl_files_written += 1
                write_spike_train_csv(csv_output_path, points)
                csv_files_written += 1

    capacity = max_nonoverlapping_spike_count(total_time, get_pulse_width())
    print(f"PWL directory tree written to: {output_root.resolve()}")
    print(f"CSV directory tree written to: {csv_output_root.resolve()}")
    print(f"PWL files written: {pwl_files_written}")
    print(f"CSV files written: {csv_files_written}")
    print(f"Non-overlap capacity for current settings: {capacity} spikes")
    print(f"Equivalent duration-limited maximum frequency: {capacity / total_time:.6g} Hz")
    print(
        "For exact integer-Hz realised means, keep total_time = 1.0 s. "
        "For other durations, realised frequency is round(f_hz * total_time) / total_time."
    )


if __name__ == "__main__":
    main()
