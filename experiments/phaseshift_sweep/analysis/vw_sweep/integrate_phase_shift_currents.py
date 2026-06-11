#!/usr/bin/env python3
"""
integrate_phase_shift_currents.py

Compute scalar current integrals for matched formatted Vw phase-shift CSV pairs.

For each phase-shift case, this script computes:
  integral(abs(1syn i_I56_Iout_A - initial) dt)
  integral(abs((2syn i_I172_Iout_A + i_I56_Iout_A) - initial) dt)

Results are printed as CSV to stdout and optionally written to --output-csv.
This script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


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


@dataclass(frozen=True)
class IntegrationResult:
    phase_shift: str
    vw_label: str
    one_syn_csv: Path
    two_syn_csv: Path
    one_syn_abs_integral_a_s: float
    two_syn_sum_abs_integral_a_s: float


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find repo root. Run from inside thesis_codebase, "
        "or pass --repo-root /path/to/thesis_codebase."
    )


def default_one_syn_dir(repo_root: Path) -> Path:
    path = repo_root / "database" / "formatted" / "phase_shift_1syn_vw_v2"
    if not path.is_dir():
        raise FileNotFoundError(f"1syn formatted directory not found: {path}")
    return path


def default_two_syn_dir(repo_root: Path) -> Path:
    path = repo_root / "database" / "formatted" / "phase_shift_2syn_vw_v2"
    if not path.is_dir():
        raise FileNotFoundError(f"2syn formatted directory not found: {path}")
    return path


def parse_phase_shift_s(path: Path) -> float:
    match = re.search(r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)_phase_shift", path.stem)
    if not match:
        return float("inf")
    return float(match.group("value"))


def parse_vw_sort_key(path: Path) -> tuple[int, float | str]:
    vw_label = ""
    for part in path.parts:
        if part.startswith("vw_"):
            vw_label = part
            break
    if not vw_label:
        return (0, "")

    value = vw_label.removeprefix("vw_").replace("p", ".")
    try:
        return (1, float(value))
    except ValueError:
        return (1, vw_label)


def csv_sort_key(path: Path) -> tuple[tuple[int, float | str], float, str]:
    return (parse_vw_sort_key(path), parse_phase_shift_s(path), str(path))


def find_csv_files(input_dir: Path) -> list[Path]:
    csvs = [
        p for p in input_dir.rglob("*.csv")
        if p.is_file()
        and p.name not in IGNORE_CSV_NAMES
        and not p.name.startswith(".")
    ]
    if not csvs:
        raise FileNotFoundError(f"No plottable CSV files found under {input_dir}")
    return sorted(csvs, key=csv_sort_key)


def csv_map_by_relative_path(input_dir: Path) -> dict[Path, Path]:
    return {path.relative_to(input_dir): path for path in find_csv_files(input_dir)}


def find_current_pairs(one_syn_dir: Path, two_syn_dir: Path) -> list[tuple[Path, Path, Path]]:
    one_syn = csv_map_by_relative_path(one_syn_dir)
    two_syn = csv_map_by_relative_path(two_syn_dir)

    missing_2syn = sorted(set(one_syn) - set(two_syn), key=lambda p: csv_sort_key(one_syn[p]))
    missing_1syn = sorted(set(two_syn) - set(one_syn), key=lambda p: csv_sort_key(two_syn[p]))
    if missing_2syn or missing_1syn:
        messages = []
        if missing_2syn:
            messages.append(f"missing 2syn matches for {len(missing_2syn)} files, first={missing_2syn[0]}")
        if missing_1syn:
            messages.append(f"missing 1syn matches for {len(missing_1syn)} files, first={missing_1syn[0]}")
        raise FileNotFoundError("Current CSV pair mismatch: " + "; ".join(messages))

    rel_paths = sorted(one_syn, key=lambda p: csv_sort_key(one_syn[p]))
    pairs = [(rel_path, one_syn[rel_path], two_syn[rel_path]) for rel_path in rel_paths]
    if not pairs:
        raise FileNotFoundError("No matching 1syn/2syn CSV pairs found.")
    return pairs


def parse_case_metadata(rel_path: Path) -> tuple[str, str]:
    parts = rel_path.with_suffix("").parts
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) >= 2:
        return parts[-1], parts[-2]
    return rel_path.stem, ""


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


def integrate_pair(rel_path: Path, one_syn_csv: Path, two_syn_csv: Path) -> IntegrationResult:
    phase_shift, vw_label = parse_case_metadata(rel_path)

    one = load_numeric_csv(one_syn_csv, [TIME_COL, ONE_SYN_CURRENT])
    two = load_numeric_csv(two_syn_csv, [TIME_COL, TWO_SYN_I172, TWO_SYN_I56])

    one_abs = baseline_subtracted_abs(one[ONE_SYN_CURRENT])
    two_sum = [i172 + i56 for i172, i56 in zip(two[TWO_SYN_I172], two[TWO_SYN_I56])]
    two_sum_abs = baseline_subtracted_abs(two_sum)

    return IntegrationResult(
        phase_shift=phase_shift,
        vw_label=vw_label,
        one_syn_csv=one_syn_csv,
        two_syn_csv=two_syn_csv,
        one_syn_abs_integral_a_s=trapezoid_integral(one[TIME_COL], one_abs),
        two_syn_sum_abs_integral_a_s=trapezoid_integral(two[TIME_COL], two_sum_abs),
    )


def write_results(rows: Iterable[IntegrationResult], handle) -> None:
    writer = csv.writer(handle)
    writer.writerow([
        "phase_shift",
        "vw_label",
        "one_syn_csv",
        "two_syn_csv",
        "one_syn_abs_integral_A_s",
        "two_syn_sum_abs_integral_A_s",
    ])
    for row in rows:
        writer.writerow([
            row.phase_shift,
            row.vw_label,
            row.one_syn_csv,
            row.two_syn_csv,
            f"{row.one_syn_abs_integral_a_s:.12e}",
            f"{row.two_syn_sum_abs_integral_a_s:.12e}",
        ])


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrate absolute baseline-subtracted phase-shift currents."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--one-syn-dir", type=Path, default=None)
    parser.add_argument("--two-syn-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        one_syn_dir = args.one_syn_dir.resolve() if args.one_syn_dir else default_one_syn_dir(repo_root)
        two_syn_dir = args.two_syn_dir.resolve() if args.two_syn_dir else default_two_syn_dir(repo_root)

        if args.start_at < 1:
            raise ValueError("--start-at must be >= 1")

        pairs = find_current_pairs(one_syn_dir, two_syn_dir)
        pairs = pairs[args.start_at - 1:]
        if args.limit is not None:
            pairs = pairs[:args.limit]
        if not pairs:
            raise FileNotFoundError("No CSV pairs selected after filtering.")

        results = [integrate_pair(rel_path, one_csv, two_csv) for rel_path, one_csv, two_csv in pairs]
        write_results(results, sys.stdout)

        if args.output_csv is not None:
            args.output_csv.parent.mkdir(parents=True, exist_ok=True)
            with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
                write_results(results, handle)

        return 0
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            print("Run again with --debug for a full traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
