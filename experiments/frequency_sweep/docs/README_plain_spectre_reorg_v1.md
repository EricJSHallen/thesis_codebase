# Plain Spectre frequency sweep pipeline for `thesis_reorg`

This bundle is adapted for the reorganised repository layout:

- startup script: `experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v1.sh`
- helper scripts: `experiments/frequency_sweep/scripts/plain_spectre_helpers/`
- PWL inputs: `experiments/frequency_sweep/input_data/spike_train_output/`
- OCN scripts: `experiments/frequency_sweep/ocn_scripts/`
- run output: `database/<timestamp>_2channel_1syn_plain/`

The worker uses a single netlist template, patches PWL paths per case, runs plain Spectre, and exports PSF waveforms to `output_signals.txt`.

## Install

From the repository root:

```bash
git checkout thesis_reorg
tar -xzf plain_spectre_frequency_sweep_reorg_v1.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v1.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## Prepare a run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v1.sh prep
```

Then enter the new run directory printed by the script:

```bash
cd database/<new_run_id>
```

## Normal workflow

If the existing Cadence netlist at `/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist` is already fresh:

```bash
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

If the netlist is stale, regenerate it first:

```bash
./run_template_ocean.sh
```

If that says `ocean not found`, paste `ciw_template_command.il` into the Cadence CIW instead.

## Important checks

Before running workers, `./import_template.sh` must report:

```text
Template placeholders and parameters verified.
```

The parameter patch includes:

```spectre
m2w=3u m2l=200n ... Vw=0.5 Vthr=0.9 Vtau=1.6 capacitance=6p
```

and keeps `__ST1_PWL__` / `__ST2_PWL__` placeholders for per-case substitution.
