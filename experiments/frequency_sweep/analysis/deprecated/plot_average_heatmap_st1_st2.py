#!/usr/bin/env python3
"""
plot_average_heatmap_st1_st2.py

Purpose
-------
Build a 2D heatmap for two selected spike trains where:

    x-axis -> frequency of spike train X
    y-axis -> frequency of spike train Y
    color   -> averaged integrated voltage-difference scalar across all valid
               matching trials for that frequency pair

This script is intended to live in:

    processing/previews/

It reads from:

    processing/sim_run_code/spike_train_output_csv

For each valid frequency pair:

    st_x/f_i + st_y/f_j

it evaluates all valid matching trial files:

    trial_1.csv with trial_1.csv
    trial_2.csv with trial_2.csv
    ...

For each trial it computes the scalar integrated voltage difference, then it
averages those scalar values across all valid matching trials for that
frequency pair.

Compared with the earlier 3D plotting script, this version:
    - uses the averaged scalar across trials
    - plots a heatmap instead of a 3D surface
    - uses a custom colormap that runs from black at 0 through
      purple/blue, then orange, and finally bright whitish yellow / white

Default use
-----------
From the repository root:

    python processing/previews/plot_average_heatmap_st1_st2.py

Useful examples:

    python processing/previews/plot_average_heatmap_st1_st2.py --st-x-index 1 --st-y-index 2
    python processing/previews/plot_average_heatmap_st1_st2.py --show

Outputs
-------
By default the script saves:

    processing/previews/heatmap_outputs/
        average_heatmap_st1_vs_st2.png
        average_heatmap_st1_vs_st2_values.csv
        average_heatmap_st1_vs_st2_pivot.csv

Notes
-----
- If more than two st_N directories exist in spike_train_output_csv, this
  script uses only the two selected ones and ignores the rest.
- Trial mixing is disabled.
- If some frequency/trial files are missing, only valid combinations are used.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from processing.previews.deprecated.preview_integrated_voltage_difference import (
    CombinationCase,
    default_input_root,
    discover_spike_train_dirs,
    discover_trial_names,
)
from processing.previews.deprecated.preview_average_integrated_voltage_difference import compute_trial_integral


MEAN_INTEGRAL_COL = "mean_voltage_difference_integral_vs"
STD_INTEGRAL_COL = "std_voltage_difference_integral_vs"
MIN_INTEGRAL_COL = "min_voltage_difference_integral_vs"
MAX_INTEGRAL_COL = "max_voltage_difference_integral_vs"
VALID_TRIAL_COUNT_COL = "valid_trial_count"
X_FREQ_COL = "frequency_st_x_hz"
Y_FREQ_COL = "frequency_st_y_hz"
RUN_NAME_COL = "run_name"


def parse_frequency_hz_from_dirname(dirname: str) -> int:
    """Convert a directory name like '17_hz' into integer 17."""
    suffix = "_hz"
    if not dirname.endswith(suffix):
        raise ValueError(f"Frequency directory does not end with '_hz': {dirname}")
    return int(dirname[:-len(suffix)])


def default_output_dir() -> Path:
    """Place outputs beside the script in processing/previews/heatmap_outputs."""
    return Path(__file__).resolve().parent / "heatmap_outputs"


def select_spike_train_dir(spike_train_dirs, st_index: int):
    """Return the discovered SpikeTrainDirectory with the requested st index."""
    for st_dir in spike_train_dirs:
        if st_dir.st_index == st_index:
            return st_dir
    available = ", ".join(f"st_{st.st_index}" for st in spike_train_dirs)
    raise ValueError(f"Requested st_{st_index} was not found. Available: {available}")


def build_case_for_two_spike_trains(
    st_x_dir,
    st_y_dir,
    freq_x_dir: Path,
    freq_y_dir: Path,
    trial_name: str,
) -> CombinationCase | None:
    """
    Build a two-spike-train CombinationCase for one (frequency_x, frequency_y,
    trial_name) triplet. Returns None when one or both required trial files are
    missing.
    """
    csv_x = freq_x_dir / trial_name
    csv_y = freq_y_dir / trial_name

    if not csv_x.is_file() or not csv_y.is_file():
        return None

    trial_stem = trial_name.removesuffix(".csv")
    trial_index = int(trial_stem.split("_")[-1])
    run_name = f"st{st_x_dir.st_index}_{freq_x_dir.name}__st{st_y_dir.st_index}_{freq_y_dir.name}__{trial_stem}"

    return CombinationCase(
        run_name=run_name,
        trial_name=trial_name,
        trial_index=trial_index,
        csv_paths=(csv_x, csv_y),
        frequency_names=(freq_x_dir.name, freq_y_dir.name),
    )


def compute_average_integral_grid_dataframe(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
) -> pd.DataFrame:
    """
    Compute one averaged scalar integral for every valid (freq_x, freq_y) pair.

    Returns a long-form DataFrame with columns:
        frequency_st_x_hz
        frequency_st_y_hz
        mean_voltage_difference_integral_vs
        std_voltage_difference_integral_vs
        min_voltage_difference_integral_vs
        max_voltage_difference_integral_vs
        valid_trial_count
        run_name
    """
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)

    st_x_dir = select_spike_train_dir(spike_train_dirs, st_x_index)
    st_y_dir = select_spike_train_dir(spike_train_dirs, st_y_index)

    trial_names = discover_trial_names((st_x_dir, st_y_dir))

    rows: list[dict[str, object]] = []

    for freq_x_dir in st_x_dir.frequency_dirs:
        for freq_y_dir in st_y_dir.frequency_dirs:
            integrals: list[float] = []
            trial_indices: list[int] = []

            for trial_name in trial_names:
                case = build_case_for_two_spike_trains(
                    st_x_dir=st_x_dir,
                    st_y_dir=st_y_dir,
                    freq_x_dir=freq_x_dir,
                    freq_y_dir=freq_y_dir,
                    trial_name=trial_name,
                )
                if case is None:
                    continue

                integrals.append(compute_trial_integral(case))
                trial_indices.append(case.trial_index)

            if not integrals:
                continue

            values = np.asarray(integrals, dtype=float)
            rows.append(
                {
                    X_FREQ_COL: parse_frequency_hz_from_dirname(freq_x_dir.name),
                    Y_FREQ_COL: parse_frequency_hz_from_dirname(freq_y_dir.name),
                    MEAN_INTEGRAL_COL: float(np.mean(values)),
                    STD_INTEGRAL_COL: float(np.std(values, ddof=0)),
                    MIN_INTEGRAL_COL: float(np.min(values)),
                    MAX_INTEGRAL_COL: float(np.max(values)),
                    VALID_TRIAL_COUNT_COL: int(values.size),
                    "trial_indices_used": ";".join(str(i) for i in trial_indices),
                    "trial_integrals_vs": ";".join(f"{v:.12e}" for v in values),
                    RUN_NAME_COL: f"st{st_x_dir.st_index}_{freq_x_dir.name}__st{st_y_dir.st_index}_{freq_y_dir.name}",
                }
            )

    if not rows:
        raise FileNotFoundError(
            f"No valid combinations were found for st_{st_x_index} and st_{st_y_index} "
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
        values=MEAN_INTEGRAL_COL,
    )
    pivot = pivot.sort_index(axis=0).sort_index(axis=1)
    return pivot


def make_custom_heatmap_colormap() -> LinearSegmentedColormap:
    """
    Build the requested colormap:
        black -> purple -> blue -> orange -> bright whitish yellow -> white
    """
    colors = [
        "#000000",  # black at 0
        "#4B0082",  # indigo / purple
        "#2F5BFF",  # blue
        "#FF8C00",  # orange
        "#FFF6B0",  # bright whitish yellow
        "#FFFFFF",  # white
    ]
    cmap = LinearSegmentedColormap.from_list("black_purple_blue_orange_white", colors, N=256)
    cmap.set_bad(color="#000000")
    return cmap


def compute_bin_edges(values: np.ndarray) -> np.ndarray:
    """
    Compute bin edges from sorted bin centers for pcolormesh.

    If only one value exists, create a symmetric bin of width 1 around it.
    """
    if values.ndim != 1:
        raise ValueError("values must be a 1D array")
    if values.size == 0:
        raise ValueError("values must not be empty")

    values = np.asarray(values, dtype=float)

    if values.size == 1:
        return np.array([values[0] - 0.5, values[0] + 0.5], dtype=float)

    diffs = np.diff(values)
    edges = np.empty(values.size + 1, dtype=float)
    edges[1:-1] = values[:-1] + diffs / 2.0
    edges[0] = values[0] - diffs[0] / 2.0
    edges[-1] = values[-1] + diffs[-1] / 2.0
    return edges


def create_average_heatmap_plot(
    pivot_df: pd.DataFrame,
    st_x_index: int,
    st_y_index: int,
    output_path: Path,
    show: bool = False,
) -> None:
    """Create and save the heatmap."""
    x_values = pivot_df.columns.to_numpy(dtype=float)
    y_values = pivot_df.index.to_numpy(dtype=float)
    z_values = pivot_df.to_numpy(dtype=float)

    x_edges = compute_bin_edges(x_values)
    y_edges = compute_bin_edges(y_values)

    X_edges, Y_edges = np.meshgrid(x_edges, y_edges)
    cmap = make_custom_heatmap_colormap()

    fig, ax = plt.subplots(figsize=(10, 8))

    mesh = ax.pcolormesh(
        X_edges,
        Y_edges,
        z_values,
        shading="auto",
        cmap=cmap,
        vmin=0.0,
    )

    ax.set_xlabel(f"Frequency of spike train {st_x_index} (Hz)")
    ax.set_ylabel(f"Frequency of spike train {st_y_index} (Hz)")
    ax.set_title(
        f"Heatmap of averaged integrated voltage difference across trials\n"
        f"st_{st_x_index} vs st_{st_y_index}"
    )

    ax.set_xticks(x_values)
    ax.set_yticks(y_values)

    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Averaged integrated excess voltage (V·s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_default_output_stem(output_dir: Path, st_x_index: int, st_y_index: int) -> Path:
    """Return the base path used for the PNG and companion CSVs."""
    return output_dir / f"average_heatmap_st{st_x_index}_vs_st{st_y_index}"


def generate_average_heatmap_outputs(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
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
    if st_x_index == st_y_index:
        raise ValueError("st_x_index and st_y_index must be different.")

    resolved_output_dir = default_output_dir() if output_dir is None else Path(output_dir)
    output_stem = make_default_output_stem(
        output_dir=resolved_output_dir,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
    )

    values_df = compute_average_integral_grid_dataframe(
        input_root=input_root,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
    )
    pivot_df = build_pivot_grid(values_df)

    plot_path = output_stem.with_suffix(".png")
    values_csv_path = output_stem.with_name(output_stem.name + "_values").with_suffix(".csv")
    pivot_csv_path = output_stem.with_name(output_stem.name + "_pivot").with_suffix(".csv")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    values_df.to_csv(values_csv_path, index=False)
    pivot_df.to_csv(pivot_csv_path)

    create_average_heatmap_plot(
        pivot_df=pivot_df,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
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
        description="Make a heatmap of averaged integrated voltage difference for two spike trains."
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
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory in which to save the heatmap and companion CSV files.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figure interactively in addition to saving it.",
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    outputs = generate_average_heatmap_outputs(
        input_root=args.input_root,
        st_x_index=args.st_x_index,
        st_y_index=args.st_y_index,
        output_dir=args.output_dir,
        show=args.show,
    )

    print(f"Saved averaged heatmap to: {outputs['plot_path']}")
    print(f"Saved long-form values CSV to: {outputs['values_csv_path']}")
    print(f"Saved pivot-grid CSV to: {outputs['pivot_csv_path']}")
    print(f"Grid shape (y, x): {outputs['pivot_df'].shape}")
    print(f"Valid averaged combinations plotted: {len(outputs['values_df'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
