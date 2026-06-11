#!/usr/bin/env python3
"""
plot_phase_shift_currents.py

Interactive Matplotlib viewer for current-only Vtau phase-shift comparisons.

For each matching formatted 1syn/2syn CSV pair, this script displays four
stacked baseline-subtracted current plots:
  1. 1syn i_I56_Iout_A
  2. 2syn i_I172_Iout_A
  3. 2syn i_I56_Iout_A
  4. 2syn i_I172_Iout_A + i_I56_Iout_A

Close each popout Matplotlib window to advance. This script does not save
figures.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import traceback
from pathlib import Path
from typing import Optional


IGNORE_CSV_NAMES = {
    "conversion_summary.csv",
    "summary.csv",
    "errors.csv",
    "conversion_errors.csv",
}

ONE_SYN_CURRENT = "i_I56_Iout_A"
TWO_SYN_I172 = "i_I172_Iout_A"
TWO_SYN_I56 = "i_I56_Iout_A"

plt = None
pd = None


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
    path = repo_root / "database" / "formatted" / "phase_shift_1syn_vtau_v2"
    if not path.is_dir():
        raise FileNotFoundError(f"1syn formatted directory not found: {path}")
    return path


def default_two_syn_dir(repo_root: Path) -> Path:
    path = repo_root / "database" / "formatted" / "phase_shift_2syn_vtau_v2"
    if not path.is_dir():
        raise FileNotFoundError(f"2syn formatted directory not found: {path}")
    return path


def parse_phase_shift_s(path: Path) -> float:
    match = re.search(r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)_phase_shift", path.stem)
    if not match:
        return float("inf")
    return float(match.group("value"))


def parse_vtau_sort_key(path: Path) -> tuple[int, float | str]:
    vtau_label = ""
    for part in path.parts:
        if part.startswith("vtau_"):
            vtau_label = part
            break
    if not vtau_label:
        return (0, "")

    value = vtau_label.removeprefix("vtau_").replace("p", ".")
    try:
        return (1, float(value))
    except ValueError:
        return (1, vtau_label)


def csv_sort_key(path: Path) -> tuple[tuple[int, float | str], float, str]:
    return (parse_vtau_sort_key(path), parse_phase_shift_s(path), str(path))


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


def require_columns(df, columns: list[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def insert_midpoint_rows(df, target_len: int, time_col: str):
    """Return a copy of df with midpoint rows inserted until len == target_len."""
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
    """Pad the shorter dataframe with artificial midpoint rows, preserving originals."""
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


def plot_current_pair(rel_path: Path, one_syn_csv: Path, two_syn_csv: Path, index: int, total: int) -> None:
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
    fig, axes = plt.subplots(4, 1, sharex=False, figsize=(12, 9))
    try:
        fig.canvas.manager.set_window_title(f"{index}/{total}: {label}")
    except Exception:
        pass

    plots = [
        (one_df[one_time], one_i56, f"1syn {ONE_SYN_CURRENT} - initial"),
        (two_df[two_time], two_i172, f"2syn {TWO_SYN_I172} - initial"),
        (two_df[two_time], two_i56, f"2syn {TWO_SYN_I56} - initial"),
        (two_df[two_time], two_syn_sum, "2syn summed current - initial"),
    ]

    for ax, (time_values, current_values, ylabel) in zip(axes, plots):
        ax.plot(time_values, current_values)
        ax.set_ylabel(ylabel)
        ax.grid(True)

    axes[0].set_title(f"{label}    [{index}/{total}]")
    axes[-1].set_xlabel("time_s")
    fig.tight_layout()

    print(f"[{index:03d}/{total:03d}] {rel_path}")
    print(f"    1syn={one_syn_csv}")
    print(f"    2syn={two_syn_csv}")
    print(f"    rows: 1syn={len(one_df)}, 2syn={len(two_df)}")
    print("    baseline: first sample subtracted from each current trace")
    if equalize_note:
        print(f"    NOTE: {equalize_note}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display phase-shift current comparisons as interactive Matplotlib plots."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--one-syn-dir", type=Path, default=None)
    parser.add_argument("--two-syn-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--open-all", action="store_true")
    parser.add_argument("--skip-errors", action="store_true")
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

        total = len(pairs)
        print(f"Repo root: {repo_root}")
        print(f"1syn input dir: {one_syn_dir}")
        print(f"2syn input dir: {two_syn_dir}")
        print(f"CSV pairs selected: {total}")
        print("Close each Matplotlib window to advance to the next CSV pair.\n")

        load_plot_dependencies()

        if args.open_all:
            for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                try:
                    plot_current_pair(rel_path, one_syn_csv, two_syn_csv, index, total)
                except Exception as exc:
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {rel_path}: {exc}", file=sys.stderr)
            plt.show()
        else:
            for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                try:
                    plot_current_pair(rel_path, one_syn_csv, two_syn_csv, index, total)
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


if __name__ == "__main__":
    raise SystemExit(main())
