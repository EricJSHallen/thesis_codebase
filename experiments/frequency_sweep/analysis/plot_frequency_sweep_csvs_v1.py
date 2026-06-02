#!/usr/bin/env python3
"""
plot_frequency_sweep_csvs_v1.py

Interactive Matplotlib viewer for formatted frequency-sweep CSV outputs.

Expected repository layout:
    thesis_codebase/
    ├── database/
    │   └── formatted/
    │       └── ...
    └── experiments/
        └── frequency_sweep/
            └── analysis/
                └── plot_frequency_sweep_csvs_v1.py

Default behaviour:
    - Finds the repo root automatically.
    - Finds the latest formatted output run under database/formatted/.
    - Recursively finds CSV files for the run.
    - Opens one Matplotlib window per CSV.
    - Each window has three vertically stacked plots:
        1. voltage 1 vs time
        2. voltage 2 vs time
        3. current vs time
    - Does not save figures.

Usage:
    python3 experiments/frequency_sweep/analysis/plot_frequency_sweep_csvs_v1.py

Optional:
    python3 experiments/frequency_sweep/analysis/plot_frequency_sweep_csvs_v1.py --limit 5
    python3 experiments/frequency_sweep/analysis/plot_frequency_sweep_csvs_v1.py --open-all
    python3 experiments/frequency_sweep/analysis/plot_frequency_sweep_csvs_v1.py --input-dir database/formatted/condense_syn_outputs/<run_id>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd


IGNORE_CSV_NAMES = {
    "conversion_summary.csv",
    "summary.csv",
    "errors.csv",
}


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk upward until a directory with database/ and experiments/ is found."""
    here = (start or Path.cwd()).resolve()

    candidates = [here, *here.parents]
    for candidate in candidates:
        if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
            return candidate

    raise FileNotFoundError(
        "Could not find repo root. Run this script from inside thesis_codebase, "
        "or pass --repo-root /path/to/thesis_codebase."
    )


