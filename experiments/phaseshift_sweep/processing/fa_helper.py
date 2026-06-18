import random


num_vpre_branch = 2
total_time = 1  # seconds
pulse_height = 1.8  # volts
pulse_width = 1e-6  # seconds
random_seed = 12345
isi = [25e-6, 10e-6, 5e-6, 3e-6, 2e-6]
frequency_start_hz = 0
frequency_step_hz = 5
max_frequency_hz = 10000


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


def generate_branch_spike_times(frequency_hz: float) -> list[list[float]]:
    branch_spike_times = []

    for branch_index in range(num_vpre_branch):
        branch_seed = random_seed + branch_index
        rng = random.Random(branch_seed)
        spike_times = generate_poisson_spike_times(rng, frequency_hz)
        branch_spike_times.append(spike_times)

    return branch_spike_times


def build_combined_spikes_for_frequency(
    frequency_hz: float,
) -> tuple[list[list[float]], list[float], list[dict[str, float]]]:
    branch_spike_times = generate_branch_spike_times(frequency_hz)
    spike_times = combine_spike_times(branch_spike_times)
    spikes = build_spikes(spike_times)
    return branch_spike_times, spike_times, spikes


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


def sweep_frequency_for_priors(priors: list[float]) -> list[dict]:
    results_by_prior = {prior: None for prior in priors}
    frequency_hz = frequency_start_hz

    while frequency_hz <= max_frequency_hz:
        branch_spike_times, spike_times, spikes = build_combined_spikes_for_frequency(
            frequency_hz
        )
        gap_records = get_adjacent_gap_records(spikes)

        for prior in priors:
            if results_by_prior[prior] is not None:
                continue

            gaps_less_than_prior = [
                record for record in gap_records if record["gap"] < prior
            ]

            if gaps_less_than_prior:
                results_by_prior[prior] = {
                    "prior": prior,
                    "frequency_hz": frequency_hz,
                    "branch_spike_times": branch_spike_times,
                    "spike_times": spike_times,
                    "spikes": spikes,
                    "gaps_less_than_prior": gaps_less_than_prior,
                }

        if all(result is not None for result in results_by_prior.values()):
            break

        frequency_hz += frequency_step_hz

    sweep_results = []
    for prior in priors:
        result = results_by_prior[prior]
        if result is None:
            sweep_results.append(
                {
                    "prior": prior,
                    "frequency_hz": None,
                    "branch_spike_times": [],
                    "spike_times": [],
                    "spikes": [],
                    "gaps_less_than_prior": [],
                }
            )
        else:
            sweep_results.append(result)

    return sweep_results


def main() -> None:
    validate_parameters()

    priors = format_isi(isi)
    sweep_results = sweep_frequency_for_priors(priors)

    print(f"Vpre branches generated: {num_vpre_branch}")
    print(
        f"Frequency sweep: {frequency_start_hz} Hz to {max_frequency_hz} Hz "
        f"by {frequency_step_hz} Hz"
    )
    print(f"Configured priors: {', '.join(f'{prior:.12e}' for prior in priors)}")

    for result in sweep_results:
        prior = result["prior"]
        frequency_hz = result["frequency_hz"]

        print(f"\nPrior {prior:.12e}:")
        if frequency_hz is None:
            print(f"No matching frequency found up to {max_frequency_hz} Hz")
            continue

        branch_spike_times = result["branch_spike_times"]
        spike_times = result["spike_times"]
        spikes = result["spikes"]
        print(f"First matching frequency: {frequency_hz} Hz")
        for branch_index, branch_spikes in enumerate(branch_spike_times):
            print(f"Branch {branch_index} spike starts generated: {len(branch_spikes)}")
        print(f"Combined spike starts generated: {len(spike_times)}")
        print(f"Non-overlapping combined spikes analyzed: {len(spikes)}")
        print(f"Overlapping combined spikes skipped: {len(spike_times) - len(spikes)}")
        print(f"Gaps < prior: {len(result['gaps_less_than_prior'])}")


if __name__ == "__main__":
    main()
