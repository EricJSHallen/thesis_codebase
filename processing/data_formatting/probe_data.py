from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

CONDENSED_DATA_DIR = BASE_DIR / "condensed_data"

# Choose which dataset to inspect.
COMBINATION_NAME = "st1_10hz_st2_10hz"
TRIAL_NAME = "trial_1.csv"

CSV_PATH = CONDENSED_DATA_DIR / COMBINATION_NAME / TRIAL_NAME


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

def load_trial_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find CSV file: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = [
        "time_s",
        "i_I172_Iout_A",
        "i_I56_Iout_A",
        "v_vp_res_V",
        "v_vpre1_res_V",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            "The CSV file is missing the following required columns:\n"
            + "\n".join(missing_columns)
            + f"\n\nAvailable columns are:\n{list(df.columns)}"
        )

    return df


# ---------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------

def plot_trial_data(df: pd.DataFrame, combination_name: str, trial_name: str) -> None:
    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(11, 8),
        sharex=True,
        constrained_layout=True,
    )

    fig.suptitle(f"{combination_name} — {trial_name}", fontsize=14)

    # -------------------------------------------------------------
    # Voltage input signals
    # -------------------------------------------------------------

    axes[0].plot(
        df["time_s"],
        df["v_vp_res_V"],
        label="v_vp_res",
        linewidth=1.2,
    )

    axes[0].plot(
        df["time_s"],
        df["v_vpre1_res_V"],
        label="v_vpre1_res",
        linewidth=1.2,
    )

    axes[0].set_ylabel("Voltage [V]")
    axes[0].set_title("Voltage input signals")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    # -------------------------------------------------------------
    # Current output signals
    # -------------------------------------------------------------

    axes[1].plot(
        df["time_s"],
        df["i_I172_Iout_A"],
        label="i_I172_Iout",
        linewidth=1.2,
    )

    axes[1].plot(
        df["time_s"],
        df["i_I56_Iout_A"],
        label="i_I56_Iout",
        linewidth=1.2,
    )

    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Current [A]")
    axes[1].set_title("Current output signals")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    plt.show()


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------

def main() -> None:
    print(f"Loading data from:\n{CSV_PATH}\n")

    df = load_trial_data(CSV_PATH)

    print("Loaded data successfully.")
    print()
    print("First five rows:")
    print(df.head())
    print()
    print("Column names:")
    print(list(df.columns))

    plot_trial_data(df, COMBINATION_NAME, TRIAL_NAME)


if __name__ == "__main__":
    main()