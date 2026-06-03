#!/usr/bin/env python3
"""
overlap_heatmap_difference_v2.py

Purpose
-------
Create a heatmap-style visualisation where the plotted value is the number of
overlap spikes detected on the difference waveform:

    df_sum        = st_1 + st_2 + st_3
    df_capped     = cap(df_sum, 1.8 V)
    df_difference = df_sum - df_capped

The count is the number of connected positive regions/spikes in df_difference.

This implements the user-requested method directly, rather than counting direct
interval intersections.

Input layout
------------
Same input layout as the previous heatmap and overlap-count scripts:

    processing/sim_run_code/spike_train_output_csv/
        st_1/
        st_2/
        st_3/
        st_4/
        ...

Visualisation behaviour
-----------------------
- st_1 varies along the x-axis.
- st_2 varies along the y-axis.
- st_3 varies along the z-axis.
- st_4, st_5, ..., st_n are fixed at their lowest available frequency and
  reported as metadata.

Important semantic note
-----------------------
The overlap count is computed from st_1, st_2, and st_3 only:

    df_sum = st_1 + st_2 + st_3

st_4+ are fixed and reported for consistency with the heatmap workflow, but
they are not included in this particular overlap-count waveform unless you
enable:

    --include-fixed-spike-trains-in-sum

If that flag is enabled:

    df_sum = st_1 + st_2 + st_3 + st_4_fixed + ... + st_n_fixed

Default cap
-----------
The cap voltage is:

    1.8 V

Thus df_difference becomes positive whenever the summed voltage exceeds 1.8 V.

Difference spike threshold
--------------------------
The default difference threshold is:

    1e-12 V

A connected positive region where:

    df_difference > difference_threshold_v

is counted as one overlap spike.

Output
------
Saves:
    1. values CSV
    2. PNG figure

Run
---
From the repository root:

    python3 processing/previews/overlap_heatmap_difference_v2.py

Useful examples:

    python3 processing/previews/overlap_heatmap_difference_v2.py --progress-every 1000
    python3 processing/previews/overlap_heatmap_difference_v2.py --difference-threshold-v 1e-9
    python3 processing/previews/overlap_heatmap_difference_v2.py --stride 2
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
from matplotlib.widgets import Slider
import numpy as np
import pandas as pd


TIME_COL = "time_s"
VOLTAGE_COL = "voltage_v"
SUM_COL = "voltage_sum_v"
CAPPED_SUM_COL = "voltage_sum_capped_v"
DIFFERENCE_COL = "voltage_difference_v"

ST_DIR_RE = re.compile(r"^st_(\d+)$")
FREQ_DIR_RE = re.compile(r"^(\d+)_hz$")
TRIAL_FILE_RE = re.compile(r"^trial_(\d+)\.csv$")

DEFAULT_CAP_V = 1.8
DEFAULT_DIFFERENCE_THRESHOLD_V = 1.0e-12
DEFAULT_PROGRESS_EVERY = 1000

RUN_NAME_COL = "run_name"
MEAN_OVERLAP_COL = "mean_difference_spike_count"
STD_OVERLAP_COL = "std_difference_spike_count"
MIN_OVERLAP_COL = "min_difference_spike_count"
MAX_OVERLAP_COL = "max_difference_spike_count"
VALID_TRIAL_COUNT_COL = "valid_trial_count"

X_FREQ_COL = "st1_frequency_hz"
Y_FREQ_COL = "st2_frequency_hz"
Z_FREQ_COL = "st3_frequency_hz"


@dataclass(frozen=True)
class SpikeTrainDirectory:
    st_index: int
    path: Path
    frequency_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class TrialDifferenceCase:
    trial_name: str
    trial_index: int
    csv_paths: tuple[Path, ...]


def natural_int_key(text: str, pattern: re.Pattern[str]) -> tuple[int, str]:
    match = pattern.match(text)
    if match is None:
        return (10**18, text)
    return (int(match.group(1)), text)


def default_input_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sim_run_code" / "spike_train_output_csv"


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "overlap_heatmap_difference_outputs_v2"


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
    cmap = LinearSegmentedColormap.from_list("overlap_heatmap_difference_v2_cmap", colors, N=512)
    cmap.set_bad(color="#000000")
    return cmap


def frequency_hz_from_dir_name(name: str) -> int:
    match = FREQ_DIR_RE.match(name)
    if match is None:
        raise ValueError(f"Invalid frequency directory name: {name}")
    return int(match.group(1))


def discover_spike_train_dirs(input_root: Path) -> tuple[SpikeTrainDirectory, ...]:
    input_root = Path(input_root).resolve()

    if not input_root.is_dir():
        raise NotADirectoryError(f"Input root does not exist or is not a directory: {input_root}")

    st_paths = [
        path for path in input_root.iterdir()
        if path.is_dir() and ST_DIR_RE.match(path.name)
    ]
    st_paths.sort(key=lambda p: natural_int_key(p.name, ST_DIR_RE))

    if not st_paths:
        raise FileNotFoundError(f"No st_N directories found in: {input_root}")

    discovered: list[SpikeTrainDirectory] = []

    for st_path in st_paths:
        st_match = ST_DIR_RE.match(st_path.name)
        assert st_match is not None

        frequency_dirs = [
            path for path in st_path.iterdir()
            if path.is_dir() and FREQ_DIR_RE.match(path.name)
        ]
        frequency_dirs.sort(key=lambda p: natural_int_key(p.name, FREQ_DIR_RE))

        if not frequency_dirs:
            raise FileNotFoundError(f"No frequency directories found in: {st_path}")

        discovered.append(
            SpikeTrainDirectory(
                st_index=int(st_match.group(1)),
                path=st_path,
                frequency_dirs=tuple(frequency_dirs),
            )
        )

    return tuple(discovered)


def discover_trial_names(spike_train_dirs: Sequence[SpikeTrainDirectory]) -> tuple[str, ...]:
    common_trials: set[str] | None = None

    for st_dir in spike_train_dirs:
        trials_for_st: set[str] = set()

        for frequency_dir in st_dir.frequency_dirs:
            trials_for_st.update(
                path.name
                for path in frequency_dir.iterdir()
                if path.is_file() and TRIAL_FILE_RE.match(path.name)
            )

        if not trials_for_st:
            raise FileNotFoundError(f"No trial_N.csv files found below: {st_dir.path}")

        if common_trials is None:
            common_trials = trials_for_st
        else:
            common_trials &= trials_for_st

    if not common_trials:
        raise FileNotFoundError("No shared trial_N.csv filenames found.")

    return tuple(sorted(common_trials, key=lambda name: natural_int_key(name, TRIAL_FILE_RE)))


def require_first_three_spike_trains(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
) -> tuple[SpikeTrainDirectory, SpikeTrainDirectory, SpikeTrainDirectory, tuple[SpikeTrainDirectory, ...]]:
    st_by_index = {st.st_index: st for st in spike_train_dirs}

    missing = [idx for idx in (1, 2, 3) if idx not in st_by_index]
    if missing:
        raise FileNotFoundError(f"Required spike-train directories missing: {missing}")

    st1 = st_by_index[1]
    st2 = st_by_index[2]
    st3 = st_by_index[3]
    fixed = tuple(st for st in spike_train_dirs if st.st_index >= 4)

    return st1, st2, st3, fixed


def choose_lowest_frequency_dir(st_dir: SpikeTrainDirectory) -> Path:
    if not st_dir.frequency_dirs:
        raise FileNotFoundError(f"No frequency directories found for st_{st_dir.st_index}")
    return st_dir.frequency_dirs[0]


def load_two_column_voltage_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if {TIME_COL, VOLTAGE_COL}.issubset(df.columns):
        df = df[[TIME_COL, VOLTAGE_COL]].copy()
    else:
        if df.shape[1] < 2:
            raise ValueError(f"Expected at least two columns in: {path}")
        df = df.iloc[:, :2].copy()
        df.columns = [TIME_COL, VOLTAGE_COL]

    df[TIME_COL] = pd.to_numeric(df[TIME_COL], errors="raise")
    df[VOLTAGE_COL] = pd.to_numeric(df[VOLTAGE_COL], errors="raise")

    df = (
        df.sort_values(TIME_COL)
        .drop_duplicates(subset=TIME_COL, keep="last")
        .reset_index(drop=True)
    )

    return df


def align_to_union_time_grid(dataframes: Sequence[pd.DataFrame]) -> tuple[np.ndarray, list[np.ndarray]]:
    if not dataframes:
        raise ValueError("No dataframes were provided.")

    common_time = dataframes[0][TIME_COL].to_numpy(dtype=float)

    for df in dataframes[1:]:
        common_time = np.union1d(common_time, df[TIME_COL].to_numpy(dtype=float))

    aligned_voltages: list[np.ndarray] = []

    for df in dataframes:
        aligned = df.set_index(TIME_COL).reindex(common_time)
        aligned[VOLTAGE_COL] = aligned[VOLTAGE_COL].interpolate(
            method="index",
            limit_direction="both",
        )
        aligned_voltages.append(aligned[VOLTAGE_COL].to_numpy(dtype=float))

    return common_time, aligned_voltages


def build_difference_dataframe_from_paths(
    csv_paths: Sequence[Path],
    cap_v: float,
    dataframe_cache: dict[Path, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Build df_difference from the selected input waveforms.

    df_sum        = sum of all selected waveforms
    df_capped     = cap(df_sum, cap_v)
    df_difference = df_sum - df_capped
    """
    cache = dataframe_cache if dataframe_cache is not None else {}

    input_dfs: list[pd.DataFrame] = []
    for path in csv_paths:
        if path not in cache:
            cache[path] = load_two_column_voltage_csv(path)
        input_dfs.append(cache[path])

    common_time, aligned_voltages = align_to_union_time_grid(input_dfs)
    summed_voltage = np.sum(np.vstack(aligned_voltages), axis=0)
    capped_voltage = np.where(summed_voltage >= cap_v, cap_v, summed_voltage)
    difference_voltage = summed_voltage - capped_voltage

    return pd.DataFrame(
        {
            TIME_COL: common_time,
            DIFFERENCE_COL: difference_voltage,
        }
    )


