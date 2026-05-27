# Plain Spectre Pipeline v2

This version fixes the failure seen in `20260527_144343_2channel_1syn_plain`.

## What failed in v1

The workers found the Spectre binary, but the direct 64-bit binary could not load its shared libraries:

```text
spectre: error while loading shared libraries: libSpectreEH_sh.so: cannot open shared object file
```

The v1 worker also streamed `select_cases.py` into a shell `while` loop. When the worker exited early, Python wrote into a closed pipe and produced:

```text
BrokenPipeError: [Errno 32] Broken pipe
```

## What v2 changes

1. Generates `setup_spectre_env.sh` inside each run directory.
2. Autodetects `SPECTRE_BIN` and sets `LD_LIBRARY_PATH` to common Cadence/Spectre library directories.
3. Workers materialize their assigned cases into `worker_state/job_X_cases.tsv` before looping, eliminating the `BrokenPipeError` path.
4. Per-case failures use `continue` rather than `exit`, so one failed case does not kill the worker.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
cp /mnt/data/spectre_sweep_plain_v2.sh processing/sim_run_code/spectre_sweep_plain_v2.sh
chmod +x processing/sim_run_code/spectre_sweep_plain_v2.sh
```

## Run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain ./processing/sim_run_code/spectre_sweep_plain_v2.sh prep
cd thesis_database/<new_run_id>
./run_template_ocean.sh
./import_template.sh
./run_all_workers.sh
./monitoring_commands.sh progress
```

If Spectre still cannot be found, run with an explicit binary:

```bash
SPECTRE_BIN=/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre \
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v2.sh prep
```

Then use the same environment variable when launching workers:

```bash
SPECTRE_BIN=/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre ./run_all_workers.sh
```
