#!/usr/bin/env python3
"""
plot_phase_shift_integral_difference.py

Plot Vthr phase-shift current integral difference and ratio versus phase shift.

Default y-axis:
  two_syn_sum_abs_integral_A_s - one_syn_abs_integral_A_s

The script displays one Matplotlib popout window and does not save figures.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


plt = None


@dataclass(frozen=True)
class IntegralRow:
    phase_shift: str
    vthr_label: str
    one_syn_csv: str
    two_syn_csv: str
    one_syn_abs_integral_a_s: float
    two_syn_sum_abs_integral_a_s: float

    @property
    def phase_shift_s(self) -> float:
        return parse_phase_shift_s(self.phase_shift)

    @property
    def difference_a_s(self) -> float:
        return self.two_syn_sum_abs_integral_a_s - self.one_syn_abs_integral_a_s

    @property
    def ratio(self) -> float:
        if self.one_syn_abs_integral_a_s == 0:
            return float("nan")
        return self.two_syn_sum_abs_integral_a_s / self.one_syn_abs_integral_a_s


def load_plot_dependency() -> None:
    global plt
    if plt is not None:
        return
    try:
        import matplotlib.pyplot as matplotlib_pyplot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Missing plotting dependency: {exc.name}. Install matplotlib to plot integral differences."
        ) from exc
    plt = matplotlib_pyplot


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "database").is_dir() and (candidate / "experiments").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find repo root. Run from inside thesis_codebase, "
        "or pass --repo-root /path/to/thesis_codebase."
    )


def parse_phase_shift_s(phase_shift: str) -> float:
    match = re.search(r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)_phase_shift", phase_shift)
    if not match:
        raise ValueError(f"Could not parse phase shift value from {phase_shift!r}")
    return float(match.group("value"))


def load_integral_rows_from_csv(path: Path) -> list[IntegralRow]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        required = [
            "phase_shift",
            "vthr_label",
            "one_syn_csv",
            "two_syn_csv",
            "one_syn_abs_integral_A_s",
            "two_syn_sum_abs_integral_A_s",
        ]
        missing = [col for col in required if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    IntegralRow(
                        phase_shift=row["phase_shift"],
                        vthr_label=row["vthr_label"],
                        one_syn_csv=row["one_syn_csv"],
                        two_syn_csv=row["two_syn_csv"],
                        one_syn_abs_integral_a_s=float(row["one_syn_abs_integral_A_s"]),
                        two_syn_sum_abs_integral_a_s=float(row["two_syn_sum_abs_integral_A_s"]),
                    )
                )
            except ValueError as exc:
                raise ValueError(f"Could not parse numeric integral on line {line_number} in {path}") from exc

    if not rows:
        raise ValueError(f"No integral rows found in {path}")
    return rows


def load_integrator_module(repo_root: Path):
    script = Path(__file__).with_name("integrate_phase_shift_currents.py")
    spec = importlib.util.spec_from_file_location("integrate_phase_shift_currents", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load integration script: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def compute_integral_rows(repo_root: Path, one_syn_dir: Path | None, two_syn_dir: Path | None) -> list[IntegralRow]:
    integrator = load_integrator_module(repo_root)
    one_dir = one_syn_dir.resolve() if one_syn_dir else integrator.default_one_syn_dir(repo_root)
    two_dir = two_syn_dir.resolve() if two_syn_dir else integrator.default_two_syn_dir(repo_root)
    pairs = integrator.find_current_pairs(one_dir, two_dir)

    rows = []
    for rel_path, one_csv, two_csv in pairs:
        result = integrator.integrate_pair(rel_path, one_csv, two_csv)
        rows.append(
            IntegralRow(
                phase_shift=result.phase_shift,
                vthr_label=result.vthr_label,
                one_syn_csv=str(result.one_syn_csv),
                two_syn_csv=str(result.two_syn_csv),
                one_syn_abs_integral_a_s=result.one_syn_abs_integral_a_s,
                two_syn_sum_abs_integral_a_s=result.two_syn_sum_abs_integral_a_s,
            )
        )
    return rows


def selected_rows(rows: Sequence[IntegralRow], start_at: int, limit: int | None) -> list[IntegralRow]:
    if start_at < 1:
        raise ValueError("--start-at must be >= 1")
    selected = list(rows)[start_at - 1:]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("No integral rows selected after filtering.")
    return selected


def group_rows_by_vthr(rows: Sequence[IntegralRow]) -> dict[str, list[IntegralRow]]:
    groups: dict[str, list[IntegralRow]] = {}
    for row in rows:
        label = row.vthr_label or "no_vthr"
        groups.setdefault(label, []).append(row)
    for label in groups:
        groups[label] = sorted(groups[label], key=lambda row: row.phase_shift_s)
    return dict(sorted(groups.items()))


def plot_rows(rows: Sequence[IntegralRow], absolute_difference: bool) -> None:
    load_plot_dependency()
    groups = group_rows_by_vthr(rows)

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 8))
    diff_ax, ratio_ax = axes
    for label, group in groups.items():
        x = [row.phase_shift_s * 1e6 for row in group]
        diff_y = [row.difference_a_s for row in group]
        ratio_y = [row.ratio for row in group]
        if absolute_difference:
            diff_y = [abs(value) for value in diff_y]
        plot_label = label if len(groups) > 1 else None
        diff_ax.plot(x, diff_y, marker="o", markersize=3, linewidth=1, label=plot_label)
        ratio_ax.plot(x, ratio_y, marker="o", markersize=3, linewidth=1, label=plot_label)

    diff_ax.set_xlabel(r"interspike interval ($\mu s$)")
    diff_ax.set_ylabel(r"$\Delta Q$")
    diff_ax.set_title(r"$\Delta Q$ of multiplexed and non multiplexed architecture")
    diff_ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    diff_ax.grid(True)
    ratio_ax.set_xlabel(r"interspike interval ($\mu s$)")
    ratio_ax.set_ylabel("ratio")
    ratio_ax.set_title("charge ratio of multiplexed and non multiplexed architecture")
    ratio_ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    ratio_ax.grid(True)
    if len(groups) > 1:
        legend_ncol = min(len(groups), 4)
        diff_ax.legend(
            title="Vthr",
            loc="upper left",
            bbox_to_anchor=(0, -0.32, 1, 0.1),
            mode="expand",
            ncol=legend_ncol,
            borderaxespad=0,
        )
        ratio_ax.legend(
            title="Vthr",
            loc="upper left",
            bbox_to_anchor=(0, -0.38, 1, 0.1),
            mode="expand",
            ncol=legend_ncol,
            borderaxespad=0,
        )
    fig.tight_layout()
    fig.subplots_adjust(hspace=1.25, bottom=0.38)

    print(f"Rows plotted: {len(rows)}")
    print(f"Vthr groups: {', '.join(groups)}")
    plt.show()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot summed-2syn-minus-1syn Vthr phase-shift integral difference."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--integrals-csv", type=Path, default=None)
    parser.add_argument("--one-syn-dir", type=Path, default=None)
    parser.add_argument("--two-syn-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--absolute-difference", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
        if args.integrals_csv is not None:
            rows = load_integral_rows_from_csv(args.integrals_csv.resolve())
        else:
            rows = compute_integral_rows(repo_root, args.one_syn_dir, args.two_syn_dir)

        rows = selected_rows(rows, args.start_at, args.limit)
        plot_rows(rows, absolute_difference=args.absolute_difference)
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
