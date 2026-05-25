#!/usr/bin/env python3
"""
heatmap_nd_v9.py

Purpose
-------
Visualise the averaged integrated voltage-difference scalar while using all
available spike trains.

Behaviour by number of discovered spike-train directories
---------------------------------------------------------
- If exactly 2 spike trains are discovered:
    produce a 2D heatmap
        x-axis = frequency of st_1
        y-axis = frequency of st_2
        color  = averaged scalar across valid matching trials

- If 3 or more spike trains are discovered:
    produce a 3D scatter "cloud"
        x-axis = frequency of st_1
        y-axis = frequency of st_2
        z-axis = frequency of st_3
        color  = averaged scalar across valid matching trials

- If 4 or more spike trains are discovered:
    st_4, st_5, ..., st_n are included in the waveform sum, but each is fixed
    at its lowest available frequency directory.

Most important semantic point
-----------------------------
This script always computes the scalar using *all* discovered spike trains.

Example with 3 spike trains:
    df_sum = st_1 + st_2 + st_3
    df_capped = cap(df_sum, 1.8 V)
    df_difference = df_sum - df_capped
    scalar = integral(df_difference)

Example with 5 spike trains:
    st_1, st_2, st_3 vary
    st_4, st_5 fixed at their lowest frequency
    df_sum = st_1 + st_2 + st_3 + st_4_fixed + st_5_fixed
    ...
    scalar = average across valid matching trials

Display behaviour
-----------------
By default the script opens an interactive matplotlib window with plt.show(),
so you can inspect and rotate the plot.

Expected location
-----------------
Place this file in:

    processing/previews/

Also place avg_integral_v7.py in the same directory.

Default input
-------------
Resolved relative to this file:

    processing/sim_run_code/spike_train_output_csv
"""

from __future__ import annotations

import argparse
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from avg_integral_v7 import (
    TIME_COL,
    VOLTAGE_COL,
    SUM_COL,
    CAPPED_SUM_COL,
    DIFFERENCE_COL,
    MEAN_INTEGRAL_COL,
    STD_INTEGRAL_COL,
    MIN_INTEGRAL_COL,
    MAX_INTEGRAL_COL,
    VALID_TRIAL_COUNT_COL,
    SpikeTrainDirectory,
    build_capped_sibling_dataframe,
    build_difference_dataframe,
    default_input_root,
    discover_spike_train_dirs,
    discover_trial_names,
    frequency_hz_from_dir_name,
    integrate_difference_transient,
    load_two_column_voltage_csv,
    align_to_union_time_grid,
)

RUN_NAME_COL = "run_name"
X_FREQ_COL = "frequency_st1_hz"
Y_FREQ_COL = "frequency_st2_hz"
Z_FREQ_COL = "frequency_st3_hz"

TRIAL_FILE_RE = re.compile(r"^trial_(\d+)\.csv$")
DEFAULT_PROGRESS_EVERY = 25


@dataclass(frozen=True)
class SweepCase:
    run_name: str
    trial_name: str
    trial_index: int
    csv_paths: tuple[Path, ...]
    frequency_names: tuple[str, ...]
    frequency_values_hz: tuple[int, ...]
    st_indices: tuple[int, ...]


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "heatmap_nd_outputs_v9"


def make_colormap() -> LinearSegmentedColormap:
    colors = [
        "#000000",  # black
        "#220033",  # very dark violet
        "#4B0082",  # purple/indigo
        "#2358FF",  # blue
        "#9B2FAE",  # magenta-violet transition
        "#FF5A1F",  # orange-red
        "#FFB000",  # orange/amber
        "#FFF6B0",  # bright whitish yellow
        "#FFFFFF",  # white
    ]
    cmap = LinearSegmentedColormap.from_list("heatmap_nd_v9_cmap", colors, N=512)
    cmap.set_bad(color="#000000")
    return cmap


def choose_variable_and_fixed_spike_trains(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
) -> tuple[tuple[SpikeTrainDirectory, ...], tuple[SpikeTrainDirectory, ...]]:
    if len(spike_train_dirs) < 2:
        raise ValueError("At least 2 spike-train directories are required.")

    variable_count = 2 if len(spike_train_dirs) == 2 else 3
    variable = tuple(spike_train_dirs[:variable_count])
    fixed = tuple(spike_train_dirs[variable_count:])
    return variable, fixed


def choose_lowest_frequency_dir(st_dir: SpikeTrainDirectory) -> Path:
    if not st_dir.frequency_dirs:
        raise FileNotFoundError(f"No frequency directories found for st_{st_dir.st_index}")
    return st_dir.frequency_dirs[0]


