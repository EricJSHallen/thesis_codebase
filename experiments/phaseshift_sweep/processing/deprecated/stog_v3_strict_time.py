import csv
import random
from pathlib import Path


output_csv = Path(__file__).resolve().with_name("spike_train.csv")


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


def write_csv(points: list[tuple[float, float]]) -> None:
    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "voltage_v"])
        for time_s, voltage_v in points:
            writer.writerow([f"{time_s:.12e}", f"{voltage_v:.12e}"])


def main() -> None:
    validate_parameters()
    rng = random.Random(random_seed)
    spike_times = generate_poisson_spike_times(rng)
    points = build_voltage_points(spike_times)
    write_csv(points)

    written_spikes = (len(points) - 2) // 2
    skipped_spikes = len(spike_times) - written_spikes
    print(f"CSV written to: {output_csv}")
    print(f"Poisson spike starts generated: {len(spike_times)}")
    print(f"Spikes written: {written_spikes}")
    print(f"Overlapping spikes skipped: {skipped_spikes}")


if __name__ == "__main__":
    main()
