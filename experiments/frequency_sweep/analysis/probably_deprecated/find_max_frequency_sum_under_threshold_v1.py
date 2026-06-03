#!/usr/bin/env python3
"""
find_max_frequency_sum_under_threshold_v1.py

Purpose
-------
Search all discovered spike-train frequency combinations and find the
combination that maximizes:

    f_1 + f_2 + f_3 + ... + f_n

subject to the averaged excess-voltage scalar being below a threshold.

The scalar is computed from the same summed/capped/difference idea used in the
heatmap scripts:

    df_sum        = st_1 + st_2 + ... + st_n
    df_capped     = cap(df_sum, cap_v)
    df_difference = df_sum - df_capped
    integral      = integral(df_difference dt)

For each frequency combination, the scalar is computed for each valid matching
trial and then averaged across trials.

Unlike the heatmap script:
    - no graph is generated
    - all discovered spike trains vary
    - st_4, st_5, ..., st_n are NOT fixed
    - the script searches for the maximum frequency sum that satisfies a
      scalar threshold

Default threshold
-----------------
By default this script thresholds the duration-normalized scalar:

    normalized_scalar_v = integral_vs / simulation_duration_s

Default:
    --threshold-mode normalized
    --threshold 0.01

That means the candidate is accepted if:

    mean(integral_vs / duration_s over trials) < 0.01 V

This default is only a starting value. You should adjust it after inspecting
your actual scalar distributions.

You can instead threshold the raw integrated scalar in V*s:

    --threshold-mode integral --threshold 0.005

Output
------
The script prints the best result and writes a one-row CSV plus an optional
candidate log CSV.

Run
---
From the repository root:

    python3 processing/previews/find_max_frequency_sum_under_threshold_v1.py

Useful tests:

    python3 processing/previews/find_max_frequency_sum_under_threshold_v1.py --max-combinations 1000
    python3 processing/previews/find_max_frequency_sum_under_threshold_v1.py --threshold 0.02
    python3 processing/previews/find_max_frequency_sum_under_threshold_v1.py --save-candidate-log

Warning
-------
This script enumerates the full Cartesian product over all discovered spike
trains:

    len(freqs_st1) * len(freqs_st2) * ... * len(freqs_stn)

For 64 spike trains, this is usually not computationally tractable unless each
spike train has extremely few possible frequencies. Use --max-combinations for
testing.
"""

from __future__ import annotations

import argparse
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

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
DEFAULT_THRESHOLD = 0.01
DEFAULT_THRESHOLD_MODE = "normalized"
DEFAULT_PROGRESS_EVERY = 1000


@dataclass(frozen=True)
class SpikeTrainDirectory:
    st_index: int
    path: Path
    frequency_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class FrequencyCombination:
    run_name: str
    frequency_dirs: tuple[Path, ...]
    frequency_names: tuple[str, ...]
    frequency_values_hz: tuple[int, ...]
    frequency_sum_hz: int
    st_indices: tuple[int, ...]


@dataclass(frozen=True)
class CandidateResult:
    run_name: str
    frequency_sum_hz: int
    mean_integral_vs: float
    mean_normalized_v: float
    std_integral_vs: float
    std_normalized_v: float
    min_integral_vs: float
    max_integral_vs: float
    min_normalized_v: float
    max_normalized_v: float
    valid_trial_count: int
    trial_indices: tuple[int, ...]
    trial_integrals_vs: tuple[float, ...]
    trial_normalized_v: tuple[float, ...]
    trial_durations_s: tuple[float, ...]
    frequency_values_hz: tuple[int, ...]
    frequency_names: tuple[str, ...]
    st_indices: tuple[int, ...]


def natural_int_key(text: str, pattern: re.Pattern[str]) -> tuple[int, str]:
    match = pattern.match(text)
    if match is None:
        return (10**18, text)
    return (int(match.group(1)), text)


def default_input_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sim_run_code" / "spike_train_output_csv"


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent / "threshold_search_outputs_v1"