def build_summed_voltage_dataframe_from_paths(csv_paths: Sequence[Path]) -> pd.DataFrame:
    input_dfs = [load_two_column_voltage_csv(path) for path in csv_paths]
    common_time, aligned_voltages = align_to_union_time_grid(input_dfs)
    summed_voltage = np.sum(np.vstack(aligned_voltages), axis=0)

    return pd.DataFrame(
        {
            TIME_COL: common_time,
            SUM_COL: summed_voltage,
        }
    )


def compute_integral_from_csv_paths(csv_paths: Sequence[Path]) -> float:
    df_sum = build_summed_voltage_dataframe_from_paths(csv_paths)
    df_capped = build_capped_sibling_dataframe(df_sum)
    df_difference = build_difference_dataframe(df_sum, df_capped)
    return integrate_difference_transient(df_difference)


def iter_sweep_cases_for_frequency_setting(
    chosen_frequency_dirs: Sequence[Path],
    chosen_st_indices: Sequence[int],
    trial_names: Sequence[str],
) -> Iterator[SweepCase]:
    frequency_names = tuple(freq_dir.name for freq_dir in chosen_frequency_dirs)
    frequency_values_hz = tuple(frequency_hz_from_dir_name(name) for name in frequency_names)

    run_name_base = "__".join(
        f"st{st_index}_{freq_name}"
        for st_index, freq_name in zip(chosen_st_indices, frequency_names, strict=True)
    )

    for trial_name in trial_names:
        match = TRIAL_FILE_RE.match(trial_name)
        if match is None:
            continue

        csv_paths = tuple(freq_dir / trial_name for freq_dir in chosen_frequency_dirs)
        if not all(path.is_file() for path in csv_paths):
            continue

        yield SweepCase(
            run_name=f"{run_name_base}__{trial_name.removesuffix('.csv')}",
            trial_name=trial_name,
            trial_index=int(match.group(1)),
            csv_paths=csv_paths,
            frequency_names=frequency_names,
            frequency_values_hz=frequency_values_hz,
            st_indices=tuple(chosen_st_indices),
        )


def compute_average_scalar_for_frequency_setting(
    chosen_frequency_dirs: Sequence[Path],
    chosen_st_indices: Sequence[int],
    trial_names: Sequence[str],
) -> dict[str, object] | None:
    trial_integrals: list[float] = []
    trial_indices: list[int] = []

    last_case: SweepCase | None = None

    for case in iter_sweep_cases_for_frequency_setting(
        chosen_frequency_dirs=chosen_frequency_dirs,
        chosen_st_indices=chosen_st_indices,
        trial_names=trial_names,
    ):
        trial_integrals.append(compute_integral_from_csv_paths(case.csv_paths))
        trial_indices.append(case.trial_index)
        last_case = case

    if not trial_integrals or last_case is None:
        return None

    values = np.asarray(trial_integrals, dtype=float)

    row: dict[str, object] = {
        RUN_NAME_COL: "__".join(
            f"st{st_index}_{freq_name}"
            for st_index, freq_name in zip(
                last_case.st_indices,
                last_case.frequency_names,
                strict=True,
            )
        ),
        MEAN_INTEGRAL_COL: float(np.mean(values)),
        STD_INTEGRAL_COL: float(np.std(values, ddof=0)),
        MIN_INTEGRAL_COL: float(np.min(values)),
        MAX_INTEGRAL_COL: float(np.max(values)),
        VALID_TRIAL_COUNT_COL: int(values.size),
        "trial_indices_used": ";".join(str(i) for i in trial_indices),
        "trial_integrals_vs": ";".join(f"{v:.12e}" for v in values),
    }

    for st_index, freq_name, freq_hz in zip(
        last_case.st_indices,
        last_case.frequency_names,
        last_case.frequency_values_hz,
        strict=True,
    ):
        row[f"st_{st_index}_frequency_name"] = freq_name
        row[f"st_{st_index}_frequency_hz"] = freq_hz

    return row



def format_progress_line(done: int, total: int, prefix: str = "Progress") -> str:
    """Return a compact terminal progress line."""
    if total <= 0:
        return f"{prefix}: {done}"
    percent = 100.0 * done / total
    return f"{prefix}: {done}/{total} ({percent:6.2f}%)"


def should_print_progress(done: int, total: int, progress_every: int) -> bool:
    """Decide whether to print a progress line."""
    if done <= 0:
        return False
    if done == total:
        return True
    return progress_every > 0 and done % progress_every == 0


def count_variable_frequency_settings(variable_spike_trains: Sequence[SpikeTrainDirectory]) -> int:
    """Return the number of variable frequency settings to evaluate."""
    total = 1
    for st_dir in variable_spike_trains:
        total *= len(st_dir.frequency_dirs)
    return total


