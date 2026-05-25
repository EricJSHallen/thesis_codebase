#!/usr/bin/env python3
"""
heatmap_avg_v6.py

Purpose
-------
Make a heatmap for two selected spike trains.

Axes:
    x-axis -> frequency of spike train X
    y-axis -> frequency of spike train Y
    color  -> averaged integrated voltage-difference scalar across all valid
              matching trials for that frequency pair

Color scale:
    black at 0 -> purple -> blue -> orange -> bright whitish yellow -> white

This file imports only avg_integral_v6.py. It does not import the older
preview_integrated_voltage_difference.py file, avoiding the circular import that
caused the previous error.

Expected location
-----------------
Place this file in:

    processing/previews/

Also place avg_integral_v6.py in:

    processing/previews/

CLI examples
------------
From the repository root:

    python processing/previews/heatmap_avg_v6.py
    python processing/previews/heatmap_avg_v6.py --st-x-index 1 --st-y-index 2
    python processing/previews/heatmap_avg_v6.py --show
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from processing.previews.deprecated.avg_integral_v6 import (
    AverageCombinationCase,
    AverageIntegralResult,
    MEAN_INTEGRAL_COL,
    STD_INTEGRAL_COL,
    MIN_INTEGRAL_COL,
    MAX_INTEGRAL_COL,
    VALID_TRIAL_COUNT_COL,
    SpikeTrainDirectory,
    compute_average_integral_for_case,
    default_input_root,
    discover_spike_train_dirs,
    discover_trial_names,
    frequency_hz_from_dir_name,
)


X_FREQ_COL = "frequency_st_x_hz"
Y_FREQ_COL = "frequency_st_y_hz"
RUN_NAME_COL = "run_name"


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "heatmap_outputs_v6"


def select_spike_train_dir(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
    st_index: int,
) -> SpikeTrainDirectory:
    for st_dir in spike_train_dirs:
        if st_dir.st_index == st_index:
            return st_dir

    available = ", ".join(f"st_{st.st_index}" for st in spike_train_dirs)
    raise ValueError(f"Requested st_{st_index} was not found. Available: {available}")


def make_pair_average_case(
    st_x_dir: SpikeTrainDirectory,
    st_y_dir: SpikeTrainDirectory,
    freq_x_dir: Path,
    freq_y_dir: Path,
) -> AverageCombinationCase:
    frequency_names = (freq_x_dir.name, freq_y_dir.name)
    frequency_values_hz = tuple(frequency_hz_from_dir_name(name) for name in frequency_names)

    return AverageCombinationCase(
        run_name=f"st{st_x_dir.st_index}_{freq_x_dir.name}__st{st_y_dir.st_index}_{freq_y_dir.name}",
        frequency_dirs=(freq_x_dir, freq_y_dir),
        frequency_names=frequency_names,
        frequency_values_hz=frequency_values_hz,
        st_indices=(st_x_dir.st_index, st_y_dir.st_index),
    )


def compute_average_integral_grid_dataframe(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
) -> pd.DataFrame:
    """
    Compute one averaged scalar value for every valid frequency pair.

    Returns a long-form DataFrame with columns:
        frequency_st_x_hz
        frequency_st_y_hz
        mean_voltage_difference_integral_vs
        std_voltage_difference_integral_vs
        min_voltage_difference_integral_vs
        max_voltage_difference_integral_vs
        valid_trial_count
        trial_indices_used
        trial_integrals_vs
        run_name
    """
    if st_x_index == st_y_index:
        raise ValueError("st_x_index and st_y_index must be different.")

    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)

    st_x_dir = select_spike_train_dir(spike_train_dirs, st_x_index)
    st_y_dir = select_spike_train_dir(spike_train_dirs, st_y_index)

    trial_names = discover_trial_names((st_x_dir, st_y_dir))

    rows: list[dict[str, object]] = []

    for freq_x_dir in st_x_dir.frequency_dirs:
        for freq_y_dir in st_y_dir.frequency_dirs:
            average_case = make_pair_average_case(
                st_x_dir=st_x_dir,
                st_y_dir=st_y_dir,
                freq_x_dir=freq_x_dir,
                freq_y_dir=freq_y_dir,
            )

            result = compute_average_integral_for_case(average_case, trial_names)
            if result is None:
                continue

            rows.append(
                {
                    X_FREQ_COL: frequency_hz_from_dir_name(freq_x_dir.name),
                    Y_FREQ_COL: frequency_hz_from_dir_name(freq_y_dir.name),
                    MEAN_INTEGRAL_COL: result.mean_integral_vs,
                    STD_INTEGRAL_COL: result.std_integral_vs,
                    MIN_INTEGRAL_COL: result.min_integral_vs,
                    MAX_INTEGRAL_COL: result.max_integral_vs,
                    VALID_TRIAL_COUNT_COL: result.valid_trial_count,
                    "trial_indices_used": ";".join(str(i) for i in result.trial_indices),
                    "trial_integrals_vs": ";".join(f"{v:.12e}" for v in result.trial_integrals_vs),
                    RUN_NAME_COL: average_case.run_name,
                }
            )

    if not rows:
        raise FileNotFoundError(
            f"No valid frequency-pair averages were found for st_{st_x_index} and st_{st_y_index} "
            f"under {Path(resolved_input_root).resolve()}"
        )

    df = pd.DataFrame(rows)
    df = df.sort_values([X_FREQ_COL, Y_FREQ_COL]).reset_index(drop=True)
    return df


def build_pivot_grid(df_values: pd.DataFrame) -> pd.DataFrame:
    pivot = df_values.pivot(
        index=Y_FREQ_COL,
        columns=X_FREQ_COL,
        values=MEAN_INTEGRAL_COL,
    )
    return pivot.sort_index(axis=0).sort_index(axis=1)


def make_custom_heatmap_colormap() -> LinearSegmentedColormap:
    colors = [
        "#000000",  # black at 0
        "#3B0066",  # deep purple
        "#4B0082",  # purple / indigo
        "#2358FF",  # saturated blue
        "#FF8C00",  # orange
        "#FFF6B0",  # bright whitish yellow
        "#FFFFFF",  # white
    ]
    cmap = LinearSegmentedColormap.from_list(
        "black_purple_blue_orange_yellow_white_v6",
        colors,
        N=256,
    )
    cmap.set_bad(color="#000000")
    return cmap


def compute_bin_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)

    if values.ndim != 1:
        raise ValueError("values must be a 1D array.")
    if values.size == 0:
        raise ValueError("values must not be empty.")

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
    x_values = pivot_df.columns.to_numpy(dtype=float)
    y_values = pivot_df.index.to_numpy(dtype=float)
    z_values = pivot_df.to_numpy(dtype=float)

    x_edges = compute_bin_edges(x_values)
    y_edges = compute_bin_edges(y_values)

    X_edges, Y_edges = np.meshgrid(x_edges, y_edges)

    fig, ax = plt.subplots(figsize=(10, 8))

    mesh = ax.pcolormesh(
        X_edges,
        Y_edges,
        z_values,
        shading="auto",
        cmap=make_custom_heatmap_colormap(),
        vmin=0.0,
    )

    ax.set_xlabel(f"Frequency of spike train {st_x_index} (Hz)")
    ax.set_ylabel(f"Frequency of spike train {st_y_index} (Hz)")
    ax.set_title(
        "Averaged integrated voltage-difference heatmap\n"
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
    return output_dir / f"heatmap_avg_v6_st{st_x_index}_vs_st{st_y_index}"


def generate_average_heatmap_outputs(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
    output_dir: Path | None = None,
    show: bool = False,
) -> dict[str, Path | pd.DataFrame]:
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

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--st-x-index", type=int, default=1)
    parser.add_argument("--st-y-index", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--show", action="store_true")

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
    print(f"Valid averaged frequency pairs plotted: {len(outputs['values_df'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
