# Plain Spectre frequency sweep reorg v6

v6 is based on the working v3/v4/v5 plain-Spectre pipeline, but replaces the v5 current-export mechanism.

## What v6 fixes

The v5 run could complete Spectre but then stall at OCEAN export. The likely cause was OCEAN branch-current lookup for `VSENSE_I56:p`. v6 avoids branch-current names entirely.

Instead, `import_template.sh` rewrites the netlist as:

```spectre
RSENSE_I56 (i56_iout 0) resistor r=1
I56 (i56_iout Vdd Vin Vtau Vthr) dynapse1
save vpre vpre1 i56_iout
```

Because `RSENSE_I56` is 1 ohm, `v(i56_iout)` is numerically equal to the output current in amperes. The exporter reads only voltages:

```skill
iout_56 = v("/i56_iout")
vpre    = v("/vpre")
vpre1   = v("/vpre1")
```

This is less semantically elegant than a perfect branch-current probe, but it is substantially more robust with your current OCEAN export environment.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v6.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v6.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## New clean run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v6.sh prep

cd database/<new_run_id>
./import_template.sh

grep -n "RSENSE_I56\|save vpre vpre1 i56_iout" netlist_template/raw/input.scs

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

Do not reuse PSF files from v5. v6 changes the circuit netlist and the saved waveform list.
