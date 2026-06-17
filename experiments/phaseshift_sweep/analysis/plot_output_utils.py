#!/usr/bin/env python3
"""Shared helpers for saving phase-shift analysis figures."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def default_output_images_dir(repo_root: Path) -> Path:
    return repo_root / "experiments" / "phaseshift_sweep" / "outputimages"


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "figure"


def add_image_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--save-images", action="store_true", help="Save generated figures under experiments/phaseshift_sweep/outputimages.")
    parser.add_argument("--no-show", action="store_true", help="Do not display Matplotlib windows. Intended for use with --save-images.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override image output directory.")
    parser.add_argument("--image-format", default="png", help="Image file format, e.g. png, pdf, svg.")
    parser.add_argument("--dpi", type=int, default=300, help="Saved image DPI.")


def resolve_output_dir(repo_root: Path, output_dir: Path | None, *parts: str) -> Path:
    root = output_dir.resolve() if output_dir is not None else default_output_images_dir(repo_root)
    return root.joinpath(*(safe_filename(part) for part in parts if part))


def save_figure(fig, output_dir: Path, filename_stem: str, image_format: str, dpi: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_format = image_format.lstrip(".")
    path = output_dir / f"{safe_filename(filename_stem)}.{image_format}"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    print(f"Saved image: {path}")
    return path