def default_best_output_csv() -> Path:
    return default_output_dir() / "best_frequency_sum_under_threshold_v1.csv"


def default_candidate_log_csv() -> Path:
    return default_output_dir() / "accepted_candidates_under_threshold_v1.csv"


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
        raise FileNotFoundError("No shared trial_N.csv filenames found across all discovered spike trains.")

    return tuple(sorted(common_trials, key=lambda name: natural_int_key(name, TRIAL_FILE_RE)))


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


def compute_integral_and_duration_from_paths(
    csv_paths: Sequence[Path],
    dataframe_cache: dict[Path, pd.DataFrame],
    cap_v: float,
) -> tuple[float, float]:
    input_dfs: list[pd.DataFrame] = []

    for path in csv_paths:
        if path not in dataframe_cache:
            dataframe_cache[path] = load_two_column_voltage_csv(path)
        input_dfs.append(dataframe_cache[path])

    common_time, aligned_voltages = align_to_union_time_grid(input_dfs)

    if common_time.size < 2:
        raise ValueError("Cannot infer simulation duration from fewer than two time points.")

    duration_s = float(common_time[-1] - common_time[0])
    if duration_s <= 0:
        raise ValueError("Could not infer a positive simulation duration.")

    summed_voltage = np.sum(np.vstack(aligned_voltages), axis=0)
    excess_voltage = np.maximum(summed_voltage - cap_v, 0.0)
    integral_vs = float(np.trapezoid(excess_voltage, common_time))

    return integral_vs, duration_s


def make_run_name(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
    frequency_dirs: Sequence[Path],
) -> str:
    return "__".join(
        f"st{st_dir.st_index}_{freq_dir.name}"
        for st_dir, freq_dir in zip(spike_train_dirs, frequency_dirs, strict=True)
    )


def iter_frequency_combinations(
    spike_train_dirs: Sequence[SpikeTrainDirectory],
) -> Iterator[FrequencyCombination]:
    frequency_dir_lists = [st_dir.frequency_dirs for st_dir in spike_train_dirs]
    st_indices = tuple(st_dir.st_index for st_dir in spike_train_dirs)

    for frequency_dirs in itertools.product(*frequency_dir_lists):
        frequency_names = tuple(freq_dir.name for freq_dir in frequency_dirs)
        frequency_values_hz = tuple(frequency_hz_from_dir_name(name) for name in frequency_names)

        yield FrequencyCombination(
            run_name=make_run_name(spike_train_dirs, frequency_dirs),
            frequency_dirs=tuple(frequency_dirs),
            frequency_names=frequency_names,
            frequency_values_hz=frequency_values_hz,
            frequency_sum_hz=int(sum(frequency_values_hz)),
            st_indices=st_indices,
        )


def count_frequency_product(spike_train_dirs: Sequence[SpikeTrainDirectory]) -> int:
    total = 1
    for st_dir in spike_train_dirs:
        total *= len(st_dir.frequency_dirs)
    return total


