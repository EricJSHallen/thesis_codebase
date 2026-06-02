#!/usr/bin/env python3
"""
plot_frequency_sweep_csvs_v2.py

Interactive Matplotlib viewer for formatted frequency-sweep CSV outputs.

Fix relative to v1:
    - Removes pd.to_numeric(errors="ignore"), which can trigger
      "invalid error value specified" in some pandas/numpy environments.
    - Adds clearer per-file error reporting and an optional --debug traceback.
    - Opens one Matplotlib window at a time by default.

Expected repo layout:
    thesis_codebase/
    ├── database/
    │   └── formatted/
    └── experiments/
        └── frequency_sweep/
            └── analysis/
"""

from __future__ import annotations

import argparse
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


IGNORE_CSV_NAMES = {
    "conversion_summary.csv",
    "summary.csv",
    "errors.csv",
    "conversion_errors.csv",
}


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find repo root. Run from inside thesis_codebase, "
        "or pass --repo-root /path/to/thesis_codebase."
    )


def latest_directory(parent: Path) -> Path:
    dirs = [p for p in parent.iterdir() if p.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No directories found under {parent}")
    return max(dirs, key=lambda p: p.stat().st_mtime)


def find_latest_formatted_run(repo_root: Path) -> Path:
    formatted = repo_root / "database" / "formatted"
    if not formatted.is_dir():
        raise FileNotFoundError(f"Formatted directory not found: {formatted}")

    condense = formatted / "condense_syn_outputs"
    if condense.is_dir():
        try:
            return latest_directory(condense)
        except FileNotFoundError:
            pass

    return latest_directory(formatted)


def csv_sort_key(path: Path) -> tuple[int, int, int, str]:
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
        raise FileNotFoundError(f"No CSV files found under {input_dir}")
    return sorted(csvs, key=csv_sort_key)


def normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns to numeric where possible.

    Avoid pd.to_numeric(errors='ignore'), because some pandas/numpy
    combinations can raise:
        ValueError: invalid error value specified
    """
    out = df.copy()

    for col in out.columns:
        converted = pd.to_numeric(out[col], errors="coerce")
        if converted.notna().any():
            out[col] = converted

    return out


def find_time_column(df: pd.DataFrame) -> str:
    normalized = {col: normalize_colname(col) for col in df.columns}

    for col, norm in normalized.items():
        if norm in {"time", "times", "timesec", "times"} or norm.startswith("time"):
            return col

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        return numeric_cols[0]

    raise ValueError("Could not identify a numeric time column.")


def choose_signal_columns(df: pd.DataFrame, time_col: str) -> tuple[str, str, str]:
    numeric_cols = [
        c for c in df.select_dtypes(include="number").columns.tolist()
        if c != time_col
    ]

    if len(numeric_cols) < 3:
        raise ValueError(
            f"Expected at least 3 numeric signal columns besides time, got {len(numeric_cols)}: {numeric_cols}"
        )

    voltage_cols = [
        c for c in numeric_cols
        if normalize_colname(c).startswith("v") or "vpre" in normalize_colname(c)
    ]

    current_cols = [
        c for c in numeric_cols
        if normalize_colname(c).startswith("i") or "iout" in normalize_colname(c)
    ]

    current_cols = sorted(
        current_cols,
        key=lambda c: (
            0 if "i56" in normalize_colname(c) else
            1 if "iout" in normalize_colname(c) else
            2,
            str(c),
        ),
    )

    vpre = [c for c in voltage_cols if "vpre1" not in normalize_colname(c) and "vpre" in normalize_colname(c)]
    vpre1 = [c for c in voltage_cols if "vpre1" in normalize_colname(c)]

    if vpre and vpre1:
        v1_col = sorted(vpre)[0]
        v2_col = sorted(vpre1)[0]
    elif len(voltage_cols) >= 2:
        v1_col, v2_col = sorted(voltage_cols)[:2]
    else:
        non_current = [c for c in numeric_cols if c not in current_cols]
        if len(non_current) >= 2:
            v1_col, v2_col = non_current[-2], non_current[-1]
        else:
            v1_col, v2_col = numeric_cols[-2], numeric_cols[-1]

    if current_cols:
        i_col = current_cols[0]
    else:
        remaining = [c for c in numeric_cols if c not in {v1_col, v2_col}]
        if not remaining:
            raise ValueError("Could not identify a current column.")
        i_col = remaining[0]

    return v1_col, v2_col, i_col


def parse_case_label(csv_path: Path) -> str:
    parent = csv_path.parent.name
    stem = csv_path.stem

    if stem.lower() in {"output", "output_signals", "signals", "trial"}:
        return parent

    if parent and parent not in {"formatted", "condense_syn_outputs"}:
        return f"{parent}/{stem}"

    return stem


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df.dropna(axis=1, how="all")
    df = coerce_numeric_columns(df)
    return df


def plot_one_csv(csv_path: Path, index: int, total: int) -> None:
    df = load_csv(csv_path)
    time_col = find_time_column(df)
    v1_col, v2_col, i_col = choose_signal_columns(df, time_col)

    label = parse_case_label(csv_path)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(11, 8.5))
    try:
        fig.canvas.manager.set_window_title(f"{index}/{total}: {label}")
    except Exception:
        pass

    axes[0].plot(df[time_col], df[v1_col])
    axes[0].set_ylabel(str(v1_col))
    axes[0].set_title(f"{label}    [{index}/{total}]")

    axes[1].plot(df[time_col], df[v2_col])
    axes[1].set_ylabel(str(v2_col))

    axes[2].plot(df[time_col], df[i_col])
    axes[2].set_ylabel(str(i_col))
    axes[2].set_xlabel(str(time_col))

    for ax in axes:
        ax.grid(True)

    fig.tight_layout()

    print(f"[{index:03d}/{total:03d}] {csv_path}")
    print(f"    time={time_col}, voltage1={v1_col}, voltage2={v2_col}, current={i_col}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument("--skip-errors", action="store_true", help="Skip unreadable/malformed CSVs.")
    parser.add_argument("--debug", action="store_true", help="Print full traceback on errors.")
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
            raise FileNotFoundError("No CSVs selected after filtering.")

        total = len(csvs)

        print(f"Repo root: {repo_root}")
        print(f"Input dir: {input_dir}")
        print(f"CSV files selected: {total}")
        print("Close each Matplotlib window to advance to the next CSV.\n")

        if args.open_all:
            for i, csv_path in enumerate(csvs, start=1):
                try:
                    plot_one_csv(csv_path, i, total)
                except Exception as exc:
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {csv_path}: {exc}", file=sys.stderr)
            plt.show()
        else:
            for i, csv_path in enumerate(csvs, start=1):
                try:
                    plot_one_csv(csv_path, i, total)
                    plt.show()
                    plt.close("all")
                except Exception as exc:
                    plt.close("all")
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {csv_path}: {exc}", file=sys.stderr)

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


if __name__ == "__main__":
    raise SystemExit(main())
