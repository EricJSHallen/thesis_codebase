import csv
import random
from pathlib import Path


#function that takes all ISIs and converts them into vector

def format_isi(isi_unformatted):
    formatted_isi = sorted(set(isi_unformatted), reverse=True)
    return formatted_isi




num_vpre_branch = 2
total_time = 0.1  # seconds
mean_frequency_hz = 9000
pulse_height = 1.8  # volts
pulse_width = 1e-6  # seconds
random_seed = 12345



def validate_parameters() -> None:
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


def build_voltage_points(spike_times: list[float]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = [(0.0, 0.0)]
    last_pulse_end = 0.0

    for start in spike_times:
        start = float(start)
        end = start + pulse_width

        if start < last_pulse_end:
            continue

        points.append((start, pulse_height))
        points.append((end, 0.0))
        last_pulse_end = end

    if points[-1][0] < total_time:
        points.append((total_time, 0.0))

    return points




def detect_spikes(times, voltages, threshold):
    spikes = []

    inside_spike = False
    current_start = None

    for i in range(len(times)):
        time = times[i]
        voltage = voltages[i]

        is_high = voltage >= threshold

        if is_high and not inside_spike:
            # We have entered a spike.
            current_start = time
            inside_spike = True

        elif not is_high and inside_spike:
            # We have left a spike.
            current_end = times[i - 1]

            spike = {"start": current_start,"end": current_end}

            spikes.append(spike)

            inside_spike = False
            current_start = None

    # Edge case: the data ends while still inside a spike.
    if inside_spike:
        current_end = times[-1]

        spike = {"start": current_start,"end": current_end}

        spikes.append(spike)

    return spikes


def find_close_adjacent_spikes(spikes, prior, posterior):
   
    if posterior >= prior:
        raise ValueError("This algorithm assumes posterior < prior.")

    # Make sure spikes are sorted by start time.
    spikes = sorted(spikes, key=lambda spike: spike["start"])

    gaps_less_than_prior = []
    gaps_less_than_posterior = []

    for i in range(len(spikes) - 1):
        current_spike = spikes[i]
        next_spike = spikes[i + 1]

        # End-to-start separation.
        gap = next_spike["start"] - current_spike["end"]

        gap_record = {
            "left_index": i,
            "right_index": i + 1,
            "left_spike": current_spike,
            "right_spike": next_spike,
            "gap": gap
        }

        if gap < prior:
            gaps_less_than_prior.append(gap_record)

            if gap < posterior:
                gaps_less_than_posterior.append(gap_record)

    return gaps_less_than_prior, gaps_less_than_posterior


def main():
    filename = "voltage_data.csv"

    threshold = 0.9

    # Example separation thresholds.
    prior = 0.010
    posterior = 0.005

    times, voltages = read_voltage_csv(filename)

    spikes = detect_spikes(times, voltages, threshold)

    gaps_less_than_a, gaps_less_than_b = find_close_adjacent_spikes(spikes,prior,posterior)

    print(f"Number of detected spikes: {len(spikes)}")
    print(f"Number of adjacent gaps less than a = {prior}: {len(gaps_less_than_a)}")
    print(f"Number of adjacent gaps less than b = {posterior}: {len(gaps_less_than_b)}")

    print("\nGaps less than a:")
    for record in gaps_less_than_a:
        print(record)

    print("\nGaps less than b:")
    for record in gaps_less_than_b:
        print(record)


if __name__ == "__main__":
    main()