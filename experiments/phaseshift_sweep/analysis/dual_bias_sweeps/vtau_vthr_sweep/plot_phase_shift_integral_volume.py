#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import SweepConfig, main_integral_volume


CONFIG = SweepConfig(
    name="Vtau/Vthr",
    bias_a="vtau",
    bias_b="vthr",
    one_syn_subdir="phase_shift_1syn_vtau_vthr_v2",
    two_syn_subdir="phase_shift_2syn_vtau_vthr_v2",
)


if __name__ == "__main__":
    raise SystemExit(main_integral_volume(CONFIG))
