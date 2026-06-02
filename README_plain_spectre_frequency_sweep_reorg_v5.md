# Plain Spectre frequency sweep reorg v5

v5 is based on the working v3/v4 plain-Spectre pipeline but fixes the current-export failure/hang observed in run `20260602_142809_2channel_1syn_plain`.

## What changed

1. `import_template.sh` now inserts an explicit 0 V current-sense source:

```spectre
VSENSE_I56 (i56_iout 0) vsource dc=0 type=dc
I56 (i56_iout Vdd Vin Vtau Vthr) dynapse1
save vpre vpre1 VSENSE_I56:p
saveOptions options save=allpub currents=all
```

This is more robust than trying to read a subcircuit-terminal current such as `/I56/Iout` directly.

2. `run_export_case.sh` now runs the OCEAN/Virtuoso exporter with stdin redirected from `/dev/null` and a timeout. This prevents OCEAN from accidentally consuming the worker TSV case list if the OCN exporter errors.

3. `export_psf_to_txt.ocn` tries several possible names for the sense-source branch current and writes `available_outputs.txt` in the case directory for debugging.

## Install

From the repository root:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v5.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v5.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## New clean run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v5.sh prep

cd database/<new_run_id>
./import_template.sh

grep -n "VSENSE_I56\|save vpre vpre1 VSENSE_I56:p\|currents=all" netlist_template/raw/input.scs

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime

./run_all_workers.sh
./monitoring_commands.sh progress
```

Do not reuse PSF files from v4. The current-sense source changes the circuit netlist, so Spectre must be rerun.
