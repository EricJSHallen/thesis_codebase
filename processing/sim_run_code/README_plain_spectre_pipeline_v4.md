# Plain Spectre pipeline v4

This version fixes the v3 direct-Spectre runtime failure:

```text
libfmc.so: cannot open shared object file
```

The v3 setup only searched the SPECTRE231 tree. On the BIC/Cadence installation, direct Spectre also needs shared libraries from other Cadence installation trees, especially IC231. v4 searches `/projects/bics/cadence/installs` for the known missing libraries and prepends their directories to `LD_LIBRARY_PATH`.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
cp /mnt/data/spectre_sweep_plain_v4.sh processing/sim_run_code/spectre_sweep_plain_v4.sh
chmod +x processing/sim_run_code/spectre_sweep_plain_v4.sh
```

## Prepare

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain ./processing/sim_run_code/spectre_sweep_plain_v4.sh prep
```

## Run

```bash
cd thesis_database/<new_run_id>
./run_template_ocean.sh      # or paste ciw_template_command.il in CIW
./import_template.sh
./run_all_workers.sh
./monitoring_commands.sh progress
```

## Debug runtime libraries

Inside the run directory:

```bash
source ./setup_spectre_env.sh
check_spectre_runtime
ldd "$SPECTRE_BIN" | grep 'not found'
```

If libraries are still missing, locate them:

```bash
find /projects/bics/cadence/installs -name 'libfmc.so' -o -name 'libvisadev.so' -o -name 'libabv.so'
```
