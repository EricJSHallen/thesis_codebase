# Plain Spectre frequency sweep reorg v8

v8 is an alternative to v6 that does **not** use a 1-ohm sense resistor.
Instead it inserts an ideal zero-volt voltage source as a current probe:

```spectre
VSENSE_I56 (i56_iout 0) vsource dc=0 type=dc
I56 (i56_iout Vdd Vin Vtau Vthr) dynapse1
saveOptions options save=allpub currents=all
save vpre vpre1 VSENSE_I56:p VSENSE_I56:n
```

This keeps the output node at ground through an ideal 0 V source, so it avoids the intentional 1-ohm shunt used in v6. The OCEAN exporter tries several possible branch-current names with `errset(...)` and the shell launcher still uses a timeout plus stdin redirection to avoid the earlier stall mode.

## Install

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg

tar -xzf plain_spectre_frequency_sweep_reorg_v8.tar.gz
chmod +x experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v8.sh
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/*.sh
```

## Clean run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v8.sh prep

cd database/<new_run_id>
./import_template.sh
grep -n "VSENSE_I56\|saveOptions.*currents=all" netlist_template/raw/input.scs

./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime

./run_all_workers.sh
./monitoring_commands.sh progress
```

Do not reuse PSF files from v6 or earlier, because the netlist current probe is different.


## v8 exporter fix

v8 fixes the OCEAN/SKILL export failure seen as:

```text
*Error* errset: too many arguments (at most 2 expected, 4 given)
ERROR: export launcher failed with rc=124
```

The exporter no longer wraps multiple statements inside one `errset(...)`; each waveform lookup is isolated as a single `errset(<one expression> nil)`. It also writes `current_probe_export_diagnostics.txt` into each case directory so that the successful current-signal name can be inspected.

If a previous v5/v6/v7 run already has PSF directories generated with `VSENSE_I56`, you can copy in the v8 export scripts and run `./extract_missing_outputs.sh` instead of rerunning Spectre.
