#!/usr/bin/env python3
"""
topo_heatmap_v7.py

Purpose
-------
Make a 3D topographical heatmap for two selected spike trains.

Axes:
    x-axis -> frequency of spike train X
    y-axis -> frequency of spike train Y
    z-axis -> averaged integrated voltage-difference scalar across all valid
              matching trials for that frequency pair

Color scale:
    black at 0 -> purple -> blue -> orange -> bright whitish yellow -> white

This script is designed to make a plot similar to a 3D topographical terrain
view: the heatmap value is both the height and the surface color.

Expected location
-----------------
Place this file in:

    processing/previews/

Also place avg_integral_v6.py in:

    processing/previews/

Default input
-------------
The default input is resolved relative to this file:

    processing/sim_run_code/spike_train_output_csv

Default output
--------------
The default output directory is:

    processing/previews/topo_heatmap_outputs_v7/

CLI examples
------------
From the repository root:

    python processing/previews/topo_heatmap_v7.py

    python processing/previews/topo_heatmap_v7.py --st-x-index 1 --st-y-index 2

    python processing/previews/topo_heatmap_v7.py --show

    python processing/previews/topo_heatmap_v7.py --elev 35 --azim -135

    python processing/previews/topo_heatmap_v7.py --wireframe

    python processing/previews/topo_heatmap_v7.py --scatter-points

Outputs
-------
For st_1 vs st_2, this saves:

    topo_heatmap_v7_st1_vs_st2_3d.png
    topo_heatmap_v7_st1_vs_st2_2d.png
    topo_heatmap_v7_st1_vs_st2_values.csv
    topo_heatmap_v7_st1_vs_st2_pivot.csv

Notes
-----
- If more than two st_N directories exist in spike_train_output_csv, this
  script uses only the two selected ones and ignores the rest.
- Trial mixing is disabled.
- The plotted scalar is averaged across all valid matching trials.
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
    return Path(__file__).resolve().parent / "topo_heatmap_outputs_v7"


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


def make_topographical_colormap() -> LinearSegmentedColormap:
    """
    Requested ramp:
        black at 0 -> purple -> blue -> orange -> bright whitish yellow -> white
    """
    colors = [
        "#000000",  # black at 0
        "#220033",  # near-black violet
        "#4B0082",  # purple / indigo
        "#2358FF",  # saturated blue
        "#9B2FAE",  # violet transition
        "#FF5A1F",  # red-orange
        "#FFB000",  # orange / amber
        "#FFF6B0",  # bright whitish yellow
        "#FFFFFF",  # white
    ]
    cmap = LinearSegmentedColormap.from_list(
        "topographical_black_purple_blue_orange_white_v7",
        colors,
        N=512,
    )
    cmap.set_bad(color="#000000")
    return cmap


def meshgrid_from_pivot(pivot_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_values = pivot_df.columns.to_numpy(dtype=float)
    y_values = pivot_df.index.to_numpy(dtype=float)
    X, Y = np.meshgrid(x_values, y_values)
    Z = pivot_df.to_numpy(dtype=float)
    return X, Y, Z


def create_3d_topographical_heatmap(
    pivot_df: pd.DataFrame,
    st_x_index: int,
    st_y_index: int,
    output_path: Path,
    elev: float = 35.0,
    azim: float = -135.0,
    show: bool = False,
    add_wireframe: bool = True,
    add_scatter_points: bool = True,
) -> None:
    """
    Create a 3D topographical surface where color and height both represent the
    averaged scalar.
    """
    X, Y, Z = meshgrid_from_pivot(pivot_df)

    if np.isnan(Z).all():
        raise ValueError("The pivot grid contains only NaN values.")

    Z_masked = np.ma.masked_invalid(Z)
    cmap = make_topographical_colormap()

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection="3d")

    surface = ax.plot_surface(
        X,
        Y,
        Z_masked,
        cmap=cmap,
        vmin=0.0,
        linewidth=0,
        antialiased=True,
        alpha=0.96,
    )

    if add_wireframe:
        ax.plot_wireframe(
            X,
            Y,
            Z_masked,
            linewidth=0.35,
            alpha=0.35,
        )

    if add_scatter_points:
        finite_mask = np.isfinite(Z)
        ax.scatter(
            X[finite_mask],
            Y[finite_mask],
            Z[finite_mask],
            c=Z[finite_mask],
            cmap=cmap,
            vmin=0.0,
            edgecolors="black",
            linewidths=0.4,
            s=35,
            depthshade=True,
        )

    z_min = 0.0
    z_max = float(np.nanmax(Z))
    z_range = z_max - z_min
    contour_offset = z_min - 0.08 * z_range if z_range > 0 else z_min - 1.0e-12

    ax.contour(
        X,
        Y,
        Z,
        zdir="z",
        offset=contour_offset,
        levels=15,
        cmap=cmap,
        vmin=0.0,
    )

    ax.set_zlim(contour_offset, z_max if z_max > 0 else 1.0e-12)

    ax.set_xlabel(f"st{st_x_index} frequency / Hz", labelpad=10)
    ax.set_ylabel(f"st{st_y_index} frequency / Hz", labelpad=10)
    ax.set_zlabel("Mean integrated excess voltage / V·s", labelpad=10)

    ax.set_title(
        "Topographical heatmap of averaged integrated voltage difference\n"
        f"st_{st_x_index} vs st_{st_y_index}"
    )

    ax.view_init(elev=elev, azim=azim)

    cbar = fig.colorbar(surface, ax=ax, shrink=0.7, pad=0.08)
    cbar.set_label("Mean integrated excess voltage / V·s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


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


def create_2d_heatmap(
    pivot_df: pd.DataFrame,
    st_x_index: int,
    st_y_index: int,
    output_path: Path,
    show: bool = False,
) -> None:
    """
    Also save a flat 2D heatmap, useful for reading values without perspective
    distortion.
    """
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
        cmap=make_topographical_colormap(),
        vmin=0.0,
    )

    ax.set_xlabel(f"st{st_x_index} frequency / Hz")
    ax.set_ylabel(f"st{st_y_index} frequency / Hz")
    ax.set_title(
        "2D heatmap of averaged integrated voltage difference\n"
        f"st_{st_x_index} vs st_{st_y_index}"
    )

    ax.set_xticks(x_values)
    ax.set_yticks(y_values)

    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Mean integrated excess voltage / V·s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_default_output_stem(output_dir: Path, st_x_index: int, st_y_index: int) -> Path:
    return output_dir / f"topo_heatmap_v7_st{st_x_index}_vs_st{st_y_index}"


def generate_topographical_heatmap_outputs(
    input_root: Path | None = None,
    st_x_index: int = 1,
    st_y_index: int = 2,
    output_dir: Path | None = None,
    show: bool = False,
    elev: float = 35.0,
    azim: float = -135.0,
    add_wireframe: bool = True,
    add_scatter_points: bool = True,
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

    plot_3d_path = output_stem.with_name(output_stem.name + "_3d").with_suffix(".png")
    plot_2d_path = output_stem.with_name(output_stem.name + "_2d").with_suffix(".png")
    values_csv_path = output_stem.with_name(output_stem.name + "_values").with_suffix(".csv")
    pivot_csv_path = output_stem.with_name(output_stem.name + "_pivot").with_suffix(".csv")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    values_df.to_csv(values_csv_path, index=False)
    pivot_df.to_csv(pivot_csv_path)

    create_3d_topographical_heatmap(
        pivot_df=pivot_df,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
        output_path=plot_3d_path,
        elev=elev,
        azim=azim,
        show=show,
        add_wireframe=add_wireframe,
        add_scatter_points=add_scatter_points,
    )

    create_2d_heatmap(
        pivot_df=pivot_df,
        st_x_index=st_x_index,
        st_y_index=st_y_index,
        output_path=plot_2d_path,
        show=False,
    )

    return {
        "values_df": values_df,
        "pivot_df": pivot_df,
        "plot_3d_path": plot_3d_path,
        "plot_2d_path": plot_2d_path,
        "values_csv_path": values_csv_path,
        "pivot_csv_path": pivot_csv_path,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Make a 3D topographical heatmap of averaged integrated voltage difference."
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--st-x-index", type=int, default=1)
    parser.add_argument("--st-y-index", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--show", action="store_true")

    parser.add_argument(
        "--elev",
        type=float,
        default=35.0,
        help="3D view elevation angle in degrees. Default: 35.",
    )
    parser.add_argument(
        "--azim",
        type=float,
        default=-135.0,
        help="3D view azimuth angle in degrees. Default: -135.",
    )
    parser.add_argument(
        "--no-wireframe",
        action="store_true",
        help="Disable the faint surface wireframe.",
    )
    parser.add_argument(
        "--no-scatter-points",
        action="store_true",
        help="Disable circular markers at measured grid points.",
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    outputs = generate_topographical_heatmap_outputs(
        input_root=args.input_root,
        st_x_index=args.st_x_index,
        st_y_index=args.st_y_index,
        output_dir=args.output_dir,
        show=args.show,
        elev=args.elev,
        azim=args.azim,
        add_wireframe=not args.no_wireframe,
        add_scatter_points=not args.no_scatter_points,
    )

    print(f"Saved 3D topographical heatmap to: {outputs['plot_3d_path']}")
    print(f"Saved 2D heatmap to: {outputs['plot_2d_path']}")
    print(f"Saved long-form values CSV to: {outputs['values_csv_path']}")
    print(f"Saved pivot-grid CSV to: {outputs['pivot_csv_path']}")
    print(f"Grid shape (y, x): {outputs['pivot_df'].shape}")
    print(f"Valid averaged frequency pairs plotted: {len(outputs['values_df'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