def compute_candidate_result(
    combination: FrequencyCombination,
    trial_names: Sequence[str],
    dataframe_cache: dict[Path, pd.DataFrame],
    cap_v: float,
) -> CandidateResult | None:
    trial_indices: list[int] = []
    trial_integrals_vs: list[float] = []
    trial_normalized_v: list[float] = []
    trial_durations_s: list[float] = []

    for trial_name in trial_names:
        match = TRIAL_FILE_RE.match(trial_name)
        if match is None:
            continue

        csv_paths = tuple(freq_dir / trial_name for freq_dir in combination.frequency_dirs)
        if not all(path.is_file() for path in csv_paths):
            continue

        integral_vs, duration_s = compute_integral_and_duration_from_paths(
            csv_paths=csv_paths,
            dataframe_cache=dataframe_cache,
            cap_v=cap_v,
        )

        trial_indices.append(int(match.group(1)))
        trial_integrals_vs.append(integral_vs)
        trial_normalized_v.append(integral_vs / duration_s)
        trial_durations_s.append(duration_s)

    if not trial_integrals_vs:
        return None

    integral_values = np.asarray(trial_integrals_vs, dtype=float)
    normalized_values = np.asarray(trial_normalized_v, dtype=float)

    return CandidateResult(
        run_name=combination.run_name,
        frequency_sum_hz=combination.frequency_sum_hz,
        mean_integral_vs=float(np.mean(integral_values)),
        mean_normalized_v=float(np.mean(normalized_values)),
        std_integral_vs=float(np.std(integral_values, ddof=0)),
        std_normalized_v=float(np.std(normalized_values, ddof=0)),
        min_integral_vs=float(np.min(integral_values)),
        max_integral_vs=float(np.max(integral_values)),
        min_normalized_v=float(np.min(normalized_values)),
        max_normalized_v=float(np.max(normalized_values)),
        valid_trial_count=len(trial_integrals_vs),
        trial_indices=tuple(trial_indices),
        trial_integrals_vs=tuple(float(v) for v in trial_integrals_vs),
        trial_normalized_v=tuple(float(v) for v in trial_normalized_v),
        trial_durations_s=tuple(float(v) for v in trial_durations_s),
        frequency_values_hz=combination.frequency_values_hz,
        frequency_names=combination.frequency_names,
        st_indices=combination.st_indices,
    )


def candidate_metric(result: CandidateResult, threshold_mode: str) -> float:
    if threshold_mode == "integral":
        return result.mean_integral_vs
    if threshold_mode == "normalized":
        return result.mean_normalized_v
    raise ValueError(f"Invalid threshold_mode: {threshold_mode}")


def is_better_candidate(
    candidate: CandidateResult,
    current_best: CandidateResult | None,
    threshold_mode: str,
) -> bool:
    if current_best is None:
        return True

    if candidate.frequency_sum_hz != current_best.frequency_sum_hz:
        return candidate.frequency_sum_hz > current_best.frequency_sum_hz

    # Tie-breaker: for the same frequency sum, prefer the lower scalar value.
    return candidate_metric(candidate, threshold_mode) < candidate_metric(current_best, threshold_mode)


def result_to_row(result: CandidateResult, threshold: float, threshold_mode: str) -> dict[str, object]:
    row: dict[str, object] = {
        "run_name": result.run_name,
        "frequency_sum_hz": result.frequency_sum_hz,
        "mean_integral_vs": result.mean_integral_vs,
        "mean_normalized_v": result.mean_normalized_v,
        "std_integral_vs": result.std_integral_vs,
        "std_normalized_v": result.std_normalized_v,
        "min_integral_vs": result.min_integral_vs,
        "max_integral_vs": result.max_integral_vs,
        "min_normalized_v": result.min_normalized_v,
        "max_normalized_v": result.max_normalized_v,
        "valid_trial_count": result.valid_trial_count,
        "trial_indices_used": ";".join(str(i) for i in result.trial_indices),
        "trial_integrals_vs": ";".join(f"{v:.12e}" for v in result.trial_integrals_vs),
        "trial_normalized_v": ";".join(f"{v:.12e}" for v in result.trial_normalized_v),
        "trial_durations_s": ";".join(f"{v:.12e}" for v in result.trial_durations_s),
        "threshold": threshold,
        "threshold_mode": threshold_mode,
    }

    for st_index, freq_hz, freq_name in zip(
        result.st_indices,
        result.frequency_values_hz,
        result.frequency_names,
        strict=True,
    ):
        row[f"st_{st_index}_frequency_hz"] = freq_hz
        row[f"st_{st_index}_frequency_name"] = freq_name

    # Convenience columns for the four-frequency case.
    for idx in range(4):
        if idx < len(result.frequency_values_hz):
            row[f"f{idx + 1}_hz"] = result.frequency_values_hz[idx]
        else:
            row[f"f{idx + 1}_hz"] = None

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


