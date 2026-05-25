#imports
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re
from scipy.interpolate import griddata
from mpl_toolkits.mplot3d import Axes3D

#this script makes a heat map based off of which frequency combinations result in large spike overlap.

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

def dataloader (outputcsv,datadir)-> tuple[pd.DataFrame, pd.DataFrame]:  

    csv_path1 = datadir / "condensed1syn" / outputcsv.name
    csv_path2 = datadir / "condensed2syn" / outputcsv.name
    df1 = pd.read_csv(csv_path1)
    df2 = pd.read_csv(csv_path2)

    return df1,df2 #data frame


# def main():
#     DATADIR = Path(__file__).resolve().parents[1] / "cadence_extracted"

#     n = 0

#     loopdir = DATADIR/"condensed1syn"

#     results = []
#     filename_pattern = re.compile(r"st1_(\d+)_hz__st2_(\d+)_hz__trial_(\d+)\.csv")

#     for csv_file in loopdir.glob("*.csv"):

#         t_min = 0.0
#         t_max = 0.5

#         time = t_max-t_min

#         n+=1

#         outputcsv = csv_file

#         df1, df2 = dataloader(outputcsv,DATADIR)
#         print(f"file {outputcsv.name}")


#         df1 = df1[(df1["time_s"] >= t_min) & (df1["time_s"] <= t_max)]
#         df2 = df2[(df2["time_s"] >= t_min) & (df2["time_s"] <= t_max)]

#         df1, df2 = align_on_union_time(df1, df2)


#         t = df1["time_s"].to_numpy()
#         delta_I = np.abs(df1["i_I56_Iout_A"].to_numpy()- (df2["i_I56_Iout_A"].to_numpy()+ df2["i_I172_Iout_A"].to_numpy()))
#         # area_delta_I = np.trapezoid(delta_I, t)
#         # print(area_delta_I,n)

#         absmin_isum = (np.min(np.abs(df2["i_I56_Iout_A"].to_numpy() + df2["i_I172_Iout_A"].to_numpy())))-np.min(np.abs(df1["i_I56_Iout_A"].to_numpy()))
#         zeroed_delta_I = np.abs(delta_I-absmin_isum)
#         zeroed_area_delta_I = np.trapezoid(zeroed_delta_I, t)
#         print(zeroed_area_delta_I) 


#     return

def main():
    DATADIR = Path(__file__).resolve().parents[1] / "cadence_extracted"

    loopdir = DATADIR / "condensed1syn"

    results = []

    filename_pattern = re.compile(
        r"st1_(\d+)_hz__st2_(\d+)_hz__trial_(\d+)\.csv"
    )

    for csv_file in loopdir.glob("*.csv"):

        t_min = 0.0
        t_max = 0.5

        outputcsv = csv_file

        match = filename_pattern.match(outputcsv.name)
        if match is None:
            print(f"Skipping file with unexpected name: {outputcsv.name}")
            continue

        st1_freq = int(match.group(1))
        st2_freq = int(match.group(2))
        trial = int(match.group(3))

        df1, df2 = dataloader(outputcsv, DATADIR)

        df1 = df1[(df1["time_s"] >= t_min) & (df1["time_s"] <= t_max)]
        df2 = df2[(df2["time_s"] >= t_min) & (df2["time_s"] <= t_max)]

        df1, df2 = align_on_union_time(df1, df2)

        t = df1["time_s"].to_numpy()

        delta_I = np.abs( df1["i_I56_Iout_A"].to_numpy() - ( df2["i_I56_Iout_A"].to_numpy()+ df2["i_I172_Iout_A"].to_numpy()))

        absmin_isum = ( np.min( np.abs(df2["i_I56_Iout_A"].to_numpy() + df2["i_I172_Iout_A"].to_numpy()) ) - np.min(np.abs(df1["i_I56_Iout_A"].to_numpy())))

        zeroed_delta_I = np.abs(delta_I - absmin_isum)
        zeroed_area_delta_I = np.trapezoid(zeroed_delta_I, t)

        print(f"file {outputcsv.name}")
        print(zeroed_area_delta_I)

        results.append(
            {
                "st1_hz": st1_freq,
                "st2_hz": st2_freq,
                "trial": trial,
                "value": zeroed_area_delta_I,
            }
        )

    results_df = pd.DataFrame(results)

    plot_frequency_heatmap(results_df)
    plot_frequency_surface(results_df)

    return

def plot_frequency_heatmap(results_df):
    """
    Plot st1 frequency versus st2 frequency.

    Point colour is controlled by the relative magnitude of the computed value.
    """

    if results_df.empty:
        print("No results to plot.")
        return

    x = results_df["st1_hz"].to_numpy()
    y = results_df["st2_hz"].to_numpy()
    values = results_df["value"].to_numpy()

    magnitudes = np.abs(values)

    fig, ax = plt.subplots(figsize=(8, 7))

    scatter = ax.scatter(
        x,
        y,
        s=160,
        c=magnitudes,
        cmap="magma",
        edgecolors="black",
        linewidths=0.5,
    )

    ax.set_xlabel("st1 frequency / Hz")
    ax.set_ylabel("st2 frequency / Hz")
    ax.set_title("Magnitude of zeroed area delta I")

    ax.set_xticks(sorted(results_df["st1_hz"].unique()))
    ax.set_yticks(sorted(results_df["st2_hz"].unique()))

    ax.grid(True, alpha=0.3)

    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label(r"$|\mathrm{value}|$")

    fig.tight_layout()
    plt.show()

def plot_frequency_surface(results_df):
    """
    Plot st1 frequency versus st2 frequency as a 3D interpolated surface.

    x-axis: st1 frequency
    y-axis: st2 frequency
    z-axis: magnitude of computed value
    colour: magnitude of computed value
    """

    if results_df.empty:
        print("No results to plot.")
        return

    x = results_df["st1_hz"].to_numpy()
    y = results_df["st2_hz"].to_numpy()
    values = results_df["value"].to_numpy()

    # Use magnitude so negative and positive deviations both count as large.
    z = np.abs(values)

    # Make a regular grid over the measured frequency space.
    x_grid = np.linspace(x.min(), x.max(), 100)
    y_grid = np.linspace(y.min(), y.max(), 100)
    X_grid, Y_grid = np.meshgrid(x_grid, y_grid)

    # Interpolate scattered data onto the regular grid.
    Z_grid = griddata(
        points=(x, y),
        values=z,
        xi=(X_grid, Y_grid),
        method="linear"
    )

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    surface = ax.plot_surface(
        X_grid,
        Y_grid,
        Z_grid,
        cmap="magma",
        linewidth=0,
        antialiased=True,
        alpha=0.95
    )

    # Also show the actual measured points.
    ax.scatter(
        x,
        y,
        z,
        c=z,
        cmap="magma",
        edgecolors="black",
        s=50
    )

    ax.set_xlabel("st1 frequency / Hz")
    ax.set_ylabel("st2 frequency / Hz")
    ax.set_zlabel(r"$|\mathrm{value}|$")
    ax.set_title("Topographical view of zeroed area delta I magnitude")

    cbar = fig.colorbar(surface, ax=ax, shrink=0.65, pad=0.1)
    cbar.set_label(r"$|\mathrm{value}|$")

    fig.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()