def count_spikes_in_difference_dataframe(
    df_difference: pd.DataFrame,
    difference_threshold_v: float,
) -> int:
    """
    Count connected positive regions on df_difference.

    A region is considered active where:

        voltage_difference_v > difference_threshold_v

    Each rising transition into an active region counts as one difference spike.
    """
    if df_difference.empty:
        return 0

    diff = df_difference[DIFFERENCE_COL].to_numpy(dtype=float)
    active = diff > difference_threshold_v

    if active.size == 0:
        return 0

    starts = active & np.concatenate(([True], ~active[:-1]))
    return int(np.count_nonzero(starts))


def iter_trial_cases_for_frequency_triplet(
    st1_freq_dir: Path,
    st2_freq_dir: Path,
    st3_freq_dir: Path,
    fixed_frequency_dirs: Sequence[Path],
    trial_names: Sequence[str],
    include_fixed_spike_trains_in_sum: bool,
) -> Iterator[TrialDifferenceCase]:
    for trial_name in trial_names:
        match = TRIAL_FILE_RE.match(trial_name)
        if match is None:
            continue

        base_paths = [
            st1_freq_dir / trial_name,
            st2_freq_dir / trial_name,
            st3_freq_dir / trial_name,
        ]

        fixed_paths = [freq_dir / trial_name for freq_dir in fixed_frequency_dirs]

        selected_paths = base_paths + fixed_paths if include_fixed_spike_trains_in_sum else base_paths

        if not all(path.is_file() for path in selected_paths):
            continue

        yield TrialDifferenceCase(
            trial_name=trial_name,
            trial_index=int(match.group(1)),
            csv_paths=tuple(selected_paths),
        )


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


