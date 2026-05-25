from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

#this is a test program to measure the difference between the spikes
# Configuration


BASE_DIR = Path(__file__).resolve().parent
CONDENSED_DATA_DIR = BASE_DIR / "condensed_data"

COMBINATION_NAME = "st1_10hz_st2_10hz"
TRIAL_NAME = "trial_1.csv"

CSV_PATH = CONDENSED_DATA_DIR / COMBINATION_NAME / TRIAL_NAME




def calculate_thresholds(df: pd.DataFrame) -> tuple[float, float]:
    max_i172 = df["i_I172_Iout_A"].max()
    max_i56 = df["i_I56_Iout_A"].max()

    min_i172 = df["i_I172_Iout_A"].min()
    min_i56 = df["i_I56_Iout_A"].min()

    max_sum = (max_i172 + max_i56) / 2
    min_sum = (min_i172 + min_i56) / 2

    return min_sum, max_sum

# Main

def main() -> None:
    df = pd.read_csv(CSV_PATH)

    time_s = df["time_s"]

    # Voltage against time

    plt.figure(figsize=(10, 5))
    plt.plot(time_s, df["v_vp_res_V"], label="v_vp_res")
    plt.plot(time_s, df["v_vpre1_res_V"], label="v_vpre1_res")
    plt.xlabel("Time [s]")
    plt.ylabel("Voltage [V]")
    plt.title(f"Voltage vs Time: {COMBINATION_NAME} — {TRIAL_NAME}")
    plt.grid(True)
    plt.legend()
    plt.show()

    # Current against time

    plt.figure(figsize=(10, 5))
    plt.plot(time_s, df["i_I172_Iout_A"], label="I172 output current")
    plt.plot(time_s, df["i_I56_Iout_A"], label="I56 output current")
    plt.xlabel("Time [s]")
    plt.ylabel("Current [A]")
    plt.title(f"Current vs Time: {COMBINATION_NAME} — {TRIAL_NAME}")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()