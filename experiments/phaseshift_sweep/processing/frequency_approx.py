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