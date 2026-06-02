# Plain Spectre frequency sweep reorg v12

v12 is based on the working current-output flow, but **completely removes `strobeperiod`**.

It keeps:

- ideal 0 V `VSENSE_I56` current probe, not a 1 ohm resistor
- `saveOptions options save=allpub currents=all`
- robust OCEAN export with long timeout and stdin isolation
- output current plus `vpre` and `vpre1`

It deliberately does **not** add `strobeperiod` to the `tran` analysis. During `./import_template.sh`, any previously injected `strobeperiod=...` token is stripped from the imported template as a guard.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v12.tar.gz

chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v12.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## Run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v12.sh prep

cd database/<new_run_id>

./import_template.sh

grep -n "VSENSE_I56\|currents=all" netlist_template/raw/input.scs
! grep -R "strobeperiod" netlist_template/raw

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime

./run_all_workers.sh
./monitoring_commands.sh progress
```

Because strobe output is removed, OCEAN export may be slow and output files may be large. This is expected.
