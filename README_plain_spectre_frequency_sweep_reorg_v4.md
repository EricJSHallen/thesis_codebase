# Plain Spectre frequency sweep reorg v4

This bundle is based on the working reorg v3 flow, with one substantive change: the imported Spectre template is patched to save terminal currents by forcing:

```spectre
saveOptions options save=allpub currents=all
```

This is intentionally broader than `save I56:Iout`, because `currents=all` is the robust way to make subcircuit terminal currents available for OCEAN `i("/I56/Iout")` during PSF export.

The export OCN prints:

```skill
iout_56 = i("/I56/Iout")
vpre    = v("/vpre")
vpre1   = v("/vpre1")
ocnPrint(... iout_56 vpre vpre1)
```

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v4.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v4.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## Run clean

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v4.sh prep

cd database/<new_run_id>
./import_template.sh

# Confirm current saving is present:
grep -n "saveOptions.*currents=all" netlist_template/raw/input.scs

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

Do not use PSF files generated before `currents=all` was added; they probably do not contain the current data. Start a clean run or delete existing case PSF/output files and rerun workers.
