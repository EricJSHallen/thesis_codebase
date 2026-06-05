# Phase-Shift OCEAN Runbook

This document describes the direct Cadence Virtuoso/OCEAN flow for the phase-shift sweep experiment.

The experiment uses one fixed `st_1` spike and sweeps the absolute delay of the `st_2` spike. This is not a frequency sweep and does not use Poisson spike generation.

## Directory Layout

Expected experiment layout:

```text
experiments/phaseshift_sweep/
  input_data/
    spike_phase_sweep.py
    single_spike_phase_sweep_output/
      st_1/base.pwl
      st_2/<phase_shift>_phase_shift/base.pwl
    single_spike_phase_sweep_output_csv/
      st_1/base.csv
      st_2/<phase_shift>_phase_shift/base.csv
  ocn_scripts/
    pwl_1syn_phase_shift.ocn
    pwl_2syn_phase_shift.ocn
  analysis/
  processing/
  formatting/
  bin/
  scripts/
```

The generated simulation output is written under the repository-level `database/` directory.

## Input Data Convention

Input PWL files are whitespace-separated files with two columns:

```text
time_s voltage_v
```

The CSV files contain the same waveform points and are mainly for inspection or downstream analysis.

Current generated input convention:

- `st_1/base.pwl` is the fixed reference spike and is reused for every case.
- `st_2/<phase_shift>_phase_shift/base.pwl` is the shifted second spike for one case.
- Phase-shift directory names encode the absolute shift, for example `1e-7_phase_shift`.
- The generated sweep runs from `1.0e-7 s` to `1.0e-5 s` in `1.0e-7 s` steps.
- The generated input duration is `2.0e-5 s`.

## Generating Input Data

