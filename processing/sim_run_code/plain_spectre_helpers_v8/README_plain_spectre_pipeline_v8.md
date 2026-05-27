# Plain Spectre Pipeline v8

This version makes the runtime setup more permanent by **copying real helper scripts** into each run directory instead of generating large helper scripts dynamically. This avoids the previously observed collapsed-newline problem in `setup_spectre_env.sh`, `refresh_spectre_runtime.sh`, and `run_all_workers.sh`.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

mkdir -p processing/sim_run_code/plain_spectre_helpers_v8

cp /mnt/data/setup_spectre_env_v8.sh \
  processing/sim_run_code/plain_spectre_helpers_v8/setup_spectre_env.sh
cp /mnt/data/refresh_spectre_runtime_v8.sh \
  processing/sim_run_code/plain_spectre_helpers_v8/refresh_spectre_runtime.sh
cp /mnt/data/run_spectre_worker_v8.sh \
  processing/sim_run_code/plain_spectre_helpers_v8/run_spectre_worker.sh
cp /mnt/data/run_all_workers_v8.sh \
  processing/sim_run_code/plain_spectre_helpers_v8/run_all_workers.sh
cp /mnt/data/spectre_sweep_plain_v8.sh \
  processing/sim_run_code/spectre_sweep_plain_v8.sh

chmod +x processing/sim_run_code/spectre_sweep_plain_v8.sh \
  processing/sim_run_code/plain_spectre_helpers_v8/*.sh
```

## Prepare a run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v8.sh prep
```

## Run stages

```bash
cd thesis_database/<new_run_id>
./run_template_ocean.sh
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
```

If `check_spectre_runtime` prints nothing, continue:

```bash
./run_all_workers.sh
./monitoring_commands.sh progress
```

If missing libraries remain, inspect:

```bash
cat logs/refresh_spectre_runtime.log
ldd "$SPECTRE_BIN" | grep 'not found'
```
