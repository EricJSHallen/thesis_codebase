#!/usr/bin/env python3
"""
plot_phase_shift_csvs.py

Interactive Matplotlib viewer for formatted phase-shift CSV outputs.

Expected formatted inputs:
  database/formatted/phase_shift_1syn/
  database/formatted/phase_shift_2syn/

Each CSV is displayed in a popout Matplotlib window. Close the window to advance
to the next CSV. This script does not save figures.

Use --combined to show matching 1syn and 2syn CSVs together as seven stacked
plots in one figure.
"""

from __future__ import annotations

import argparse
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

KIND_TO_FORMATTED_SUBDIR = {
    "1syn": "phase_shift_1syn",
    "2syn": "phase_shift_2syn",
}

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


def resolve_input_dir(repo_root: Path, kind: str | None, input_dir: Path | None) -> Path:
    if kind is not None and input_dir is not None:
        raise ValueError("Use either --kind or --input-dir, not both.")
    if input_dir is not None:
        resolved = input_dir.resolve()
    elif kind is not None:
        resolved = repo_root / "database" / "formatted" / KIND_TO_FORMATTED_SUBDIR[kind]
    else:
        raise ValueError("Use --kind {1syn,2syn} or --input-dir.")

    if not resolved.is_dir():
        raise FileNotFoundError(f"Input directory not found: {resolved}")
    return resolved


def default_input_dir(repo_root: Path, kind: str) -> Path:
    resolved = repo_root / "database" / "formatted" / KIND_TO_FORMATTED_SUBDIR[kind]
    if not resolved.is_dir():
        raise FileNotFoundError(f"Input directory not found for {kind}: {resolved}")
    return resolved


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
        raise FileNotFoundError(
            f"No plottable CSV files found under {input_dir}. "
            "Expected formatted phase-shift case CSVs."
        )
    return sorted(csvs, key=csv_sort_key)


def csv_map_by_relative_path(input_dir: Path) -> dict[Path, Path]:
    return {path.relative_to(input_dir): path for path in find_csv_files(input_dir)}


def find_combined_pairs(repo_root: Path) -> tuple[Path, Path, list[tuple[Path, Path, Path]]]:
    one_syn_dir = default_input_dir(repo_root, "1syn")
    two_syn_dir = default_input_dir(repo_root, "2syn")
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
        raise FileNotFoundError("Combined CSV pair mismatch: " + "; ".join(messages))

    rel_paths = sorted(one_syn, key=lambda p: csv_sort_key(one_syn[p]))
    pairs = [(rel_path, one_syn[rel_path], two_syn[rel_path]) for rel_path in rel_paths]
    if not pairs:
        raise FileNotFoundError("No combined 1syn/2syn CSV pairs found.")
    return one_syn_dir, two_syn_dir, pairs


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
        norm = normalize_colname(col)
        if norm.startswith("time"):
            return col

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        return numeric_cols[0]
    raise ValueError("Could not identify a numeric time column.")


def signal_columns(df, time_col: str) -> list[str]:
    cols = [
        col for col in df.select_dtypes(include="number").columns.tolist()
        if col != time_col
    ]
    if not cols:
        raise ValueError("No numeric signal columns besides time were found.")
    return cols


def parse_case_label(csv_path: Path, input_dir: Path) -> str:
    try:
        rel = csv_path.relative_to(input_dir)
    except ValueError:
        return csv_path.stem
    return str(rel.with_suffix(""))


def plot_one_csv(csv_path: Path, input_dir: Path, index: int, total: int) -> None:
    df = load_csv(csv_path)
    time_col = find_time_column(df)
    signals = signal_columns(df, time_col)
    label = parse_case_label(csv_path, input_dir)

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

    print(f"[{index:03d}/{total:03d}] {csv_path}")
    print(f"    time={time_col}, signals={', '.join(map(str, signals))}")


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

    print(f"[{index:03d}/{total:03d}] {rel_path}")
    print(f"    1syn={one_syn_csv}")
    print(f"    2syn={two_syn_csv}")
    print(f"    1syn time={one_time}, signals={', '.join(map(str, one_signals))}")
    print(f"    2syn time={two_time}, signals={', '.join(map(str, two_signals))}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display formatted phase-shift CSVs as interactive Matplotlib plots."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--kind", choices=sorted(KIND_TO_FORMATTED_SUBDIR), default=None)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--combined", action="store_true", help="Plot matching 1syn and 2syn CSVs as seven stacked subplots.")
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

        if args.combined and (args.kind is not None or args.input_dir is not None):
            raise ValueError("Use --combined by itself, not with --kind or --input-dir.")

        if args.start_at < 1:
            raise ValueError("--start-at must be >= 1")

        if args.combined:
            one_syn_dir, two_syn_dir, pairs = find_combined_pairs(repo_root)
            pairs = pairs[args.start_at - 1:]
            if args.limit is not None:
                pairs = pairs[:args.limit]
            if not pairs:
                raise FileNotFoundError("No combined CSV pairs selected after filtering.")

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
                        plot_combined_pair(rel_path, one_syn_csv, two_syn_csv, index, total)
                    except Exception as exc:
                        if not args.skip_errors:
                            raise
                        print(f"SKIP {rel_path}: {exc}", file=sys.stderr)
                plt.show()
            else:
                for index, (rel_path, one_syn_csv, two_syn_csv) in enumerate(pairs, start=1):
                    try:
                        plot_combined_pair(rel_path, one_syn_csv, two_syn_csv, index, total)
                        plt.show()
                        plt.close("all")
                    except Exception as exc:
                        plt.close("all")
                        if not args.skip_errors:
                            raise
                        print(f"SKIP {rel_path}: {exc}", file=sys.stderr)

            return 0

        input_dir = resolve_input_dir(repo_root, args.kind, args.input_dir)
        csvs = find_csv_files(input_dir)

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

        load_plot_dependencies()

        if args.open_all:
            for index, csv_path in enumerate(csvs, start=1):
                try:
                    plot_one_csv(csv_path, input_dir, index, total)
                except Exception as exc:
                    if not args.skip_errors:
                        raise
                    print(f"SKIP {csv_path}: {exc}", file=sys.stderr)
            plt.show()
        else:
            for index, csv_path in enumerate(csvs, start=1):
                try:
                    plot_one_csv(csv_path, input_dir, index, total)
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
