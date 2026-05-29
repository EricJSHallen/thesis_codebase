#!/usr/bin/env python3
"""
preview_average_integrated_voltage_difference.py

Computes one averaged scalar output per frequency combination.

For each frequency combination:
    st_1/f_i + st_2/f_j + ... + st_n/f_m

it evaluates all valid matching trials:
    trial_1 with trial_1 with ... with trial_1
    trial_2 with trial_2 with ... with trial_2
    ...

For each trial it computes the integrated voltage-difference transient using
functions imported from preview_integrated_voltage_difference.py, then returns
or saves the average across trials.

Place this script in:
    processing/previews/

It expects preview_integrated_voltage_difference.py to be in the same directory.
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

from processing.previews.deprecated.preview_integrated_voltage_difference import (
    CombinationCase,
    build_capped_sibling_dataframe,
    build_difference_dataframe,
    build_summed_voltage_dataframe,
    default_input_root,
    discover_spike_train_dirs,
    discover_trial_names,
    integrate_difference_transient,
)

FREQ_DIR_RE = re.compile(r"^(\d+)_hz$")
TRIAL_FILE_RE = re.compile(r"^trial_(\d+)\.csv$")

MEAN_INTEGRAL_COL = "mean_voltage_difference_integral_vs"
STD_INTEGRAL_COL = "std_voltage_difference_integral_vs"
MIN_INTEGRAL_COL = "min_voltage_difference_integral_vs"
MAX_INTEGRAL_COL = "max_voltage_difference_integral_vs"
VALID_TRIAL_COUNT_COL = "valid_trial_count"


@dataclass(frozen=True)
class AverageCombinationCase:
    """One frequency combination, before averaging across trials."""

    run_name: str
    frequency_dirs: tuple[Path, ...]
    frequency_names: tuple[str, ...]
    frequency_values_hz: tuple[int, ...]
    st_indices: tuple[int, ...]


@dataclass(frozen=True)
class AverageIntegralResult:
    """The averaged scalar result for one frequency combination."""

    mean_integral_vs: float
    std_integral_vs: float
    min_integral_vs: float
    max_integral_vs: float
    valid_trial_count: int
    trial_indices: tuple[int, ...]
    trial_integrals_vs: tuple[float, ...]


def frequency_hz_from_dir_name(name: str) -> int:
    match = FREQ_DIR_RE.match(name)
    if match is None:
        raise ValueError(f"Invalid frequency directory name: {name}")
    return int(match.group(1))


def default_output_csv() -> Path:
    return Path(__file__).resolve().parent / "average_integrated_voltage_difference.csv"


def make_average_run_name(spike_train_dirs, frequency_dirs: Sequence[Path]) -> str:
    parts = [
        f"st{st_dir.st_index}_{freq_dir.name}"
        for st_dir, freq_dir in zip(spike_train_dirs, frequency_dirs, strict=True)
    ]
    return "__".join(parts)


def iter_average_combination_cases(input_root: Path | None = None) -> Iterator[AverageCombinationCase]:
    """Yield every frequency combination once, independent of trial number."""
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
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


def make_trial_case(average_case: AverageCombinationCase, trial_name: str) -> CombinationCase | None:
    """
    Build the concrete per-trial CombinationCase expected by the imported
    integration functions. Returns None if any selected frequency directory is
    missing the requested trial file.
    """
    trial_match = TRIAL_FILE_RE.match(trial_name)
    if trial_match is None:
        raise ValueError(f"Invalid trial filename: {trial_name}")

    csv_paths = tuple(freq_dir / trial_name for freq_dir in average_case.frequency_dirs)
    if not all(path.is_file() for path in csv_paths):
        return None

    trial_stem = trial_name.removesuffix(".csv")

    return CombinationCase(
        run_name=f"{average_case.run_name}__{trial_stem}",
        trial_name=trial_name,
        trial_index=int(trial_match.group(1)),
        csv_paths=csv_paths,
        frequency_names=average_case.frequency_names,
    )


def compute_trial_integral(trial_case: CombinationCase) -> float:
    """Compute the scalar integral for one concrete same-trial combination."""
    df_sum = build_summed_voltage_dataframe(trial_case)
    df_capped = build_capped_sibling_dataframe(df_sum)
    df_difference = build_difference_dataframe(df_sum, df_capped)
    return integrate_difference_transient(df_difference)


def compute_average_integral_for_case(
    average_case: AverageCombinationCase,
    trial_names: Sequence[str],
) -> AverageIntegralResult:
    """Compute the average scalar integral across all valid matching trials."""
    integrals: list[float] = []
    trial_indices: list[int] = []

    for trial_name in trial_names:
        trial_case = make_trial_case(average_case, trial_name)
        if trial_case is None:
            continue

        integrals.append(compute_trial_integral(trial_case))
        trial_indices.append(trial_case.trial_index)

    if not integrals:
        raise FileNotFoundError(f"No valid matching trial files found for: {average_case.run_name}")

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
    """Yield one averaged scalar result per frequency combination."""
    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
    trial_names = discover_trial_names(spike_train_dirs)

    generated = 0

    for average_case in iter_average_combination_cases(resolved_input_root):
        try:
            result = compute_average_integral_for_case(average_case, trial_names)
        except FileNotFoundError:
            # Some frequency combinations may not contain any complete matching
            # trial across all selected st_N directories. Skip those cases.
            continue

        yield average_case, result

        generated += 1
        if max_combinations is not None and generated >= max_combinations:
            break


def iter_average_integrals(
    input_root: Path | None = None,
    max_combinations: int | None = None,
) -> Iterator[tuple[AverageCombinationCase, float]]:
    """Yield only the mean scalar integral for each frequency combination."""
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
    """Return one row per frequency combination."""
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
        "input_root": input_root.resolve(),
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
    """Callable top-level function."""
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
