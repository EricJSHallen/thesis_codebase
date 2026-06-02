#!/usr/bin/env python3
"""
condense_syn_outputs_reorg_v4.py

Convert plain-Spectre/OCEAN exported waveform text files from the latest raw
frequency-sweep run into CSV files.

Expected reorganized repository layout:

    thesis_codebase/
    ├── database/
    │   ├── raw/
    │   │   └── 20260601_154328_2channel_1syn_plain/
    │   │       └── cases/
    │   │           └── st1_1_hz__st2_1_hz__trial_1/
    │   │               └── output_signals.txt   # or output.txt
    │   └── formatted/
    │       └── condense_syn_outputs/
    └── experiments/
        └── frequency_sweep/
            └── formatting/
                └── condense_syn_outputs_reorg_v4.py

Main properties:
  - Automatically finds the repository root.
  - Automatically selects the latest run under database/raw unless --run-dir is given.
  - Accepts output_signals.txt or output.txt by default.
  - Handles files with or without the I172 current column.
  - Writes CSVs under database/formatted/condense_syn_outputs/<run_name>/.
  - Writes conversion_summary.csv and conversion_errors.log.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_INPUT_NAMES = ("output_signals.txt", "output.txt")
DEFAULT_FORMATTED_SUBDIR = "condense_syn_outputs"

SUFFIX_MULTIPLIERS: dict[str, float] = {
    "a": 1e-18,   # atto
    "f": 1e-15,   # femto
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

CASE_DIR_RE = re.compile(
    r"^st1_(?P<st1>\d+)_hz__st2_(?P<st2>\d+)_hz__trial_(?P<trial>\d+)$"
)

RUN_TIMESTAMP_RE = re.compile(r"^(?P<stamp>\d{8}_\d{6}).*")


@dataclass(frozen=True)
class CaseInfo:
    st1_hz: int
    st2_hz: int
    trial: int
    run_name: str


@dataclass(frozen=True)
class ConversionResult:
    case_dir: Path
    input_txt: Path | None
    output_csv: Path | None
    status: str
    message: str
    rows_written: int = 0
    columns_written: int = 0


# -----------------------------------------------------------------------------
# Repository/run discovery
# -----------------------------------------------------------------------------


def find_repo_root(start: Path | None = None) -> Path:
    """Find the thesis_codebase repository root from this script location/CWD."""
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
            # Looser fallback for partially copied repos.
            if (candidate / "database").is_dir() and candidate.name == "thesis_codebase":
                return candidate

    raise FileNotFoundError(
        "Could not find repository root. Expected a parent directory containing "
        "both database/ and experiments/. Use --repo-root explicitly."
    )


def raw_runs_dir(repo_root: Path) -> Path:
    path = repo_root / "database" / "raw"
    if not path.is_dir():
        raise FileNotFoundError(f"Raw database directory not found: {path}")
    return path


def formatted_dir(repo_root: Path) -> Path:
    path = repo_root / "database" / "formatted"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_sort_key(path: Path) -> tuple[str, float, str]:
    """Prefer timestamped directory names, then mtime."""
    match = RUN_TIMESTAMP_RE.match(path.name)
    stamp = match.group("stamp") if match else ""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (stamp, mtime, path.name)


def find_latest_raw_run(repo_root: Path, pattern: str = "*") -> Path:
    runs = [p for p in raw_runs_dir(repo_root).iterdir() if p.is_dir() and p.match(pattern)]
    # Prefer directories that look like real plain-Spectre runs.
    real_runs = [p for p in runs if (p / "cases").is_dir()]
    if real_runs:
        runs = real_runs
    if not runs:
        raise FileNotFoundError(
            f"No raw run directories found in {raw_runs_dir(repo_root)} matching {pattern!r}"
        )
    return sorted(runs, key=run_sort_key)[-1]


# -----------------------------------------------------------------------------
# Parsing helpers
# -----------------------------------------------------------------------------


def parse_engineering_number(value: str) -> float:
    value = value.strip().strip('"')
    match = NUMERIC_RE.match(value)
    if not match:
        raise ValueError(f"Could not parse numeric value: {value!r}")
    number_str, suffix = match.groups()
    return float(number_str) * SUFFIX_MULTIPLIERS[suffix]


def parse_case_dir_name(name: str) -> CaseInfo | None:
    match = CASE_DIR_RE.match(name)
    if not match:
        return None
    st1 = int(match.group("st1"))
    st2 = int(match.group("st2"))
    trial = int(match.group("trial"))
    return CaseInfo(st1_hz=st1, st2_hz=st2, trial=trial, run_name=name)


def read_nonempty_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.strip() for line in handle if line.strip()]


def looks_numeric_row(tokens: Sequence[str]) -> bool:
    if not tokens:
        return False
    for token in tokens:
        try:
            parse_engineering_number(token)
        except ValueError:
            return False
    return True


def normalise_header_token(token: str) -> str:
    token = token.strip().strip('"').strip("'")
    token = token.replace("/", "_").replace("(", "_").replace(")", "_")
    token = token.replace(".", "_").replace(":", "_")
    token = re.sub(r"[^A-Za-z0-9_]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "col"


def infer_header(raw_header_tokens: Sequence[str] | None, data_width: int) -> list[str]:
    """
    Infer a stable CSV header.

    Known output widths:
      4 = time, I56, vpre, vpre1
      5 = time, I172, I56, vpre, vpre1

    If the simulator header exists and is useful, its tokens are used only to
    distinguish whether I172 is present. Otherwise width-based fallbacks are used.
    """
    joined = " ".join(raw_header_tokens or [])
    joined_lower = joined.lower()

    if data_width == 4:
        return ["time_s", "i_I56_Iout_A", "v_vpre_res_V", "v_vpre1_res_V"]

    if data_width == 5:
        if "i172" in joined_lower or "i/i172" in joined_lower or "/i172" in joined_lower:
            return ["time_s", "i_I172_Iout_A", "i_I56_Iout_A", "v_vpre_res_V", "v_vpre1_res_V"]
        # Five columns almost certainly means the older 2-syn/duo export including I172.
        return ["time_s", "i_I172_Iout_A", "i_I56_Iout_A", "v_vpre_res_V", "v_vpre1_res_V"]

    if raw_header_tokens and len(raw_header_tokens) == data_width:
        header = [normalise_header_token(t) for t in raw_header_tokens]
        # Ensure uniqueness.
        seen: dict[str, int] = {}
        unique = []
        for name in header:
            count = seen.get(name, 0)
            seen[name] = count + 1
            unique.append(name if count == 0 else f"{name}_{count + 1}")
        return unique

    return ["time_s", *[f"value_{idx}" for idx in range(1, data_width)]]


def split_header_and_data(lines: list[str]) -> tuple[list[str] | None, list[str]]:
    """
    OCEAN output normally starts with a non-numeric header line. Some exports may
    not. Return (header_tokens, data_lines).
    """
    if not lines:
        raise ValueError("file is empty")

    first_tokens = lines[0].split()
    if looks_numeric_row(first_tokens):
        return None, lines
    return first_tokens, lines[1:]


# -----------------------------------------------------------------------------
# Conversion
# -----------------------------------------------------------------------------


def find_input_txt(case_dir: Path, names: Sequence[str]) -> Path | None:
    for name in names:
        candidate = case_dir / name
        if candidate.is_file():
            return candidate
    return None


def output_path_for_case(
    output_root: Path,
    case_info: CaseInfo,
    flat: bool,
) -> Path:
    if flat:
        return output_root / f"{case_info.run_name}.csv"
    combo = f"st1_{case_info.st1_hz}hz_st2_{case_info.st2_hz}hz"
    return output_root / combo / f"trial_{case_info.trial}.csv"


def convert_one_case(
    case_dir: Path,
    output_root: Path,
    input_names: Sequence[str],
    overwrite: bool,
    flat: bool,
) -> ConversionResult:
    case_info = parse_case_dir_name(case_dir.name)
    if case_info is None:
        return ConversionResult(case_dir, None, None, "skipped", "unrecognised case directory name")

    input_txt = find_input_txt(case_dir, input_names)
    if input_txt is None:
        return ConversionResult(
            case_dir,
            None,
            None,
            "skipped",
            f"none of these files found: {', '.join(input_names)}",
        )

    output_csv = output_path_for_case(output_root, case_info, flat=flat)
    if output_csv.exists() and not overwrite:
        return ConversionResult(case_dir, input_txt, output_csv, "skipped", "output exists and overwrite is false")

    try:
        lines = read_nonempty_lines(input_txt)
        raw_header_tokens, data_lines = split_header_and_data(lines)
        if not data_lines:
            raise ValueError("no data rows found after optional header")

        rows: list[list[float]] = []
        expected_width: int | None = None
        for line_number, line in enumerate(data_lines, start=2 if raw_header_tokens else 1):
            parts = line.split()
            if expected_width is None:
                expected_width = len(parts)
            if len(parts) != expected_width:
                raise ValueError(
                    f"inconsistent column count on line {line_number}: "
                    f"expected {expected_width}, got {len(parts)}; content={line!r}"
                )
            rows.append([parse_engineering_number(value) for value in parts])

        assert expected_width is not None
        header = infer_header(raw_header_tokens, expected_width)
        if len(header) != expected_width:
            raise ValueError(
                f"internal header-width mismatch: header has {len(header)} columns, "
                f"data has {expected_width}"
            )

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

        return ConversionResult(
            case_dir=case_dir,
            input_txt=input_txt,
            output_csv=output_csv,
            status="converted",
            message="ok",
            rows_written=len(rows),
            columns_written=expected_width,
        )
    except Exception as exc:
        return ConversionResult(case_dir, input_txt, output_csv, "error", str(exc))


def iter_case_dirs(run_dir: Path) -> Iterable[Path]:
    cases = run_dir / "cases"
    if not cases.is_dir():
        raise FileNotFoundError(f"Run directory does not contain cases/: {run_dir}")
    yield from sorted(p for p in cases.iterdir() if p.is_dir())


def write_summary(output_root: Path, run_dir: Path, results: Sequence[ConversionResult]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)

    summary_path = output_root / "conversion_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "status",
            "case_dir",
            "input_txt",
            "output_csv",
            "rows_written",
            "columns_written",
            "message",
        ])
        for result in results:
            writer.writerow([
                result.status,
                str(result.case_dir),
                str(result.input_txt) if result.input_txt else "",
                str(result.output_csv) if result.output_csv else "",
                result.rows_written,
                result.columns_written,
                result.message,
            ])

    errors_path = output_root / "conversion_errors.log"
    with errors_path.open("w", encoding="utf-8") as handle:
        handle.write(f"run_dir={run_dir}\n")
        handle.write(f"output_root={output_root}\n\n")
        for result in results:
            if result.status == "error":
                handle.write(f"ERROR {result.case_dir.name}: {result.message}\n")
            elif result.status == "skipped":
                handle.write(f"SKIPPED {result.case_dir.name}: {result.message}\n")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Condense waveform text outputs from the latest database/raw run into "
            "database/formatted CSV files."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Default: auto-detect from script/CWD.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Specific raw run directory. Default: latest directory under database/raw with cases/.",
    )
    parser.add_argument(
        "--run-pattern",
        default="*",
        help="Pattern for selecting latest run under database/raw. Default: '*'.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Output directory. Default: "
            "database/formatted/condense_syn_outputs/<run_name>."
        ),
    )
    parser.add_argument(
        "--input-name",
        action="append",
        dest="input_names",
        default=None,
        help=(
            "Input filename to search inside each case directory. Can be repeated. "
            "Default: output_signals.txt and output.txt."
        ),
    )
    parser.add_argument(
        "--nested",
        action="store_true",
        help="Write st1_Xhz_st2_Yhz/trial_N.csv instead of one flat CSV list.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip CSVs that already exist instead of overwriting them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
    run_dir = args.run_dir.resolve() if args.run_dir else find_latest_raw_run(repo_root, args.run_pattern)
    input_names = tuple(args.input_names) if args.input_names else DEFAULT_INPUT_NAMES

    if args.output_root is not None:
        output_root = args.output_root.resolve()
    else:
        output_root = formatted_dir(repo_root) / DEFAULT_FORMATTED_SUBDIR / run_dir.name

    print("Resolved paths")
    print(f"  repo_root  : {repo_root}")
    print(f"  run_dir    : {run_dir}")
    print(f"  cases_dir  : {run_dir / 'cases'}")
    print(f"  output_root: {output_root}")
    print(f"  input_names: {', '.join(input_names)}")
    print(f"  layout     : {'nested' if args.nested else 'flat'}")

    results = [
        convert_one_case(
            case_dir=case_dir,
            output_root=output_root,
            input_names=input_names,
            overwrite=not args.no_overwrite,
            flat=not args.nested,
        )
        for case_dir in iter_case_dirs(run_dir)
    ]

    write_summary(output_root, run_dir, results)

    converted = sum(1 for r in results if r.status == "converted")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    print("\nFinished.")
    print(f"  converted: {converted}")
    print(f"  skipped  : {skipped}")
    print(f"  errors   : {errors}")
    print(f"  summary  : {output_root / 'conversion_summary.csv'}")
    print(f"  error log: {output_root / 'conversion_errors.log'}")

    if errors:
        return 2
    if converted == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