def compute_visualisation_dataframe(
    input_root: Path | None = None,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> tuple[pd.DataFrame, dict[str, object]]:
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)

    variable_spike_trains, fixed_spike_trains = choose_variable_and_fixed_spike_trains(spike_train_dirs)
    trial_names = discover_trial_names(spike_train_dirs)

    variable_frequency_lists = [st_dir.frequency_dirs for st_dir in variable_spike_trains]
    fixed_frequency_dirs = [choose_lowest_frequency_dir(st_dir) for st_dir in fixed_spike_trains]

    variable_st_indices = [st_dir.st_index for st_dir in variable_spike_trains]
    fixed_st_indices = [st_dir.st_index for st_dir in fixed_spike_trains]

    rows: list[dict[str, object]] = []
    total_settings = count_variable_frequency_settings(variable_spike_trains)
    processed_settings = 0

    if progress:
        print(format_progress_line(0, total_settings, prefix='Frequency-grid progress'))

    for variable_frequency_dirs in itertools.product(*variable_frequency_lists):
        chosen_frequency_dirs = list(variable_frequency_dirs) + fixed_frequency_dirs
        chosen_st_indices = variable_st_indices + fixed_st_indices

        row = compute_average_scalar_for_frequency_setting(
            chosen_frequency_dirs=chosen_frequency_dirs,
            chosen_st_indices=chosen_st_indices,
            trial_names=trial_names,
        )
        processed_settings += 1

        if row is None:
            if progress and should_print_progress(processed_settings, total_settings, progress_every):
                print(format_progress_line(processed_settings, total_settings, prefix='Frequency-grid progress'))
            continue

        row[X_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[0].name)
        row[Y_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[1].name)

        if len(variable_spike_trains) >= 3:
            row[Z_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[2].name)

        rows.append(row)

        if progress and should_print_progress(processed_settings, total_settings, progress_every):
            print(format_progress_line(processed_settings, total_settings, prefix='Frequency-grid progress'))

    if not rows:
        raise FileNotFoundError("No valid average results could be generated for the current configuration.")

    df = pd.DataFrame(rows)
    sort_cols = [X_FREQ_COL, Y_FREQ_COL] + ([Z_FREQ_COL] if Z_FREQ_COL in df.columns else [])
    df = df.sort_values(sort_cols).reset_index(drop=True)

    metadata = {
        "input_root": resolved_input_root.resolve(),
        "spike_train_count": len(spike_train_dirs),
        "variable_spike_trains": tuple(st_dir.st_index for st_dir in variable_spike_trains),
        "fixed_spike_trains": tuple(st_dir.st_index for st_dir in fixed_spike_trains),
        "fixed_frequency_names": tuple(freq_dir.name for freq_dir in fixed_frequency_dirs),
        "mode": "2d" if len(variable_spike_trains) == 2 else "3d",
        "frequency_settings_evaluated": processed_settings,
        "frequency_settings_total": total_settings,
    }

    return df, metadata


