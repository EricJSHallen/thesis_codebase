#!/usr/bin/env python3
"""
avg_integral_v6.py

Purpose
-------
Compute one averaged integrated voltage-difference scalar per frequency
combination.

For each frequency combination:

    st_1/f_i + st_2/f_j + ... + st_n/f_m

this script evaluates all valid matching trials:

    trial_1.csv with trial_1.csv with ... with trial_1.csv
    trial_2.csv with trial_2.csv with ... with trial_2.csv
    ...

It does not mix trial numbers. It computes one scalar integral per valid trial,
then outputs the average across trials for that frequency combination.

This file is self-contained. It does not import the earlier preview scripts.

Expected location
-----------------
Place in:

    processing/previews/

Default input
-------------
The default input is resolved relative to this file:

    processing/sim_run_code/spike_train_output_csv

CLI examples
------------
From the repository root:

    python processing/previews/avg_integral_v6.py --summary-only
    python processing/previews/avg_integral_v6.py --max-combinations 5 --verbose
    python processing/previews/avg_integral_v6.py --save-csv

Callable example
----------------

    from pathlib import Path
    from avg_integral_v6 import iter_average_integrals

    input_root = Path("processing/sim_run_code/spike_train_output_csv")

    for case, mean_integral_vs in iter_average_integrals(input_root=input_root):
        print(case.run_name, mean_integral_vs)
"""

from __future__ import annotations

import argparse
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence

import numpy as np
import pandas as pd


TIME_COL = "time_s"
VOLTAGE_COL = "voltage_v"
SUM_COL = "voltage_sum_v"
CAPPED_SUM_COL = "voltage_sum_capped_v"
DIFFERENCE_COL = "voltage_difference_v"

MEAN_INTEGRAL_COL = "mean_voltage_difference_integral_vs"
STD_INTEGRAL_COL = "std_voltage_difference_integral_vs"
MIN_INTEGRAL_COL = "min_voltage_difference_integral_vs"
MAX_INTEGRAL_COL = "max_voltage_difference_integral_vs"
VALID_TRIAL_COUNT_COL = "valid_trial_count"

VOLTAGE_CAP_V = 1.8

ST_DIR_RE = re.compile(r"^st_(\d+)$")
FREQ_DIR_RE = re.compile(r"^(\d+)_hz$")
TRIAL_FILE_RE = re.compile(r"^trial_(\d+)\.csv$")


@dataclass(frozen=True)
class SpikeTrainDirectory:
    st_index: int
    path: Path
    frequency_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class AverageCombinationCase:
    run_name: str
    frequency_dirs: tuple[Path, ...]
    frequency_names: tuple[str, ...]
    frequency_values_hz: tuple[int, ...]
    st_indices: tuple[int, ...]


@dataclass(frozen=True)
class TrialCombinationCase:
    run_name: str
    parent_run_name: str
    trial_name: str
    trial_index: int
    csv_paths: tuple[Path, ...]
    frequency_names: tuple[str, ...]
    frequency_values_hz: tuple[int, ...]
    st_indices: tuple[int, ...]


@dataclass(frozen=True)
class AverageIntegralResult:
    mean_integral_vs: float
    std_integral_vs: float
    min_integral_vs: float
    max_integral_vs: float
    valid_trial_count: int
    trial_indices: tuple[int, ...]
    trial_integrals_vs: tuple[float, ...]


def natural_int_key(text: str, pattern: re.Pattern[str]) -> tuple[int, str]:
    match = pattern.match(text)
    if match is None:
        return (10**18, text)
    return (int(match.group(1)), text)


def frequency_hz_from_dir_name(name: str) -> int:
    match = FREQ_DIR_RE.match(name)
    if match is None:
        raise ValueError(f"Invalid frequency directory name: {name}")
    return int(match.group(1))


def default_input_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sim_run_code" / "spike_train_output_csv"


def default_output_csv() -> Path:
    return Path(__file__).resolve().parent / "average_integrated_voltage_difference_v6.csv"


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
        raise FileNotFoundError("No trial_N.csv filename is shared by all selected st_N directories.")

    return tuple(sorted(common_trials, key=lambda name: natural_int_key(name, TRIAL_FILE_RE)))


def make_average_run_name(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
    frequency_dirs: Sequence[Path],
) -> str:
    parts = [
        f"st{st_dir.st_index}_{freq_dir.name}"
        for st_dir, freq_dir in zip(spike_train_dirs, frequency_dirs, strict=True)
    ]
    return "__".join(parts)


