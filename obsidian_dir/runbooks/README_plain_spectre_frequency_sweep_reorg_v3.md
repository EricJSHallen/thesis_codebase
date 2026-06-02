# Plain Spectre frequency sweep reorg v3

This bundle targets the `thesis_reorg` branch layout:

```text
experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v3.sh
experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
experiments/frequency_sweep/ocn_scripts/export_psf_to_txt_reorg_v3.ocn
```

v3 fixes the failure observed in run `20260601_152416_2channel_1syn_plain`: Spectre completed, but PSF export failed with `export_rc=127` because the OCEAN/Virtuoso launcher could not load `libvsacpp.so`.

The fix is in `refresh_spectre_runtime.sh`: it resolves missing shared libraries for the IC/OCEAN export launcher, writes `support/cadence_ic_runtime.env`, and `setup_spectre_env.sh` loads that file before `run_export_case.sh` calls OCEAN.

## Install from repo root

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v3.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v3.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## New clean run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v3.sh prep

cd database/<new_run_id>
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

## Salvage a run where Spectre already completed but export failed

From the failed run directory:

```bash
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_export_runtime
./extract_missing_outputs.sh
find cases -name output_signals.txt | wc -l
```

Do not rerun Spectre just to recover `output_signals.txt`; use `extract_missing_outputs.sh` if PSF directories already exist.
