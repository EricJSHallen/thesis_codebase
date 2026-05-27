# Plain Spectre sweep pipeline v6

This version fixes a v5 false-positive sanity check: `run_spectre_worker.sh` is intentionally compact and may be about 55 lines. v5 incorrectly required at least 70 lines and aborted even when the generated file was structurally valid.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

cp /mnt/data/spectre_sweep_plain_v6.sh \
processing/sim_run_code/spectre_sweep_plain_v6.sh

chmod +x processing/sim_run_code/spectre_sweep_plain_v6.sh
```

## Prepare

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v6.sh prep
```

## Run

```bash
cd thesis_database/<new_run_id>
./run_template_ocean.sh
./import_template.sh
./run_all_workers.sh
./monitoring_commands.sh progress
```

## Manual checks before `run_all_workers.sh`

```bash
wc -l run_all_workers.sh run_spectre_worker.sh setup_spectre_env.sh select_cases.py monitoring_commands.sh
source ./setup_spectre_env.sh
check_spectre_runtime
ldd "$SPECTRE_BIN" | grep 'not found' || echo "Spectre runtime libraries resolved"
```

`run_spectre_worker.sh` around 55 lines is acceptable.