def search_max_frequency_sum_under_threshold(
    input_root: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    threshold_mode: str = DEFAULT_THRESHOLD_MODE,
    cap_v: float = DEFAULT_CAP_V,
    strict_less_than: bool = True,
    max_combinations: int | None = None,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    save_candidate_log: bool = False,
) -> tuple[CandidateResult | None, list[CandidateResult], dict[str, object]]:
    if threshold_mode not in {"normalized", "integral"}:
        raise ValueError("--threshold-mode must be either 'normalized' or 'integral'.")

    resolved_input_root = default_input_root() if input_root is None else Path(input_root)
    spike_train_dirs = discover_spike_train_dirs(resolved_input_root)
    trial_names = discover_trial_names(spike_train_dirs)

    total_combinations = count_frequency_product(spike_train_dirs)
    total_to_process = min(total_combinations, max_combinations) if max_combinations is not None else total_combinations

    dataframe_cache: dict[Path, pd.DataFrame] = {}
    accepted_candidates: list[CandidateResult] = []
    best: CandidateResult | None = None
    processed = 0
    valid_results = 0

    if progress:
        print(format_progress_line(0, total_to_process, prefix="Threshold-search progress"))

    for combination in iter_frequency_combinations(spike_train_dirs):
        if max_combinations is not None and processed >= max_combinations:
            break

        result = compute_candidate_result(
            combination=combination,
            trial_names=trial_names,
            dataframe_cache=dataframe_cache,
            cap_v=cap_v,
        )

        processed += 1

        if result is not None:
            valid_results += 1
            metric = candidate_metric(result, threshold_mode)

            passes_threshold = metric < threshold if strict_less_than else metric <= threshold

            if passes_threshold:
                if save_candidate_log:
                    accepted_candidates.append(result)

                if is_better_candidate(result, best, threshold_mode):
                    best = result
                    print(
                        "New best: "
                        f"frequency_sum={best.frequency_sum_hz} Hz, "
                        f"mean_integral={best.mean_integral_vs:.12e} V*s, "
                        f"mean_normalized={best.mean_normalized_v:.12e} V, "
                        f"run={best.run_name}"
                    )

        if progress and should_print_progress(processed, total_to_process, progress_every):
            print(format_progress_line(processed, total_to_process, prefix="Threshold-search progress"))

    metadata = {
        "input_root": resolved_input_root.resolve(),
        "spike_train_count": len(spike_train_dirs),
        "trial_count": len(trial_names),
        "total_frequency_combinations": total_combinations,
        "processed_frequency_combinations": processed,
        "valid_results": valid_results,
        "threshold": threshold,
        "threshold_mode": threshold_mode,
        "strict_less_than": strict_less_than,
        "cap_v": cap_v,
        "unique_dataframes_cached": len(dataframe_cache),
    }

    return best, accepted_candidates, metadata


