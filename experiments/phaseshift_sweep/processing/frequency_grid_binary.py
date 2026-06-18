import csv
from pathlib import Path
import random


total_time = 1  # seconds
pulse_width = 1e-6  # seconds
random_seed = 12345
num_runs = 10
success_threshold = 9
isi = [25e-6, 10e-6, 5e-6, 3e-6, 2e-6]
frequency_start_hz = 0
frequency_step_hz = 5
max_frequency_hz = 500
output_csv = Path(__file__).resolve().with_name("frequency_grid_binary.csv")


def format_isi(isi_unformatted: list[float]) -> list[float]:
    return sorted(set(isi_unformatted), reverse=True)


def validate_parameters() -> None:
    if total_time <= 0:
        raise ValueError("total_time must be positive.")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")
    if pulse_width >= total_time:
        raise ValueError("pulse_width must be smaller than total_time.")
    if not isinstance(num_runs, int):
        raise TypeError("num_runs must be an integer.")
    if num_runs <= 0:
        raise ValueError("num_runs must be positive.")
    if not isinstance(success_threshold, int):
        raise TypeError("success_threshold must be an integer.")
    if success_threshold <= 0:
        raise ValueError("success_threshold must be positive.")
    if success_threshold > num_runs:
        raise ValueError("success_threshold must be less than or equal to num_runs.")
    if not isi:
        raise ValueError("isi must contain at least one value.")
    if any(isi_value <= 0 for isi_value in isi):
        raise ValueError("isi must contain only positive values.")
    if not isinstance(frequency_start_hz, int):
        raise TypeError("frequency_start_hz must be an integer.")
    if not isinstance(frequency_step_hz, int):
        raise TypeError("frequency_step_hz must be an integer.")
    if not isinstance(max_frequency_hz, int):
        raise TypeError("max_frequency_hz must be an integer.")
    if frequency_start_hz < 0:
        raise ValueError("frequency_start_hz must be non-negative.")
    if frequency_step_hz <= 0:
        raise ValueError("frequency_step_hz must be positive.")
    if max_frequency_hz < frequency_start_hz:
        raise ValueError("max_frequency_hz must be greater than or equal to frequency_start_hz.")


def get_frequency_values() -> list[int]:
    return list(range(frequency_start_hz, max_frequency_hz + 1, frequency_step_hz))


def get_pair_seed(
    mean_frequency_1_hz: int,
    mean_frequency_2_hz: int,
    branch_index: int,
    run_index: int,
) -> int:
    return (
        random_seed
        + mean_frequency_1_hz * 1_000_003
        + mean_frequency_2_hz * 10_007
        + branch_index * 101
        + run_index * 1_000_000_007
    )


def generate_poisson_spike_times(
    rng: random.Random,
    frequency_hz: int,
) -> list[float]:
    if frequency_hz <= 0:
        return []

    spike_times: list[float] = []
    time_s = 0.0
    latest_start = total_time - pulse_width

    while True:
        time_s += rng.expovariate(frequency_hz)
        if time_s > latest_start:
            break
        spike_times.append(time_s)

    return spike_times


def generate_spike_times_for_frequency_pair(
    mean_frequency_1_hz: int,
    mean_frequency_2_hz: int,
    run_index: int,
) -> list[float]:
    rng_1 = random.Random(get_pair_seed(mean_frequency_1_hz, mean_frequency_2_hz, 0, run_index))
    rng_2 = random.Random(get_pair_seed(mean_frequency_1_hz, mean_frequency_2_hz, 1, run_index))
    spike_times_1 = generate_poisson_spike_times(rng_1, mean_frequency_1_hz)
    spike_times_2 = generate_poisson_spike_times(rng_2, mean_frequency_2_hz)
    return sorted(spike_times_1 + spike_times_2)


def build_spikes(spike_times: list[float]) -> list[tuple[float, float]]:
    spikes: list[tuple[float, float]] = []
    last_pulse_end = 0.0

    for start in spike_times:
        start = float(start)
        end = start + pulse_width

        if start < last_pulse_end:
            continue

        spikes.append((start, end))
        last_pulse_end = end

    return spikes


def get_adjacent_gaps(spikes: list[tuple[float, float]]) -> list[float]:
    return [
        spikes[i + 1][0] - spikes[i][1]
        for i in range(len(spikes) - 1)
    ]


def isi_column_name(isi_value: float) -> str:
    isi_us = isi_value * 1e6
    if isi_us.is_integer():
        return f"isi_{int(isi_us)}us"
    return f"isi_{isi_value:.6e}s"


def get_binary_values_for_frequency_pair(
    mean_frequency_1_hz: int,
    mean_frequency_2_hz: int,
    isi_values: list[float],
    run_index: int,
) -> list[int]:
    combined_spike_times = generate_spike_times_for_frequency_pair(
        mean_frequency_1_hz,
        mean_frequency_2_hz,
        run_index,
    )
    spikes = build_spikes(combined_spike_times)
    gaps = get_adjacent_gaps(spikes)

    return [int(any(gap < isi_value for gap in gaps)) for isi_value in isi_values]


def get_aggregated_binary_values_for_frequency_pair(
    mean_frequency_1_hz: int,
    mean_frequency_2_hz: int,
    isi_values: list[float],
) -> list[int]:
    success_counts = [0] * len(isi_values)

    for run_index in range(num_runs):
        binary_values = get_binary_values_for_frequency_pair(
            mean_frequency_1_hz,
            mean_frequency_2_hz,
            isi_values,
            run_index,
        )
        success_counts = [
            success_count + binary_value
            for success_count, binary_value in zip(success_counts, binary_values)
        ]

    return [int(success_count >= success_threshold) for success_count in success_counts]


def write_binary_grid_csv() -> int:
    frequency_values = get_frequency_values()
    isi_values = format_isi(isi)
    rows_written = 0

    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["mean_frequency_1_hz", "mean_frequency_2_hz"]
            + [isi_column_name(isi_value) for isi_value in isi_values]
        )

        for mean_frequency_1_hz in frequency_values:
            for mean_frequency_2_hz in frequency_values:
                binary_values = get_aggregated_binary_values_for_frequency_pair(
                    mean_frequency_1_hz,
                    mean_frequency_2_hz,
                    isi_values,
                )
                writer.writerow(
                    [mean_frequency_1_hz, mean_frequency_2_hz, *binary_values]
                )
                rows_written += 1

    return rows_written


def main() -> None:
    validate_parameters()
    rows_written = write_binary_grid_csv()

    print(
        f"Frequency grid: {frequency_start_hz} Hz to {max_frequency_hz} Hz "
        f"by {frequency_step_hz} Hz"
    )
    print(f"Runs per grid point: {num_runs}")
    print(f"Success threshold: {success_threshold}/{num_runs}")
    print(f"Rows written: {rows_written}")
    print(f"CSV written to: {output_csv}")


if __name__ == "__main__":
    main()