def iter_average_combination_cases(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
) -> Iterator[AverageCombinationCase]:
    frequency_dir_lists = [st_dir.frequency_dirs for st_dir in spike_train_dirs]
    st_indices = tuple(st_dir.st_index for st_dir in spike_train_dirs)

    for frequency_dirs in itertools.product(*frequency_dir_lists):
        frequency_names = tuple(freq_dir.name for freq_dir in frequency_dirs)
        frequency_values_hz = tuple(frequency_hz_from_dir_name(name) for name in frequency_names)

        yield AverageCombinationCase(
            run_name=make_average_run_name(spike_train_dirs, frequency_dirs),
            frequency_dirs=tuple(frequency_dirs),
            frequency_names=frequency_names,
            frequency_values_hz=frequency_values_hz,
            st_indices=st_indices,
        )


def iter_valid_trial_cases(
    average_case: AverageCombinationCase,
    trial_names: Sequence[str],
) -> Iterator[TrialCombinationCase]:
    for trial_name in trial_names:
        trial_match = TRIAL_FILE_RE.match(trial_name)
        if trial_match is None:
            continue

        csv_paths = tuple(freq_dir / trial_name for freq_dir in average_case.frequency_dirs)

        if not all(path.is_file() for path in csv_paths):
            continue

        trial_stem = trial_name.removesuffix(".csv")

        yield TrialCombinationCase(
            run_name=f"{average_case.run_name}__{trial_stem}",
            parent_run_name=average_case.run_name,
            trial_name=trial_name,
            trial_index=int(trial_match.group(1)),
            csv_paths=csv_paths,
            frequency_names=average_case.frequency_names,
            frequency_values_hz=average_case.frequency_values_hz,
            st_indices=average_case.st_indices,
        )


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


def build_summed_voltage_dataframe(case: TrialCombinationCase) -> pd.DataFrame:
    input_dfs = [load_two_column_voltage_csv(path) for path in case.csv_paths]
    common_time, aligned_voltages = align_to_union_time_grid(input_dfs)
    summed_voltage = np.sum(np.vstack(aligned_voltages), axis=0)

    return pd.DataFrame(
        {
            TIME_COL: common_time,
            SUM_COL: summed_voltage,
        }
    )


def build_capped_sibling_dataframe(df_sum: pd.DataFrame) -> pd.DataFrame:
    sum_values = df_sum[SUM_COL].to_numpy(dtype=float)

    return pd.DataFrame(
        {
            TIME_COL: df_sum[TIME_COL].to_numpy(copy=True),
            CAPPED_SUM_COL: np.where(sum_values >= VOLTAGE_CAP_V, VOLTAGE_CAP_V, sum_values),
        }
    )


def build_difference_dataframe(df_sum: pd.DataFrame, df_capped: pd.DataFrame) -> pd.DataFrame:
    if len(df_sum) != len(df_capped):
        raise ValueError("df_sum and df_capped must have the same number of rows.")

    sum_time = df_sum[TIME_COL].to_numpy(dtype=float)
    capped_time = df_capped[TIME_COL].to_numpy(dtype=float)

    if not np.array_equal(sum_time, capped_time):
        raise ValueError("df_sum and df_capped must use the same time grid.")

    return pd.DataFrame(
        {
            TIME_COL: sum_time.copy(),
            DIFFERENCE_COL: (
                df_sum[SUM_COL].to_numpy(dtype=float)
                - df_capped[CAPPED_SUM_COL].to_numpy(dtype=float)
            ),
        }
    )


def integrate_difference_transient(df_difference: pd.DataFrame) -> float:
    if df_difference.empty:
        return 0.0

    time_s = df_difference[TIME_COL].to_numpy(dtype=float)
    voltage_difference_v = df_difference[DIFFERENCE_COL].to_numpy(dtype=float)

    if len(time_s) < 2:
        return 0.0

    if np.any(np.diff(time_s) < 0):
        raise ValueError("df_difference time grid must be monotonically nondecreasing.")

    return float(np.trapezoid(voltage_difference_v, time_s))


def compute_trial_integral(case: TrialCombinationCase) -> float:
    df_sum = build_summed_voltage_dataframe(case)
    df_capped = build_capped_sibling_dataframe(df_sum)
    df_difference = build_difference_dataframe(df_sum, df_capped)
    return integrate_difference_transient(df_difference)


def compute_average_integral_for_case(
    average_case: AverageCombinationCase,
    trial_names: Sequence[str],
) -> AverageIntegralResult | None:
    integrals: list[float] = []
    trial_indices: list[int] = []

    for trial_case in iter_valid_trial_cases(average_case, trial_names):
        integrals.append(compute_trial_integral(trial_case))
        trial_indices.append(trial_case.trial_index)

    if not integrals:
        return None

    values = np.asarray(integrals, dtype=float)

    return AverageIntegralResult(
        mean_integral_vs=float(np.mean(values)),
        std_integral_vs=float(np.std(values, ddof=0)),
        min_integral_vs=float(np.min(values)),
        max_integral_vs=float(np.max(values)),
        valid_trial_count=int(values.size),
        trial_indices=tuple(trial_indices),
        trial_integrals_vs=tuple(float(v) for v in values),
    )


