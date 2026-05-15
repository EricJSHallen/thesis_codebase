import csv
import shutil
from pathlib import Path

import numpy as np

#filename sdgo == spike train generator overwrite

# -----------------------------
# User variables
# -----------------------------


#need to modify this code to do every 5 frequencies.

output_root = Path(__file__).resolve().parent / "spike_train_output"

num_spike_train_sets = 2      # Creates st_1, st_2, ..., st_n
max_frequency_hz = 600         # Highest frequency directory to create, e.g. up to 600_hz
step_size = 40                 # Frequency step size: 1 -> 1,2,3,...; 2 -> 1,3,5,...; 3 -> 1,4,7,...
trials_per_frequency = 1       # Creates trial_1.pwl, ..., trial_j.pwl

total_time = 1.0              # seconds; use 1.0 s if you want exactly i spikes for i Hz
pulse_height = 1.8            # volts
pulse_width = 10e-6          # seconds; width of each spike pulse

rise_time = 1e-8              # seconds; finite rising edge for simulator-friendly pulses
fall_time = 1e-8              # seconds; finite falling edge for simulator-friendly pulses

random_seed = None            # Set to an integer, e.g. 12345, for reproducible output
overwrite_output_directory = True  # If True, delete and recreate output_root on every run


# -----------------------------
# Pulse-width function
# -----------------------------

def get_pulse_width() -> float:
    """
    Replace this later with your own pulse-width function if desired.

    The generator uses this value for every spike in the output PWL files.
    """
    return pulse_width


# -----------------------------
# Validation
# -----------------------------

def validate_user_variables() -> None:
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

    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")

    if rise_time <= 0 or fall_time <= 0:
        raise ValueError("rise_time and fall_time must be positive.")

    if pulse_width <= rise_time + fall_time:
        raise ValueError("pulse_width must be larger than rise_time + fall_time.")

    max_possible_spikes = int(np.floor(total_time / pulse_width))
    requested_max_spikes = int(round(max_frequency_hz * total_time))

    if requested_max_spikes > max_possible_spikes:
        raise ValueError(
            "The requested maximum frequency is too high for the chosen total_time "
            "and pulse_width. Reduce max_frequency_hz or pulse_width, or increase total_time."
        )


# -----------------------------
# Spike-train generation
# -----------------------------

def generate_spike_times_exact_rate(
    mean_frequency_hz: int,
    duration_s: float,
    width_s: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate random spike start times whose realised mean frequency is exactly
    mean_frequency_hz when duration_s = 1.0.

    More generally, the realised mean frequency is:

        round(mean_frequency_hz * duration_s) / duration_s

    For exact integer-Hz output, keep total_time = 1.0 s.

    The spike times are uniformly distributed over the valid interval and then
    sorted. A simple rejection step prevents pulse overlap.
    """
    spike_count = int(round(mean_frequency_hz * duration_s))

    if spike_count == 0:
        return np.array([], dtype=float)

    latest_start = duration_s - width_s
    if latest_start <= 0:
        raise ValueError("duration_s must be larger than width_s.")

    max_attempts = 10_000

    for _ in range(max_attempts):
        starts = np.sort(rng.uniform(0.0, latest_start, size=spike_count))

        if spike_count == 1 or np.all(np.diff(starts) >= width_s):
            return starts

    raise RuntimeError(
        "Could not place non-overlapping spikes after many attempts. "
        "Try reducing max_frequency_hz or pulse_width, or increasing total_time."
    )


def build_pulse_points(spike_starts: np.ndarray, duration_s: float) -> list[tuple[float, float]]:
    """
    Convert spike start times into a piecewise-linear voltage signal.

    Each row in the output PWL file represents a point in a PWL waveform:

        time_s, voltage_v
    """
    points: list[tuple[float, float]] = [(0.0, 0.0)]

    for start in spike_starts:
        width = get_pulse_width()
        end_high = start + width
        end_fall = end_high + fall_time

        if end_fall > duration_s:
            continue

        points.append((float(start), 0.0))
        points.append((float(start + rise_time), pulse_height))
        points.append((float(end_high), pulse_height))
        points.append((float(end_fall), 0.0))

    if points[-1][0] < duration_s:
        points.append((duration_s, 0.0))

    return points


# -----------------------------
# PWL writing
# -----------------------------

def write_spike_train_pwl(
    output_path: Path,
    points: list[tuple[float, float]],
    spike_count: int,
    requested_frequency_hz: int,
) -> None:
    """
    Write one spike-train PWL file.

    The output file contains only whitespace-separated numeric PWL points,
    with no metadata lines and no header row.
    """
    with output_path.open("w", newline="") as f:
        for time, voltage in points:
            f.write(f"{time:.12e} {voltage:.12e}\n")



# -----------------------------
# Output-directory reset
# -----------------------------

def reset_output_directory(path: Path) -> None:
    """
    Completely remove the old output directory and recreate it empty.

    Using Path(__file__).resolve().parent above makes the output location
    independent of the terminal's current working directory. The generated
    spike_train_output folder will always sit next to this Python script.
    """
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


# -----------------------------
# Main directory-tree generator
# -----------------------------

def main() -> None:
    validate_user_variables()

    rng = np.random.default_rng(random_seed)

    reset_output_directory(output_root)

    files_written = 0

    for st_index in range(1, num_spike_train_sets + 1):
        st_dir = output_root / f"st_{st_index}"
        st_dir.mkdir(parents=True, exist_ok=True)

        for frequency_hz in range(1, max_frequency_hz + 1, step_size):
            frequency_dir = st_dir / f"{frequency_hz}_hz"
            frequency_dir.mkdir(parents=True, exist_ok=True)

            for trial_index in range(1, trials_per_frequency + 1):
                spike_starts = generate_spike_times_exact_rate(
                    mean_frequency_hz=frequency_hz,
                    duration_s=total_time,
                    width_s=get_pulse_width(),
                    rng=rng,
                )

                points = build_pulse_points(spike_starts, total_time)
                output_path = frequency_dir / f"trial_{trial_index}.pwl"

                write_spike_train_pwl(
                    output_path=output_path,
                    points=points,
                    spike_count=len(spike_starts),
                    requested_frequency_hz=frequency_hz,
                )

                files_written += 1

    print(f"Directory tree written to: {output_root.resolve()}")
    print(f"Frequency sequence used: 1_hz, {1 + step_size}_hz, {1 + 2 * step_size}_hz, ... up to <= {max_frequency_hz}_hz")
    print(f"PWL files written: {files_written}")
    print(
        "For exact integer-Hz realised means, keep total_time = 1.0 s. "
        "For other durations, realised frequency is round(i_hz * total_time) / total_time."
    )


if __name__ == "__main__":
    main()
