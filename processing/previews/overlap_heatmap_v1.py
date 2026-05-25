#!/usr/bin/env python3
"""
overlap_heatmap_v1.py

Purpose
-------
Create a heatmap-style visualisation where the plotted value is the number of
triple-overlap spike events among st_1, st_2, and st_3.

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
- This script varies:
      st_1, st_2, st_3
- It fixes:
      st_4, st_5, ..., st_n
  at their lowest available frequency, matching the earlier heatmap logic.

- The plotted scalar is:
      mean_overlap_count
  i.e. the average number of triple-overlap spike events across matching trials.

- For 3 varying spike trains (the default design here), the output is a 3D cube
  heatmap:
      x-axis = st_1 frequency
      y-axis = st_2 frequency
      z-axis = st_3 frequency
      color   = mean overlap count
      opacity = exponential function of mean overlap count

Counting logic
--------------
Rather than using the difference graph, this script counts connected intervals
where all three waveforms are simultaneously high.

A waveform is treated as "high" when:

    voltage_v >= high_threshold_v

Default:
    high_threshold_v = 0.9 V

Output
------
Saves:
    1. values CSV
    2. PNG figure

Run
---
From the repository root:

    python3 processing/previews/overlap_heatmap_v1.py

Useful examples:

    python3 processing/previews/overlap_heatmap_v1.py --progress-every 1000
    python3 processing/previews/overlap_heatmap_v1.py --alpha-threshold 0.01
    python3 processing/previews/overlap_heatmap_v1.py --stride 2
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

ST_DIR_RE = re.compile(r"^st_(\d+)$")
FREQ_DIR_RE = re.compile(r"^(\d+)_hz$")
TRIAL_FILE_RE = re.compile(r"^trial_(\d+)\.csv$")

DEFAULT_HIGH_THRESHOLD_V = 0.9
DEFAULT_PROGRESS_EVERY = 1000

RUN_NAME_COL = "run_name"
MEAN_OVERLAP_COL = "mean_overlap_count"
STD_OVERLAP_COL = "std_overlap_count"
MIN_OVERLAP_COL = "min_overlap_count"
MAX_OVERLAP_COL = "max_overlap_count"
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
class TrialOverlapCase:
    trial_name: str
    trial_index: int
    st1_csv: Path
    st2_csv: Path
    st3_csv: Path


def natural_int_key(text: str, pattern: re.Pattern[str]) -> tuple[int, str]:
    match = pattern.match(text)
    if match is None:
        return (10**18, text)
    return (int(match.group(1)), text)


def default_input_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sim_run_code" / "spike_train_output_csv"


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "overlap_heatmap_outputs_v1"


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
    cmap = LinearSegmentedColormap.from_list("overlap_heatmap_v1_cmap", colors, N=512)
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


def merge_intervals(
    intervals: Sequence[tuple[float, float]],
    tolerance_s: float = 1e-15,
) -> list[tuple[float, float]]:
    if not intervals:
        return []

    cleaned = sorted(
        (float(start), float(end))
        for start, end in intervals
        if end > start
    )

    if not cleaned:
        return []

    merged: list[tuple[float, float]] = [cleaned[0]]

    for start, end in cleaned[1:]:
        prev_start, prev_end = merged[-1]

        if start <= prev_end + tolerance_s:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def waveform_to_high_intervals(
    df: pd.DataFrame,
    high_threshold_v: float,
) -> list[tuple[float, float]]:
    time = df[TIME_COL].to_numpy(dtype=float)
    voltage = df[VOLTAGE_COL].to_numpy(dtype=float)

    if len(time) != len(voltage):
        raise ValueError("time and voltage arrays must have the same length.")
    if len(time) < 2:
        return []
    if np.any(np.diff(time) < 0):
        raise ValueError("time grid must be monotonically nondecreasing.")

    intervals: list[tuple[float, float]] = []

    for idx in range(len(time) - 1):
        t0 = float(time[idx])
        t1 = float(time[idx + 1])
        v0 = float(voltage[idx])
        v1 = float(voltage[idx + 1])

        if t1 <= t0:
            continue

        high0 = v0 >= high_threshold_v
        high1 = v1 >= high_threshold_v

        if high0 and high1:
            intervals.append((t0, t1))
            continue

        if not high0 and not high1:
            continue

        if np.isclose(v1, v0):
            continue

        crossing_t = t0 + (high_threshold_v - v0) * (t1 - t0) / (v1 - v0)
        crossing_t = float(np.clip(crossing_t, t0, t1))

        if high0 and not high1:
            intervals.append((t0, crossing_t))
        elif not high0 and high1:
            intervals.append((crossing_t, t1))

    return merge_intervals(intervals)


def intersect_two_interval_lists(
    a: Sequence[tuple[float, float]],
    b: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    i = 0
    j = 0
    intersections: list[tuple[float, float]] = []

    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])

        if end > start:
            intersections.append((start, end))

        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1

    return merge_intervals(intersections)


def count_triple_overlap_intervals(
    st1_intervals: Sequence[tuple[float, float]],
    st2_intervals: Sequence[tuple[float, float]],
    st3_intervals: Sequence[tuple[float, float]],
) -> int:
    st12 = intersect_two_interval_lists(st1_intervals, st2_intervals)
    st123 = intersect_two_interval_lists(st12, st3_intervals)
    return len(st123)


def count_triple_overlap_for_trial_case(
    case: TrialOverlapCase,
    high_threshold_v: float,
    waveform_cache: dict[Path, list[tuple[float, float]]] | None = None,
) -> int:
    cache = waveform_cache if waveform_cache is not None else {}

    intervals: list[list[tuple[float, float]]] = []

    for csv_path in (case.st1_csv, case.st2_csv, case.st3_csv):
        if csv_path not in cache:
            df = load_two_column_voltage_csv(csv_path)
            cache[csv_path] = waveform_to_high_intervals(df, high_threshold_v=high_threshold_v)
        intervals.append(cache[csv_path])

    return count_triple_overlap_intervals(
        intervals[0],
        intervals[1],
        intervals[2],
    )


def iter_trial_cases_for_frequency_triplet(
    st1_freq_dir: Path,
    st2_freq_dir: Path,
    st3_freq_dir: Path,
    trial_names: Sequence[str],
) -> Iterator[TrialOverlapCase]:
    for trial_name in trial_names:
        match = TRIAL_FILE_RE.match(trial_name)
        if match is None:
            continue

        st1_csv = st1_freq_dir / trial_name
        st2_csv = st2_freq_dir / trial_name
        st3_csv = st3_freq_dir / trial_name

        if not (st1_csv.is_file() and st2_csv.is_file() and st3_csv.is_file()):
            continue

        yield TrialOverlapCase(
            trial_name=trial_name,
            trial_index=int(match.group(1)),
            st1_csv=st1_csv,
            st2_csv=st2_csv,
            st3_csv=st3_csv,
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


def compute_nice_ticks(
    values: np.ndarray,
    max_ticks: int = 5,
) -> np.ndarray:
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


def compute_overlap_dataframe(
    input_root: Path | None = None,
    high_threshold_v: float = DEFAULT_HIGH_THRESHOLD_V,
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
    waveform_cache: dict[Path, list[tuple[float, float]]] = {}

    if progress:
        print(format_progress_line(0, total_settings, prefix="Overlap heatmap progress"))

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
            trial_names,
        ):
            count = count_triple_overlap_for_trial_case(
                case,
                high_threshold_v=high_threshold_v,
                waveform_cache=waveform_cache,
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
                "trial_overlap_counts": ";".join(str(int(c)) for c in trial_counts),
                "high_threshold_v": float(high_threshold_v),
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
            print(format_progress_line(processed, total_settings, prefix="Overlap heatmap progress"))

    if not rows:
        raise FileNotFoundError("No valid overlap-heatmap rows were generated.")

    df = pd.DataFrame(rows)
    df = df.sort_values([X_FREQ_COL, Y_FREQ_COL, Z_FREQ_COL]).reset_index(drop=True)

    metadata = {
        "input_root": resolved_input_root.resolve(),
        "spike_train_count": len(spike_train_dirs),
        "variable_spike_trains": (1, 2, 3),
        "fixed_spike_trains": tuple(st.st_index for st in fixed_spike_trains),
        "fixed_frequency_names": tuple(freq.name for freq in fixed_frequency_dirs),
        "high_threshold_v": high_threshold_v,
        "frequency_settings_total": total_settings,
        "frequency_settings_processed": processed,
        "unique_waveforms_cached": len(waveform_cache),
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

    title = "3D overlap-count heatmap"
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
    cbar.set_label("Mean triple-overlap count")

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
    return output_dir / "overlap_heatmap_v1_3d_st1_st2_st3"


def generate_visualisation(
    input_root: Path | None = None,
    output_dir: Path | None = None,
    high_threshold_v: float = DEFAULT_HIGH_THRESHOLD_V,
    show: bool = True,
    elev: float = 25.0,
    azim: float = -55.0,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    alpha_threshold: float = 0.01,
    stride: int = 1,
    max_interactive_cubes: int | None = None,
) -> dict[str, object]:
    df_values, metadata = compute_overlap_dataframe(
        input_root=input_root,
        high_threshold_v=high_threshold_v,
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
            "number of triple-overlap spike events among st_1, st_2, and st_3."
        )
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--high-threshold-v", type=float, default=DEFAULT_HIGH_THRESHOLD_V)
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
        high_threshold_v=args.high_threshold_v,
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
    print(f"High threshold: {metadata['high_threshold_v']} V")
    print(f"Frequency settings processed: {metadata['frequency_settings_processed']}/{metadata['frequency_settings_total']}")
    print(f"Unique waveforms cached: {metadata['unique_waveforms_cached']}")
    print(f"Saved values CSV to: {outputs['values_csv_path']}")
    print(f"Saved plot to: {outputs['plot_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
