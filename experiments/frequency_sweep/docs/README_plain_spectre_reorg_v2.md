# Plain Spectre frequency_sweep reorg v2

This bundle is for the `thesis_reorg` branch layout:

- startup script: `experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v2.sh`
- helpers: `experiments/frequency_sweep/scripts/plain_spectre_helpers/`
- OCEAN template script: `experiments/frequency_sweep/ocn_scripts/make_spectre_template_reorg_v2.ocn`
- spike input: `experiments/frequency_sweep/input_data/spike_train_output/`
- run database: `database/<run_id>/`

The OCEAN template script has reorg-aware defaults and also receives explicit `CAD_REPO_DIR`, `CAD_EXP_DIR`, `CAD_SPIKE_DIR`, `CAD_TEMPLATE_DIR`, and `CAD_PROJECT_DIR` from `run_template_ocean.sh`.

Run from repo root:

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain ./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v2.sh prep
cd database/<new_run_id>
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh && check_spectre_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

Only run `./run_template_ocean.sh` if you need to regenerate the Cadence netlist. If `ocean` is unavailable in the shell, paste `ciw_template_command.il` into the CIW.
