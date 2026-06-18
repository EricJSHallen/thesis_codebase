import random


num_vpre_branch = 2
total_time = 1  # seconds
mean_frequency_hz = 1000
pulse_height = 1.8  # volts
pulse_width = 1e-6  # seconds
random_seed = 12345
isi = [25e-6, 10e-6, 5e-6, 3e-6, 2e-6]


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
    if mean_frequency_hz <= 0:
        raise ValueError("mean_frequency_hz must be positive.")
    if pulse_height <= 0:
        raise ValueError("pulse_height must be positive.")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be positive.")
    if pulse_width >= total_time:
        raise ValueError("pulse_width must be smaller than total_time.")


def generate_poisson_spike_times(rng: random.Random) -> list[float]:
    spike_times: list[float] = []
    time_s = 0.0
    latest_start = total_time - pulse_width

    while True:
        time_s += rng.expovariate(mean_frequency_hz)
        if time_s > latest_start:
            break
        spike_times.append(time_s)

    return spike_times


def generate_branch_spike_times() -> list[list[float]]:
    branch_spike_times = []

    for branch_index in range(num_vpre_branch):
        branch_seed = random_seed + branch_index
        rng = random.Random(branch_seed)
        spike_times = generate_poisson_spike_times(rng)
        branch_spike_times.append(spike_times)

    return branch_spike_times


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

def get_interspike_intervals(spikes: list[dict[str, float]]) -> list[float]:
    return [
        spikes[i + 1]["start"] - spikes[i]["end"]
        for i in range(len(spikes) - 1)
    ]


def find_close_adjacent_spikes(
    spikes: list[dict[str, float]],
    prior_window: float,
    posterior_window: float,
) -> tuple[list[dict], list[dict]]:
    if posterior_window >= prior_window:
        raise ValueError("posterior_window must be smaller than prior_window.")

    spikes = sorted(spikes, key=lambda spike: spike["start"])
    gaps_less_than_prior = []
    gaps_less_than_posterior = []

    for i in range(len(spikes) - 1):
        current_spike = spikes[i]
        next_spike = spikes[i + 1]
        gap = next_spike["start"] - current_spike["end"]

        gap_record = {
            "left_index": i,
            "right_index": i + 1,
            "left_spike": current_spike,
            "right_spike": next_spike,
            "gap": gap,
        }

        if gap < prior_window:
            gaps_less_than_prior.append(gap_record)

            if gap < posterior_window:
                gaps_less_than_posterior.append(gap_record)

    return gaps_less_than_prior, gaps_less_than_posterior


def sweep_isi_windows(
    spikes: list[dict[str, float]],
    formatted_interspike_intervals: list[float],
) -> list[dict]:
    sweep_results = []

    for i in range(len(formatted_interspike_intervals) - 1):
        prior = formatted_interspike_intervals[i]
        posterior = formatted_interspike_intervals[i + 1]

        gaps_less_than_prior, gaps_less_than_posterior = find_close_adjacent_spikes(
            spikes,
            prior,
            posterior,
        )

        sweep_results.append(
            {
                "run_index": i,
                "prior": prior,
                "posterior": posterior,
                "gaps_less_than_prior": gaps_less_than_prior,
                "gaps_less_than_posterior": gaps_less_than_posterior,
            }
        )

    return sweep_results


def main() -> None:
    validate_parameters()

    branch_spike_times = generate_branch_spike_times()
    spike_times = combine_spike_times(branch_spike_times)
    spikes = build_spikes(spike_times)
    formatted_interspike_intervals = format_isi(isi)

    print(f"Vpre branches generated: {num_vpre_branch}")
    for branch_index, branch_spikes in enumerate(branch_spike_times):
        print(f"Branch {branch_index} spike starts generated: {len(branch_spikes)}")
    print(f"Combined spike starts generated: {len(spike_times)}")
    print(f"Non-overlapping combined spikes analyzed: {len(spikes)}")
    print(f"Overlapping combined spikes skipped: {len(spike_times) - len(spikes)}")
    print(f"Unique interspike intervals: {len(formatted_interspike_intervals)}")

    if len(formatted_interspike_intervals) < 2:
        print("Need at least two unique interspike intervals to sweep prior/posterior windows.")
        return

    sweep_results = sweep_isi_windows(spikes, formatted_interspike_intervals)

    for result in sweep_results:
        print(
            f"Run {result['run_index']}: "
            f"prior={result['prior']:.12e}, "
            f"posterior={result['posterior']:.12e}, "
            f"gaps < prior={len(result['gaps_less_than_prior'])}, "
            f"gaps < posterior={len(result['gaps_less_than_posterior'])}"
        )


if __name__ == "__main__":
    main()
