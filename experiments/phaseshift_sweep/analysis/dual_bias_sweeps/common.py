#!/usr/bin/env python3
"""Shared analysis utilities for dual-bias phase-shift sweeps."""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plot_output_utils import add_image_output_args, resolve_output_dir, save_figure


IGNORE_CSV_NAMES = {
    "conversion_summary.csv",
    "summary.csv",
    "errors.csv",
    "conversion_errors.csv",
}

TIME_COL = "time_s"
ONE_SYN_CURRENT = "i_I56_Iout_A"
TWO_SYN_I172 = "i_I172_Iout_A"
TWO_SYN_I56 = "i_I56_Iout_A"

plt = None
pd = None


@dataclass(frozen=True)
class SweepConfig:
    name: str
    bias_a: str
    bias_b: str
    one_syn_subdir: str
    two_syn_subdir: str

    @property
    def biases(self) -> tuple[str, str]:
        return self.bias_a, self.bias_b


@dataclass(frozen=True)
class CaseMetadata:
    phase_shift: str
    labels: dict[str, str]


@dataclass(frozen=True)
class IntegrationResult:
    phase_shift: str
    bias_a_label: str
    bias_b_label: str
    one_syn_csv: Path
    two_syn_csv: Path
    one_syn_abs_integral_a_s: float
    two_syn_sum_abs_integral_a_s: float


@dataclass(frozen=True)
class BinnedIntegrationResult:
    phase_shift: str
    bias_a_label: str
    bias_b_label: str
    one_syn_csv: Path
    two_syn_csv: Path
    bin_start_s: float
    bin_end_s: float
    one_syn_integral_a_s: float
    two_syn_sum_integral_a_s: float

    @property
    def difference_a_s(self) -> float:
        return self.two_syn_sum_integral_a_s - self.one_syn_integral_a_s

    @property
    def ratio(self) -> float:
        if self.one_syn_integral_a_s == 0:
            return float("nan")
        return self.two_syn_sum_integral_a_s / self.one_syn_integral_a_s


@dataclass(frozen=True)
class IntegralRow:
    phase_shift: str
    bias_a_label: str
    bias_b_label: str
    one_syn_csv: str
    two_syn_csv: str
    one_syn_abs_integral_a_s: float
    two_syn_sum_abs_integral_a_s: float

    @property
    def phase_shift_s(self) -> float:
        return parse_phase_shift_value(self.phase_shift)

    @property
    def difference_a_s(self) -> float:
        return self.two_syn_sum_abs_integral_a_s - self.one_syn_abs_integral_a_s

    @property
    def ratio(self) -> float:
        if self.one_syn_abs_integral_a_s == 0:
            return float("nan")
        return self.two_syn_sum_abs_integral_a_s / self.one_syn_abs_integral_a_s


@dataclass(frozen=True)
class BinnedIntegralRow:
    phase_shift: str
    bias_a_label: str
    bias_b_label: str
    bin_start_us: float
    bin_end_us: float
    one_syn_integral_a_s: float
    two_syn_sum_integral_a_s: float
    one_syn_csv: str
    two_syn_csv: str

    @property
    def phase_shift_s(self) -> float:
        return parse_phase_shift_value(self.phase_shift)

    @property
    def difference_a_s(self) -> float:
        return self.two_syn_sum_integral_a_s - self.one_syn_integral_a_s

    @property
    def ratio(self) -> float:
        if self.one_syn_integral_a_s == 0:
            return float("nan")
        return self.two_syn_sum_integral_a_s / self.one_syn_integral_a_s

    @property
    def pair_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.phase_shift,
            self.bias_a_label,
            self.bias_b_label,
            self.one_syn_csv,
            self.two_syn_csv,
        )


def load_plot_dependencies() -> None:
    global plt, pd
    if plt is not None and pd is not None:
        return
    try:
        import matplotlib.pyplot as matplotlib_pyplot
        import pandas as pandas_module
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Missing plotting dependency: {exc.name}. Install matplotlib and pandas to plot CSVs."
        ) from exc
    plt = matplotlib_pyplot
    pd = pandas_module


def load_matplotlib_dependency() -> None:
    global plt
    if plt is not None:
        return
    try:
        import matplotlib.pyplot as matplotlib_pyplot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Missing plotting dependency: {exc.name}. Install matplotlib to plot integral differences."
        ) from exc
    plt = matplotlib_pyplot


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find repo root. Run from inside thesis_codebase, "
        "or pass --repo-root /path/to/thesis_codebase."
    )


def default_one_syn_dir(repo_root: Path, config: SweepConfig) -> Path:
    path = repo_root / "database" / "formatted" / config.one_syn_subdir
    if not path.is_dir():
        raise FileNotFoundError(f"1syn formatted directory not found: {path}")
    return path


def default_two_syn_dir(repo_root: Path, config: SweepConfig) -> Path:
    path = repo_root / "database" / "formatted" / config.two_syn_subdir
    if not path.is_dir():
        raise FileNotFoundError(f"2syn formatted directory not found: {path}")
    return path


def parse_phase_shift_value(value: str) -> float:
    match = re.search(r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)_phase_shift", value)
    if not match:
        raise ValueError(f"Could not parse phase shift value from {value!r}")
    return float(match.group("value"))


def parse_phase_shift_s(path: Path) -> float:
    try:
        return parse_phase_shift_value(path.stem)
    except ValueError:
        return float("inf")


def label_to_voltage(label: str, bias: str) -> float:
    return float(label.removeprefix(f"{bias}_").replace("p", "."))


def normalize_bias_label(bias: str, value: str) -> str:
    return value if value.startswith(f"{bias}_") else f"{bias}_{value}"


def extract_bias_label(path: Path, bias: str) -> str | None:
    prefix = f"{bias}_"
    for part in path.parts:
        if part.startswith(prefix):
            return part
    return None


def parse_bias_sort_key(path: Path, bias: str) -> tuple[int, float | str]:
    label = extract_bias_label(path, bias)
    if label is None:
        return (0, "")
    try:
        return (1, label_to_voltage(label, bias))
    except ValueError:
        return (1, label)


def csv_sort_key(path: Path, config: SweepConfig) -> tuple[tuple[int, float | str], tuple[int, float | str], float, str]:
    return (
        parse_bias_sort_key(path, config.bias_a),
        parse_bias_sort_key(path, config.bias_b),
        parse_phase_shift_s(path),
        str(path),
    )


def find_csv_files(input_dir: Path, config: SweepConfig) -> list[Path]:
    csvs = [
        p for p in input_dir.rglob("*.csv")
        if p.is_file()
        and p.name not in IGNORE_CSV_NAMES
        and not p.name.startswith(".")
    ]
    if not csvs:
        raise FileNotFoundError(f"No plottable CSV files found under {input_dir}")
    return sorted(csvs, key=lambda path: csv_sort_key(path, config))


def csv_map_by_relative_path(input_dir: Path, config: SweepConfig) -> dict[Path, Path]:
    return {path.relative_to(input_dir): path for path in find_csv_files(input_dir, config)}


def find_current_pairs(one_syn_dir: Path, two_syn_dir: Path, config: SweepConfig) -> list[tuple[Path, Path, Path]]:
    one_syn = csv_map_by_relative_path(one_syn_dir, config)
    two_syn = csv_map_by_relative_path(two_syn_dir, config)

    missing_2syn = sorted(set(one_syn) - set(two_syn), key=lambda p: csv_sort_key(one_syn[p], config))
    missing_1syn = sorted(set(two_syn) - set(one_syn), key=lambda p: csv_sort_key(two_syn[p], config))
    if missing_2syn or missing_1syn:
        messages = []
        if missing_2syn:
            messages.append(f"missing 2syn matches for {len(missing_2syn)} files, first={missing_2syn[0]}")
        if missing_1syn:
            messages.append(f"missing 1syn matches for {len(missing_1syn)} files, first={missing_1syn[0]}")
        raise FileNotFoundError("Current CSV pair mismatch: " + "; ".join(messages))

    rel_paths = sorted(one_syn, key=lambda p: csv_sort_key(one_syn[p], config))
    pairs = [(rel_path, one_syn[rel_path], two_syn[rel_path]) for rel_path in rel_paths]
    if not pairs:
        raise FileNotFoundError("No matching 1syn/2syn CSV pairs found.")
    return pairs


def parse_case_metadata(rel_path: Path, config: SweepConfig) -> CaseMetadata:
    parts = rel_path.with_suffix("").parts
    if len(parts) != 3:
        raise ValueError(
            f"expected <{config.bias_a}_label>/<{config.bias_b}_label>/<phase_shift>, got {'/'.join(parts)!r}"
        )
    return CaseMetadata(
        phase_shift=parts[2],
        labels={config.bias_a: parts[0], config.bias_b: parts[1]},
    )


def normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def coerce_numeric_columns(df):
    out = df.copy()
    for col in out.columns:
        converted = pd.to_numeric(out[col], errors="coerce")
        if converted.notna().any():
            out[col] = converted
    return out


def load_csv(csv_path: Path):
    df = pd.read_csv(csv_path)
    df = df.dropna(axis=1, how="all")
    return coerce_numeric_columns(df)


def find_time_column(df) -> str:
    for col in df.columns:
        if normalize_colname(col).startswith("time"):
            return col
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        return numeric_cols[0]
    raise ValueError("Could not identify a numeric time column.")


def signal_columns(df, time_col: str) -> list[str]:
    cols = [col for col in df.select_dtypes(include="number").columns.tolist() if col != time_col]
    if not cols:
        raise ValueError("No numeric signal columns besides time were found.")
    return cols


