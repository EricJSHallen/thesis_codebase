#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import bias_axis_label, find_repo_root, label_to_voltage

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plot_output_utils import add_image_output_args, resolve_output_dir, save_figure


@dataclass(frozen=True)
class ThresholdRow:
    vtau_label: str
    vthr_label: str
    threshold: str
    max_us: str
    crossing_us: float | None
    tau_us: float | None
    status: str


def parse_optional_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    return parsed


def load_threshold_rows(path: Path) -> list[ThresholdRow]:
    required = {
        "fixed_bias",
        "fixed_bias_label",
        "curve_bias",
        "curve_bias_label",
        "threshold",
        "max_us",
        "tau_us",
        "crossing_us",
        "status",
    }
    rows: list[ThresholdRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")

        seen: set[tuple[str, str]] = set()
        for line_number, row in enumerate(reader, start=2):
            if row["curve_bias"] != "vtau" or row["fixed_bias"] != "vthr":
                continue
            key = (row["curve_bias_label"], row["fixed_bias_label"])
            if key in seen:
                raise ValueError(f"duplicate vtau/vthr cell on line {line_number}: {key[0]}, {key[1]}")
            seen.add(key)
            rows.append(
                ThresholdRow(
                    vtau_label=row["curve_bias_label"],
                    vthr_label=row["fixed_bias_label"],
                    threshold=row["threshold"],
                    max_us=row["max_us"],
                    crossing_us=parse_optional_float(row["crossing_us"]),
                    tau_us=parse_optional_float(row["tau_us"]),
                    status=row["status"],
                )
            )

    if not rows:
        raise ValueError(f"No vtau/vthr threshold rows found in {path}")
    return rows


def sorted_labels(rows: Sequence[ThresholdRow], attr: str, bias: str) -> list[str]:
    labels = {getattr(row, attr) for row in rows}
    return sorted(labels, key=lambda label: label_to_voltage(label, bias))


def metric_value(row: ThresholdRow, metric: str) -> float:
    if metric == "crossing-us":
        if row.status == "not_crossed_by_max_us" or row.crossing_us is None:
            return math.nan
        return row.crossing_us
    if metric == "tau-us":
        return math.nan if row.tau_us is None else row.tau_us
    raise ValueError(f"unknown metric: {metric}")


def heatmap_matrix(rows: Sequence[ThresholdRow], vtau_labels: Sequence[str], vthr_labels: Sequence[str], metric: str) -> list[list[float]]:
    vtau_index = {label: index for index, label in enumerate(vtau_labels)}
    vthr_index = {label: index for index, label in enumerate(vthr_labels)}
    matrix = [[math.nan for _ in vtau_labels] for _ in vthr_labels]
    for row in rows:
        matrix[vthr_index[row.vthr_label]][vtau_index[row.vtau_label]] = metric_value(row, metric)
    return matrix


def title_value(values: set[str], label: str) -> str:
    if len(values) == 1:
        return next(iter(values))
    return f"multiple {label}s"


def plot_heatmap(
    rows: Sequence[ThresholdRow],
    metric: str,
    cmap: str,
    vmin: float | None,
    vmax: float | None,
    annotate: bool,
):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Missing plotting dependency: matplotlib. Install matplotlib to plot heatmaps.") from exc

    vtau_labels = sorted_labels(rows, "vtau_label", "vtau")
    vthr_labels = sorted_labels(rows, "vthr_label", "vthr")
    matrix = heatmap_matrix(rows, vtau_labels, vthr_labels, metric)
    missing = sum(1 for row in matrix for value in row if math.isnan(value))
    if missing:
        print(f"WARNING: {missing} blank heatmap cells", file=sys.stderr)

    threshold = title_value({row.threshold for row in rows}, "threshold")
    max_us = title_value({row.max_us for row in rows}, "max_us")
    metric_label = "Threshold crossing ISI (us)" if metric == "crossing-us" else "Fit tau (us)"

    fig, ax = plt.subplots(1, 1, figsize=(7.5, 6.2), constrained_layout=True)
    image = ax.imshow(matrix, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(f"Ratio Fit Threshold Heatmap, threshold={threshold}, max={max_us} us")
    ax.set_xlabel(bias_axis_label("vtau"))
    ax.set_ylabel(bias_axis_label("vthr"))
    ax.set_xticks(
        range(len(vtau_labels)),
        [f"{label_to_voltage(label, 'vtau'):g}" for label in vtau_labels],
        rotation=45,
        ha="right",
    )
    ax.set_yticks(range(len(vthr_labels)), [f"{label_to_voltage(label, 'vthr'):g}" for label in vthr_labels])
    fig.colorbar(image, ax=ax, label=metric_label)

    if annotate:
        for y_index, row in enumerate(matrix):
            for x_index, value in enumerate(row):
                if math.isnan(value):
                    continue
                ax.text(x_index, y_index, f"{value:g}", ha="center", va="center", fontsize=8)
    return fig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot a Vtau/Vthr heatmap from ratio-fit threshold CSV output.")
    parser.add_argument("--threshold-csv", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--metric", choices=("crossing-us", "tau-us"), default="crossing-us")
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--vmin", type=float, default=None)
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--debug", action="store_true")
    add_image_output_args(parser)
    args = parser.parse_args(argv)

    try:
        rows = load_threshold_rows(args.threshold_csv)
        fig = plot_heatmap(rows, args.metric, args.cmap, args.vmin, args.vmax, args.annotate)
        if args.save_images:
            repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root()
            output_dir = resolve_output_dir(repo_root, args.output_dir, "dual_bias_sweeps", "vtau_vthr_sweep")
            save_figure(fig, output_dir, f"ratio_fit_threshold_heatmap_{args.metric}", args.image_format, args.dpi)
        if not args.no_show:
            import matplotlib.pyplot as plt

            plt.show()
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
