# Plain Spectre pipeline v9

v9 changes the Spectre launch model: it prefers the **site Spectre wrapper** (`.../SPECTRE231/tools/bin/spectre`, `.../bin/spectre`, or `.../tools.lnx86/bin/spectre`) instead of the raw ELF binary at `tools.lnx86/spectre/bin/64bit/spectre`.

That matters because the raw binary can show many missing libraries (`libSpectreEH_sh.so`, `libfmc.so`, `libvisadev.so`, etc.) unless the Cadence runtime environment has already been loaded. The wrapper normally supplies that environment.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
mkdir -p processing/sim_run_code/plain_spectre_helpers_v9

cp /mnt/data/setup_spectre_env_v9.sh processing/sim_run_code/plain_spectre_helpers_v9/setup_spectre_env.sh
cp /mnt/data/refresh_spectre_runtime_v9.sh processing/sim_run_code/plain_spectre_helpers_v9/refresh_spectre_runtime.sh
cp /mnt/data/run_spectre_worker_v9.sh processing/sim_run_code/plain_spectre_helpers_v9/run_spectre_worker.sh
cp /mnt/data/run_all_workers_v9.sh processing/sim_run_code/plain_spectre_helpers_v9/run_all_workers.sh
cp /mnt/data/spectre_sweep_plain_v9.sh processing/sim_run_code/spectre_sweep_plain_v9.sh

chmod +x processing/sim_run_code/spectre_sweep_plain_v9.sh
chmod +x processing/sim_run_code/plain_spectre_helpers_v9/*.sh
```

## Run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain ./processing/sim_run_code/spectre_sweep_plain_v9.sh prep
cd thesis_database/<new_run_id>
./run_template_ocean.sh
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

`check_spectre_runtime` should report a wrapper/script launcher and should not show a long list of missing libraries. If it falls back to the raw ELF binary and still shows missing libraries, find the wrapper with:

```bash
find /projects/bics/cadence/installs/SPECTRE231 -path '*/bin/spectre' -type f -print -exec file {} \;
```

Then run prep with:

```bash
SPECTRE_CMD=/path/to/wrapper/spectre NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain ./processing/sim_run_code/spectre_sweep_plain_v9.sh prep
```
