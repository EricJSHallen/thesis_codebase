#!/usr/bin/env python3
"""
plot_3d_topography_st1_st2.py

Purpose
-------
Build a 3D topographical map from the scalar integral produced by
preview_integrated_voltage_difference.py.

The intended axes are:
    x -> frequency of spike train 1 (or a user-selected st_x)
    y -> frequency of spike train 2 (or a user-selected st_y)
    z -> scalar integral value for that frequency combination

This script is intended to live in:
    processing/previews/

It reads two selected spike-train directories from:
    processing/sim_run_code/spike_train_output_csv

For a fixed trial index, it evaluates every valid frequency pair:
    st_x/f_i/trial_k.csv + st_y/f_j/trial_k.csv

For each pair it computes:
    df_sum
    df_capped
    df_difference = df_sum - df_capped
    integral_vs   = ∫ df_difference(t) dt

Then it:
    1) builds a long-form DataFrame containing:
           frequency_st_x_hz, frequency_st_y_hz, voltage_difference_integral_vs
    2) builds a pivot table / grid suitable for surface plotting
    3) creates and saves a 3D surface plot

Default use
-----------
From the repository root:

    python processing/previews/plot_3d_topography_st1_st2.py

Useful examples:

    python processing/previews/plot_3d_topography_st1_st2.py --trial-index 1
    python processing/previews/plot_3d_topography_st1_st2.py --st-x-index 1 --st-y-index 2
    python processing/previews/plot_3d_topography_st1_st2.py --show

Outputs
-------
By default the script saves:

    processing/previews/topography_outputs/
        topography_st1_vs_st2_trial_1.png
        topography_st1_vs_st2_trial_1_values.csv
        topography_st1_vs_st2_trial_1_pivot.csv

Notes
-----
- If more than two st_N directories exist in spike_train_output_csv, this script
  uses only the two selected ones and ignores the rest.
- Trial mixing is disabled. Only one trial index is used at a time.
- If some frequency/trial files are missing, only valid combinations are plotted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Import reusable logic from the previously generated preview script.
from processing.previews.deprecated.preview_integrated_voltage_difference import (
    CombinationCase,
    build_capped_sibling_dataframe,
    build_difference_dataframe,
    build_summed_voltage_dataframe,
    default_input_root,
    discover_spike_train_dirs,
    integrate_difference_transient,
)


INTEGRAL_COL = "voltage_difference_integral_vs"
X_FREQ_COL = "frequency_st_x_hz"
Y_FREQ_COL = "frequency_st_y_hz"
RUN_NAME_COL = "run_name"
TRIAL_INDEX_COL = "trial_index"


def parse_frequency_hz_from_dirname(dirname: str) -> int:
    """Convert a directory name like '17_hz' into integer 17."""
    suffix = "_hz"
    if not dirname.endswith(suffix):
        raise ValueError(f"Frequency directory does not end with '_hz': {dirname}")
    return int(dirname[:-len(suffix)])


def default_output_dir() -> Path:
    """Place outputs beside the script in processing/previews/topography_outputs."""
    return Path(__file__).resolve().parent / "topography_outputs"


def select_spike_train_dir(spike_train_dirs, st_index: int):
    """Return the discovered SpikeTrainDirectory with the requested st index."""
    for st_dir in spike_train_dirs:
        if st_dir.st_index == st_index:
            return st_dir
    available = ", ".join(f"st_{st.st_index}" for st in spike_train_dirs)
    raise ValueError(f"Requested st_{st_index} was not found. Available: {available}")


def build_case_for_two_spike_trains(st_x_dir, st_y_dir, freq_x_dir: Path, freq_y_dir: Path, trial_index: int) -> CombinationCase | None:
    """
    Build a two-spike-train CombinationCase for one (frequency_x, frequency_y, trial)
    triplet. Returns None when one or both required trial files are missing.
    """
    trial_name = f"trial_{trial_index}.csv"
    csv_x = freq_x_dir / trial_name
    csv_y = freq_y_dir / trial_name

    if not csv_x.is_file() or not csv_y.is_file():
        return None

    run_name = f"st{st_x_dir.st_index}_{freq_x_dir.name}__st{st_y_dir.st_index}_{freq_y_dir.name}__trial_{trial_index}"

    return CombinationCase(
        run_name=run_name,
        trial_name=trial_name,
        trial_index=trial_index,
        csv_paths=(csv_x, csv_y),
        frequency_names=(freq_x_dir.name, freq_y_dir.name),
    )


def compute_integral_grid_dataframe(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
    trial_index: int = 1,
) -> pd.DataFrame:
    """
    Compute one scalar integral for every valid (freq_x, freq_y) combination.

    Returns a long-form DataFrame with columns:
        frequency_st_x_hz
        frequency_st_y_hz
        voltage_difference_integral_vs
        run_name
        trial_index
    """
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)

    st_x_dir = select_spike_train_dir(spike_train_dirs, st_x_index)
    st_y_dir = select_spike_train_dir(spike_train_dirs, st_y_index)

    rows: list[dict[str, object]] = []

    for freq_x_dir in st_x_dir.frequency_dirs:
        for freq_y_dir in st_y_dir.frequency_dirs:
            case = build_case_for_two_spike_trains(
                st_x_dir=st_x_dir,
                st_y_dir=st_y_dir,
                freq_x_dir=freq_x_dir,
                freq_y_dir=freq_y_dir,
                trial_index=trial_index,
            )
            if case is None:
                continue

            df_sum = build_summed_voltage_dataframe(case)
            df_capped = build_capped_sibling_dataframe(df_sum)
            df_difference = build_difference_dataframe(df_sum, df_capped)
            difference_integral_vs = integrate_difference_transient(df_difference)

            rows.append(
                {
                    X_FREQ_COL: parse_frequency_hz_from_dirname(freq_x_dir.name),
                    Y_FREQ_COL: parse_frequency_hz_from_dirname(freq_y_dir.name),
                    INTEGRAL_COL: difference_integral_vs,
                    RUN_NAME_COL: case.run_name,
                    TRIAL_INDEX_COL: trial_index,
                }
            )

    if not rows:
        raise FileNotFoundError(
            f"No valid combinations were found for st_{st_x_index}, st_{st_y_index}, trial_{trial_index} "
            f"under {resolved_input_root.resolve()}"
        )

    df = pd.DataFrame(rows)
    df = df.sort_values([X_FREQ_COL, Y_FREQ_COL]).reset_index(drop=True)
    return df


def build_pivot_grid(df_values: pd.DataFrame) -> pd.DataFrame:
    """Convert the long-form values DataFrame into a y-by-x pivot table."""
    pivot = df_values.pivot(
        index=Y_FREQ_COL,
        columns=X_FREQ_COL,
        values=INTEGRAL_COL,
    )
    pivot = pivot.sort_index(axis=0).sort_index(axis=1)
    return pivot


def create_3d_topography_plot(
    pivot_df: pd.DataFrame,
    st_x_index: int,
    st_y_index: int,
    trial_index: int,
    output_path: Path,
    show: bool = False,
) -> None:
    """
    Create and save a 3D surface plot with an optional contour projection.
    """
    x_values = pivot_df.columns.to_numpy(dtype=float)
    y_values = pivot_df.index.to_numpy(dtype=float)
    X, Y = np.meshgrid(x_values, y_values)
    Z = pivot_df.to_numpy(dtype=float)

    # Mask missing points, if any.
    Z_masked = np.ma.masked_invalid(Z)

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    surface = ax.plot_surface(X, Y, Z_masked, linewidth=0, antialiased=True)

    # Add a contour projection at the base to strengthen the topographical feel.
    z_min = float(np.nanmin(Z)) if not np.isnan(Z).all() else 0.0
    ax.contour(X, Y, Z, zdir="z", offset=z_min, levels=12)

    ax.set_xlabel(f"Frequency of spike train {st_x_index} (Hz)")
    ax.set_ylabel(f"Frequency of spike train {st_y_index} (Hz)")
    ax.set_zlabel("Integrated excess voltage (V·s)")
    ax.set_title(
        f"3D topographical map of integrated voltage difference\n"
        f"st_{st_x_index} vs st_{st_y_index}, trial_{trial_index}"
    )

    fig.colorbar(surface, ax=ax, shrink=0.7, pad=0.1, label="Integrated excess voltage (V·s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_default_output_stem(output_dir: Path, st_x_index: int, st_y_index: int, trial_index: int) -> Path:
    """Return the base path used for the PNG and companion CSVs."""
    return output_dir / f"topography_st{st_x_index}_vs_st{st_y_index}_trial_{trial_index}"


def generate_topography_outputs(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
    trial_index: int = 1,
    output_dir: Path | None = None,
    show: bool = False,
) -> dict[str, Path | pd.DataFrame]:
    """
    Callable API for other scripts.

    Returns a dictionary containing:
        values_df
        pivot_df
        plot_path
        values_csv_path
        pivot_csv_path
    """
    resolved_output_dir = default_output_dir() if output_dir is None else Path(output_dir)
    output_stem = make_default_output_stem(
        output_dir=resolved_output_dir,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
        trial_index=trial_index,
    )

    values_df = compute_integral_grid_dataframe(
        input_root=input_root,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
        trial_index=trial_index,
    )
    pivot_df = build_pivot_grid(values_df)

    plot_path = output_stem.with_suffix(".png")
    values_csv_path = output_stem.with_name(output_stem.name + "_values").with_suffix(".csv")
    pivot_csv_path = output_stem.with_name(output_stem.name + "_pivot").with_suffix(".csv")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    values_df.to_csv(values_csv_path, index=False)
    pivot_df.to_csv(pivot_csv_path)

    create_3d_topography_plot(
        pivot_df=pivot_df,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
        trial_index=trial_index,
        output_path=plot_path,
        show=show,
    )

    return {
        "values_df": values_df,
        "pivot_df": pivot_df,
        "plot_path": plot_path,
        "values_csv_path": values_csv_path,
        "pivot_csv_path": pivot_csv_path,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Make a 3D topographical map of integrated voltage difference for two spike trains."
    )

    parser.add_argument(
        "--input-root",
        type=Path,
        default=default_input_root(),
        help=(
            "Path to spike_train_output_csv. Defaults to "
            "processing/sim_run_code/spike_train_output_csv relative to this script."
        ),
    )

    parser.add_argument(
        "--st-x-index",
        type=int,
        default=1,
        help="st index to use on the x axis. Default: 1",
    )

    parser.add_argument(
        "--st-y-index",
        type=int,
        default=2,
        help="st index to use on the y axis. Default: 2",
    )

    parser.add_argument(
        "--trial-index",
        type=int,
        default=1,
        help="trial index to evaluate (same trial used for both spike trains). Default: 1",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory in which to save the plot and companion CSV files.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figure interactively in addition to saving it.",
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.st_x_index == args.st_y_index:
        raise ValueError("st-x-index and st-y-index must be different.")

    outputs = generate_topography_outputs(
        input_root=args.input_root,
        st_x_index=args.st_x_index,
        st_y_index=args.st_y_index,
        trial_index=args.trial_index,
        output_dir=args.output_dir,
        show=args.show,
    )

    print(f"Saved 3D topography plot to: {outputs['plot_path']}")
    print(f"Saved long-form values CSV to: {outputs['values_csv_path']}")
    print(f"Saved pivot-grid CSV to: {outputs['pivot_csv_path']}")
    print(f"Grid shape (y, x): {outputs['pivot_df'].shape}")
    print(f"Valid combinations plotted: {len(outputs['values_df'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
