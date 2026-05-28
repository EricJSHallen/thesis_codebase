import csv
import shutil
from pathlib import Path

import numpy as np

#filename stog == spiketrain output generator

# -----------------------------
# User variables
# -----------------------------


#need to modify this code to do every 5 frequencies.

output_root = Path(__file__).resolve().parent / "spike_train_output"
csv_output_root = Path(__file__).resolve().parent / "spike_train_output_csv"

num_spike_train_sets = 2  # Creates st_1, st_2, ..., st_n
max_frequency_hz = 9000         # Highest frequency directory to create, e.g. up to 600_hz
step_size = 500               # Frequency step size: 1 -> 1,2,3,...; 2 -> 1,3,5,...; 3 -> 1,4,7,...
trials_per_frequency = 1 # Creates trial_1.pwl, ..., trial_j.pwl

total_time = 0.1              # seconds; use 1.0 s if you want exactly i spikes for i Hz
pulse_height = 1.8            # volts
pulse_width = 1e-6          # seconds; width of each spike pulse

rise_time = 1e-8              # seconds; finite rising edge for simulator-friendly pulses
fall_time = 1e-8              # seconds; finite falling edge for simulator-friendly pulses

random_seed = 12345            # Set to an integer, e.g. 12345, for reproducible output
overwrite_output_directory = True  # If True, delete and recreate output_root on every run

# Minimum gap used to make the written PWL/CSV timestamps strictly increasing.
# This is also safely above the rounding resolution used by the .12e output format.
minimum_time_step = 1e-12


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

    if minimum_time_step <= 0:
        raise ValueError("minimum_time_step must be positive.")

    # A complete emitted pulse occupies rise + high + fall points up to:
    #     start + pulse_width + fall_time
    # Consecutive pulse starts therefore need at least pulse_width + fall_time
    # of separation. The small extra minimum_time_step prevents equal timestamps
    # after file formatting and gives the waveform a strictly increasing time axis.
    effective_pulse_duration = pulse_width + fall_time + minimum_time_step
    max_possible_spikes = int(np.floor(total_time / effective_pulse_duration))
    requested_max_spikes = int(round(max_frequency_hz * total_time))

    if requested_max_spikes > max_possible_spikes:
        raise ValueError(
            "The requested maximum frequency is too high for the chosen total_time, "
            "pulse_width, fall_time, and minimum_time_step. Reduce max_frequency_hz, "
            "pulse_width, or fall_time, or increase total_time."
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
    sorted. A rejection step prevents overlap between the complete emitted
    pulses, including the falling edge. The first possible spike is offset by
    minimum_time_step so the initial baseline point at t = 0 is not duplicated.
    """
    spike_count = int(round(mean_frequency_hz * duration_s))

    if spike_count == 0:
        return np.array([], dtype=float)

    # The generated PWL points for a pulse extend from start to
    # start + width_s + fall_time. Starts must be separated by this amount,
    # plus a tiny guard interval, to keep output timestamps strictly increasing.
    required_start_spacing = width_s + fall_time + minimum_time_step
    earliest_start = minimum_time_step
    latest_start = duration_s - width_s - fall_time

    if latest_start <= earliest_start:
        raise ValueError(
            "duration_s must be larger than width_s + fall_time + minimum_time_step."
        )

    if spike_count > 1:
        available_span = latest_start - earliest_start
        minimum_required_span = (spike_count - 1) * required_start_spacing
        if minimum_required_span > available_span:
            raise ValueError(
                "Cannot place the requested number of strictly non-overlapping spikes. "
                "Reduce frequency, pulse_width, or fall_time, or increase total_time."
            )

    max_attempts = 10_000

    for _ in range(max_attempts):
        starts = np.sort(rng.uniform(earliest_start, latest_start, size=spike_count))

        if spike_count == 1 or np.all(np.diff(starts) >= required_start_spacing):
            return starts

    raise RuntimeError(
        "Could not place strictly non-overlapping spikes after many attempts. "
        "Try reducing max_frequency_hz, pulse_width, or fall_time, or increasing total_time."
    )


def build_pulse_points(spike_starts: np.ndarray, duration_s: float) -> list[tuple[float, float]]:
    """
    Convert spike start times into a piecewise-linear voltage signal.

    Each row in the output PWL file represents a point in a PWL waveform:

        time_s, voltage_v

    The returned time values are guaranteed to be strictly increasing.
    """
    points: list[tuple[float, float]] = [(0.0, 0.0)]

    def append_strict(time_s: float, voltage_v: float) -> None:
        """Append a PWL point only if it preserves strictly increasing time."""
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

        if end_fall > duration_s:
            continue

        append_strict(start, 0.0)
        append_strict(rise_end, pulse_height)
        append_strict(end_high, pulse_height)
        append_strict(end_fall, 0.0)

    if points[-1][0] < duration_s:
        append_strict(duration_s, 0.0)

    return points


def assert_strictly_increasing_time(points: list[tuple[float, float]]) -> None:
    """Raise an error if any neighbouring PWL points have non-increasing time."""
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


def write_spike_train_csv(
    output_path: Path,
    points: list[tuple[float, float]],
    spike_count: int,
    requested_frequency_hz: int,
) -> None:
    """
    Write one spike-train CSV file.

    The CSV file contains the same PWL points as the sibling .pwl file,
    but stores them as comma-separated values with a header row.
    """
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "voltage_v"])
        for time, voltage in points:
            writer.writerow([f"{time:.12e}", f"{voltage:.12e}"])



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
    reset_output_directory(csv_output_root)

    pwl_files_written = 0
    csv_files_written = 0

    for st_index in range(1, num_spike_train_sets + 1):
        st_dir = output_root / f"st_{st_index}"
        csv_st_dir = csv_output_root / f"st_{st_index}"

        st_dir.mkdir(parents=True, exist_ok=True)
        csv_st_dir.mkdir(parents=True, exist_ok=True)

        for frequency_hz in range(1, max_frequency_hz + 1, step_size):
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

                write_spike_train_pwl(
                    output_path=pwl_output_path,
                    points=points,
                    spike_count=len(spike_starts),
                    requested_frequency_hz=frequency_hz,
                )
                pwl_files_written += 1

                write_spike_train_csv(
                    output_path=csv_output_path,
                    points=points,
                    spike_count=len(spike_starts),
                    requested_frequency_hz=frequency_hz,
                )
                csv_files_written += 1

    print(f"PWL directory tree written to: {output_root.resolve()}")
    print(f"CSV directory tree written to: {csv_output_root.resolve()}")
    print(f"Frequency sequence used: 1_hz, {1 + step_size}_hz, {1 + 2 * step_size}_hz, ... up to <= {max_frequency_hz}_hz")
    print(f"PWL files written: {pwl_files_written}")
    print(f"CSV files written: {csv_files_written}")
    print(
        "For exact integer-Hz realised means, keep total_time = 1.0 s. "
        "For other durations, realised frequency is round(i_hz * total_time) / total_time."
    )


if __name__ == "__main__":
    main()
