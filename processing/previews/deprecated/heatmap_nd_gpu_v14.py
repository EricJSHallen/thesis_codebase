#!/usr/bin/env python3
"""
heatmap_nd_gpu_v14.py

GPU/Numba-aware version of heatmap_nd_v9.py.

Behaviour
---------
- If exactly 2 spike trains are discovered:
    creates a 2D heatmap.

- If 3 or more spike trains are discovered:
    creates a 3D scatter/cloud heatmap.

- If 4 or more spike trains are discovered:
    st_1, st_2, st_3 vary; st_4..st_n are included in the waveform sum but fixed
    at their lowest available frequency.

Backends
--------
Uses avg_integral_gpu_v9.py and supports:

    --backend auto
    --backend cpu
    --backend numba
    --backend cupy

The GPU/CuPy backend accelerates the dense cap/difference/integration kernel
after CSV loading and interpolation have already happened on the CPU.
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

from avg_integral_gpu_v9 import (
    TIME_COL,
    SUM_COL,
    MEAN_INTEGRAL_COL,
    STD_INTEGRAL_COL,
    MIN_INTEGRAL_COL,
    MAX_INTEGRAL_COL,
    VALID_TRIAL_COUNT_COL,
    ComputeBackend,
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
    return Path(__file__).resolve().parent / "heatmap_nd_gpu_outputs_v14"


def make_colormap() -> LinearSegmentedColormap:
    colors = [
        "#000000",
        "#220033",
        "#4B0082",
        "#2358FF",
        "#9B2FAE",
        "#FF5A1F",
        "#FFB000",
        "#FFF6B0",
        "#FFFFFF",
    ]
    cmap = LinearSegmentedColormap.from_list("heatmap_nd_gpu_v14_cmap", colors, N=512)
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


def compute_integral_from_csv_paths(csv_paths: Sequence[Path], backend: ComputeBackend) -> float:
    input_dfs = [load_two_column_voltage_csv(path) for path in csv_paths]
    common_time, aligned_voltages = align_to_union_time_grid(input_dfs)
    return backend.integrate_excess_from_aligned_arrays(common_time, aligned_voltages)


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
    backend: ComputeBackend,
) -> dict[str, object] | None:
    trial_integrals: list[float] = []
    trial_indices: list[int] = []
    last_case: SweepCase | None = None

    for case in iter_sweep_cases_for_frequency_setting(
        chosen_frequency_dirs=chosen_frequency_dirs,
        chosen_st_indices=chosen_st_indices,
        trial_names=trial_names,
    ):
        trial_integrals.append(compute_integral_from_csv_paths(case.csv_paths, backend=backend))
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
    if total <= 0:
        return f"{prefix}: {done}"
    percent = 100.0 * done / total
    return f"{prefix}: {done}/{total} ({percent:6.2f}%)"


def should_print_progress(done: int, total: int, progress_every: int) -> bool:
    if done <= 0:
        return False
    if done == total:
        return True
    return progress_every > 0 and done % progress_every == 0


def count_variable_frequency_settings(variable_spike_trains: Sequence[SpikeTrainDirectory]) -> int:
    total = 1
    for st_dir in variable_spike_trains:
        total *= len(st_dir.frequency_dirs)
    return total


def compute_visualisation_dataframe(
    input_root: Path | None = None,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    backend_name: str = "auto",
) -> tuple[pd.DataFrame, dict[str, object]]:
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
    backend = ComputeBackend(backend_name)

    variable_spike_trains, fixed_spike_trains = choose_variable_and_fixed_spike_trains(spike_train_dirs)
    trial_names = discover_trial_names(spike_train_dirs)

    variable_frequency_lists = [st_dir.frequency_dirs for st_dir in variable_spike_trains]
    fixed_frequency_dirs = [choose_lowest_frequency_dir(st_dir) for st_dir in fixed_spike_trains]

    variable_st_indices = [st_dir.st_index for st_dir in variable_spike_trains]
    fixed_st_indices = [st_dir.st_index for st_dir in fixed_spike_trains]

    rows: list[dict[str, object]] = []
    total_settings = count_variable_frequency_settings(variable_spike_trains)
    processed_settings = 0

    print(f"Requested backend: {backend_name}")
    print(f"Resolved backend: {backend.describe()}")

    if progress:
        print(format_progress_line(0, total_settings, prefix="Frequency-grid progress"))

    for variable_frequency_dirs in itertools.product(*variable_frequency_lists):
        chosen_frequency_dirs = list(variable_frequency_dirs) + fixed_frequency_dirs
        chosen_st_indices = variable_st_indices + fixed_st_indices

        row = compute_average_scalar_for_frequency_setting(
            chosen_frequency_dirs=chosen_frequency_dirs,
            chosen_st_indices=chosen_st_indices,
            trial_names=trial_names,
            backend=backend,
        )

        processed_settings += 1

        if row is None:
            if progress and should_print_progress(processed_settings, total_settings, progress_every):
                print(format_progress_line(processed_settings, total_settings, prefix="Frequency-grid progress"))
            continue

        row[X_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[0].name)
        row[Y_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[1].name)

        if len(variable_spike_trains) >= 3:
            row[Z_FREQ_COL] = frequency_hz_from_dir_name(variable_frequency_dirs[2].name)

        rows.append(row)

        if progress and should_print_progress(processed_settings, total_settings, progress_every):
            print(format_progress_line(processed_settings, total_settings, prefix="Frequency-grid progress"))

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
        "resolved_backend": backend.describe(),
    }

    return df, metadata


def build_2d_pivot(df: pd.DataFrame) -> pd.DataFrame:
    pivot = df.pivot(
        index="frequency_st2_hz",
        columns="frequency_st1_hz",
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

    nice_x_ticks = compute_nice_ticks(x_values, max_ticks=6)
    nice_y_ticks = compute_nice_ticks(y_values, max_ticks=6)

    ax.set_xlabel(f"st{metadata['variable_spike_trains'][0]} frequency / Hz")
    ax.set_ylabel(f"st{metadata['variable_spike_trains'][1]} frequency / Hz")
    ax.set_title("2D heatmap of averaged integrated voltage difference")
    ax.set_xticks(nice_x_ticks)
    ax.set_yticks(nice_y_ticks)

    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Mean integrated excess voltage / V·s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)



def compute_exponential_alpha(
    value: float,
    value_min: float,
    value_max: float,
    k: float = 6.0,
    alpha_floor: float = 0.04,
) -> float:
    """
    Exponential opacity mapping with a small opacity floor.

    Design goal:
        - highest values -> opacity 1
        - middle values -> small but nonzero opacity
        - low values -> approximately 0, but still slightly more visible than
          in the previous version

    Let t be the normalized value in [0, 1].
    Base mapping:
        base_alpha = exp(k * (t - 1))

    Then lift everything slightly:
        alpha = alpha_floor + (1 - alpha_floor) * base_alpha
    """
    if value_max <= value_min:
        return 1.0

    t = (value - value_min) / (value_max - value_min)
    t = float(np.clip(t, 0.0, 1.0))
    base_alpha = float(np.exp(k * (t - 1.0)))
    alpha = alpha_floor + (1.0 - alpha_floor) * base_alpha
    return float(np.clip(alpha, 0.0, 1.0))


def compute_nice_step(raw_step: float) -> float:
    """
    Convert a raw step size into a visually nicer rounded step.
    """
    if raw_step <= 0:
        return 1.0

    exponent = np.floor(np.log10(raw_step))
    fraction = raw_step / (10.0 ** exponent)

    if fraction <= 1.0:
        nice_fraction = 1.0
    elif fraction <= 2.0:
        nice_fraction = 2.0
    elif fraction <= 2.5:
        nice_fraction = 2.5
    elif fraction <= 5.0:
        nice_fraction = 5.0
    else:
        nice_fraction = 10.0

    return float(nice_fraction * (10.0 ** exponent))


def compute_nice_ticks(
    values: np.ndarray,
    max_ticks: int = 6,
) -> np.ndarray:
    """
    Compute a reduced set of clean-looking ticks for an axis.

    The ticks are chosen from a rounded step size and need not match the exact
    data values. This is intentional, to avoid cluttered or odd-looking tick
    labels when the underlying frequency samples are irregular.
    """
    values = np.asarray(values, dtype=float)

    if values.size == 0:
        return np.array([], dtype=float)

    vmin = float(np.min(values))
    vmax = float(np.max(values))

    if np.isclose(vmin, vmax):
        return np.array([vmin], dtype=float)

    raw_step = (vmax - vmin) / max(1, max_ticks - 1)
    step = compute_nice_step(raw_step)

    tick_start = np.ceil(vmin / step) * step
    tick_end = np.floor(vmax / step) * step

    if tick_end < tick_start:
        return np.array([vmin, vmax], dtype=float)

    ticks = np.arange(tick_start, tick_end + 0.5 * step, step, dtype=float)

    if ticks.size < 2:
        ticks = np.array([vmin, vmax], dtype=float)

    # Round for stable, clean labels.
    ticks = np.round(ticks, decimals=8)

    return ticks


def create_3d_cube_heatmap(
    df_values: pd.DataFrame,
    metadata: dict[str, object],
    output_path: Path,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
) -> None:
    """
    Create a 3D heatmap in which each sampled frequency point is rendered as a
    cube occupying its full cell in the frequency grid.

    Cube placement:
        - x, y, z axes are the three varying spike-train frequencies.
        - each cube spans the full bin width in x, y, and z so that adjacent
          cubes touch and there is no empty space between neighboring cells.

    Visual encoding:
        - color is mapped from the averaged scalar value
        - opacity (alpha) follows an exponential mapping so that:
            highest scalar values are opaque
            middle values are close to 0 but still visible
            low values are approximately 0
    """
    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")

    x_vals = np.sort(df_values[X_FREQ_COL].unique().astype(float))
    y_vals = np.sort(df_values[Y_FREQ_COL].unique().astype(float))
    z_vals = np.sort(df_values[Z_FREQ_COL].unique().astype(float))

    x_edges = compute_bin_edges(x_vals)
    y_edges = compute_bin_edges(y_vals)
    z_edges = compute_bin_edges(z_vals)

    x_index = {float(v): i for i, v in enumerate(x_vals)}
    y_index = {float(v): i for i, v in enumerate(y_vals)}
    z_index = {float(v): i for i, v in enumerate(z_vals)}

    c = df_values[MEAN_INTEGRAL_COL].to_numpy(dtype=float)
    c_min = float(np.nanmin(c))
    c_max = float(np.nanmax(c))

    cmap = make_colormap()
    norm = plt.Normalize(vmin=0.0, vmax=c_max if c_max > 0 else 1.0)

    bar_x = []
    bar_y = []
    bar_z = []
    bar_dx = []
    bar_dy = []
    bar_dz = []
    bar_colors = []

    for _, row in df_values.iterrows():
        xv = float(row[X_FREQ_COL])
        yv = float(row[Y_FREQ_COL])
        zv = float(row[Z_FREQ_COL])
        val = float(row[MEAN_INTEGRAL_COL])

        ix = x_index[xv]
        iy = y_index[yv]
        iz = z_index[zv]

        x0 = x_edges[ix]
        y0 = y_edges[iy]
        z0 = z_edges[iz]

        dx = x_edges[ix + 1] - x_edges[ix]
        dy = y_edges[iy + 1] - y_edges[iy]
        dz = z_edges[iz + 1] - z_edges[iz]

        alpha = compute_exponential_alpha(
            value=val,
            value_min=c_min,
            value_max=c_max,
            k=6.0,
        )

        rgba = list(cmap(norm(val)))
        rgba[3] = float(np.clip(alpha, 0.0, 1.0))

        bar_x.append(x0)
        bar_y.append(y0)
        bar_z.append(z0)
        bar_dx.append(dx)
        bar_dy.append(dy)
        bar_dz.append(dz)
        bar_colors.append(tuple(rgba))

    collection = ax.bar3d(
        np.asarray(bar_x, dtype=float),
        np.asarray(bar_y, dtype=float),
        np.asarray(bar_z, dtype=float),
        np.asarray(bar_dx, dtype=float),
        np.asarray(bar_dy, dtype=float),
        np.asarray(bar_dz, dtype=float),
        color=bar_colors,
        shade=True,
        zsort="average",
        edgecolor="none",
        linewidth=0.0,
    )

    ax.set_xlim(x_edges[0], x_edges[-1])
    ax.set_ylim(y_edges[0], y_edges[-1])
    ax.set_zlim(z_edges[0], z_edges[-1])

    nice_x_ticks = compute_nice_ticks(x_vals, max_ticks=5)
    nice_y_ticks = compute_nice_ticks(y_vals, max_ticks=5)
    nice_z_ticks = compute_nice_ticks(z_vals, max_ticks=5)

    ax.set_xticks(nice_x_ticks)
    ax.set_yticks(nice_y_ticks)
    ax.set_zticks(nice_z_ticks)

    ax.set_xlabel(f"st{metadata['variable_spike_trains'][0]} frequency / Hz", labelpad=10)
    ax.set_ylabel(f"st{metadata['variable_spike_trains'][1]} frequency / Hz", labelpad=10)
    ax.set_zlabel(f"st{metadata['variable_spike_trains'][2]} frequency / Hz", labelpad=10)

    title = "3D cube heatmap of averaged integrated voltage difference"
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

    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array(c)
    cbar = fig.colorbar(mappable, ax=ax, pad=0.08, shrink=0.75)
    cbar.set_label("Mean integrated excess voltage / V·s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_output_stem(metadata: dict[str, object], output_dir: Path) -> Path:
    var = "_".join(f"st{idx}" for idx in metadata["variable_spike_trains"])
    return output_dir / f"heatmap_nd_gpu_v14_{metadata['mode']}_{var}"


def generate_visualisation(
    input_root: Path | None = None,
    output_dir: Path | None = None,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    backend_name: str = "auto",
) -> dict[str, object]:
    df_values, metadata = compute_visualisation_dataframe(
        input_root=input_root,
        progress=progress,
        progress_every=progress_every,
        backend_name=backend_name,
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

        create_2d_heatmap(df_values=df_values, metadata=metadata, output_path=values_png_path, show=show)
    else:
        pivot_csv_path = None
        create_3d_cube_heatmap(
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


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "heatmap_nd_gpu_outputs_v14"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a 2D or 3D heatmap-style matplotlib visualisation using all spike trains."
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--backend", choices=["auto", "cpu", "numba", "cupy"], default="auto")
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--elev", type=float, default=25.0)
    parser.add_argument("--azim", type=float, default=-55.0)
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)

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
        backend_name=args.backend,
    )

    metadata = outputs["metadata"]
    print(f"Input root: {metadata['input_root']}")
    print(f"Spike-train count: {metadata['spike_train_count']}")
    print(f"Mode: {metadata['mode']}")
    print(f"Variable spike trains: {metadata['variable_spike_trains']}")
    print(f"Fixed spike trains: {metadata['fixed_spike_trains']}")
    print(f"Fixed frequency names: {metadata['fixed_frequency_names']}")
    print(f"Frequency settings evaluated: {metadata['frequency_settings_evaluated']}/{metadata['frequency_settings_total']}")
    print(f"Resolved backend: {metadata['resolved_backend']}")
    print(f"Saved plot to: {outputs['plot_path']}")
    print(f"Saved values CSV to: {outputs['values_csv_path']}")
    if outputs["pivot_csv_path"] is not None:
        print(f"Saved pivot CSV to: {outputs['pivot_csv_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
