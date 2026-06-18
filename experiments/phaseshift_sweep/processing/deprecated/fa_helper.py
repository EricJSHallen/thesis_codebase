import csv
from itertools import product
from pathlib import Path
import random


num_vpre_branch = 2
total_time = 1  # seconds
pulse_height = 1.8  # volts
pulse_width = 1e-6  # seconds
random_seed = 12345
isi = [25e-6, 10e-6, 5e-6, 3e-6, 2e-6]
frequency_start_hz = 0
frequency_step_hz = 20
max_frequency_hz = 1000
output_csv = Path(__file__).resolve().with_name("frequency_grid_matches.csv")


def format_isi(isi_unformatted: list[float]) -> list[float]:
    """Convert repeated ISI values into a sorted unique vector."""
    formatted_isi = sorted(set(isi_unformatted), reverse=True)
    return formatted_isi


def validate_parameters() -> None:
    if not isinstance(num_vpre_branch, int):
        raise TypeError("num_vpre_branch must be an integer.")
    if num_vpre_branch <= 0:
        raise ValueError("num_vpre_branch must be positive.")
    if total_time <= 0:
        raise ValueError("total_time must be positive.")
    if pulse_height <= 0:
        raise ValueError("pulse_height must be positive.")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")
    if pulse_width >= total_time:
        raise ValueError("pulse_width must be smaller than total_time.")
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


def generate_poisson_spike_times(
    rng: random.Random,
    frequency_hz: float,
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


def generate_branch_spike_times(
    branch_frequencies_hz: tuple[int, ...],
) -> list[list[float]]:
    if len(branch_frequencies_hz) != num_vpre_branch:
        raise ValueError("branch_frequencies_hz must match num_vpre_branch.")

    branch_spike_times = []

    for branch_index, frequency_hz in enumerate(branch_frequencies_hz):
        branch_seed = random_seed + branch_index
        rng = random.Random(branch_seed)
        spike_times = generate_poisson_spike_times(rng, frequency_hz)
        branch_spike_times.append(spike_times)

    return branch_spike_times


def build_combined_spikes_for_frequency_combo(
    branch_frequencies_hz: tuple[int, ...],
) -> tuple[list[list[float]], list[float], list[dict[str, float]]]:
    branch_spike_times = generate_branch_spike_times(branch_frequencies_hz)
    spike_times = combine_spike_times(branch_spike_times)
    spikes = build_spikes(spike_times)
    return branch_spike_times, spike_times, spikes


def get_frequency_values() -> list[int]:
    return list(range(frequency_start_hz, max_frequency_hz + 1, frequency_step_hz))


def generate_frequency_grid():
    return product(get_frequency_values(), repeat=num_vpre_branch)


def combine_spike_times(branch_spike_times: list[list[float]]) -> list[float]:
    combined_spike_times = []

    for spike_times in branch_spike_times:
        combined_spike_times.extend(spike_times)

    return sorted(combined_spike_times)


def build_spikes(spike_times: list[float]) -> list[dict[str, float]]:
    spikes: list[dict[str, float]] = []
    last_pulse_end = 0.0

    for start in spike_times:
        start = float(start)
        end = start + pulse_width

        if start < last_pulse_end:
            continue

        spikes.append({"start": start, "end": end})
        last_pulse_end = end

    return spikes

def get_adjacent_gap_records(spikes: list[dict[str, float]]) -> list[dict]:
    gap_records = []

    for i in range(len(spikes) - 1):
        current_spike = spikes[i]
        next_spike = spikes[i + 1]
        gap_records.append(
            {
                "left_index": i,
                "right_index": i + 1,
                "left_spike": current_spike,
                "right_spike": next_spike,
                "gap": next_spike["start"] - current_spike["end"],
            }
        )

    return gap_records


def sweep_frequency_grid_for_priors(priors: list[float]) -> list[dict]:
    grid_results = []

    for branch_frequencies_hz in generate_frequency_grid():
        _, _, spikes = build_combined_spikes_for_frequency_combo(branch_frequencies_hz)
        gap_records = get_adjacent_gap_records(spikes)

        for prior in priors:
            gap_less_than_prior = any(record["gap"] < prior for record in gap_records)
            grid_results.append(
                {
                    "prior": prior,
                    "branch_frequencies_hz": branch_frequencies_hz,
                    "gap_less_than_prior": gap_less_than_prior,
                }
            )

    return grid_results


def write_frequency_grid_matches_csv(
    grid_results: list[dict],
) -> None:
    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["prior_s"]
            + [
                f"vpre_{branch_index}_frequency_hz"
                for branch_index in range(num_vpre_branch)
            ]
            + ["gap_less_than_prior"]
        )

        for record in grid_results:
            writer.writerow(
                [
                    f"{record['prior']:.12e}",
                    *record["branch_frequencies_hz"],
                    int(record["gap_less_than_prior"]),
                ]
            )


def main() -> None:
    validate_parameters()

    priors = format_isi(isi)
    grid_results = sweep_frequency_grid_for_priors(priors)
    write_frequency_grid_matches_csv(grid_results)
    frequency_values = get_frequency_values()
    grid_points_checked = len(frequency_values) ** num_vpre_branch

    print(f"Vpre branches generated: {num_vpre_branch}")
    print(
        f"Frequency grid: {frequency_start_hz} Hz to {max_frequency_hz} Hz "
        f"by {frequency_step_hz} Hz"
    )
    print(f"Grid points checked: {grid_points_checked}")
    print(f"Configured priors: {', '.join(f'{prior:.12e}' for prior in priors)}")
    print(f"CSV written to: {output_csv}")

    for prior in priors:
        matching_count = sum(
            1
            for record in grid_results
            if record["prior"] == prior and record["gap_less_than_prior"]
        )
        print(
            f"Prior {prior:.12e}: "
            f"{matching_count} matching frequency combinations out of {grid_points_checked}"
        )


if __name__ == "__main__":
    main()
