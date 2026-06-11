#!/usr/bin/env python3
"""
format_raw_phaseshift_vtau_outputs.py

Convert Vtau phase-shift OCEAN output_signals.txt files into analysis-ready CSVs.

Default raw inputs:
  database/raw/phase_shift_1syn_ocean_output_vtau_v2/
  database/raw/phase_shift_2syn_ocean_output_vtau_v2/

Default formatted outputs:
  database/formatted/phase_shift_1syn_vtau_v2/
  database/formatted/phase_shift_2syn_vtau_v2/

The formatter only includes the Vtau-aware layout:
  <vtau_label>/<phase_shift>/output_signals.txt
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_INPUT_NAME = "output_signals.txt"
VTAU_DIR_RE = re.compile(r"^vtau_\d+p\d+$")

SUFFIX_MULTIPLIERS: dict[str, float] = {
    "a": 1e-18,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

NUMERIC_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([afpnumkKMG]?)$"
)


@dataclass(frozen=True)
class FormatJob:
    kind: str
    raw_subdir: str
    formatted_subdir: str
    header: tuple[str, ...]


@dataclass(frozen=True)
class CaseInfo:
    case_name: str
    phase_shift: str
    vtau_label: str
    input_txt: Path
    output_csv: Path


@dataclass(frozen=True)
class ConversionResult:
    kind: str
    case_name: str
    phase_shift: str
    vtau_label: str
    input_txt: Path
    output_csv: Path
    status: str
    message: str
    rows_written: int = 0
    columns_written: int = 0


JOBS: dict[str, FormatJob] = {
    "1syn": FormatJob(
        kind="1syn",
        raw_subdir="phase_shift_1syn_ocean_output_vtau_v2",
        formatted_subdir="phase_shift_1syn_vtau_v2",
        header=("time_s", "i_I56_Iout_A", "v_vpre_res_V", "v_vpre1_res_V"),
    ),
    "2syn": FormatJob(
        kind="2syn",
        raw_subdir="phase_shift_2syn_ocean_output_vtau_v2",
        formatted_subdir="phase_shift_2syn_vtau_v2",
        header=("time_s", "i_I172_Iout_A", "i_I56_Iout_A", "v_vpre_res_V", "v_vpre1_res_V"),
    ),
}


def find_repo_root(start: Path | None = None) -> Path:
    anchors = []
    if start is not None:
        anchors.append(start.resolve())
    anchors.append(Path(__file__).resolve())
    anchors.append(Path.cwd().resolve())

    seen: set[Path] = set()
    for anchor in anchors:
        path = anchor if anchor.is_dir() else anchor.parent
        for candidate in [path, *path.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
                return candidate

    raise FileNotFoundError(
        "Could not find repository root. Expected a parent directory containing "
        "both database/ and experiments/. Use --repo-root explicitly."
    )


def parse_engineering_number(value: str) -> float:
    value = value.strip().strip('"')
    match = NUMERIC_RE.match(value)
    if not match:
        raise ValueError(f"Could not parse numeric value: {value!r}")
    number_str, suffix = match.groups()
    return float(number_str) * SUFFIX_MULTIPLIERS[suffix]


def looks_numeric_row(tokens: Sequence[str]) -> bool:
    if not tokens:
        return False
    for token in tokens:
        try:
            parse_engineering_number(token)
        except ValueError:
            return False
    return True


def read_nonempty_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.strip() for line in handle if line.strip()]


def extract_numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    expected_width: int | None = None

    for line_number, line in enumerate(read_nonempty_lines(path), start=1):
        if line.startswith("#"):
            continue

        parts = line.split()
        if not looks_numeric_row(parts):
            continue

        if expected_width is None:
            expected_width = len(parts)
        if len(parts) != expected_width:
            raise ValueError(
                f"inconsistent column count on line {line_number}: "
                f"expected {expected_width}, got {len(parts)}; content={line!r}"
            )
        rows.append([parse_engineering_number(value) for value in parts])

    if not rows:
        raise ValueError("no numeric data rows found")
    return rows


def raw_root(repo_root: Path, job: FormatJob, input_root: Path | None) -> Path:
    if input_root is not None:
        root = input_root / job.raw_subdir if input_root.name != job.raw_subdir else input_root
    else:
        root = repo_root / "database" / "raw" / job.raw_subdir

    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Raw input directory not found for {job.kind}: {root}")
    return root


def output_root(repo_root: Path, job: FormatJob, output_root_arg: Path | None) -> Path:
    if output_root_arg is not None:
        root = output_root_arg / job.formatted_subdir if output_root_arg.name != job.formatted_subdir else output_root_arg
    else:
        root = repo_root / "database" / "formatted" / job.formatted_subdir
    return root.resolve()


def output_relative_path(raw_root_dir: Path, input_txt: Path) -> tuple[Path, str, str, str]:
    rel_parent = input_txt.parent.relative_to(raw_root_dir)
    parts = rel_parent.parts
    if len(parts) == 1:
        vtau_label = ""
        phase_shift = parts[0]
        case_name = phase_shift
        rel_csv = Path(f"{phase_shift}.csv")
    elif len(parts) == 2:
        vtau_label, phase_shift = parts
        case_name = f"{vtau_label}/{phase_shift}"
        rel_csv = Path(vtau_label) / f"{phase_shift}.csv"
    else:
        vtau_label = parts[-2] if len(parts) >= 2 else ""
        phase_shift = parts[-1]
        case_name = "/".join(parts)
        rel_csv = Path(*parts[:-1]) / f"{phase_shift}.csv"
    return rel_csv, case_name, phase_shift, vtau_label


def is_vtau_case(raw_root_dir: Path, input_txt: Path) -> bool:
    rel_parent = input_txt.parent.relative_to(raw_root_dir)
    parts = rel_parent.parts
    return len(parts) == 2 and VTAU_DIR_RE.match(parts[0]) is not None


def discover_cases(raw_root_dir: Path, output_root_dir: Path) -> list[CaseInfo]:
    cases: list[CaseInfo] = []
    for input_txt in sorted(raw_root_dir.rglob(DEFAULT_INPUT_NAME)):
        if not is_vtau_case(raw_root_dir, input_txt):
            continue

        rel_csv, case_name, phase_shift, vtau_label = output_relative_path(raw_root_dir, input_txt)
        cases.append(
            CaseInfo(
                case_name=case_name,
                phase_shift=phase_shift,
                vtau_label=vtau_label,
                input_txt=input_txt,
                output_csv=output_root_dir / rel_csv,
            )
        )
    if not cases:
        raise FileNotFoundError(
            f"No nested vtau_*p*/<phase_shift>/{DEFAULT_INPUT_NAME} files found under {raw_root_dir}"
        )
    return cases


def convert_case(job: FormatJob, case: CaseInfo, overwrite: bool, dry_run: bool) -> ConversionResult:
    if case.output_csv.exists() and not overwrite:
        return ConversionResult(
            job.kind,
            case.case_name,
            case.phase_shift,
            case.vtau_label,
            case.input_txt,
            case.output_csv,
            "skipped",
            "output exists and overwrite is false",
        )

    try:
        rows = extract_numeric_rows(case.input_txt)
        width = len(rows[0])
        if width != len(job.header):
            raise ValueError(
                f"expected {len(job.header)} columns for {job.kind}, got {width}"
            )

        if dry_run:
            return ConversionResult(
                job.kind,
                case.case_name,
                case.phase_shift,
                case.vtau_label,
                case.input_txt,
                case.output_csv,
                "validated",
                "dry run ok",
                rows_written=len(rows),
                columns_written=width,
            )

        case.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with case.output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(job.header)
            writer.writerows(rows)

        return ConversionResult(
            job.kind,
            case.case_name,
            case.phase_shift,
            case.vtau_label,
            case.input_txt,
            case.output_csv,
            "converted",
            "ok",
            rows_written=len(rows),
            columns_written=width,
        )
    except Exception as exc:
        return ConversionResult(
            job.kind,
            case.case_name,
            case.phase_shift,
            case.vtau_label,
            case.input_txt,
            case.output_csv,
            "error",
            str(exc),
        )


def write_summary(output_root_dir: Path, results: Sequence[ConversionResult]) -> None:
    output_root_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_root_dir / "conversion_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "status",
            "kind",
            "case_name",
            "phase_shift",
            "vtau_label",
            "input_txt",
            "output_csv",
            "rows_written",
            "columns_written",
            "message",
        ])
        for result in results:
            writer.writerow([
                result.status,
                result.kind,
                result.case_name,
                result.phase_shift,
                result.vtau_label,
                str(result.input_txt),
                str(result.output_csv),
                result.rows_written,
                result.columns_written,
                result.message,
            ])

    errors_path = output_root_dir / "conversion_errors.log"
    with errors_path.open("w", encoding="utf-8") as handle:
        handle.write(f"output_root={output_root_dir}\n\n")
        for result in results:
            if result.status == "error":
                handle.write(f"ERROR {result.case_name}: {result.message}\n")
            elif result.status == "skipped":
                handle.write(f"SKIPPED {result.case_name}: {result.message}\n")


def selected_jobs(kind: str | None, all_jobs: bool) -> list[FormatJob]:
    if all_jobs:
        return [JOBS["1syn"], JOBS["2syn"]]
    if kind is None:
        raise ValueError("Use --all or --kind {1syn,2syn}.")
    return [JOBS[kind]]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format raw Vtau phase-shift OCEAN output_signals.txt files into CSVs."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--kind", choices=sorted(JOBS), default=None)
    parser.add_argument("--all", action="store_true", help="Format both 1syn and 2syn outputs.")
    parser.add_argument("--list-inputs", action="store_true", help="List default raw/formatted dirs and exit.")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=None,
        help="Override raw input root. Pass database/raw or a specific raw kind directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override formatted output root. Pass database/formatted or a specific formatted kind directory.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()

    if args.list_inputs:
        print("Vtau phase-shift formatter inputs")
        for job in (JOBS["1syn"], JOBS["2syn"]):
            raw = repo_root / "database" / "raw" / job.raw_subdir
            formatted = repo_root / "database" / "formatted" / job.formatted_subdir
            marker = "*" if raw.is_dir() else " "
            print(f"  {marker} {job.kind}: {raw} -> {formatted}")
        return 0

    try:
        jobs = selected_jobs(args.kind, args.all)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    overall_errors = 0
    overall_work = 0

    for job in jobs:
        try:
            input_dir = raw_root(repo_root, job, args.input_root.resolve() if args.input_root else None)
            output_dir = output_root(repo_root, job, args.output_root.resolve() if args.output_root else None)
            cases = discover_cases(input_dir, output_dir)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            overall_errors += 1
            continue

        print(f"\n{job.kind}")
        print(f"  input_root : {input_dir}")
        print(f"  output_root: {output_dir}")
        print(f"  cases      : {len(cases)}")
        print(f"  dry_run    : {args.dry_run}")

        results = [
            convert_case(job, case, overwrite=not args.no_overwrite, dry_run=args.dry_run)
            for case in cases
        ]

        if not args.dry_run:
            write_summary(output_dir, results)

        converted = sum(1 for r in results if r.status == "converted")
        validated = sum(1 for r in results if r.status == "validated")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors = sum(1 for r in results if r.status == "error")

        print(f"  converted  : {converted}")
        if args.dry_run:
            print(f"  validated  : {validated}")
        print(f"  skipped    : {skipped}")
        print(f"  errors     : {errors}")
        if not args.dry_run:
            print(f"  summary    : {output_dir / 'conversion_summary.csv'}")
            print(f"  error log  : {output_dir / 'conversion_errors.log'}")

        overall_errors += errors
        overall_work += converted + validated

    if overall_errors:
        return 2
    if overall_work == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