def build_2d_pivot(df: pd.DataFrame) -> pd.DataFrame:
    pivot = df.pivot(
        index=Y_FREQ_COL,
        columns=X_FREQ_COL,
        values=MEAN_INTEGRAL_COL,
    )
    return pivot.sort_index(axis=0).sort_index(axis=1)


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
    df_values: pd.DataFrame,
    metadata: dict[str, object],
    output_path: Path,
    show: bool = True,
) -> None:
    pivot_df = build_2d_pivot(df_values)
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
        cmap=make_colormap(),
        vmin=0.0,
    )

    ax.set_xlabel(f"st{metadata['variable_spike_trains'][0]} frequency / Hz")
    ax.set_ylabel(f"st{metadata['variable_spike_trains'][1]} frequency / Hz")
    ax.set_title("2D heatmap of averaged integrated voltage difference")

    if metadata["fixed_spike_trains"]:
        fixed_desc = ", ".join(
            f"st{st}={freq}"
            for st, freq in zip(
                metadata["fixed_spike_trains"],
                metadata["fixed_frequency_names"],
                strict=True,
            )
        )
        ax.set_title(
            "2D heatmap of averaged integrated voltage difference\n"
            f"Fixed extra spike trains: {fixed_desc}"
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


def create_3d_scatter_heatmap(
    df_values: pd.DataFrame,
    metadata: dict[str, object],
    output_path: Path,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
) -> None:
    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")

    x = df_values[X_FREQ_COL].to_numpy(dtype=float)
    y = df_values[Y_FREQ_COL].to_numpy(dtype=float)
    z = df_values[Z_FREQ_COL].to_numpy(dtype=float)
    c = df_values[MEAN_INTEGRAL_COL].to_numpy(dtype=float)

    size = np.full_like(c, 60.0, dtype=float)
    if np.nanmax(c) > 0:
        size = 40.0 + 140.0 * (c / np.nanmax(c))

    scatter = ax.scatter(
        x,
        y,
        z,
        c=c,
        s=size,
        cmap=make_colormap(),
        vmin=0.0,
        alpha=0.9,
        edgecolors="black",
        linewidths=0.4,
        depthshade=True,
    )

    ax.set_xlabel(f"st{metadata['variable_spike_trains'][0]} frequency / Hz", labelpad=10)
    ax.set_ylabel(f"st{metadata['variable_spike_trains'][1]} frequency / Hz", labelpad=10)
    ax.set_zlabel(f"st{metadata['variable_spike_trains'][2]} frequency / Hz", labelpad=10)

    title = "3D scatter heatmap of averaged integrated voltage difference"
    if metadata["fixed_spike_trains"]:
        fixed_desc = ", ".join(
            f"st{st}={freq}"
            for st, freq in zip(
                metadata["fixed_spike_trains"],
                metadata["fixed_frequency_names"],
                strict=True,
            )
        )
        title += f"\nFixed extra spike trains: {fixed_desc}"
    ax.set_title(title)

    ax.view_init(elev=elev, azim=azim)

    cbar = fig.colorbar(scatter, ax=ax, pad=0.08, shrink=0.75)
    cbar.set_label("Mean integrated excess voltage / V·s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_output_stem(metadata: dict[str, object], output_dir: Path) -> Path:
    var = "_".join(f"st{idx}" for idx in metadata["variable_spike_trains"])
    return output_dir / f"heatmap_nd_v9_{metadata['mode']}_{var}"


def generate_visualisation(
    input_root: Path | None = None,
    output_dir: Path | None = None,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> dict[str, object]:
    df_values, metadata = compute_visualisation_dataframe(
        input_root=input_root,
        progress=progress,
        progress_every=progress_every,
    )

    resolved_output_dir = default_output_dir() if output_dir is None else Path(output_dir)
    stem = make_output_stem(metadata, resolved_output_dir)

    values_csv_path = stem.with_name(stem.name + "_values").with_suffix(".csv")
    values_png_path = stem.with_suffix(".png")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    df_values.to_csv(values_csv_path, index=False)

    if metadata["mode"] == "2d":
        pivot_df = build_2d_pivot(df_values)
        pivot_csv_path = stem.with_name(stem.name + "_pivot").with_suffix(".csv")
        pivot_df.to_csv(pivot_csv_path)

        create_2d_heatmap(
            df_values=df_values,
            metadata=metadata,
            output_path=values_png_path,
            show=show,
        )
    else:
        pivot_csv_path = None
        create_3d_scatter_heatmap(
            df_values=df_values,
            metadata=metadata,
            output_path=values_png_path,
            show=show,
            elev=elev,
            azim=azim,
        )

    return {
        "dataframe": df_values,
        "metadata": metadata,
        "values_csv_path": values_csv_path,
        "pivot_csv_path": pivot_csv_path,
        "plot_path": values_png_path,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a 2D or 3D heatmap-style matplotlib visualisation using all "
            "spike trains. If 4 or more spike trains exist, spike trains 4..n "
            "are fixed at their lowest frequency."
        )
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the interactive matplotlib popup window.",
    )
    parser.add_argument(
        "--elev",
        type=float,
        default=25.0,
        help="3D elevation angle, used only in 3D mode.",
    )
    parser.add_argument(
        "--azim",
        type=float,
        default=-55.0,
        help="3D azimuth angle, used only in 3D mode.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable terminal progress output.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help="Print progress every N frequency-grid settings. Default: 25.",
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    outputs = generate_visualisation(
        input_root=args.input_root,
        output_dir=args.output_dir,
        show=not args.no_show,
        elev=args.elev,
        azim=args.azim,
        progress=not args.no_progress,
        progress_every=args.progress_every,
    )

    metadata = outputs["metadata"]
    print(f"Input root: {metadata['input_root']}")
    print(f"Spike-train count: {metadata['spike_train_count']}")
    print(f"Mode: {metadata['mode']}")
    print(f"Variable spike trains: {metadata['variable_spike_trains']}")
    print(f"Fixed spike trains: {metadata['fixed_spike_trains']}")
    print(f"Fixed frequency names: {metadata['fixed_frequency_names']}")
    print(f"Frequency settings evaluated: {metadata['frequency_settings_evaluated']}/{metadata['frequency_settings_total']}")
    print(f"Saved plot to: {outputs['plot_path']}")
    print(f"Saved values CSV to: {outputs['values_csv_path']}")
    if outputs["pivot_csv_path"] is not None:
        print(f"Saved pivot CSV to: {outputs['pivot_csv_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