def latest_directory(parent: Path) -> Path:
    """Return the most recently modified child directory."""
    dirs = [p for p in parent.iterdir() if p.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No directories found under {parent}")
    return max(dirs, key=lambda p: p.stat().st_mtime)


def find_latest_formatted_run(repo_root: Path) -> Path:
    """
    Find the latest run directory under database/formatted.

    Supports both:
        database/formatted/<run_id>/
    and:
        database/formatted/condense_syn_outputs/<run_id>/
    """
    formatted = repo_root / "database" / "formatted"
    if not formatted.is_dir():
        raise FileNotFoundError(f"Formatted database directory not found: {formatted}")

    # Prefer the condense_syn_outputs layout if it exists and contains run dirs.
    condense = formatted / "condense_syn_outputs"
    if condense.is_dir():
        try:
            return latest_directory(condense)
        except FileNotFoundError:
            pass

    return latest_directory(formatted)


def csv_sort_key(path: Path) -> tuple[int, int, int, str]:
    """
    Sort by st1 frequency, st2 frequency, trial if encoded in the filename/path.
    Falls back to lexical path order.
    """
    text = str(path)
    st1 = re.search(r"st1[_-]?(\d+)[_\s-]*hz", text, flags=re.IGNORECASE)
    st2 = re.search(r"st2[_-]?(\d+)[_\s-]*hz", text, flags=re.IGNORECASE)
    trial = re.search(r"trial[_-]?(\d+)", text, flags=re.IGNORECASE)

    return (
        int(st1.group(1)) if st1 else 10**9,
        int(st2.group(1)) if st2 else 10**9,
        int(trial.group(1)) if trial else 10**9,
        text,
    )


def find_csv_files(input_dir: Path) -> list[Path]:
    csvs = [
        p for p in input_dir.rglob("*.csv")
        if p.is_file()
        and p.name not in IGNORE_CSV_NAMES
        and not p.name.startswith(".")
    ]

    if not csvs:
        raise FileNotFoundError(f"No CSV output files found under {input_dir}")

    return sorted(csvs, key=csv_sort_key)


def normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def find_time_column(df: pd.DataFrame) -> str:
    normalized = {col: normalize_colname(col) for col in df.columns}

    for col, norm in normalized.items():
        if norm in {"times", "time", "t"} or norm.startswith("time"):
            return col

    # Conservative fallback: first numeric column.
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        return numeric_cols[0]

    raise ValueError("Could not identify a numeric time column.")


def choose_signal_columns(df: pd.DataFrame, time_col: str) -> tuple[str, str, str]:
    """
    Choose voltage1, voltage2, current columns.

    Works with column sets like:
        time_s, i_I56_Iout_A, v_vpre_res_V, v_vpre1_res_V

    or with I172 included:
        time_s, i_I172_Iout_A, i_I56_Iout_A, v_vpre_res_V, v_vpre1_res_V

    Preference:
        voltage 1: first voltage column, preferably vpre
        voltage 2: second voltage column, preferably vpre1
        current:   i_I56_Iout if present; otherwise first current column
    """
    cols = [c for c in df.columns if c != time_col]
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

    voltage_cols = [
        c for c in numeric_cols
        if normalize_colname(c).startswith("v") or "vpre" in normalize_colname(c)
    ]

    current_cols = [
        c for c in numeric_cols
        if normalize_colname(c).startswith("i") or "iout" in normalize_colname(c)
    ]

    # Prefer original output names where possible.
    voltage_cols = sorted(
        voltage_cols,
        key=lambda c: (
            0 if "vpre1" not in normalize_colname(c) and "vpre" in normalize_colname(c) else
            1 if "vpre1" in normalize_colname(c) else
            2,
            c,
        ),
    )

    current_cols = sorted(
        current_cols,
        key=lambda c: (
            0 if "i56" in normalize_colname(c) else
            1 if "iout" in normalize_colname(c) else
            2,
            c,
        ),
    )

    if len(voltage_cols) >= 2:
        v1, v2 = voltage_cols[0], voltage_cols[1]
    elif len(voltage_cols) == 1:
        v1 = voltage_cols[0]
        remaining = [c for c in numeric_cols if c != v1]
        if not remaining:
            raise ValueError("Only one numeric signal column found; need at least voltage/current signals.")
        v2 = remaining[-1]
    else:
        # Fallback to the last two numeric non-time columns if names are not descriptive.
        non_current = [c for c in numeric_cols if c not in current_cols]
        if len(non_current) >= 2:
            v1, v2 = non_current[-2], non_current[-1]
        elif len(numeric_cols) >= 3:
            v1, v2 = numeric_cols[-2], numeric_cols[-1]
        else:
            raise ValueError("Could not identify two voltage columns.")

    if current_cols:
        current = current_cols[0]
    else:
        remaining = [c for c in numeric_cols if c not in {v1, v2}]
        if not remaining:
            raise ValueError("Could not identify a current column.")
        current = remaining[0]

    return v1, v2, current


def parse_case_label(csv_path: Path) -> str:
    """Create a readable title from CSV path."""
    stem = csv_path.stem
    parent = csv_path.parent.name

    if stem.lower() in {"output", "output_signals", "signals", "trial"}:
        return parent

    if parent not in {"condense_syn_outputs", "formatted"}:
        return f"{parent}/{stem}"

    return stem


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Drop completely empty columns created by trailing delimiters.
    df = df.dropna(axis=1, how="all")

    # Convert possible numeric strings to numeric; leave nonnumeric metadata alone.
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    return df


def plot_one_csv(csv_path: Path, index: int, total: int) -> None:
    df = load_csv(csv_path)
    time_col = find_time_column(df)
    v1_col, v2_col, i_col = choose_signal_columns(df, time_col)

    case_label = parse_case_label(csv_path)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(11, 8.5))
    fig.canvas.manager.set_window_title(f"{index}/{total}: {case_label}")

    axes[0].plot(df[time_col], df[v1_col])
    axes[0].set_ylabel(v1_col)
    axes[0].set_title(f"{case_label}    [{index}/{total}]")

    axes[1].plot(df[time_col], df[v2_col])
    axes[1].set_ylabel(v2_col)

    axes[2].plot(df[time_col], df[i_col])
    axes[2].set_ylabel(i_col)
    axes[2].set_xlabel(time_col)

    for ax in axes:
        ax.grid(True, alpha=0.35)

    fig.tight_layout()

    print(f"[{index:03d}/{total:03d}] {csv_path}")
    print(f"    time={time_col}, voltage1={v1_col}, voltage2={v2_col}, current={i_col}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cycle through formatted frequency-sweep CSVs and display Matplotlib panels."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Path to thesis_codebase. Defaults to auto-detection from current directory.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Formatted run directory containing CSV files. Defaults to latest database/formatted run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only plot the first N CSVs. Useful for testing.",
    )
    parser.add_argument(
        "--open-all",
        action="store_true",
        help="Open all figures at once. Default is one window at a time.",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=1,
        help="1-based index of the first CSV to plot after sorting.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        input_dir = args.input_dir.resolve() if args.input_dir else find_latest_formatted_run(repo_root)

        csvs = find_csv_files(input_dir)

        if args.start_at < 1:
            raise ValueError("--start-at must be >= 1")

        csvs = csvs[args.start_at - 1:]
        if args.limit is not None:
            csvs = csvs[:args.limit]

        if not csvs:
            raise FileNotFoundError("No CSV files selected after --start-at/--limit filtering.")

        total = len(csvs)
        print(f"Repo root: {repo_root}")
        print(f"Input dir: {input_dir}")
        print(f"CSV files selected: {total}")
        print("Close each Matplotlib window to advance to the next CSV.\n")

        if args.open_all:
            for i, csv_path in enumerate(csvs, start=1):
                plot_one_csv(csv_path, i, total)
            plt.show()
        else:
            for i, csv_path in enumerate(csvs, start=1):
                plot_one_csv(csv_path, i, total)
                plt.show()
                plt.close("all")

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