def iter_average_integral_results(
    input_root: Path | None = None,
    max_combinations: int | None = None,
) -> Iterator[tuple[AverageCombinationCase, AverageIntegralResult]]:
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
    trial_names = discover_trial_names(spike_train_dirs)

    generated = 0

    for average_case in iter_average_combination_cases(spike_train_dirs):
        result = compute_average_integral_for_case(average_case, trial_names)

        if result is None:
            continue

        yield average_case, result

        generated += 1
        if max_combinations is not None and generated >= max_combinations:
            break


def iter_average_integrals(
    input_root: Path | None = None,
    max_combinations: int | None = None,
) -> Iterator[tuple[AverageCombinationCase, float]]:
    for case, result in iter_average_integral_results(input_root, max_combinations):
        yield case, result.mean_integral_vs


def result_to_row(case: AverageCombinationCase, result: AverageIntegralResult) -> dict[str, object]:
    row: dict[str, object] = {
        "run_name": case.run_name,
        MEAN_INTEGRAL_COL: result.mean_integral_vs,
        STD_INTEGRAL_COL: result.std_integral_vs,
        MIN_INTEGRAL_COL: result.min_integral_vs,
        MAX_INTEGRAL_COL: result.max_integral_vs,
        VALID_TRIAL_COUNT_COL: result.valid_trial_count,
        "trial_indices_used": ";".join(str(x) for x in result.trial_indices),
        "trial_integrals_vs": ";".join(f"{x:.12e}" for x in result.trial_integrals_vs),
    }

    for st_index, freq_name, freq_hz in zip(
        case.st_indices,
        case.frequency_names,
        case.frequency_values_hz,
        strict=True,
    ):
        row[f"st_{st_index}_frequency_name"] = freq_name
        row[f"st_{st_index}_frequency_hz"] = freq_hz

    return row


def build_average_integral_dataframe(
    input_root: Path | None = None,
    max_combinations: int | None = None,
) -> pd.DataFrame:
    rows = [
        result_to_row(case, result)
        for case, result in iter_average_integral_results(input_root, max_combinations)
    ]
    return pd.DataFrame(rows)


def summarise_input_structure(input_root: Path) -> dict[str, object]:
    spike_train_dirs = discover_spike_train_dirs(input_root)
    trial_names = discover_trial_names(spike_train_dirs)

    raw_frequency_cases = 1
    for st_dir in spike_train_dirs:
        raw_frequency_cases *= len(st_dir.frequency_dirs)

    return {
        "input_root": Path(input_root).resolve(),
        "spike_train_count": len(spike_train_dirs),
        "trial_count": len(trial_names),
        "raw_frequency_cases": raw_frequency_cases,
        "raw_trial_evaluations_upper_bound": raw_frequency_cases * len(trial_names),
    }


def run_average_integral_generation(
    input_root: Path | None = None,
    max_combinations: int | None = None,
    verbose: bool = False,
    summary_only: bool = False,
    save_csv: bool = False,
    output_csv: Path | None = None,
    handler: Callable[[AverageCombinationCase, AverageIntegralResult], None] | None = None,
) -> int:
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    summary = summarise_input_structure(resolved_input_root)

    print(f"Input root: {summary['input_root']}")
    print(f"Spike-train directories discovered: {summary['spike_train_count']}")
    print(f"Common trial filenames discovered: {summary['trial_count']}")
    print(f"Raw frequency combinations: {summary['raw_frequency_cases']}")
    print(f"Raw trial evaluations upper bound: {summary['raw_trial_evaluations_upper_bound']}")
    print("Frequency mixing: enabled")
    print("Trial mixing: disabled")
    print("Trial averaging: enabled")

    if summary_only:
        return 0

    rows: list[dict[str, object]] = []
    generated = 0

    for case, result in iter_average_integral_results(resolved_input_root, max_combinations):
        if handler is not None:
            handler(case, result)
        elif verbose:
            print(
                f"{case.run_name}: "
                f"mean={result.mean_integral_vs:.12e} V*s, "
                f"std={result.std_integral_vs:.12e} V*s, "
                f"trials={result.valid_trial_count}"
            )

        if save_csv:
            rows.append(result_to_row(case, result))

        generated += 1

    if save_csv:
        csv_path = default_output_csv() if output_csv is None else Path(output_csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(csv_path, index=False)
        print(f"Saved averaged scalar CSV to: {csv_path.resolve()}")

    print(f"Averaged scalar outputs generated: {generated}")
    return generated


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Average integrated voltage-difference scalar outputs across matching trials."
    )
    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--max-combinations", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--save-csv", action="store_true")
    parser.add_argument("--output-csv", type=Path, default=default_output_csv())
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run_average_integral_generation(
        input_root=args.input_root,
        max_combinations=args.max_combinations,
        verbose=args.verbose,
        summary_only=args.summary_only,
        save_csv=args.save_csv,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
