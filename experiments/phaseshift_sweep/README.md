# Phase-Shift Sweep Experiment

This experiment generates and runs a single-spike phase-shift sweep for Cadence Virtuoso/OCEAN.

The input convention is fixed `st_1/base.pwl` against shifted `st_2/<phase_shift>_phase_shift/base.pwl` cases. The OCEAN scripts are intended to run on the BICS/server checkout at `/home/s5117909/Documents/thesis/thesis_codebase`.

Main documentation:

```text
experiments/phaseshift_sweep/docs/README_phase_shift_ocean.md
```

Primary scripts:

```text
input_data/spike_phase_sweep.py
ocn_scripts/pwl_1syn_phase_shift.ocn
ocn_scripts/pwl_2syn_phase_shift.ocn
```

CIW entrypoints on the server:

```skill
Load("/home/s5117909/Documents/thesis/thesis_codebase/experiments/phaseshift_sweep/ocn_scripts/pwl_1syn_phase_shift.ocn")
Load("/home/s5117909/Documents/thesis/thesis_codebase/experiments/phaseshift_sweep/ocn_scripts/pwl_2syn_phase_shift.ocn")
```