def run_search(
    input_root: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    threshold_mode: str = DEFAULT_THRESHOLD_MODE,
    cap_v: float = DEFAULT_CAP_V,
    strict_less_than: bool = True,
    max_combinations: int | None = None,
    progress: bool = True,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    output_csv: Path | None = None,
    save_candidate_log: bool = False,
    candidate_log_csv: Path | None = None,
) -> int:
    best, accepted_candidates, metadata = search_max_frequency_sum_under_threshold(
        input_root=input_root,
        threshold=threshold,
        threshold_mode=threshold_mode,
        cap_v=cap_v,
        strict_less_than=strict_less_than,
        max_combinations=max_combinations,
        progress=progress,
        progress_every=progress_every,
        save_candidate_log=save_candidate_log,
    )

    resolved_output_csv = default_best_output_csv() if output_csv is None else Path(output_csv)
    resolved_output_csv.parent.mkdir(parents=True, exist_ok=True)

    print("")
    print("Search summary")
    print("--------------")
    print(f"Input root: {metadata['input_root']}")
    print(f"Spike-train count: {metadata['spike_train_count']}")
    print(f"Trial count: {metadata['trial_count']}")
    print(f"Total frequency combinations: {metadata['total_frequency_combinations']}")
    print(f"Processed frequency combinations: {metadata['processed_frequency_combinations']}")
    print(f"Valid results: {metadata['valid_results']}")
    print(f"Threshold mode: {metadata['threshold_mode']}")
    print(f"Threshold: {metadata['threshold']}")
    print(f"Strict less-than: {metadata['strict_less_than']}")
    print(f"Cap voltage: {metadata['cap_v']} V")
    print(f"Unique dataframes cached: {metadata['unique_dataframes_cached']}")

    if best is None:
        print("")
        print("No candidate satisfied the threshold.")
        pd.DataFrame([metadata]).to_csv(resolved_output_csv, index=False)
        print(f"Wrote metadata-only CSV to: {resolved_output_csv.resolve()}")
        return 1

    best_row = result_to_row(best, threshold=threshold, threshold_mode=threshold_mode)
    for key, value in metadata.items():
        best_row[f"search_{key}"] = value

    pd.DataFrame([best_row]).to_csv(resolved_output_csv, index=False)

    print("")
    print("Best candidate")
    print("--------------")
    print(f"Run name: {best.run_name}")
    print(f"Frequency sum: {best.frequency_sum_hz} Hz")
    print(f"Mean integral: {best.mean_integral_vs:.12e} V*s")
    print(f"Mean normalized scalar: {best.mean_normalized_v:.12e} V")
    print(f"Valid trial count: {best.valid_trial_count}")

    print("")
    print("Frequencies")
    print("-----------")
    for st_index, freq_hz, freq_name in zip(
        best.st_indices,
        best.frequency_values_hz,
        best.frequency_names,
        strict=True,
    ):
        print(f"st_{st_index}: {freq_hz} Hz ({freq_name})")

    print("")
    print("First four frequencies")
    print("----------------------")
    for idx in range(4):
        if idx < len(best.frequency_values_hz):
            print(f"f{idx + 1}: {best.frequency_values_hz[idx]} Hz")
        else:
            print(f"f{idx + 1}: not available")

    print("")
    print(f"Saved best-result CSV to: {resolved_output_csv.resolve()}")

    if save_candidate_log:
        resolved_candidate_log_csv = (
            default_candidate_log_csv()
            if candidate_log_csv is None
            else Path(candidate_log_csv)
        )
        resolved_candidate_log_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            result_to_row(result, threshold=threshold, threshold_mode=threshold_mode)
            for result in accepted_candidates
        ]
        pd.DataFrame(rows).to_csv(resolved_candidate_log_csv, index=False)
        print(f"Saved accepted-candidate log CSV to: {resolved_candidate_log_csv.resolve()}")

    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find the maximum sum of all spike-train frequencies such that the "
            "averaged excess-voltage scalar is below a threshold."
        )
    )

    parser.add_argument("--input-root", type=Path, default=default_input_root())
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--threshold-mode",
        choices=["normalized", "integral"],
        default=DEFAULT_THRESHOLD_MODE,
        help=(
            "normalized: threshold mean(integral/duration) in V. "
            "integral: threshold mean(integral) in V*s."
        ),
    )
    parser.add_argument("--cap-v", type=float, default=DEFAULT_CAP_V)
    parser.add_argument(
        "--allow-equal",
        action="store_true",
        help="Use <= threshold instead of < threshold.",
    )
    parser.add_argument("--max-combinations", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--output-csv", type=Path, default=default_best_output_csv())
    parser.add_argument("--save-candidate-log", action="store_true")
    parser.add_argument("--candidate-log-csv", type=Path, default=default_candidate_log_csv())

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    return run_search(
        input_root=args.input_root,
        threshold=args.threshold,
        threshold_mode=args.threshold_mode,
        cap_v=args.cap_v,
        strict_less_than=not args.allow_equal,
        max_combinations=args.max_combinations,
        progress=not args.no_progress,
        progress_every=args.progress_every,
        output_csv=args.output_csv,
        save_candidate_log=args.save_candidate_log,
        candidate_log_csv=args.candidate_log_csv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
