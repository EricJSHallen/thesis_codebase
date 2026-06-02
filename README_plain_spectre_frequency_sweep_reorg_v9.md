# Plain Spectre frequency sweep reorg v9

v9 fixes the v6/v8 export-timeout failure observed in `20260602_145618_2channel_1syn_plain`.

The simulations were completing, but OCEAN export failed on higher-frequency cases because the PSF contained tens of thousands of adaptive transient points and `ocnPrint` exceeded the exporter timeout.

v9 changes the flow in two ways:

1. Adds `strobeperiod=500u` to the transient analysis during `./import_template.sh`, so saved PSF data is a regular, much smaller grid.
2. Raises the default export timeout from 45 s to 300 s.

v9 also uses the non-resistive ideal 0 V probe method:

```spectre
VSENSE_I56 (i56_iout 0) vsource dc=0 type=dc
I56 (i56_iout Vdd Vin Vtau Vthr) dynapse1
saveOptions options save=allpub currents=all
save vpre vpre1 VSENSE_I56:p VSENSE_I56:n
```

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v9.tar.gz

chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v9.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## Clean run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v9.sh prep

cd database/<new_run_id>

./import_template.sh

grep -n "strobeperiod\|VSENSE_I56\|saveOptions.*currents=all" netlist_template/raw/input.scs

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime

./run_all_workers.sh
./monitoring_commands.sh progress
```

You should not reuse PSFs from pre-v9 runs if you want the smaller, regular output grid. Rerun Spectre with the v9-imported template.