def require_columns(df, columns: list[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def insert_midpoint_rows(df, target_len: int, time_col: str):
    if len(df) > target_len:
        raise ValueError("cannot reduce dataframe length with midpoint insertion")
    if len(df) == target_len:
        return df.copy()
    if len(df) < 2:
        raise ValueError("cannot insert midpoint rows into a dataframe with fewer than two rows")

    out = df.sort_values(time_col).reset_index(drop=True).copy()
    while len(out) < target_len:
        remaining = target_len - len(out)
        gaps = out[time_col].diff().iloc[1:].abs().sort_values(ascending=False)
        insert_positions = sorted((idx for idx in gaps.index[:remaining]), reverse=True)

        for idx in insert_positions:
            prev_row = out.iloc[idx - 1]
            next_row = out.iloc[idx]
            midpoint = {}
            for col in out.columns:
                if pd.api.types.is_numeric_dtype(out[col]):
                    midpoint[col] = (prev_row[col] + next_row[col]) / 2.0
                else:
                    midpoint[col] = prev_row[col]

            top = out.iloc[:idx]
            bottom = out.iloc[idx:]
            out = pd.concat([top, pd.DataFrame([midpoint]), bottom], ignore_index=True)

    return out.reset_index(drop=True)


def equalize_dataframe_lengths(one_df, two_df, one_time: str, two_time: str):
    if len(one_df) == len(two_df):
        return one_df.copy(), two_df.copy(), ""

    target_len = max(len(one_df), len(two_df))
    if len(one_df) < target_len:
        one_df = insert_midpoint_rows(one_df, target_len, one_time)
        return one_df, two_df.copy(), f"Inserted midpoint rows into 1syn to match {target_len} rows."

    two_df = insert_midpoint_rows(two_df, target_len, two_time)
    return one_df.copy(), two_df, f"Inserted midpoint rows into 2syn to match {target_len} rows."


def subtract_initial(series):
    if series.empty:
        raise ValueError("cannot subtract initial value from an empty series")
    return series - series.iloc[0]


def load_numeric_csv(path: Path, required_columns: Sequence[str]) -> dict[str, list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = [col for col in required_columns if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")

        values: dict[str, list[float]] = {col: [] for col in required_columns}
        for row_number, row in enumerate(reader, start=2):
            for col in required_columns:
                try:
                    values[col].append(float(row[col]))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Could not parse {col} on line {row_number} in {path}: {row[col]!r}"
                    ) from exc

    if not values[required_columns[0]]:
        raise ValueError(f"CSV contains no data rows: {path}")
    return values


def baseline_subtracted_abs(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("cannot baseline-subtract an empty sequence")
    initial = values[0]
    return [abs(value - initial) for value in values]


def trapezoid_integral(time_s: Sequence[float], values: Sequence[float]) -> float:
    if len(time_s) != len(values):
        raise ValueError(f"time/value length mismatch: {len(time_s)} vs {len(values)}")
    if len(time_s) < 2:
        raise ValueError("at least two data points are required for trapezoidal integration")

    points = sorted(zip(time_s, values), key=lambda item: item[0])
    area = 0.0
    prev_t, prev_y = points[0]
    for t, y in points[1:]:
        dt = t - prev_t
        if dt < 0:
            raise ValueError("time values must be nondecreasing after sorting")
        area += dt * (y + prev_y) / 2.0
        prev_t, prev_y = t, y
    return area


def interpolate_value(points: Sequence[tuple[float, float]], target_t: float) -> float:
    if target_t <= points[0][0]:
        return points[0][1]
    if target_t >= points[-1][0]:
        return points[-1][1]

    prev_t, prev_y = points[0]
    for t, y in points[1:]:
        if target_t == t:
            return y
        if target_t < t:
            dt = t - prev_t
            if dt == 0:
                return y
            fraction = (target_t - prev_t) / dt
            return prev_y + fraction * (y - prev_y)
        prev_t, prev_y = t, y
    return points[-1][1]


def trapezoid_integral_between(time_s: Sequence[float], values: Sequence[float], start_s: float, end_s: float) -> float:
    if end_s <= start_s:
        raise ValueError("integration bin end must be greater than bin start")
    if len(time_s) != len(values):
        raise ValueError(f"time/value length mismatch: {len(time_s)} vs {len(values)}")
    if len(time_s) < 2:
        raise ValueError("at least two data points are required for trapezoidal integration")

    points = sorted(zip(time_s, values), key=lambda item: item[0])
    data_start = points[0][0]
    data_end = points[-1][0]
    clipped_start = max(start_s, data_start)
    clipped_end = min(end_s, data_end)
    if clipped_end <= clipped_start:
        return 0.0

    bin_points = [(clipped_start, interpolate_value(points, clipped_start))]
    bin_points.extend((t, y) for t, y in points if clipped_start < t < clipped_end)
    bin_points.append((clipped_end, interpolate_value(points, clipped_end)))
    return trapezoid_integral([t for t, _ in bin_points], [y for _, y in bin_points])


def bin_edges_for_pair(one_time_s: Sequence[float], two_time_s: Sequence[float], bin_width_s: float) -> list[tuple[float, float]]:
    if bin_width_s <= 0:
        raise ValueError("--bin-width-us must be greater than 0")
    max_time_s = max(max(one_time_s), max(two_time_s))
    if max_time_s <= 0:
        raise ValueError("CSV time range does not extend beyond 0 seconds")
    bin_count = math.ceil(max_time_s / bin_width_s)
    return [(index * bin_width_s, (index + 1) * bin_width_s) for index in range(bin_count)]


def integrate_pair(rel_path: Path, one_syn_csv: Path, two_syn_csv: Path, config: SweepConfig) -> IntegrationResult:
    metadata = parse_case_metadata(rel_path, config)
    one = load_numeric_csv(one_syn_csv, [TIME_COL, ONE_SYN_CURRENT])
    two = load_numeric_csv(two_syn_csv, [TIME_COL, TWO_SYN_I172, TWO_SYN_I56])

    one_abs = baseline_subtracted_abs(one[ONE_SYN_CURRENT])
    two_sum = [i172 + i56 for i172, i56 in zip(two[TWO_SYN_I172], two[TWO_SYN_I56])]
    two_sum_abs = baseline_subtracted_abs(two_sum)

    return IntegrationResult(
        phase_shift=metadata.phase_shift,
        bias_a_label=metadata.labels[config.bias_a],
        bias_b_label=metadata.labels[config.bias_b],
        one_syn_csv=one_syn_csv,
        two_syn_csv=two_syn_csv,
        one_syn_abs_integral_a_s=trapezoid_integral(one[TIME_COL], one_abs),
        two_syn_sum_abs_integral_a_s=trapezoid_integral(two[TIME_COL], two_sum_abs),
    )


def integrate_pair_binned(
    rel_path: Path,
    one_syn_csv: Path,
    two_syn_csv: Path,
    config: SweepConfig,
    bin_width_us: float,
) -> list[BinnedIntegrationResult]:
    metadata = parse_case_metadata(rel_path, config)
    one = load_numeric_csv(one_syn_csv, [TIME_COL, ONE_SYN_CURRENT])
    two = load_numeric_csv(two_syn_csv, [TIME_COL, TWO_SYN_I172, TWO_SYN_I56])

    one_signed = [value - one[ONE_SYN_CURRENT][0] for value in one[ONE_SYN_CURRENT]]
    two_sum = [i172 + i56 for i172, i56 in zip(two[TWO_SYN_I172], two[TWO_SYN_I56])]
    two_sum_initial = two_sum[0]
    two_sum_signed = [value - two_sum_initial for value in two_sum]

    bin_width_s = bin_width_us * 1e-6
    rows = []
    for bin_start_s, bin_end_s in bin_edges_for_pair(one[TIME_COL], two[TIME_COL], bin_width_s):
        rows.append(
            BinnedIntegrationResult(
                phase_shift=metadata.phase_shift,
                bias_a_label=metadata.labels[config.bias_a],
                bias_b_label=metadata.labels[config.bias_b],
                one_syn_csv=one_syn_csv,
                two_syn_csv=two_syn_csv,
                bin_start_s=bin_start_s,
                bin_end_s=bin_end_s,
                one_syn_integral_a_s=trapezoid_integral_between(one[TIME_COL], one_signed, bin_start_s, bin_end_s),
                two_syn_sum_integral_a_s=trapezoid_integral_between(two[TIME_COL], two_sum_signed, bin_start_s, bin_end_s),
            )
        )
    return rows


def write_results(rows: Iterable[IntegrationResult], handle, config: SweepConfig) -> None:
    writer = csv.writer(handle)
    writer.writerow([
        "phase_shift",
        f"{config.bias_a}_label",
        f"{config.bias_b}_label",
        "one_syn_csv",
        "two_syn_csv",
        "one_syn_abs_integral_A_s",
        "two_syn_sum_abs_integral_A_s",
    ])
    for row in rows:
        writer.writerow([
            row.phase_shift,
            row.bias_a_label,
            row.bias_b_label,
            row.one_syn_csv,
            row.two_syn_csv,
            f"{row.one_syn_abs_integral_a_s:.12e}",
            f"{row.two_syn_sum_abs_integral_a_s:.12e}",
        ])


def write_binned_results(rows: Iterable[BinnedIntegrationResult], handle, config: SweepConfig) -> None:
    writer = csv.writer(handle)
    writer.writerow([
        "phase_shift",
        f"{config.bias_a}_label",
        f"{config.bias_b}_label",
        "bin_start_us",
        "bin_end_us",
        "one_syn_integral_A_s",
        "two_syn_sum_integral_A_s",
        "difference_A_s",
        "ratio",
        "one_syn_csv",
        "two_syn_csv",
    ])
    for row in rows:
        writer.writerow([
            row.phase_shift,
            row.bias_a_label,
            row.bias_b_label,
            f"{row.bin_start_s * 1e6:.12e}",
            f"{row.bin_end_s * 1e6:.12e}",
            f"{row.one_syn_integral_a_s:.12e}",
            f"{row.two_syn_sum_integral_a_s:.12e}",
            f"{row.difference_a_s:.12e}",
            f"{row.ratio:.12e}",
            row.one_syn_csv,
            row.two_syn_csv,
        ])


def load_integral_rows_from_csv(path: Path, config: SweepConfig) -> list[IntegralRow]:
    bias_a_col = f"{config.bias_a}_label"
    bias_b_col = f"{config.bias_b}_label"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        required = [
            "phase_shift",
            bias_a_col,
            bias_b_col,
            "one_syn_csv",
            "two_syn_csv",
            "one_syn_abs_integral_A_s",
            "two_syn_sum_abs_integral_A_s",
        ]
        missing = [col for col in required if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    IntegralRow(
                        phase_shift=row["phase_shift"],
                        bias_a_label=row[bias_a_col],
                        bias_b_label=row[bias_b_col],
                        one_syn_csv=row["one_syn_csv"],
                        two_syn_csv=row["two_syn_csv"],
                        one_syn_abs_integral_a_s=float(row["one_syn_abs_integral_A_s"]),
                        two_syn_sum_abs_integral_a_s=float(row["two_syn_sum_abs_integral_A_s"]),
                    )
                )
            except ValueError as exc:
                raise ValueError(f"Could not parse numeric integral on line {line_number} in {path}") from exc

    if not rows:
        raise ValueError(f"No integral rows found in {path}")
    return rows


def load_binned_integral_rows_from_csv(path: Path, config: SweepConfig) -> list[BinnedIntegralRow]:
    bias_a_col = f"{config.bias_a}_label"
    bias_b_col = f"{config.bias_b}_label"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        required = [
            "phase_shift",
            bias_a_col,
            bias_b_col,
            "bin_start_us",
            "bin_end_us",
            "one_syn_integral_A_s",
            "two_syn_sum_integral_A_s",
            "one_syn_csv",
            "two_syn_csv",
        ]
        missing = [col for col in required if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    BinnedIntegralRow(
                        phase_shift=row["phase_shift"],
                        bias_a_label=row[bias_a_col],
                        bias_b_label=row[bias_b_col],
                        bin_start_us=float(row["bin_start_us"]),
                        bin_end_us=float(row["bin_end_us"]),
                        one_syn_integral_a_s=float(row["one_syn_integral_A_s"]),
                        two_syn_sum_integral_a_s=float(row["two_syn_sum_integral_A_s"]),
                        one_syn_csv=row["one_syn_csv"],
                        two_syn_csv=row["two_syn_csv"],
                    )
                )
            except ValueError as exc:
                raise ValueError(f"Could not parse numeric binned integral on line {line_number} in {path}") from exc

    if not rows:
        raise ValueError(f"No binned integral rows found in {path}")
    return rows


def binned_results_to_rows(results: Iterable[BinnedIntegrationResult]) -> list[BinnedIntegralRow]:
    return [
        BinnedIntegralRow(
            phase_shift=result.phase_shift,
            bias_a_label=result.bias_a_label,
            bias_b_label=result.bias_b_label,
            bin_start_us=result.bin_start_s * 1e6,
            bin_end_us=result.bin_end_s * 1e6,
            one_syn_integral_a_s=result.one_syn_integral_a_s,
            two_syn_sum_integral_a_s=result.two_syn_sum_integral_a_s,
            one_syn_csv=str(result.one_syn_csv),
            two_syn_csv=str(result.two_syn_csv),
        )
        for result in results
    ]


def compute_integral_rows(repo_root: Path, one_syn_dir: Path | None, two_syn_dir: Path | None, config: SweepConfig) -> list[IntegralRow]:
    one_dir = one_syn_dir.resolve() if one_syn_dir else default_one_syn_dir(repo_root, config)
    two_dir = two_syn_dir.resolve() if two_syn_dir else default_two_syn_dir(repo_root, config)
    pairs = find_current_pairs(one_dir, two_dir, config)

    rows = []
    for rel_path, one_csv, two_csv in pairs:
        result = integrate_pair(rel_path, one_csv, two_csv, config)
        rows.append(
            IntegralRow(
                phase_shift=result.phase_shift,
                bias_a_label=result.bias_a_label,
                bias_b_label=result.bias_b_label,
                one_syn_csv=str(result.one_syn_csv),
                two_syn_csv=str(result.two_syn_csv),
                one_syn_abs_integral_a_s=result.one_syn_abs_integral_a_s,
                two_syn_sum_abs_integral_a_s=result.two_syn_sum_abs_integral_a_s,
            )
        )
    return rows


def compute_binned_integral_rows(
    repo_root: Path,
    one_syn_dir: Path | None,
    two_syn_dir: Path | None,
    config: SweepConfig,
    bin_width_us: float,
) -> list[BinnedIntegralRow]:
    one_dir = one_syn_dir.resolve() if one_syn_dir else default_one_syn_dir(repo_root, config)
    two_dir = two_syn_dir.resolve() if two_syn_dir else default_two_syn_dir(repo_root, config)
    pairs = find_current_pairs(one_dir, two_dir, config)

    rows = []
    for rel_path, one_csv, two_csv in pairs:
        rows.extend(binned_results_to_rows(integrate_pair_binned(rel_path, one_csv, two_csv, config, bin_width_us)))
    return rows


def selected_rows(rows: Sequence[IntegralRow], start_at: int, limit: int | None) -> list[IntegralRow]:
    if start_at < 1:
        raise ValueError("--start-at must be >= 1")
    selected = list(rows)[start_at - 1:]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("No integral rows selected after filtering.")
    return selected


def selected_binned_pair_groups(
    rows: Sequence[BinnedIntegralRow],
    start_at: int,
    limit: int | None,
) -> list[tuple[tuple[str, str, str, str, str], list[BinnedIntegralRow]]]:
    if start_at < 1:
        raise ValueError("--start-at must be >= 1")
    groups = group_binned_rows_by_pair(rows)
    selected = groups[start_at - 1:]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("No binned integral pairs selected after filtering.")
    return selected


def apply_pair_filters(pairs: list[tuple[Path, Path, Path]], args: argparse.Namespace, config: SweepConfig) -> list[tuple[Path, Path, Path]]:
    filtered = pairs
    for bias in config.biases:
        requested = getattr(args, bias, None)
        if requested is None:
            continue
        label = normalize_bias_label(bias, requested)
        filtered = [pair for pair in filtered if extract_bias_label(pair[1], bias) == label]
        if not filtered:
            raise FileNotFoundError(f"No CSV pairs found for {bias} label: {label}")
    return filtered


def apply_binned_row_filters(rows: list[BinnedIntegralRow], args: argparse.Namespace, config: SweepConfig) -> list[BinnedIntegralRow]:
    filtered = rows
    labels_by_bias = {config.bias_a: "bias_a_label", config.bias_b: "bias_b_label"}
    for bias in config.biases:
        requested = getattr(args, bias, None)
        if requested is None:
            continue
        label = normalize_bias_label(bias, requested)
        attr = labels_by_bias[bias]
        filtered = [row for row in filtered if getattr(row, attr) == label]
        if not filtered:
            raise FileNotFoundError(f"No binned integral rows found for {bias} label: {label}")
    return filtered


def apply_row_filters(rows: list[IntegralRow], args: argparse.Namespace, config: SweepConfig) -> list[IntegralRow]:
    filtered = rows
    labels_by_bias = {config.bias_a: "bias_a_label", config.bias_b: "bias_b_label"}
    for bias in config.biases:
        requested = getattr(args, bias, None)
        if requested is None:
            continue
        label = normalize_bias_label(bias, requested)
        attr = labels_by_bias[bias]
        filtered = [row for row in filtered if getattr(row, attr) == label]
        if not filtered:
            raise FileNotFoundError(f"No integral rows found for {bias} label: {label}")
    return filtered


def group_binned_rows_by_pair(
    rows: Sequence[BinnedIntegralRow],
) -> list[tuple[tuple[str, str, str, str, str], list[BinnedIntegralRow]]]:
    groups: dict[tuple[str, str, str, str, str], list[BinnedIntegralRow]] = {}
    for row in rows:
        groups.setdefault(row.pair_key, []).append(row)
    return [
        (key, sorted(group, key=lambda row: (row.bin_start_us, row.bin_end_us)))
        for key, group in sorted(
            groups.items(),
            key=lambda item: (
                label_to_voltage(item[0][1], item[0][1].split("_", 1)[0]),
                label_to_voltage(item[0][2], item[0][2].split("_", 1)[0]),
                parse_phase_shift_value(item[0][0]),
                item[0][3],
            ),
        )
    ]


def group_rows(rows: Sequence[IntegralRow], attr: str) -> dict[str, list[IntegralRow]]:
    groups: dict[str, list[IntegralRow]] = {}
    for row in rows:
        label = getattr(row, attr)
        groups.setdefault(label, []).append(row)
    for label in groups:
        groups[label] = sorted(groups[label], key=lambda row: row.phase_shift_s)
    return dict(sorted(groups.items()))


def darken_color(color, factor: float = 0.75):
    red, green, blue, alpha = color
    return (red * factor, green * factor, blue * factor, alpha)


def format_bias_plot_label(bias: str, label: str) -> str:
    return rf"$V_{{{bias.removeprefix('v')}}} = {label_to_voltage(label, bias):g}V$"


def filter_rows_by_max_phase_shift_us(rows: Sequence[IntegralRow], max_phase_shift_us: float | None) -> list[IntegralRow]:
    if max_phase_shift_us is None:
        return list(rows)
    if max_phase_shift_us <= 0:
        raise ValueError("--max-phase-shift-us must be > 0")
    filtered = [row for row in rows if row.phase_shift_s * 1e6 <= max_phase_shift_us]
    if not filtered:
        raise ValueError(f"No integral rows remain at or below {max_phase_shift_us:g} us")
    return filtered


def filter_binned_rows_by_max_phase_shift_us(rows: Sequence[BinnedIntegralRow], max_phase_shift_us: float | None) -> list[BinnedIntegralRow]:
    if max_phase_shift_us is None:
        return list(rows)
    if max_phase_shift_us <= 0:
        raise ValueError("--max-phase-shift-us must be > 0")
    filtered = [row for row in rows if row.phase_shift_s * 1e6 <= max_phase_shift_us]
    if not filtered:
        raise ValueError(f"No binned integral rows remain at or below {max_phase_shift_us:g} us")
    return filtered


def exponential_decay(x, y_inf: float, amplitude: float, tau: float):
    import numpy as np

    return y_inf + amplitude * np.exp(-x / tau)


def fit_exponential_decay(
    x_values: Sequence[float],
    y_values: Sequence[float],
    min_points: int,
    samples: int,
) -> tuple[float, float, float, list[float], list[float]]:
    try:
        import numpy as np
        from scipy.optimize import curve_fit
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Ratio fitting requires numpy and scipy.") from exc

    if min_points < 3:
        raise ValueError("--fit-min-points must be >= 3")
    if samples < 2:
        raise ValueError("--fit-samples must be >= 2")

    points = [
        (float(x), float(y))
        for x, y in zip(x_values, y_values)
        if math.isfinite(float(x)) and math.isfinite(float(y))
    ]
    points = sorted(points, key=lambda item: item[0])
    if len(points) < min_points:
        raise ValueError(f"only {len(points)} finite points available")

    x = np.asarray([point[0] for point in points], dtype=float)
    y = np.asarray([point[1] for point in points], dtype=float)
    x_span = float(x[-1] - x[0])
    if x_span <= 0:
        raise ValueError("x values must span a positive range")

    y_inf0 = float(y[-1])
    amplitude0 = float(y[0] - y[-1])
    if amplitude0 == 0:
        amplitude0 = 1e-12
    tau0 = max(x_span / 3.0, 1e-12)
    params, _ = curve_fit(
        exponential_decay,
        x,
        y,
        p0=(y_inf0, amplitude0, tau0),
        bounds=([-math.inf, -math.inf, 1e-12], [math.inf, math.inf, math.inf]),
        maxfev=10000,
    )
    y_inf = float(params[0])
    amplitude = float(params[1])
    tau = float(params[2])
    x_fit = np.linspace(float(x[0]), float(x[-1]), samples)
    y_fit = exponential_decay(x_fit, *params)
    return y_inf, amplitude, tau, x_fit.tolist(), y_fit.tolist()


def ratio_fit_params(
    rows: Sequence[IntegralRow],
    min_points: int,
) -> tuple[float, float, float, float]:
    y_inf, amplitude, tau, _, _ = fit_exponential_decay(
        [row.phase_shift_s * 1e6 for row in rows],
        [row.ratio for row in rows],
        min_points,
        2,
    )
    x_min = min(row.phase_shift_s * 1e6 for row in rows)
    return y_inf, amplitude, tau, x_min


def threshold_crossing_us(
    y_inf: float,
    amplitude: float,
    tau: float,
    x_min: float,
    max_us: float,
    threshold: float,
) -> tuple[str, float | None]:
    y_at_min = y_inf + amplitude * math.exp(-x_min / tau)
    y_at_max = y_inf + amplitude * math.exp(-max_us / tau)
    if y_at_min <= threshold:
        return "already_below_threshold", x_min
    if y_at_max > threshold:
        return "not_crossed_by_max_us", None
    if amplitude == 0:
        return "not_crossed_by_max_us", None

    ratio = (threshold - y_inf) / amplitude
    if ratio <= 0 or not math.isfinite(ratio):
        return "not_crossed_by_max_us", None
    crossing = -tau * math.log(ratio)
    if not math.isfinite(crossing) or crossing < x_min or crossing > max_us:
        return "not_crossed_by_max_us", None
    return "crossed", crossing


def load_fit_dependencies() -> None:
    try:
        import numpy  # noqa: F401
        import scipy.optimize  # noqa: F401
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Ratio fitting requires numpy and scipy.") from exc


def plot_integral_page(
    page_label: str,
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    absolute_difference: bool,
    max_phase_shift_us: float | None,
    fit_ratio: bool = False,
    fit_min_points: int = 3,
    fit_samples: int = 200,
) -> None:
    curve_attr = "bias_a_label"
    groups = group_rows(rows, curve_attr)
    group_items = sorted(groups.items(), key=lambda item: label_to_voltage(item[0], config.bias_a))
    cmap = plt.get_cmap("rainbow")
    colors = {
        label: darken_color(cmap(index / max(len(group_items) - 1, 1)))
        for index, (label, _) in enumerate(group_items)
    }

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), gridspec_kw={"height_ratios": [4, 4, 2]})
    diff_ax, ratio_ax, legend_ax = axes
    legend_ax.axis("off")
    for label, group in group_items:
        x = [row.phase_shift_s * 1e6 for row in group]
        diff_y = [row.difference_a_s * 1e12 for row in group]
        ratio_y = [row.ratio for row in group]
        if absolute_difference:
            diff_y = [abs(value) for value in diff_y]
        plot_label = format_bias_plot_label(config.bias_a, label) if len(groups) > 1 else None
        diff_ax.plot(x, diff_y, marker="o", markersize=3, linewidth=1.3, color=colors[label], label=plot_label)
        ratio_ax.plot(x, ratio_y, marker="o", markersize=3, linewidth=1.3, color=colors[label], label=plot_label)
        if fit_ratio:
            try:
                _, _, tau, fit_x, fit_y = fit_exponential_decay(x, ratio_y, fit_min_points, fit_samples)
            except Exception as exc:
                print(f"WARNING: could not fit ratio for {page_label}/{label}: {exc}", file=sys.stderr)
            else:
                fit_label = f"fit tau={tau:g} us" if plot_label is None else f"{plot_label} fit tau={tau:g} us"
                ratio_ax.plot(fit_x, fit_y, linestyle="--", linewidth=1.2, color=colors[label], label=fit_label)

    fixed_title = format_bias_plot_label(config.bias_b, page_label)
    diff_ax.set_xlabel(r"interspike interval ($\mu s$)")
    diff_ax.set_ylabel(r"$\Delta Q$ (pC)")
    diff_ax.set_title(rf"$\Delta Q$ of multiplexed and non multiplexed architecture, {fixed_title}")
    diff_ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    diff_ax.grid(True)
    ratio_ax.set_xlabel(r"interspike interval ($\mu s$)")
    ratio_ax.set_ylabel("ratio")
    ratio_ax.set_title(rf"charge ratio of multiplexed and non multiplexed architecture, {fixed_title}")
    ratio_ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    ratio_ax.grid(True)
    if max_phase_shift_us is not None:
        diff_ax.set_xlim(right=max_phase_shift_us)
        ratio_ax.set_xlim(right=max_phase_shift_us)
    if len(groups) > 1 or fit_ratio:
        ratio_handles, ratio_labels = ratio_ax.get_legend_handles_labels()
        if ratio_handles:
            legend_ax.legend(
                ratio_handles,
                ratio_labels,
                title=rf"$V_{{{config.bias_a.removeprefix('v')}}}$",
                loc="center",
                mode="expand",
                ncol=min(len(ratio_handles), 4),
            )
    fig.tight_layout()
    fig.subplots_adjust(hspace=0.55)
    return fig


def plot_integral_rows(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    absolute_difference: bool,
    open_all: bool,
    dry_run: bool,
    max_phase_shift_us: float | None,
    repo_root: Path,
    save_images: bool,
    no_show: bool,
    output_dir: Path | None,
    image_format: str,
    dpi: int,
    fit_ratio: bool = False,
    fit_min_points: int = 3,
    fit_samples: int = 200,
) -> None:
    pages = group_rows(rows, "bias_b_label")
    page_items = sorted(pages.items(), key=lambda item: label_to_voltage(item[0], config.bias_b))
    print(f"Rows plotted: {len(rows)}")
    print(f"{config.bias_b} pages: {', '.join(label for label, _ in page_items)}")
    print(f"{config.bias_a} curves: {', '.join(group_rows(rows, 'bias_a_label'))}")
    if max_phase_shift_us is not None:
        print(f"Max phase shift: {max_phase_shift_us:g} us")
    if fit_ratio:
        print(f"Ratio fit: y = y_inf + A * exp(-x / tau), min_points={fit_min_points}, samples={fit_samples}")
    if dry_run:
        return

    load_matplotlib_dependency()
    if fit_ratio:
        load_fit_dependencies()
    image_output_dir = resolve_output_dir(repo_root, output_dir, "dual_bias_sweeps", f"{config.bias_a}_{config.bias_b}_sweep")
    if open_all:
        for page_label, page_rows in page_items:
            fig = plot_integral_page(
                page_label,
                page_rows,
                config,
                absolute_difference,
                max_phase_shift_us,
                fit_ratio,
                fit_min_points,
                fit_samples,
            )
            if save_images:
                stem = f"{config.bias_a}_{config.bias_b}_integral_difference_{page_label}"
                if fit_ratio:
                    stem += "_ratio_fit"
                save_figure(fig, image_output_dir, stem, image_format, dpi)
        if not no_show:
            plt.show()
        return

    for page_label, page_rows in page_items:
        fig = plot_integral_page(
            page_label,
            page_rows,
            config,
            absolute_difference,
            max_phase_shift_us,
            fit_ratio,
            fit_min_points,
            fit_samples,
        )
        if save_images:
            stem = f"{config.bias_a}_{config.bias_b}_integral_difference_{page_label}"
            if fit_ratio:
                stem += "_ratio_fit"
            save_figure(fig, image_output_dir, stem, image_format, dpi)
        if not no_show:
            plt.show()
        plt.close("all")


def binned_metric_title(metric: str, cumulative_ratio: bool = False) -> str:
    if metric == "ratio":
        if cumulative_ratio:
            return "cumulative signed binned charge ratio"
        return "signed binned charge ratio"
    if metric == "charge-difference":
        return "signed binned charge difference"
    raise ValueError(f"unknown binned metric: {metric}")


def cumulative_binned_ratios(rows: Sequence[BinnedIntegralRow]) -> list[float]:
    one_total = 0.0
    two_total = 0.0
    ratios = []
    for row in rows:
        one_total += row.one_syn_integral_a_s
        two_total += row.two_syn_sum_integral_a_s
        if one_total == 0:
            ratios.append(float("nan"))
        else:
            ratios.append(two_total / one_total)
    return ratios


def binned_metric_values(rows: Sequence[BinnedIntegralRow], metric: str, cumulative_ratio: bool = False) -> list[float]:
    if metric == "ratio":
        if cumulative_ratio:
            return cumulative_binned_ratios(rows)
        return [row.ratio if math.isfinite(row.ratio) else math.nan for row in rows]
    if metric == "charge-difference":
        return [row.difference_a_s * 1e12 for row in rows]
    raise ValueError(f"unknown binned metric: {metric}")


def binned_metric_ylabel(metric: str, cumulative_ratio: bool = False) -> str:
    if metric == "ratio":
        if cumulative_ratio:
            return "cumulative signed integral ratio (2syn / 1syn)"
        return "signed integral ratio (2syn / 1syn)"
    if metric == "charge-difference":
        return "signed charge difference, 2syn - 1syn (pC)"
    raise ValueError(f"unknown binned metric: {metric}")


def binned_metric_series_label(metric: str) -> str:
    if metric == "ratio":
        return "ratio"
    if metric == "charge-difference":
        return "charge difference"
    raise ValueError(f"unknown binned metric: {metric}")


def binned_pair_title(rows: Sequence[BinnedIntegralRow], config: SweepConfig, metric: str, cumulative_ratio: bool = False) -> str:
    if not rows:
        raise ValueError("cannot title an empty binned pair")
    row = rows[0]
    return (
        f"{config.name} {binned_metric_title(metric, cumulative_ratio)}, "
        f"{format_bias_plot_label(config.bias_a, row.bias_a_label)}, "
        f"{format_bias_plot_label(config.bias_b, row.bias_b_label)}, "
        f"ISI = {row.phase_shift_s * 1e6:g} us"
    )


def binned_pair_stem(rows: Sequence[BinnedIntegralRow], config: SweepConfig, plot_kind: str, metric: str, cumulative_ratio: bool = False) -> str:
    if not rows:
        raise ValueError("cannot name an empty binned pair")
    row = rows[0]
    metric_label = metric.replace("-", "_")
    if metric == "ratio" and cumulative_ratio:
        metric_label = "cumulative_ratio"
    return f"{config.bias_a}_{config.bias_b}_binned_{metric_label}_{plot_kind}_{row.bias_a_label}_{row.bias_b_label}_{row.phase_shift}"


def voltage_spike_traces(rows: Sequence[BinnedIntegralRow]) -> tuple[Sequence[float], list[tuple[str, Sequence[float]]]]:
    if not rows:
        raise ValueError("cannot load voltage spikes for an empty binned pair")
    load_plot_dependencies()

    errors = []
    for csv_path_text, source in ((rows[0].two_syn_csv, "2syn"), (rows[0].one_syn_csv, "1syn")):
        csv_path = Path(csv_path_text)
        try:
            df = load_csv(csv_path)
            time_col = find_time_column(df)
            signals = signal_columns(df, time_col)
            if len(signals) < 2:
                raise ValueError(f"{source} CSV has fewer than two signal columns")
            voltage_cols = signals[-2:]
            traces = [(f"{source} {col}", df[col]) for col in voltage_cols]
            return df[time_col] * 1e6, traces
        except Exception as exc:
            errors.append(f"{source}={csv_path}: {exc}")
    raise ValueError("Could not load voltage spike traces from original CSVs: " + "; ".join(errors))


def overlay_voltage_spikes(ax, rows: Sequence[BinnedIntegralRow]) -> None:
    time_us, traces = voltage_spike_traces(rows)
    voltage_ax = ax.twinx()
    colors = ["tab:orange", "tab:green"]
    for index, (label, values) in enumerate(traces):
        voltage_ax.plot(
            time_us,
            values,
            linestyle="--",
            linewidth=1.0,
            alpha=0.75,
            color=colors[index % len(colors)],
            label=label,
        )
    voltage_ax.set_ylabel("voltage input spikes (V)")

    left_handles, left_labels = ax.get_legend_handles_labels()
    right_handles, right_labels = voltage_ax.get_legend_handles_labels()
    ax.legend(left_handles + right_handles, left_labels + right_labels, loc="best")


def plot_binned_ratio_pair(
    rows: Sequence[BinnedIntegralRow],
    config: SweepConfig,
    plot_kind: str,
    overlay_voltage: bool,
    metric: str,
    cumulative_ratio: bool = False,
):
    if not rows:
        raise ValueError("cannot plot an empty binned pair")
    if plot_kind not in {"histogram", "line"}:
        raise ValueError(f"unknown binned ratio plot kind: {plot_kind}")
    if metric not in {"ratio", "charge-difference"}:
        raise ValueError(f"unknown binned metric: {metric}")
    if cumulative_ratio and metric != "ratio":
        raise ValueError("cumulative ratio mode is only valid for ratio plots")
    sorted_rows = sorted(rows, key=lambda row: (row.bin_start_us, row.bin_end_us))
    x = [(row.bin_start_us + row.bin_end_us) / 2.0 for row in sorted_rows]
    widths = [max((row.bin_end_us - row.bin_start_us) * 0.82, 1e-9) for row in sorted_rows]
    y_values = binned_metric_values(sorted_rows, metric, cumulative_ratio)
    labels = [f"{row.bin_start_us:g}-{row.bin_end_us:g}" for row in sorted_rows]

    fig, ax = plt.subplots(1, 1, figsize=(12, 5.8), constrained_layout=True)
    if plot_kind == "histogram":
        ax.bar(x, y_values, width=widths, align="center", edgecolor="black", linewidth=0.5)
    else:
        ax.plot(x, y_values, marker="o", markersize=4, linewidth=1.4, label=binned_metric_series_label(metric))
    reference_value = 1.0 if metric == "ratio" else 0.0
    reference_label = "ratio = 1" if metric == "ratio" else "difference = 0 pC"
    ax.axhline(reference_value, color="black", linestyle="--", linewidth=1.0, label=reference_label)
    ax.set_xlabel(r"integration time / waveform time ($\mu s$)")
    ax.set_ylabel(binned_metric_ylabel(metric, cumulative_ratio))
    ax.set_title(binned_pair_title(sorted_rows, config, metric, cumulative_ratio))
    ax.grid(True, axis="y" if plot_kind == "histogram" else "both", alpha=0.35)
    if overlay_voltage and plot_kind == "line":
        overlay_voltage_spikes(ax, sorted_rows)
    else:
        ax.legend(loc="best")
    if plot_kind == "histogram" and len(labels) <= 30:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right")
    else:
        ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    return fig


def print_binned_ratio_dry_run(
    pair_groups: Sequence[tuple[tuple[str, str, str, str, str], list[BinnedIntegralRow]]],
    config: SweepConfig,
    max_phase_shift_us: float | None,
    plot_kind: str,
    overlay_voltage: bool,
    metric: str,
    cumulative_ratio: bool,
) -> None:
    print(f"Current pairs plotted: {len(pair_groups)}")
    print(f"Plot kind: {plot_kind}")
    print(f"Metric: {metric}")
    if metric == "ratio":
        print(f"Cumulative ratio: {'enabled' if cumulative_ratio else 'disabled'}")
    print(f"Voltage overlay: {'enabled' if overlay_voltage else 'disabled'}")
    if max_phase_shift_us is not None:
        print(f"Max phase shift: {max_phase_shift_us:g} us")
    for index, (_, rows) in enumerate(pair_groups[:10], start=1):
        row = rows[0]
        print(
            f"  [{index}] {row.bias_a_label}/{row.bias_b_label}/{row.phase_shift}: "
            f"{len(rows)} bins, ISI={row.phase_shift_s * 1e6:g} us"
        )
    if len(pair_groups) > 10:
        print(f"  ... {len(pair_groups) - 10} more")


def plot_binned_ratio_pair_groups(
    pair_groups: Sequence[tuple[tuple[str, str, str, str, str], list[BinnedIntegralRow]]],
    config: SweepConfig,
    plot_kind: str,
    overlay_voltage: bool,
    metric: str,
    cumulative_ratio: bool,
    open_all: bool,
    dry_run: bool,
    max_phase_shift_us: float | None,
    repo_root: Path,
    save_images: bool,
    no_show: bool,
    output_dir: Path | None,
    image_format: str,
    dpi: int,
) -> None:
    print_binned_ratio_dry_run(pair_groups, config, max_phase_shift_us, plot_kind, overlay_voltage, metric, cumulative_ratio)
    if dry_run:
        return

    load_matplotlib_dependency()
    image_output_dir = resolve_output_dir(repo_root, output_dir, "dual_bias_sweeps", f"{config.bias_a}_{config.bias_b}_sweep")
    if open_all:
        for _, rows in pair_groups:
            fig = plot_binned_ratio_pair(rows, config, plot_kind, overlay_voltage, metric, cumulative_ratio)
            if save_images:
                save_figure(fig, image_output_dir, binned_pair_stem(rows, config, plot_kind, metric, cumulative_ratio), image_format, dpi)
        if not no_show:
            plt.show()
        return

    for _, rows in pair_groups:
        fig = plot_binned_ratio_pair(rows, config, plot_kind, overlay_voltage, metric, cumulative_ratio)
        if save_images:
            save_figure(fig, image_output_dir, binned_pair_stem(rows, config, plot_kind, metric, cumulative_ratio), image_format, dpi)
        if not no_show:
            plt.show()
        plt.close("all")


def group_rows_by_phase_shift(rows: Sequence[IntegralRow]) -> dict[str, list[IntegralRow]]:
    groups: dict[str, list[IntegralRow]] = {}
    for row in rows:
        groups.setdefault(row.phase_shift, []).append(row)
    return dict(sorted(groups.items(), key=lambda item: parse_phase_shift_value(item[0])))


def sorted_voltage_labels(rows: Sequence[IntegralRow], attr: str, bias: str) -> list[str]:
    labels = {getattr(row, attr) for row in rows}
    return sorted(labels, key=lambda label: label_to_voltage(label, bias))


def matrix_dimensions(rows: Sequence[IntegralRow], config: SweepConfig) -> tuple[list[str], list[str]]:
    x_labels = sorted_voltage_labels(rows, "bias_a_label", config.bias_a)
    y_labels = sorted_voltage_labels(rows, "bias_b_label", config.bias_b)
    return x_labels, y_labels


def heatmap_value(row: IntegralRow, metric: str, charge_scale: float) -> float:
    if metric == "charge":
        return abs(row.difference_a_s) * charge_scale
    if metric == "ratio":
        return row.ratio
    if metric == "inverse_ratio":
        if row.ratio == 0:
            return math.nan
        return 1 / row.ratio
    raise ValueError(f"unknown heatmap metric: {metric}")


def heatmap_matrix(
    rows: Sequence[IntegralRow],
    x_labels: Sequence[str],
    y_labels: Sequence[str],
    metric: str,
    charge_scale: float,
) -> list[list[float]]:
    x_index = {label: index for index, label in enumerate(x_labels)}
    y_index = {label: index for index, label in enumerate(y_labels)}
    matrix = [[math.nan for _ in x_labels] for _ in y_labels]
    for row in rows:
        matrix[y_index[row.bias_b_label]][x_index[row.bias_a_label]] = heatmap_value(row, metric, charge_scale)
    return matrix


def missing_heatmap_cells(rows: Sequence[IntegralRow], x_labels: Sequence[str], y_labels: Sequence[str]) -> list[tuple[str, str]]:
    present = {(row.bias_a_label, row.bias_b_label) for row in rows}
    return [(x_label, y_label) for y_label in y_labels for x_label in x_labels if (x_label, y_label) not in present]


def phase_shift_title(phase_shift: str) -> str:
    return f"ISI = {parse_phase_shift_value(phase_shift) * 1e6:g} us"


def bias_axis_label(bias: str) -> str:
    return rf"$V_{{{bias.removeprefix('v')}}}$ (V)"


def heatmap_specs(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    charge_unit: str,
    charge_vmin: float | None,
    charge_vmax: float | None,
    ratio_vmin: float | None,
    ratio_vmax: float | None,
    inverse_ratio_vmin: float | None,
    inverse_ratio_vmax: float | None,
) -> tuple[list[str], list[str], list[tuple[str, list[list[float]], float | None, float | None]]]:
    x_labels, y_labels = matrix_dimensions(rows, config)
    charge_scale = 1e12 if charge_unit == "pC" else 1.0
    charge_matrix = heatmap_matrix(rows, x_labels, y_labels, "charge", charge_scale)
    ratio_matrix = heatmap_matrix(rows, x_labels, y_labels, "ratio", charge_scale)
    inverse_ratio_matrix = heatmap_matrix(rows, x_labels, y_labels, "inverse_ratio", charge_scale)
    specs = [
        (f"Absolute charge difference ({charge_unit})", charge_matrix, charge_vmin, charge_vmax),
        ("Charge ratio", ratio_matrix, ratio_vmin, ratio_vmax),
        ("Inverse charge ratio", inverse_ratio_matrix, inverse_ratio_vmin, inverse_ratio_vmax),
    ]
    return x_labels, y_labels, specs


def draw_heatmap(ax, fig, matrix, title: str, vmin: float | None, vmax: float | None, x_labels: Sequence[str], y_labels: Sequence[str], config: SweepConfig, cmap: str) -> None:
    x_ticks = [label_to_voltage(label, config.bias_a) for label in x_labels]
    y_ticks = [label_to_voltage(label, config.bias_b) for label in y_labels]
    image = ax.imshow(matrix, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xlabel(bias_axis_label(config.bias_a))
    ax.set_ylabel(bias_axis_label(config.bias_b))
    ax.set_xticks(range(len(x_labels)), [f"{value:g}" for value in x_ticks], rotation=45, ha="right")
    ax.set_yticks(range(len(y_labels)), [f"{value:g}" for value in y_ticks])
    fig.colorbar(image, ax=ax)


def plot_heatmap_page(
    phase_shift: str,
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    charge_unit: str,
    charge_vmin: float | None,
    charge_vmax: float | None,
    ratio_vmin: float | None,
    ratio_vmax: float | None,
    inverse_ratio_vmin: float | None,
    inverse_ratio_vmax: float | None,
    cmap: str,
) -> None:
    x_labels, y_labels, specs = heatmap_specs(
        rows,
        config,
        charge_unit,
        charge_vmin,
        charge_vmax,
        ratio_vmin,
        ratio_vmax,
        inverse_ratio_vmin,
        inverse_ratio_vmax,
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8), constrained_layout=True)
    fig.suptitle(phase_shift_title(phase_shift))
    for ax, (title, matrix, vmin, vmax) in zip(axes, specs):
        draw_heatmap(ax, fig, matrix, title, vmin, vmax, x_labels, y_labels, config, cmap)
    return fig


def plot_single_heatmap_page(
    phase_shift: str,
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    title: str,
    matrix: list[list[float]],
    vmin: float | None,
    vmax: float | None,
    x_labels: Sequence[str],
    y_labels: Sequence[str],
    cmap: str,
) -> None:
    fig, ax = plt.subplots(1, 1, figsize=(7.5, 6.2), constrained_layout=True)
    fig.suptitle(f"{phase_shift_title(phase_shift)} - {title}")
    draw_heatmap(ax, fig, matrix, title, vmin, vmax, x_labels, y_labels, config, cmap)
    return fig


def print_heatmap_dry_run(rows: Sequence[IntegralRow], config: SweepConfig, sequential: bool) -> None:
    phase_groups = group_rows_by_phase_shift(rows)
    x_labels, y_labels = matrix_dimensions(rows, config)
    print(f"Rows plotted: {len(rows)}")
    print(f"Display mode: {'sequential metrics' if sequential else 'side-by-side metrics'}")
    print(f"Phase-shift pages: {', '.join(phase_groups)}")
    print(f"{config.bias_a} x-axis labels: {', '.join(x_labels)}")
    print(f"{config.bias_b} y-axis labels: {', '.join(y_labels)}")
    for phase_shift, phase_rows in phase_groups.items():
        missing = missing_heatmap_cells(phase_rows, x_labels, y_labels)
        if missing:
            print(f"WARNING {phase_shift}: {len(missing)} missing heatmap cells")


def plot_integral_heatmaps(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    charge_unit: str,
    charge_vmin: float | None,
    charge_vmax: float | None,
    ratio_vmin: float | None,
    ratio_vmax: float | None,
    inverse_ratio_vmin: float | None,
    inverse_ratio_vmax: float | None,
    cmap: str,
    open_all: bool,
    sequential: bool,
    dry_run: bool,
    repo_root: Path,
    save_images: bool,
    no_show: bool,
    output_dir: Path | None,
    image_format: str,
    dpi: int,
) -> None:
    phase_groups = group_rows_by_phase_shift(rows)
    print_heatmap_dry_run(rows, config, sequential)
    if dry_run:
        return

    load_matplotlib_dependency()
    image_output_dir = resolve_output_dir(repo_root, output_dir, "dual_bias_sweeps", f"{config.bias_a}_{config.bias_b}_sweep")
    if sequential:
        for phase_shift, phase_rows in phase_groups.items():
            x_labels, y_labels, specs = heatmap_specs(
                phase_rows,
                config,
                charge_unit,
                charge_vmin,
                charge_vmax,
                ratio_vmin,
                ratio_vmax,
                inverse_ratio_vmin,
                inverse_ratio_vmax,
            )
            for title, matrix, vmin, vmax in specs:
                fig = plot_single_heatmap_page(phase_shift, phase_rows, config, title, matrix, vmin, vmax, x_labels, y_labels, cmap)
                if save_images:
                    save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_heatmap_{phase_shift}_{title}", image_format, dpi)
                if not no_show:
                    plt.show()
                plt.close("all")
        return

    if open_all:
        for phase_shift, phase_rows in phase_groups.items():
            fig = plot_heatmap_page(
                phase_shift,
                phase_rows,
                config,
                charge_unit,
                charge_vmin,
                charge_vmax,
                ratio_vmin,
                ratio_vmax,
                inverse_ratio_vmin,
                inverse_ratio_vmax,
                cmap,
            )
            if save_images:
                save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_heatmap_{phase_shift}", image_format, dpi)
        if not no_show:
            plt.show()
        return

    for phase_shift, phase_rows in phase_groups.items():
        fig = plot_heatmap_page(
            phase_shift,
            phase_rows,
            config,
            charge_unit,
            charge_vmin,
            charge_vmax,
            ratio_vmin,
            ratio_vmax,
            inverse_ratio_vmin,
            inverse_ratio_vmax,
            cmap,
        )
        if save_images:
            save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_heatmap_{phase_shift}", image_format, dpi)
        if not no_show:
            plt.show()
        plt.close("all")


def tolerance_matrix(
    rows: Sequence[IntegralRow],
    x_labels: Sequence[str],
    y_labels: Sequence[str],
    tollerance: float,
) -> list[list[float]]:
    lower = 1.0 - tollerance
    upper = 1.0 + tollerance
    x_index = {label: index for index, label in enumerate(x_labels)}
    y_index = {label: index for index, label in enumerate(y_labels)}
    matrix = [[0.0 for _ in x_labels] for _ in y_labels]
    for row in rows:
        ratio = row.ratio
        if not math.isnan(ratio) and lower <= ratio <= upper:
            matrix[y_index[row.bias_b_label]][x_index[row.bias_a_label]] = 1.0
    return matrix


def tolerance_title(tollerance: float) -> str:
    return f"Charge ratio within {tollerance * 100:g}% of 1"


def tolerance_filename_value(tollerance: float) -> str:
    return f"{tollerance:g}".replace("-", "m").replace(".", "p")


def plot_tolerance_heatmap_page(
    phase_shift: str,
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    tollerance: float,
) -> None:
    from matplotlib.colors import ListedColormap

    x_labels, y_labels = matrix_dimensions(rows, config)
    matrix = tolerance_matrix(rows, x_labels, y_labels, tollerance)
    fig, ax = plt.subplots(1, 1, figsize=(7.5, 6.2), constrained_layout=True)
    title = tolerance_title(tollerance)
    fig.suptitle(f"{phase_shift_title(phase_shift)} - {title}")
    draw_heatmap(
        ax,
        fig,
        matrix,
        title,
        0,
        1,
        x_labels,
        y_labels,
        config,
        ListedColormap(["white", "black"]),
    )
    return fig


def print_tolerance_heatmap_dry_run(rows: Sequence[IntegralRow], config: SweepConfig, tollerance: float) -> None:
    phase_groups = group_rows_by_phase_shift(rows)
    x_labels, y_labels = matrix_dimensions(rows, config)
    print(f"Rows plotted: {len(rows)}")
    print(f"Tolerance: +/-{tollerance * 100:g}%")
    print(f"Phase-shift pages: {', '.join(phase_groups)}")
    print(f"{config.bias_a} x-axis labels: {', '.join(x_labels)}")
    print(f"{config.bias_b} y-axis labels: {', '.join(y_labels)}")
    for phase_shift, phase_rows in phase_groups.items():
        missing = missing_heatmap_cells(phase_rows, x_labels, y_labels)
        if missing:
            print(f"WARNING {phase_shift}: {len(missing)} missing heatmap cells")


def plot_integral_tolerance_heatmaps(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    tollerance: float,
    open_all: bool,
    dry_run: bool,
    repo_root: Path,
    save_images: bool,
    no_show: bool,
    output_dir: Path | None,
    image_format: str,
    dpi: int,
) -> None:
    if tollerance < 0:
        raise ValueError("--tollerance must be >= 0")
    phase_groups = group_rows_by_phase_shift(rows)
    print_tolerance_heatmap_dry_run(rows, config, tollerance)
    if dry_run:
        return

    load_matplotlib_dependency()
    image_output_dir = resolve_output_dir(repo_root, output_dir, "dual_bias_sweeps", f"{config.bias_a}_{config.bias_b}_sweep")
    filename_tol = tolerance_filename_value(tollerance)
    if open_all:
        for phase_shift, phase_rows in phase_groups.items():
            fig = plot_tolerance_heatmap_page(phase_shift, phase_rows, config, tollerance)
            if save_images:
                save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_tolerance_heatmap_{phase_shift}_tol_{filename_tol}", image_format, dpi)
        if not no_show:
            plt.show()
        return

    for phase_shift, phase_rows in phase_groups.items():
        fig = plot_tolerance_heatmap_page(phase_shift, phase_rows, config, tollerance)
        if save_images:
            save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_tolerance_heatmap_{phase_shift}_tol_{filename_tol}", image_format, dpi)
        if not no_show:
            plt.show()
        plt.close("all")


def normalize_volume_metric(metric: str) -> str:
    if metric == "inverse-ratio":
        return "inverse_ratio"
    return metric


def selected_volume_metrics(metric: str | None) -> list[str]:
    if metric is None:
        return ["charge", "ratio", "inverse_ratio"]
    return [normalize_volume_metric(metric)]


def volume_metric_title(metric: str, charge_unit: str) -> str:
    if metric == "charge":
        return f"absolute charge difference ({charge_unit})"
    if metric == "ratio":
        return "charge ratio"
    if metric == "inverse_ratio":
        return "inverse charge ratio"
    raise ValueError(f"unknown volume metric: {metric}")


def phase_stride_groups(phase_groups: dict[str, list[IntegralRow]], stride_phase: int) -> dict[str, list[IntegralRow]]:
    if stride_phase < 1:
        raise ValueError("--stride-phase must be >= 1")
    return dict(list(phase_groups.items())[::stride_phase])


def volume_points(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    metric: str,
    charge_unit: str,
) -> tuple[list[float], list[float], list[float], list[float]]:
    charge_scale = 1e12 if charge_unit == "pC" else 1.0
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    values: list[float] = []
    for row in rows:
        value = heatmap_value(row, metric, charge_scale)
        if math.isnan(value):
            continue
        xs.append(label_to_voltage(row.bias_a_label, config.bias_a))
        ys.append(label_to_voltage(row.bias_b_label, config.bias_b))
        zs.append(row.phase_shift_s * 1e6)
        values.append(value)
    if not values:
        raise ValueError("No finite values available for volume plot")
    return xs, ys, zs, values


def finite_vmin_vmax(values: Sequence[float], vmin: float | None, vmax: float | None) -> tuple[float, float]:
    finite = [value for value in values if not math.isnan(value)]
    if not finite:
        raise ValueError("No finite values available for color scale")
    return (min(finite) if vmin is None else vmin, max(finite) if vmax is None else vmax)


def print_volume_dry_run(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    metrics: Sequence[str],
    charge_unit: str,
    stride_phase: int,
) -> None:
    phase_groups = phase_stride_groups(group_rows_by_phase_shift(rows), stride_phase)
    x_labels, y_labels = matrix_dimensions(rows, config)
    print(f"Rows plotted: {len(rows)}")
    metric_titles = [volume_metric_title(metric, charge_unit) for metric in metrics]
    label = "Metrics" if len(metric_titles) > 1 else "Metric"
    print(f"{label}: {', '.join(metric_titles)}")
    print(f"Phase-shift z-axis values: {', '.join(phase_groups)}")
    print(f"{config.bias_a} x-axis labels: {', '.join(x_labels)}")
    print(f"{config.bias_b} y-axis labels: {', '.join(y_labels)}")
    if stride_phase > 1:
        print(f"Phase stride: {stride_phase}")
    for phase_shift, phase_rows in phase_groups.items():
        missing = missing_heatmap_cells(phase_rows, x_labels, y_labels)
        if missing:
            print(f"WARNING {phase_shift}: {len(missing)} missing volume cells")


def setup_volume_axes(fig, config: SweepConfig, metric: str, charge_unit: str):
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title(f"{config.name} integral volume: {volume_metric_title(metric, charge_unit)}")
    ax.set_xlabel(bias_axis_label(config.bias_a))
    ax.set_ylabel(bias_axis_label(config.bias_b))
    ax.set_zlabel(r"interspike interval ($\mu s$)")
    return ax


def plot_volume_scatter(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    metric: str,
    charge_unit: str,
    marker_size: float,
    alpha: float,
    cmap: str,
    vmin: float | None,
    vmax: float | None,
) -> None:
    xs, ys, zs, values = volume_points(rows, config, metric, charge_unit)
    fig = plt.figure(figsize=(11, 8))
    ax = setup_volume_axes(fig, config, metric, charge_unit)
    scatter = ax.scatter(
        xs,
        ys,
        zs,
        c=values,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=marker_size,
        alpha=alpha,
        depthshade=True,
    )
    fig.colorbar(scatter, ax=ax, shrink=0.7, pad=0.12)
    fig.tight_layout()
    return fig


def plot_volume_surfaces(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    metric: str,
    charge_unit: str,
    alpha: float,
    cmap: str,
    vmin: float | None,
    vmax: float | None,
) -> None:
    try:
        import numpy as np
        from matplotlib import cm, colors
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Surface volume view requires numpy and matplotlib.") from exc

    phase_groups = group_rows_by_phase_shift(rows)
    x_labels, y_labels = matrix_dimensions(rows, config)
    x_values = [label_to_voltage(label, config.bias_a) for label in x_labels]
    y_values = [label_to_voltage(label, config.bias_b) for label in y_labels]
    x_grid, y_grid = np.meshgrid(x_values, y_values)
    charge_scale = 1e12 if charge_unit == "pC" else 1.0
    _, _, _, all_values = volume_points(rows, config, metric, charge_unit)
    norm = colors.Normalize(*finite_vmin_vmax(all_values, vmin, vmax))
    color_map = cm.get_cmap(cmap)

    fig = plt.figure(figsize=(11, 8))
    ax = setup_volume_axes(fig, config, metric, charge_unit)
    last_surface = None
    for phase_shift, phase_rows in phase_groups.items():
        z_value = parse_phase_shift_value(phase_shift) * 1e6
        z_grid = np.full_like(x_grid, z_value, dtype=float)
        matrix = np.array(heatmap_matrix(phase_rows, x_labels, y_labels, metric, charge_scale), dtype=float)
        facecolors = color_map(norm(matrix))
        last_surface = ax.plot_surface(
            x_grid,
            y_grid,
            z_grid,
            facecolors=facecolors,
            linewidth=0,
            antialiased=False,
            shade=False,
            alpha=alpha,
        )
        ax.plot_wireframe(x_grid, y_grid, z_grid, color="black", linewidth=0.25, alpha=min(alpha + 0.2, 1.0))

    if last_surface is not None:
        mappable = cm.ScalarMappable(norm=norm, cmap=color_map)
        mappable.set_array([])
        fig.colorbar(mappable, ax=ax, shrink=0.7, pad=0.12)
    fig.tight_layout()
    return fig


def plot_integral_volume(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    metric: str | None,
    view: str,
    charge_unit: str,
    alpha: float,
    marker_size: float,
    cmap: str,
    vmin: float | None,
    vmax: float | None,
    stride_phase: int,
    dry_run: bool,
    repo_root: Path,
    save_images: bool,
    no_show: bool,
    output_dir: Path | None,
    image_format: str,
    dpi: int,
) -> None:
    metrics = selected_volume_metrics(metric)
    phase_groups = phase_stride_groups(group_rows_by_phase_shift(rows), stride_phase)
    rows = [row for phase_rows in phase_groups.values() for row in phase_rows]
    print_volume_dry_run(rows, config, metrics, charge_unit, stride_phase)
    if dry_run:
        return

    load_matplotlib_dependency()
    image_output_dir = resolve_output_dir(repo_root, output_dir, "dual_bias_sweeps", f"{config.bias_a}_{config.bias_b}_sweep")
    for metric_name in metrics:
        if view == "scatter":
            fig = plot_volume_scatter(rows, config, metric_name, charge_unit, marker_size, alpha, cmap, vmin, vmax)
        elif view == "surfaces":
            fig = plot_volume_surfaces(rows, config, metric_name, charge_unit, alpha, cmap, vmin, vmax)
        else:
            raise ValueError(f"unknown volume view: {view}")
        if save_images:
            save_figure(fig, image_output_dir, f"{config.bias_a}_{config.bias_b}_volume_{metric_name}", image_format, dpi)
        if not no_show:
            plt.show()
        plt.close("all")


def plot_one_csv(csv_path: Path, input_dir: Path, index: int, total: int) -> None:
    df = load_csv(csv_path)
    time_col = find_time_column(df)
    signals = signal_columns(df, time_col)
    label = str(csv_path.relative_to(input_dir).with_suffix(""))

    fig_height = max(5.0, 2.2 * len(signals))
    fig, axes = plt.subplots(len(signals), 1, sharex=True, figsize=(11, fig_height))
    if len(signals) == 1:
        axes = [axes]

    try:
        fig.canvas.manager.set_window_title(f"{index}/{total}: {label}")
    except Exception:
        pass

    for ax, col in zip(axes, signals):
        ax.plot(df[time_col], df[col])
        ax.set_ylabel(str(col))
        ax.grid(True)

    axes[0].set_title(f"{label}    [{index}/{total}]")
    axes[-1].set_xlabel(str(time_col))
    fig.tight_layout()


def plot_combined_pair(rel_path: Path, one_syn_csv: Path, two_syn_csv: Path, index: int, total: int) -> None:
    one_df = load_csv(one_syn_csv)
    two_df = load_csv(two_syn_csv)
    one_time = find_time_column(one_df)
    two_time = find_time_column(two_df)
    one_signals = signal_columns(one_df, one_time)
    two_signals = signal_columns(two_df, two_time)

    plots = [("1syn", one_df, one_time, col) for col in one_signals]
    plots.extend(("2syn", two_df, two_time, col) for col in two_signals)

    fig_height = max(8.0, 2.0 * len(plots))
    fig, axes = plt.subplots(len(plots), 1, sharex=False, figsize=(12, fig_height))
    if len(plots) == 1:
        axes = [axes]

    label = str(rel_path.with_suffix(""))
    try:
        fig.canvas.manager.set_window_title(f"{index}/{total}: {label}")
    except Exception:
        pass

    for ax, (source, df, time_col, signal_col) in zip(axes, plots):
        ax.plot(df[time_col], df[signal_col])
        ax.set_ylabel(f"{source} {signal_col}")
        ax.grid(True)

    axes[0].set_title(f"{label}    [{index}/{total}]")
    axes[-1].set_xlabel("time_s")
    fig.tight_layout()


def plot_current_pair(rel_path: Path, one_syn_csv: Path, two_syn_csv: Path, index: int, total: int, filled: bool) -> None:
    one_df = load_csv(one_syn_csv)
    two_df = load_csv(two_syn_csv)
    one_time = find_time_column(one_df)
    two_time = find_time_column(two_df)

    require_columns(one_df, [one_time, ONE_SYN_CURRENT], "1syn")
    require_columns(two_df, [two_time, TWO_SYN_I172, TWO_SYN_I56], "2syn")

    one_df, two_df, equalize_note = equalize_dataframe_lengths(one_df, two_df, one_time, two_time)
    one_i56 = subtract_initial(one_df[ONE_SYN_CURRENT])
    two_i172 = subtract_initial(two_df[TWO_SYN_I172])
    two_i56 = subtract_initial(two_df[TWO_SYN_I56])
    two_syn_sum = subtract_initial(two_df[TWO_SYN_I172] + two_df[TWO_SYN_I56])

    label = str(rel_path.with_suffix(""))
    if filled:
        one_i56 = one_i56 * 1e9
        two_syn_sum = two_syn_sum * 1e9
        plots = [
            (one_df[one_time] * 1e6, one_i56, r"$I_{syn}$ multiplexed (nA)"),
            (two_df[two_time] * 1e6, two_syn_sum, r"$I_{syn}$ non-multiplexed (nA)"),
        ]
        fig, axes = plt.subplots(2, 1, sharex=False, figsize=(12, 7))
        y_min = min(one_i56.min(), two_syn_sum.min(), 0)
        y_max = max(one_i56.max(), two_syn_sum.max(), 0)
        padding = (y_max - y_min) * 0.05 or 1e-12
        for ax, (time_values, current_values, ylabel) in zip(axes, plots):
            ax.plot(time_values, current_values)
            ax.fill_between(time_values, current_values, 0, alpha=0.25)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_ylim(y_min - padding, y_max + padding)
            ax.set_ylabel(ylabel)
            ax.grid(True)
        axes[-1].set_xlabel(r"time ($\mu s$)")
    else:
        plots = [
            (one_df[one_time], one_i56, f"1syn {ONE_SYN_CURRENT} - initial"),
            (two_df[two_time], two_i172, f"2syn {TWO_SYN_I172} - initial"),
            (two_df[two_time], two_i56, f"2syn {TWO_SYN_I56} - initial"),
            (two_df[two_time], two_syn_sum, "2syn summed current - initial"),
        ]
        fig, axes = plt.subplots(4, 1, sharex=False, figsize=(12, 9))
        for ax, (time_values, current_values, ylabel) in zip(axes, plots):
            ax.plot(time_values, current_values)
            ax.set_ylabel(ylabel)
            ax.grid(True)
        axes[-1].set_xlabel("time_s")

    try:
        fig.canvas.manager.set_window_title(f"{index}/{total}: {label}")
    except Exception:
        pass
    axes[0].set_title(f"{label}    [{index}/{total}]")
    fig.tight_layout()
    print(f"[{index:03d}/{total:03d}] {rel_path}")
    print(f"    1syn={one_syn_csv}")
    print(f"    2syn={two_syn_csv}")
    print(f"    rows: 1syn={len(one_df)}, 2syn={len(two_df)}")
    print("    baseline: first sample subtracted from each current trace")
    if equalize_note:
        print(f"    NOTE: {equalize_note}")


def add_common_pair_args(parser: argparse.ArgumentParser, config: SweepConfig) -> None:
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--one-syn-dir", type=Path, default=None)
    parser.add_argument("--two-syn-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    for bias in config.biases:
        parser.add_argument(f"--{bias}", default=None, help=f"Only include this {bias} label, e.g. {bias}_0p7 or 0p7.")
    parser.add_argument("--debug", action="store_true")


def select_pairs(args: argparse.Namespace, config: SweepConfig) -> tuple[Path, Path, Path, list[tuple[Path, Path, Path]]]:
    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
    one_syn_dir = args.one_syn_dir.resolve() if args.one_syn_dir else default_one_syn_dir(repo_root, config)
    two_syn_dir = args.two_syn_dir.resolve() if args.two_syn_dir else default_two_syn_dir(repo_root, config)
    if args.start_at < 1:
        raise ValueError("--start-at must be >= 1")
    pairs = apply_pair_filters(find_current_pairs(one_syn_dir, two_syn_dir, config), args, config)
    pairs = pairs[args.start_at - 1:]
    if args.limit is not None:
        pairs = pairs[:args.limit]
    if not pairs:
        raise FileNotFoundError("No CSV pairs selected after filtering.")
    return repo_root, one_syn_dir, two_syn_dir, pairs


def main_integrate(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Integrate absolute baseline-subtracted {config.name} phase-shift currents.")
    add_common_pair_args(parser, config)
    parser.add_argument("--output-csv", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        _, one_syn_dir, two_syn_dir, pairs = select_pairs(args, config)
        results = [integrate_pair(rel_path, one_csv, two_csv, config) for rel_path, one_csv, two_csv in pairs]
        write_results(results, sys.stdout, config)
        if args.output_csv is not None:
            args.output_csv.parent.mkdir(parents=True, exist_ok=True)
            with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
                write_results(results, handle, config)
        return 0
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_binned_currents(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Integrate signed {config.name} phase-shift currents in fixed-width time bins.")
    add_common_pair_args(parser, config)
    parser.add_argument(
        "--bin-width-us",
        type=float,
        default=1.0,
        help="Time-bin width in microseconds. Default: 1.0.",
    )
    parser.add_argument("--output-csv", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.bin_width_us <= 0:
            raise ValueError("--bin-width-us must be greater than 0")

        _, one_syn_dir, two_syn_dir, pairs = select_pairs(args, config)
        results = []
        for rel_path, one_csv, two_csv in pairs:
            results.extend(integrate_pair_binned(rel_path, one_csv, two_csv, config, args.bin_width_us))

        write_binned_results(results, sys.stdout, config)
        if args.output_csv is not None:
            args.output_csv.parent.mkdir(parents=True, exist_ok=True)
            with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
                write_binned_results(results, handle, config)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_binned_plot(config: SweepConfig, plot_kind: str, metric: str, argv: Optional[list[str]] = None) -> int:
    if plot_kind not in {"histogram", "line"}:
        raise ValueError(f"unknown binned ratio plot kind: {plot_kind}")
    if metric not in {"ratio", "charge-difference"}:
        raise ValueError(f"unknown binned metric: {metric}")
    description_kind = "histogram-style bar charts" if plot_kind == "histogram" else "continuous line plots"
    description_metric = "integral ratios" if metric == "ratio" else "charge differences"
    parser = argparse.ArgumentParser(description=f"Plot per-current-pair signed binned {description_metric} as {description_kind} for {config.name}.")
    add_common_pair_args(parser, config)
    parser.add_argument("--binned-integrals-csv", type=Path, default=None)
    parser.add_argument(
        "--bin-width-us",
        type=float,
        default=1.0,
        help="Time-bin width in microseconds when computing binned integrals directly. Default: 1.0.",
    )
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot current pairs at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument(
        "--no-voltage-overlay",
        action="store_true",
        help="Disable voltage input spike overlay on continuous line plots.",
    )
    parser.add_argument(
        "--cumulative-ratio",
        action="store_true",
        help="For ratio plots, use cumulative integrals from 0 through each bin instead of per-bin integrals.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate selected binned-ratio plots without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        if args.bin_width_us <= 0:
            raise ValueError("--bin-width-us must be greater than 0")
        if args.cumulative_ratio and metric != "ratio":
            raise ValueError("--cumulative-ratio is only valid for ratio plots")

        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.binned_integrals_csv is not None:
            rows = load_binned_integral_rows_from_csv(args.binned_integrals_csv.resolve(), config)
        else:
            rows = compute_binned_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config, args.bin_width_us)
        rows = apply_binned_row_filters(rows, args, config)
        rows = filter_binned_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        pair_groups = selected_binned_pair_groups(rows, args.start_at, args.limit)
        plot_binned_ratio_pair_groups(
            pair_groups,
            config,
            plot_kind,
            plot_kind == "line" and not args.no_voltage_overlay,
            metric,
            args.cumulative_ratio,
            args.open_all,
            args.dry_run,
            args.max_phase_shift_us,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_binned_ratio_histogram(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    return main_binned_plot(config, "histogram", "ratio", argv)


def main_binned_ratio_line(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    return main_binned_plot(config, "line", "ratio", argv)


def main_binned_charge_difference_line(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    return main_binned_plot(config, "line", "charge-difference", argv)


def main_integral_difference(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Plot summed-2syn-minus-1syn {config.name} phase-shift integral difference.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--absolute-difference", action="store_true")
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot phase-shift points at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print plot pages without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)
        plot_integral_rows(
            rows,
            config,
            args.absolute_difference,
            args.open_all,
            args.dry_run,
            args.max_phase_shift_us,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_integral_difference_fit(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Plot {config.name} phase-shift integral difference with ratio exponential fits.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--absolute-difference", action="store_true")
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot phase-shift points at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument("--fit-min-points", type=int, default=3, help="Minimum finite ratio points required to fit a curve.")
    parser.add_argument("--fit-samples", type=int, default=200, help="Number of samples used to draw each fitted curve.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print plot pages without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        if args.fit_min_points < 3:
            raise ValueError("--fit-min-points must be >= 3")
        if args.fit_samples < 2:
            raise ValueError("--fit-samples must be >= 2")
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)
        plot_integral_rows(
            rows,
            config,
            args.absolute_difference,
            args.open_all,
            args.dry_run,
            args.max_phase_shift_us,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
            fit_ratio=True,
            fit_min_points=args.fit_min_points,
            fit_samples=args.fit_samples,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def write_ratio_fit_threshold_rows(
    rows: Sequence[IntegralRow],
    config: SweepConfig,
    threshold: float,
    max_us: float,
    fit_min_points: int,
    handle,
) -> None:
    writer = csv.writer(handle)
    writer.writerow([
        "fixed_bias",
        "fixed_bias_label",
        "curve_bias",
        "curve_bias_label",
        "threshold",
        "max_us",
        "tau_us",
        "y_inf",
        "amplitude",
        "crossing_us",
        "status",
    ])

    pages = group_rows(rows, "bias_b_label")
    for fixed_label, page_rows in sorted(pages.items(), key=lambda item: label_to_voltage(item[0], config.bias_b)):
        groups = group_rows(page_rows, "bias_a_label")
        for curve_label, curve_rows in sorted(groups.items(), key=lambda item: label_to_voltage(item[0], config.bias_a)):
            try:
                y_inf, amplitude, tau, x_min = ratio_fit_params(curve_rows, fit_min_points)
                status, crossing = threshold_crossing_us(y_inf, amplitude, tau, x_min, max_us, threshold)
                writer.writerow([
                    config.bias_b,
                    fixed_label,
                    config.bias_a,
                    curve_label,
                    f"{threshold:.12g}",
                    f"{max_us:.12g}",
                    f"{tau:.12g}",
                    f"{y_inf:.12g}",
                    f"{amplitude:.12g}",
                    "" if crossing is None else f"{crossing:.12g}",
                    status,
                ])
            except Exception as exc:
                writer.writerow([
                    config.bias_b,
                    fixed_label,
                    config.bias_a,
                    curve_label,
                    f"{threshold:.12g}",
                    f"{max_us:.12g}",
                    "",
                    "",
                    "",
                    "",
                    f"fit_failed: {exc}",
                ])


def main_ratio_fit_threshold(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Export {config.name} ratio-fit threshold crossing data as CSV.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--threshold", type=float, required=True, help="Ratio threshold, e.g. 1.2.")
    parser.add_argument("--max-us", type=float, default=500.0, help="Maximum extrapolated interspike interval in microseconds.")
    parser.add_argument("--fit-min-points", type=int, default=3, help="Minimum finite ratio points required to fit a curve.")
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only use phase-shift points at or below this interspike interval in microseconds for fitting.",
    )
    parser.add_argument("--output-csv", type=Path, default=None, help="Write CSV here instead of stdout.")
    args = parser.parse_args(argv)
    try:
        if args.threshold <= 0:
            raise ValueError("--threshold must be > 0")
        if args.max_us <= 0:
            raise ValueError("--max-us must be > 0")
        if args.fit_min_points < 3:
            raise ValueError("--fit-min-points must be >= 3")
        load_fit_dependencies()
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)

        if args.output_csv is None:
            write_ratio_fit_threshold_rows(rows, config, args.threshold, args.max_us, args.fit_min_points, sys.stdout)
        else:
            args.output_csv.parent.mkdir(parents=True, exist_ok=True)
            with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
                write_ratio_fit_threshold_rows(rows, config, args.threshold, args.max_us, args.fit_min_points, handle)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_integral_heatmap(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Plot {config.name} phase-shift integral heatmaps by phase shift.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Show charge, ratio, and inverse-ratio heatmaps one at a time instead of side by side.",
    )
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot phase-shift points at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument("--charge-unit", choices=("C", "pC"), default="pC")
    parser.add_argument("--charge-vmin", type=float, default=None)
    parser.add_argument("--charge-vmax", type=float, default=None)
    parser.add_argument("--ratio-vmin", type=float, default=None)
    parser.add_argument("--ratio-vmax", type=float, default=None)
    parser.add_argument("--inverse-ratio-vmin", type=float, default=None)
    parser.add_argument("--inverse-ratio-vmax", type=float, default=None)
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print heatmap pages without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        if args.sequential and args.open_all:
            raise ValueError("Use either --sequential or --open-all, not both.")
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)
        plot_integral_heatmaps(
            rows,
            config,
            args.charge_unit,
            args.charge_vmin,
            args.charge_vmax,
            args.ratio_vmin,
            args.ratio_vmax,
            args.inverse_ratio_vmin,
            args.inverse_ratio_vmax,
            args.cmap,
            args.open_all,
            args.sequential,
            args.dry_run,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_integral_tolerance_heatmap(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Plot binary {config.name} phase-shift integral ratio tolerance heatmaps.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot phase-shift points at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument(
        "--tollerance",
        type=float,
        required=True,
        help="Symmetric fractional tolerance around charge ratio 1.0, e.g. 0.05 for +/-5% or 0.20 for +/-20%.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print heatmap pages without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)
        plot_integral_tolerance_heatmaps(
            rows,
            config,
            args.tollerance,
            args.open_all,
            args.dry_run,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_integral_volume(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Plot {config.name} phase-shift integral values as a 3D volume.")
    add_common_pair_args(parser, config)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument(
        "--max-phase-shift-us",
        type=float,
        default=None,
        help="Only plot phase-shift points at or below this interspike interval in microseconds, e.g. 20.",
    )
    parser.add_argument(
        "--metric",
        choices=("charge", "ratio", "inverse-ratio"),
        default=None,
        help="Plot only one metric. If omitted, cycles through charge, ratio, and inverse-ratio.",
    )
    parser.add_argument("--view", choices=("scatter", "surfaces"), default="scatter")
    parser.add_argument("--charge-unit", choices=("C", "pC"), default="pC")
    parser.add_argument("--alpha", type=float, default=None, help="Plot transparency. Defaults depend on --view.")
    parser.add_argument("--marker-size", type=float, default=45.0)
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--vmin", type=float, default=None)
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--stride-phase", type=int, default=1, help="Plot every Nth phase-shift slice.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print volume dimensions without opening Matplotlib windows.")
    add_image_output_args(parser)
    args = parser.parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve(), config)
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir, config)
        rows = apply_row_filters(rows, args, config)
        rows = filter_rows_by_max_phase_shift_us(rows, args.max_phase_shift_us)
        rows = selected_rows(rows, args.start_at, args.limit)
        alpha = args.alpha
        if alpha is None:
            alpha = 0.75 if args.view == "scatter" else 0.45
        if alpha <= 0 or alpha > 1:
            raise ValueError("--alpha must be > 0 and <= 1")
        plot_integral_volume(
            rows,
            config,
            args.metric,
            args.view,
            args.charge_unit,
            alpha,
            args.marker_size,
            args.cmap,
            args.vmin,
            args.vmax,
            args.stride_phase,
            args.dry_run,
            repo_root,
            args.save_images,
            args.no_show,
            args.output_dir,
            args.image_format,
            args.dpi,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_currents(config: SweepConfig, filled: bool, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Display {config.name} phase-shift current comparisons as interactive Matplotlib plots.")
    add_common_pair_args(parser, config)
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument("--skip-errors", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate selected CSV pairs without opening Matplotlib windows.")
    args = parser.parse_args(argv)
    try:
        repo_root, one_syn_dir, two_syn_dir, pairs = select_pairs(args, config)
        total = len(pairs)
        print(f"Repo root: {repo_root}")
        print(f"1syn input dir: {one_syn_dir}")
        print(f"2syn input dir: {two_syn_dir}")
        print(f"CSV pairs selected: {total}")
        if args.dry_run:
            for rel_path, _, _ in pairs[:10]:
                print(f"  {rel_path}")
            return 0

        load_plot_dependencies()
        if args.open_all:
            for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                try:
                    plot_current_pair(rel_path, one_syn_csv, two_syn_csv, index, total, filled)
                except Exception as exc:
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {rel_path}: {exc}", file=sys.stderr)
            plt.show()
        else:
            for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                try:
                    plot_current_pair(rel_path, one_syn_csv, two_syn_csv, index, total, filled)
                    plt.show()
                    plt.close("all")
                except Exception as exc:
                    plt.close("all")
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {rel_path}: {exc}", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


def main_csvs(config: SweepConfig, argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=f"Display formatted {config.name} phase-shift CSVs as interactive Matplotlib plots.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--kind", choices=("1syn", "2syn"), default=None)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--combined", action="store_true", help="Plot matching 1syn and 2syn CSVs together.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    for bias in config.biases:
        parser.add_argument(f"--{bias}", default=None, help=f"Only include this {bias} label, e.g. {bias}_0p7 or 0p7.")
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument("--skip-errors", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate selected CSVs without opening Matplotlib windows.")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.start_at < 1:
            raise ValueError("--start-at must be >= 1")
        if args.combined:
            if args.kind is not None or args.input_dir is not None:
                raise ValueError("Use --combined by itself, not with --kind or --input-dir.")
            one_syn_dir = default_one_syn_dir(repo_root, config)
            two_syn_dir = default_two_syn_dir(repo_root, config)
            pairs = apply_pair_filters(find_current_pairs(one_syn_dir, two_syn_dir, config), args, config)
            pairs = pairs[args.start_at - 1:]
            if args.limit is not None:
                pairs = pairs[:args.limit]
            if not pairs:
                raise FileNotFoundError("No combined CSV pairs selected after filtering.")
            print(f"CSV pairs selected: {len(pairs)}")
            if args.dry_run:
                for rel_path, _, _ in pairs[:10]:
                    print(f"  {rel_path}")
                return 0
            load_plot_dependencies()
            for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                try:
                    plot_combined_pair(rel_path, one_syn_csv, two_syn_csv, index, len(pairs))
                    if not args.open_all:
                        plt.show()
                        plt.close("all")
                except Exception as exc:
                    plt.close("all")
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {rel_path}: {exc}", file=sys.stderr)
            if args.open_all:
                plt.show()
            return 0

        if args.kind is not None and args.input_dir is not None:
            raise ValueError("Use either --kind or --input-dir, not both.")
        if args.input_dir is not None:
            input_dir = args.input_dir.resolve()
        elif args.kind == "1syn":
            input_dir = default_one_syn_dir(repo_root, config)
        elif args.kind == "2syn":
            input_dir = default_two_syn_dir(repo_root, config)
        else:
            raise ValueError("Use --kind {1syn,2syn}, --input-dir, or --combined.")
        if not input_dir.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        csvs = find_csv_files(input_dir, config)
        for bias in config.biases:
            requested = getattr(args, bias, None)
            if requested is not None:
                label = normalize_bias_label(bias, requested)
                csvs = [path for path in csvs if extract_bias_label(path, bias) == label]
                if not csvs:
                    raise FileNotFoundError(f"No CSVs found for {bias} label: {label}")
        csvs = csvs[args.start_at - 1:]
        if args.limit is not None:
            csvs = csvs[:args.limit]
        if not csvs:
            raise FileNotFoundError("No CSVs selected after filtering.")
        print(f"CSV files selected: {len(csvs)}")
        if args.dry_run:
            for path in csvs[:10]:
                print(f"  {path.relative_to(input_dir)}")
            return 0
        load_plot_dependencies()
        for index, csv_path in enumerate(csvs, start=1):
            try:
                plot_one_csv(csv_path, input_dir, index, len(csvs))
                if not args.open_all:
                    plt.show()
                    plt.close("all")
            except Exception as exc:
                plt.close("all")
                if not args.skip_errors:
                    raise
                print(f"SKIP {csv_path}: {exc}", file=sys.stderr)
        if args.open_all:
            plt.show()
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1
