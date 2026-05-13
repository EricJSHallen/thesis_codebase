from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONDENSED_DATA_DIR = BASE_DIR / "condensed_data"

COMBINATION_NAME = "st1_1hz_st2_1hz"
TRIAL_NAME = "trial_1.csv"

CSV_PATH = CONDENSED_DATA_DIR / COMBINATION_NAME / TRIAL_NAME

SAVE_FIGURE = True
SHOW_FIGURE = True

FIGURE_OUTPUT_DIR = BASE_DIR / "figures"

ZOOM_PADDING_S = 0.00005


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

def load_trial_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find CSV file: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = ["time_s", "i_I172_Iout_A", "i_I56_Iout_A"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}\n"
            f"Available columns: {list(df.columns)}"
        )

    return df.sort_values("time_s").reset_index(drop=True)


# ---------------------------------------------------------------------
# Spike-overlap detection
# ---------------------------------------------------------------------

def calculate_thresholds(df: pd.DataFrame) -> tuple[float, float]:
    max_i172 = df["i_I172_Iout_A"].max()
    max_i56 = df["i_I56_Iout_A"].max()

    min_i172 = df["i_I172_Iout_A"].min()
    min_i56 = df["i_I56_Iout_A"].min()

    max_sum = (max_i172 + max_i56) / 2
    min_sum = (min_i172 + min_i56) / 2

    return min_sum, max_sum


def find_first_spike_overlap_region(
    time_s: np.ndarray,
    i_sum: np.ndarray,
    min_sum: float,
    max_sum: float,
) -> tuple[float, float] | None:
    """
    Finds the first contiguous region where:

        I_sum < min_sum

    or:

        I_sum > max_sum

    Returns the corresponding time-window limits.
    """

    overlap_mask = (i_sum < min_sum) | (i_sum > max_sum)

    if not overlap_mask.any():
        return None

    overlap_indices = np.where(overlap_mask)[0]

    start_index = overlap_indices[0]
    end_index = start_index

    while end_index + 1 < len(overlap_mask) and overlap_mask[end_index + 1]:
        end_index += 1

    t_start = time_s[start_index]
    t_end = time_s[end_index]

    zoom_left = max(time_s.min(), t_start - ZOOM_PADDING_S)
    zoom_right = min(time_s.max(), t_end + ZOOM_PADDING_S)

    return zoom_left, zoom_right


# ---------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------

def plot_first_spike_overlap(df: pd.DataFrame) -> None:
    time_s = df["time_s"].to_numpy()
    i172 = df["i_I172_Iout_A"].to_numpy()
    i56 = df["i_I56_Iout_A"].to_numpy()

    i_sum = i172 + i56

    min_sum, max_sum = calculate_thresholds(df)

    zoom_limits = find_first_spike_overlap_region(
        time_s=time_s,
        i_sum=i_sum,
        min_sum=min_sum,
        max_sum=max_sum,
    )

    print("Thresholds")
    print("----------")
    print(f"min_sum = {min_sum:.12e} A")
    print(f"max_sum = {max_sum:.12e} A")
    print()

    if zoom_limits is None:
        print("No spike overlap found.")
        return

    zoom_left, zoom_right = zoom_limits
    zoom_mask = (time_s >= zoom_left) & (time_s <= zoom_right)

    print("First spike-overlap window")
    print("--------------------------")
    print(f"start = {zoom_left:.12e} s")
    print(f"end   = {zoom_right:.12e} s")
    print(f"width = {zoom_right - zoom_left:.12e} s")

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)

    ax.plot(time_s[zoom_mask], i172[zoom_mask], label="I172 output current")
    ax.plot(time_s[zoom_mask], i56[zoom_mask], label="I56 output current")
    ax.plot(time_s[zoom_mask], i_sum[zoom_mask], label="I172 + I56", linewidth=2)

    ax.axhline(max_sum, linestyle="--", linewidth=1.2, label="max_sum")
    ax.axhline(min_sum, linestyle="--", linewidth=1.2, label="min_sum")

    ax.set_title(f"First spike overlap: {COMBINATION_NAME} — {TRIAL_NAME}")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Current [A]")
    ax.set_xlim(zoom_left, zoom_right)
    ax.grid(True, alpha=0.3)
    ax.legend()

    if SAVE_FIGURE:
        FIGURE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = FIGURE_OUTPUT_DIR / (
            f"first_spike_overlap__{COMBINATION_NAME}__"
            f"{TRIAL_NAME.replace('.csv', '')}.png"
        )

        fig.savefig(output_path, dpi=300)

        print()
        print("Saved figure to:")
        print(output_path)

    if SHOW_FIGURE:
        plt.show()
    else:
        plt.close(fig)


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------

def main() -> None:
    print("Loading data from:")
    print(CSV_PATH)
    print()

    df = load_trial_data(CSV_PATH)
    plot_first_spike_overlap(df)


if __name__ == "__main__":
    main()