Run on the server from the input-data directory:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase/experiments/phaseshift_sweep/input_data
python3 spike_phase_sweep.py
```

The generator currently has:

```python
total_time = 2.0e-5
base_spike_start_time = 1.0e-6
phase_shift_start = 1.0e-7
phase_shift_stop = 1.0e-5
phase_shift_step = 1.0e-7
overwrite_output_directory = True
base_filename_stem = "base"
```

Because `overwrite_output_directory = True`, rerunning the generator deletes and recreates `single_spike_phase_sweep_output/` and `single_spike_phase_sweep_output_csv/`.

## OCEAN Script Convention

There are two OCEAN scripts. They intentionally use identical input data and identical phase-shift traversal. They differ only where the circuit topology and exported signals require it.

### `pwl_1syn_phase_shift.ocn`

- Circuit cell: `synapsedualinputtb`
- Virtuoso design call: `design("sebastian_thesis_pilot" "synapsedualinputtb" "schematic")`
- Output base directory: `database/phase_shift_1syn_ocean_output`
- Exported columns: `iout_56 vpre vpre1`

### `pwl_2syn_phase_shift.ocn`

- Circuit cell: `dynapsetb1`
- Virtuoso design call: `design("sebastian_thesis_pilot" "dynapsetb1" "schematic")`
- Output base directory: `database/phase_shift_2syn_ocean_output`
- Exported columns: `iout_172 iout_56 vpre vpre1`

Both scripts use the BICS/server repository path:

```skill
baseRepoDir = "/home/s5117909/Documents/thesis/thesis_codebase"
```

This path is intentional. These scripts are meant to run on the server where Cadence Virtuoso and the XP018 design kit are available, not on local development machines.

## Cadence CIW Usage

Load the scripts directly from the Cadence CIW on the server:

```skill
Load("/home/s5117909/Documents/thesis/thesis_codebase/experiments/phaseshift_sweep/ocn_scripts/pwl_1syn_phase_shift.ocn")
```

or:

```skill
Load("/home/s5117909/Documents/thesis/thesis_codebase/experiments/phaseshift_sweep/ocn_scripts/pwl_2syn_phase_shift.ocn")
```

If no job-splitting environment variables are set, `Load(...)` runs a single sequential job.

## Parallel Job Convention

The OCEAN scripts optionally support round-robin splitting through environment variables:

- `CAD_NUM_JOBS`: total number of OCEAN jobs.
- `CAD_JOB_INDEX`: zero-based index of the current job.

Defaults:

- If `CAD_NUM_JOBS` is absent, the script uses `1`.
- If `CAD_JOB_INDEX` is absent, the script uses `0`.

Example shell launch from an OCEAN-capable server shell:

```bash
CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 ocean -nograph -restore pwl_1syn_phase_shift.ocn
CAD_NUM_JOBS=4 CAD_JOB_INDEX=1 ocean -nograph -restore pwl_1syn_phase_shift.ocn
CAD_NUM_JOBS=4 CAD_JOB_INDEX=2 ocean -nograph -restore pwl_1syn_phase_shift.ocn
CAD_NUM_JOBS=4 CAD_JOB_INDEX=3 ocean -nograph -restore pwl_1syn_phase_shift.ocn
```

When `CAD_NUM_JOBS=4`, all four job indices `0`, `1`, `2`, and `3` must be launched to cover the full case list.

## Output Convention

Each phase-shift case gets its own output directory:

```text
database/phase_shift_1syn_ocean_output/<phase_shift>_phase_shift/output_signals.txt
database/phase_shift_2syn_ocean_output/<phase_shift>_phase_shift/output_signals.txt
```

Each job also writes a manifest:

```text
run_manifest_job_<jobIndex>_of_<numJobs>.csv
```

Manifest columns:

```text
run_name,phase_shift,st1_file,st2_file,run_dir
```

## Resume Behavior

If a case already has `output_signals.txt`, the OCEAN script skips that case.

For a newly run case, waveform output is first written to:

```text
output_signals.txt.tmp
```

After `ocnPrint(...)` completes, the temporary file is moved to:

```text
output_signals.txt
```

This reduces the chance that an interrupted export leaves a partial file that later resume runs treat as complete.

## Simulation Time Convention

The OCEAN scripts currently use:

```skill
analysis('tran ?stop "2.0e-5s")
```

This must match the generated PWL duration in `spike_phase_sweep.py`:

```python
total_time = 2.0e-5
```

If `total_time` changes, update the transient stop time in both OCEAN scripts.

## Maintenance Rules

- If `total_time` changes in `spike_phase_sweep.py`, update `analysis('tran ?stop ...)` in both `.ocn` scripts.
- If `base_filename_stem` changes from `base`, update both OCEAN scripts to look for the new PWL filename.
- If `single_spike_phase_sweep_output/` is renamed or moved, update `pwlBaseDir` in both OCEAN scripts.
- If Virtuoso signal names change, update `save(...)`, waveform reads such as `i("/I56/Iout")`, and `ocnPrint(...)`.
- Keep the 1-synapse and 2-synapse OCEAN scripts identical except for the header, `design(...)`, `outputBaseDir`, and the extra I172 save/read/export lines.
- Keep `/home/s5117909/...` paths in OCEAN scripts unless the server checkout path changes.

## Verification Checklist

Before exporting to the server or running in Cadence, check:

- `single_spike_phase_sweep_output/st_1/base.pwl` exists.
- Every `single_spike_phase_sweep_output/st_2/*_phase_shift/` directory contains `base.pwl`.
- Both OCEAN scripts use `/home/s5117909/Documents/thesis/thesis_codebase`.
- Both OCEAN scripts use `single_spike_phase_sweep_output`.
- Both OCEAN scripts use `analysis('tran ?stop "2.0e-5s")`.
- The CIW `Load(...)` path matches the server checkout path.
- `pwl_1syn_phase_shift.ocn` exports `iout_56 vpre vpre1`.
- `pwl_2syn_phase_shift.ocn` exports `iout_172 iout_56 vpre vpre1`.