def compute_nice_step(raw_step: float) -> float:
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


def compute_nice_ticks(values: np.ndarray, max_ticks: int = 5) -> np.ndarray:
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

    return np.round(ticks, decimals=8)


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


def compute_exponential_alpha(
    value: float,
    value_min: float,
    value_max: float,
    k: float = 6.0,
) -> float:
    if value_max <= value_min:
        return 1.0

    t = (value - value_min) / (value_max - value_min)
    t = float(np.clip(t, 0.0, 1.0))
    alpha = float(np.exp(k * (t - 1.0)))
    return float(np.clip(alpha, 0.0, 1.0))


def compute_difference_spike_count_dataframe(
    input_root: Path | None = None,
    cap_v: float = DEFAULT_CAP_V,
    difference_threshold_v: float = DEFAULT_DIFFERENCE_THRESHOLD_V,
    include_fixed_spike_trains_in_sum: bool = False,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> tuple[pd.DataFrame, dict[str, object]]:
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
    st1, st2, st3, fixed_spike_trains = require_first_three_spike_trains(spike_train_dirs)

    trial_names = discover_trial_names((st1, st2, st3))
    fixed_frequency_dirs = [choose_lowest_frequency_dir(st_dir) for st_dir in fixed_spike_trains]

    total_settings = len(st1.frequency_dirs) * len(st2.frequency_dirs) * len(st3.frequency_dirs)
    rows: list[dict[str, object]] = []
    processed = 0
    dataframe_cache: dict[Path, pd.DataFrame] = {}

    if progress:
        print(format_progress_line(0, total_settings, prefix="Difference-count heatmap progress"))

    for st1_freq_dir, st2_freq_dir, st3_freq_dir in itertools.product(
        st1.frequency_dirs,
        st2.frequency_dirs,
        st3.frequency_dirs,
    ):
        trial_counts: list[int] = []
        trial_indices: list[int] = []

        for case in iter_trial_cases_for_frequency_triplet(
            st1_freq_dir,
            st2_freq_dir,
            st3_freq_dir,
            fixed_frequency_dirs=fixed_frequency_dirs,
            trial_names=trial_names,
            include_fixed_spike_trains_in_sum=include_fixed_spike_trains_in_sum,
        ):
            df_difference = build_difference_dataframe_from_paths(
                case.csv_paths,
                cap_v=cap_v,
                dataframe_cache=dataframe_cache,
            )
            count = count_spikes_in_difference_dataframe(
                df_difference,
                difference_threshold_v=difference_threshold_v,
            )
            trial_counts.append(count)
            trial_indices.append(case.trial_index)

        processed += 1

        if trial_counts:
            counts = np.asarray(trial_counts, dtype=float)

            row: dict[str, object] = {
                RUN_NAME_COL: "__".join(
                    [
                        f"st1_{st1_freq_dir.name}",
                        f"st2_{st2_freq_dir.name}",
                        f"st3_{st3_freq_dir.name}",
                    ]
                ),
                X_FREQ_COL: frequency_hz_from_dir_name(st1_freq_dir.name),
                Y_FREQ_COL: frequency_hz_from_dir_name(st2_freq_dir.name),
                Z_FREQ_COL: frequency_hz_from_dir_name(st3_freq_dir.name),
                MEAN_OVERLAP_COL: float(np.mean(counts)),
                STD_OVERLAP_COL: float(np.std(counts, ddof=0)),
                MIN_OVERLAP_COL: int(np.min(counts)),
                MAX_OVERLAP_COL: int(np.max(counts)),
                VALID_TRIAL_COUNT_COL: int(counts.size),
                "trial_indices_used": ";".join(str(i) for i in trial_indices),
                "trial_difference_spike_counts": ";".join(str(int(c)) for c in trial_counts),
                "cap_v": float(cap_v),
                "difference_threshold_v": float(difference_threshold_v),
                "include_fixed_spike_trains_in_sum": bool(include_fixed_spike_trains_in_sum),
            }

            for fixed_st_dir, fixed_freq_dir in zip(
                fixed_spike_trains,
                fixed_frequency_dirs,
                strict=True,
            ):
                row[f"fixed_st_{fixed_st_dir.st_index}_frequency_name"] = fixed_freq_dir.name
                row[f"fixed_st_{fixed_st_dir.st_index}_frequency_hz"] = frequency_hz_from_dir_name(fixed_freq_dir.name)

            rows.append(row)

        if progress and should_print_progress(processed, total_settings, progress_every):
            print(format_progress_line(processed, total_settings, prefix="Difference-count heatmap progress"))

    if not rows:
        raise FileNotFoundError("No valid difference-count heatmap rows were generated.")

    df = pd.DataFrame(rows)
    df = df.sort_values([X_FREQ_COL, Y_FREQ_COL, Z_FREQ_COL]).reset_index(drop=True)

    metadata = {
        "input_root": resolved_input_root.resolve(),
        "spike_train_count": len(spike_train_dirs),
        "variable_spike_trains": (1, 2, 3),
        "fixed_spike_trains": tuple(st.st_index for st in fixed_spike_trains),
        "fixed_frequency_names": tuple(freq.name for freq in fixed_frequency_dirs),
        "cap_v": cap_v,
        "difference_threshold_v": difference_threshold_v,
        "include_fixed_spike_trains_in_sum": include_fixed_spike_trains_in_sum,
        "frequency_settings_total": total_settings,
        "frequency_settings_processed": processed,
        "unique_dataframes_cached": len(dataframe_cache),
    }

    return df, metadata


def create_3d_cube_heatmap(
    df_values: pd.DataFrame,
    metadata: dict[str, object],
    output_path: Path,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
    alpha_threshold: float = 0.01,
    stride: int = 1,
    max_interactive_cubes: int | None = None,
) -> None:
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

    c = df_values[MEAN_OVERLAP_COL].to_numpy(dtype=float)
    c_min = float(np.nanmin(c))
    c_max = float(np.nanmax(c))

    cmap = make_colormap()
    norm = plt.Normalize(vmin=0.0, vmax=c_max if c_max > 0 else 1.0)

    rendered_rows = df_values.copy()

    if stride < 1:
        raise ValueError("stride must be >= 1.")

    if stride > 1:
        rendered_rows = rendered_rows[
            rendered_rows[X_FREQ_COL].isin(x_vals[::stride])
            & rendered_rows[Y_FREQ_COL].isin(y_vals[::stride])
            & rendered_rows[Z_FREQ_COL].isin(z_vals[::stride])
        ].copy()

    if alpha_threshold > 0:
        rendered_rows["_alpha_preview"] = rendered_rows[MEAN_OVERLAP_COL].apply(
            lambda value: compute_exponential_alpha(
                value=float(value),
                value_min=c_min,
                value_max=c_max,
                k=6.0,
            )
        )
        rendered_rows = rendered_rows[rendered_rows["_alpha_preview"] >= alpha_threshold].copy()

    if max_interactive_cubes is not None and len(rendered_rows) > max_interactive_cubes:
        rendered_rows = (
            rendered_rows
            .sort_values(MEAN_OVERLAP_COL, ascending=False)
            .head(max_interactive_cubes)
            .sort_values([X_FREQ_COL, Y_FREQ_COL, Z_FREQ_COL])
            .copy()
        )

    print(f"Cubes in data: {len(df_values)}")
    print(f"Cubes rendered: {len(rendered_rows)}")

    bar_x = []
    bar_y = []
    bar_z = []
    bar_dx = []
    bar_dy = []
    bar_dz = []
    bar_colors = []

    for _, row in rendered_rows.iterrows():
        xv = float(row[X_FREQ_COL])
        yv = float(row[Y_FREQ_COL])
        zv = float(row[Z_FREQ_COL])
        val = float(row[MEAN_OVERLAP_COL])

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

    ax.bar3d(
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

    ax.set_xticks(compute_nice_ticks(x_vals, max_ticks=5))
    ax.set_yticks(compute_nice_ticks(y_vals, max_ticks=5))
    ax.set_zticks(compute_nice_ticks(z_vals, max_ticks=5))

    ax.set_xlabel(f"st{metadata['variable_spike_trains'][0]} frequency / Hz", labelpad=10)
    ax.set_ylabel(f"st{metadata['variable_spike_trains'][1]} frequency / Hz", labelpad=10)
    ax.set_zlabel(f"st{metadata['variable_spike_trains'][2]} frequency / Hz", labelpad=10)

    title = "3D difference-spike-count heatmap"
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
    cbar.set_label("Mean difference-spike count")

    fig.subplots_adjust(bottom=0.18)

    elev_ax = fig.add_axes([0.20, 0.08, 0.60, 0.025])
    azim_ax = fig.add_axes([0.20, 0.04, 0.60, 0.025])

    elev_slider = Slider(
        ax=elev_ax,
        label="Elevation",
        valmin=-90.0,
        valmax=90.0,
        valinit=float(elev),
        valstep=1.0,
    )
    azim_slider = Slider(
        ax=azim_ax,
        label="Azimuth",
        valmin=-180.0,
        valmax=180.0,
        valinit=float(azim),
        valstep=1.0,
    )

    def update_view(_value) -> None:
        ax.view_init(
            elev=float(elev_slider.val),
            azim=float(azim_slider.val),
        )
        fig.canvas.draw_idle()

    elev_slider.on_changed(update_view)
    azim_slider.on_changed(update_view)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


def make_output_stem(output_dir: Path) -> Path:
    return output_dir / "overlap_heatmap_difference_v2_3d_st1_st2_st3"


def generate_visualisation(
    input_root: Path | None = None,
    output_dir: Path | None = None,
    cap_v: float = DEFAULT_CAP_V,
    difference_threshold_v: float = DEFAULT_DIFFERENCE_THRESHOLD_V,
    include_fixed_spike_trains_in_sum: bool = False,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    alpha_threshold: float = 0.01,
    stride: int = 1,
    max_interactive_cubes: int | None = None,
) -> dict[str, object]:
    df_values, metadata = compute_difference_spike_count_dataframe(
        input_root=input_root,
        cap_v=cap_v,
        difference_threshold_v=difference_threshold_v,
        include_fixed_spike_trains_in_sum=include_fixed_spike_trains_in_sum,
        progress=progress,
        progress_every=progress_every,
    )

    resolved_output_dir = default_output_dir() if output_dir is None else Path(output_dir)
    stem = make_output_stem(resolved_output_dir)

    values_csv_path = stem.with_name(stem.name + "_values").with_suffix(".csv")
    values_png_path = stem.with_suffix(".png")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    df_values.to_csv(values_csv_path, index=False)

    create_3d_cube_heatmap(
        df_values=df_values,
        metadata=metadata,
        output_path=values_png_path,
        show=show,
        elev=elev,
        azim=azim,
        alpha_threshold=alpha_threshold,
        stride=stride,
        max_interactive_cubes=max_interactive_cubes,
    )

    return {
        "dataframe": df_values,
        "metadata": metadata,
        "values_csv_path": values_csv_path,
        "plot_path": values_png_path,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a 3D heatmap-style plot where the value is the average "
            "number of spikes on df_difference = df_sum - cap(df_sum)."
        )
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--cap-v", type=float, default=DEFAULT_CAP_V)
    parser.add_argument("--difference-threshold-v", type=float, default=DEFAULT_DIFFERENCE_THRESHOLD_V)
    parser.add_argument(
        "--include-fixed-spike-trains-in-sum",
        action="store_true",
        help=(
            "Include st_4+ fixed-frequency waveforms in df_sum. By default, "
            "the difference count uses only st_1, st_2, and st_3."
        ),
    )
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--elev", type=float, default=25.0)
    parser.add_argument("--azim", type=float, default=-55.0)
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    parser.add_argument(
        "--alpha-threshold",
        type=float,
        default=0.01,
        help="Skip cubes with opacity below this value.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Render only every Nth cube along each axis for faster interaction.",
    )
    parser.add_argument(
        "--max-interactive-cubes",
        type=int,
        default=None,
        help="If set, render only the strongest N cubes after thresholding/striding.",
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    outputs = generate_visualisation(
        input_root=args.input_root,
        output_dir=args.output_dir,
        cap_v=args.cap_v,
        difference_threshold_v=args.difference_threshold_v,
        include_fixed_spike_trains_in_sum=args.include_fixed_spike_trains_in_sum,
        show=not args.no_show,
        elev=args.elev,
        azim=args.azim,
        progress=not args.no_progress,
        progress_every=args.progress_every,
        alpha_threshold=args.alpha_threshold,
        stride=args.stride,
        max_interactive_cubes=args.max_interactive_cubes,
    )

    metadata = outputs["metadata"]
    print(f"Input root: {metadata['input_root']}")
    print(f"Spike-train count discovered: {metadata['spike_train_count']}")
    print(f"Variable spike trains: {metadata['variable_spike_trains']}")
    print(f"Fixed spike trains: {metadata['fixed_spike_trains']}")
    print(f"Fixed frequency names: {metadata['fixed_frequency_names']}")
    print(f"Cap voltage: {metadata['cap_v']} V")
    print(f"Difference threshold: {metadata['difference_threshold_v']} V")
    print(f"Include fixed spike trains in sum: {metadata['include_fixed_spike_trains_in_sum']}")
    print(f"Frequency settings processed: {metadata['frequency_settings_processed']}/{metadata['frequency_settings_total']}")
    print(f"Unique dataframes cached: {metadata['unique_dataframes_cached']}")
    print(f"Saved values CSV to: {outputs['values_csv_path']}")
    print(f"Saved plot to: {outputs['plot_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
