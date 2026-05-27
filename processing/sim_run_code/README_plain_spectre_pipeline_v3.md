# Plain Spectre pipeline v3

This version fixes the v2 failure where the Spectre binary was found but could not load `libSpectreEH_sh.so`.

## What changed

- `setup_spectre_env.sh` now determines the Spectre install root from `SPECTRE_BIN`.
- It prepends the usual Spectre/Cadence library directories to `LD_LIBRARY_PATH`.
- It also searches the Spectre install tree for `libSpectreEH_sh.so` and related Cadence shared libraries, then prepends the directories where they are actually found.
- Worker logs now include an `ldd` diagnostic block called `runtime_missing_libs:`.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

cp /mnt/data/spectre_sweep_plain_v3.sh \
processing/sim_run_code/spectre_sweep_plain_v3.sh

chmod +x processing/sim_run_code/spectre_sweep_plain_v3.sh
```

## Prepare a clean run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v3.sh prep
```

## Run stages

```bash
cd thesis_database/<new_run_id>

./run_template_ocean.sh
./import_template.sh
./run_all_workers.sh
./monitoring_commands.sh progress
```

## If Spectre still has missing libraries

Inspect:

```bash
grep -H -A20 "runtime_missing_libs" logs/spectre_worker_*.log
```

Then find the missing library manually:

```bash
find /projects/bics/cadence/installs/SPECTRE231 -name 'libSpectreEH_sh.so' -print
```

Add its directory explicitly before running workers:

```bash
export LD_LIBRARY_PATH=/path/to/dir/containing/libSpectreEH_sh.so:${LD_LIBRARY_PATH:-}
./run_all_workers.sh
```
