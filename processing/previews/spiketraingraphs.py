#imports
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re





def dataloader ():  
    DATADIR = Path(__file__).resolve().parents[1] / "cadence_extracted"
    csv_path1 = DATADIR / "condensed1syn" / "st1_561_hz__st2_561_hz__trial_1.csv"
    csv_path2 = DATADIR / "condensed2syn" / "st1_561_hz__st2_561_hz__trial_1.csv"
    df1 = pd.read_csv(csv_path1)
    df2 = pd.read_csv(csv_path2)
    return df1,df2 #data frame


def align_on_union_time(df1, df2, time_col="time_s"):
    """
    Align two dataframes onto the union of their timestamps.

    If a timestamp exists in one dataframe but not the other, an artificial row
    is inserted. Numeric columns are filled by linear interpolation between the
    previous and next datapoints.

    Non-numeric columns, if any, are forward-filled and then backward-filled.
    """

    # Sort by time
    df1 = df1.sort_values(time_col).copy()
    df2 = df2.sort_values(time_col).copy()

    # Remove duplicate timestamps
    df1 = df1.drop_duplicates(subset=time_col, keep="last")
    df2 = df2.drop_duplicates(subset=time_col, keep="last")

    # Common time grid: all timestamps appearing in either dataframe
    common_time = np.union1d(
        df1[time_col].to_numpy(),
        df2[time_col].to_numpy()
    )

    def reindex_and_interpolate(df):
        df_aligned = (
            df.set_index(time_col)
              .reindex(common_time)
        )

        # Numeric columns: interpolate between previous and next values
        numeric_cols = df_aligned.select_dtypes(include=[np.number]).columns
        df_aligned[numeric_cols] = df_aligned[numeric_cols].interpolate(
            method="index",
            limit_direction="both"
        )

        # Non-numeric columns: fill nearest available values
        non_numeric_cols = df_aligned.columns.difference(numeric_cols)
        df_aligned[non_numeric_cols] = (
            df_aligned[non_numeric_cols]
            .ffill()
            .bfill()
        )

        return (
            df_aligned
            .reset_index()
            .rename(columns={"index": time_col})
        )

    df1_aligned = reindex_and_interpolate(df1)
    df2_aligned = reindex_and_interpolate(df2)

    return df1_aligned, df2_aligned


def minmax_normalise(x):
    x = np.asarray(x, dtype=float)
    x_min = np.min(x)
    x_max = np.max(x)

    if x_max == x_min:
        return np.zeros_like(x)

    return (x - x_min) / (x_max - x_min)

def main():

    df1, df2 = dataloader()

    fig, axes = plt.subplots(9, 1, sharex=True, figsize=(10, 12))

    t_min = 0.17864
    t_max = 0.17874

    df1 = df1[(df1["time_s"] >= t_min) & (df1["time_s"] <= t_max)]
    df2 = df2[(df2["time_s"] >= t_min) & (df2["time_s"] <= t_max)]

    df1, df2 = align_on_union_time(df1, df2)


    axes[0].plot(df1["time_s"], df1["v_vpre_res_V"])
    axes[0].set_ylabel("Vst1")
    axes[1].plot(df1["time_s"], df1["v_vpre1_res_V"])
    axes[1].set_ylabel("Vst2")
    axes[2].plot(df1["time_s"], df1["i_I56_Iout_A"])
    axes[2].set_ylabel("I56_1syn")

    axes[3].plot(df2["time_s"], df2["v_vpre_res_V"])
    axes[3].set_ylabel("Vst1")
    axes[4].plot(df2["time_s"], df2["v_vpre1_res_V"])
    axes[4].set_ylabel("Vst2")
    axes[5].plot(df2["time_s"], df2["i_I56_Iout_A"])
    axes[5].set_ylabel("I56_2syn")
    axes[6].plot(df2["time_s"], df2["i_I172_Iout_A"])
    axes[6].set_ylabel("I172_2syn")


    axes[7].plot(df1["time_s"].to_numpy(), abs(df1["i_I56_Iout_A"].to_numpy() - (df2["i_I56_Iout_A"].to_numpy()+df2["i_I172_Iout_A"])))
    axes[7].set_ylabel(r"$\Delta$I")

    # i1 = df1["i_I56_Iout_A"].to_numpy()
    # i2 = (df2["i_I56_Iout_A"].to_numpy() + df2["i_I172_Iout_A"].to_numpy())
    # i1_norm = minmax_normalise(i1)
    # i2_norm = minmax_normalise(i2)
    # axes[8].plot(df1["time_s"].to_numpy(),np.abs(i1_norm - i2_norm))
    # axes[8].set_ylabel("min-max normalised current diff")

    i1 = df1["i_I56_Iout_A"].to_numpy()
    i2 = (df2["i_I56_Iout_A"].to_numpy()+ df2["i_I172_Iout_A"].to_numpy())
    i1_norm = i1 / np.max(np.abs(i1))
    i2_norm = i2 / np.max(np.abs(i2))
    axes[8].plot(df1["time_s"].to_numpy(),np.abs(i1_norm - i2_norm))
    axes[8].set_ylabel(r"norm $\Delta$I")

    for ax in axes:
        ax.grid(True)

    axes[-1].set_xlabel("Time / s")

    plt.tight_layout()
    plt.show()

    return

if __name__ == "__main__":
    main()


