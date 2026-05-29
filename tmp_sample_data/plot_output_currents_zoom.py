from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "output_currents.csv"
OUTPUT_FIGURE = BASE_DIR / "output_currents_plot_overlap_counted.png"

# Keep the same zoom width you chose: 0.45 to 0.46 is a 0.01 s window.
WINDOW_WIDTH_S = 0.02

# If True, the script automatically centers the 0.01 s window on the region
# with the largest number of overlapping spikes.
AUTO_CENTER_ON_OVERLAP = True

# Used only if AUTO_CENTER_ON_OVERLAP = False.
START_TIME_S = 0.28
END_TIME_S = 0.30

# Spike-detection settings.
# A spike is detected as a local minimum below this fraction of the full
# current excursion from baseline to minimum.
SPIKE_THRESHOLD_FRACTION = 0.30

# Two detected spikes are counted as overlapping if their minima are closer
# than this time separation.
OVERLAP_MAX_SEPARATION_S = 0.00035


# ---------------------------------------------------------------------
# Spike detection
# ---------------------------------------------------------------------
def detect_spikes(df: pd.DataFrame) -> pd.DataFrame:
    time = df["time_s"].to_numpy()
    current = df["current_A"].to_numpy()

    # For this data, the resting current is near the least-negative values.
    baseline_current = df["current_A"].quantile(0.95)
    minimum_current = df["current_A"].min()

    threshold_current = baseline_current - SPIKE_THRESHOLD_FRACTION * (
        baseline_current - minimum_current
    )

    raw_minima = []

    for index in range(1, len(df) - 1):
        is_local_minimum = (
            current[index] < current[index - 1]
            and current[index] <= current[index + 1]
        )
        is_large_enough_spike = current[index] < threshold_current

        if is_local_minimum and is_large_enough_spike:
            raw_minima.append((time[index], current[index]))

    if not raw_minima:
        return pd.DataFrame(columns=["time_s", "current_A"])

    # Some individual spikes produce several adjacent local minima because of
    # duplicated or near-duplicated simulator time points. Merge minima that are
    # extremely close together into one spike event.
    raw_minima.sort(key=lambda pair: pair[0])

    merged_spikes = []
    current_cluster = [raw_minima[0]]

    for point in raw_minima[1:]:
        previous_time = current_cluster[-1][0]

        if point[0] - previous_time <= 0.0002:
            current_cluster.append(point)
        else:
            # Keep the deepest minimum in the cluster.
            deepest = min(current_cluster, key=lambda pair: pair[1])
            merged_spikes.append(deepest)
            current_cluster = [point]

    deepest = min(current_cluster, key=lambda pair: pair[1])
    merged_spikes.append(deepest)

    return pd.DataFrame(merged_spikes, columns=["time_s", "current_A"])


def find_overlap_pairs(spikes: pd.DataFrame) -> pd.DataFrame:
    overlap_pairs = []

    spike_times = spikes["time_s"].to_list()

    for index in range(len(spike_times) - 1):
        first_time = spike_times[index]
        second_time = spike_times[index + 1]
        separation = second_time - first_time

        if separation <= OVERLAP_MAX_SEPARATION_S:
            overlap_pairs.append(
                {
                    "first_spike_s": first_time,
                    "second_spike_s": second_time,
                    "separation_s": separation,
                    "midpoint_s": 0.5 * (first_time + second_time),
                }
            )

    return pd.DataFrame(overlap_pairs)


def find_best_window(overlap_pairs: pd.DataFrame, df: pd.DataFrame) -> tuple[float, float]:
    if overlap_pairs.empty:
        # Fallback: use the configured window if no overlap is detected.
        return START_TIME_S, START_TIME_S + WINDOW_WIDTH_S

    data_start = df["time_s"].min()
    data_end = df["time_s"].max()

    best_start = data_start
    best_score = -1

    # Search possible 0.01 s windows in 0.0001 s increments.
    step_s = 0.0001
    number_of_steps = int((data_end - data_start - WINDOW_WIDTH_S) / step_s) + 1

    for step_index in range(number_of_steps):
        start = data_start + step_index * step_s
        end = start + WINDOW_WIDTH_S

        score = (
            (overlap_pairs["midpoint_s"] >= start)
            & (overlap_pairs["midpoint_s"] <= end)
        ).sum()

        if score > best_score:
            best_score = score
            best_start = start

    return best_start, best_start + WINDOW_WIDTH_S


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------
def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Could not find CSV file: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    required_columns = ["time_s", "current_A"]
    for column in required_columns:
        if column not in df.columns:
            raise ValueError(
                f"Missing required column: {column!r}. "
                f"Found columns: {list(df.columns)}"
            )

    spikes = detect_spikes(df)
    print(f"Total detected spikes in full CSV: {len(spikes)}")
    overlap_pairs = find_overlap_pairs(spikes)

    if AUTO_CENTER_ON_OVERLAP:
        start_time_s, end_time_s = find_best_window(overlap_pairs, df)
    else:
        start_time_s = START_TIME_S
        end_time_s = END_TIME_S

    center_time_s = 0.5 * (start_time_s + end_time_s)

    df_window = df[
        (df["time_s"] >= start_time_s)
        & (df["time_s"] <= end_time_s)
    ]

    spikes_in_window = spikes[
        (spikes["time_s"] >= start_time_s)
        & (spikes["time_s"] <= end_time_s)
    ]

    overlaps_in_window = overlap_pairs[
        (overlap_pairs["midpoint_s"] >= start_time_s)
        & (overlap_pairs["midpoint_s"] <= end_time_s)
    ]

    if df_window.empty:
        raise ValueError(
            f"No data points found between {start_time_s} s and {end_time_s} s. "
            f"The CSV time range is {df['time_s'].min()} s to {df['time_s'].max()} s."
        )

    plt.figure(figsize=(10, 6))
    plt.plot(df_window["time_s"], df_window["current_A"], linewidth=1)

    # Mark detected spike minima in the window.
    if not spikes_in_window.empty:
        plt.scatter(
            spikes_in_window["time_s"],
            spikes_in_window["current_A"],
            s=25,
            label="Detected spike minima",
        )

    # Mark overlap midpoints.
    for _, row in overlaps_in_window.iterrows():
        plt.axvline(row["midpoint_s"], linestyle="--", linewidth=0.8)

    plt.xlabel("Time (s)")
    plt.ylabel("Current (A)")
    plt.title("Output Current vs Time, Counted Spike-Overlap Region")
    plt.xlim(start_time_s, end_time_s)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.savefig(OUTPUT_FIGURE, dpi=300)
    plt.show()

    print(f"Window start: {start_time_s:.6f} s")
    print(f"Window end:   {end_time_s:.6f} s")
    print(f"Window center:{center_time_s:.6f} s")
    print(f"Rows plotted: {len(df_window)}")
    print(f"Detected spikes in window: {len(spikes_in_window)}")
    print(
        "Detected spike overlaps in window: "
        f"{len(overlaps_in_window)} "
        f"(spike minima separated by <= {OVERLAP_MAX_SEPARATION_S} s)"
    )

    if overlaps_in_window.empty:
        print("Overlap locations: none detected in this window.")
    else:
        print("Overlap locations:")
        for _, row in overlaps_in_window.iterrows():
            print(
                f"  midpoint = {row['midpoint_s']:.9f} s, "
                f"spikes at {row['first_spike_s']:.9f} s and "
                f"{row['second_spike_s']:.9f} s, "
                f"separation = {row['separation_s']:.9f} s"
            )

    print(f"Plot saved to: {OUTPUT_FIGURE}")


if __name__ == "__main__":
    main()
