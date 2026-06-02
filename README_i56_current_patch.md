# I56 current output patch

This patch fixes missing I56 output current in the plain-Spectre frequency sweep output.

The previous netlist saved only voltages:

```spectre
save vpre vpre1
```

The export script tried to print `i("/I56/Iout")`, but that current is not present in PSF unless the netlist explicitly saves the subcircuit terminal current. The patch changes the generated run template to:

```spectre
save vpre vpre1 I56:Iout
```

and replaces the export OCN so `output_signals.txt` contains:

1. `i("/I56/Iout")`
2. `v("/vpre")`
3. `v("/vpre1")`

## Install in codebase

From repo root:

```bash
tar -xzf i56_current_output_patch_v1.tar.gz
chmod +x experiments/frequency_sweep/scripts/plain_spectre_helpers/patch_run_save_i56_current.sh
```

## Patch a prepared run

Run this after `./import_template.sh` and before `./run_all_workers.sh`:

```bash
cd database/<run_id>
cp /home/s5117909/Documents/thesis/thesis_codebase/experiments/frequency_sweep/scripts/plain_spectre_helpers/patch_run_save_i56_current.sh .
chmod +x patch_run_save_i56_current.sh
./patch_run_save_i56_current.sh
```

Then verify:

```bash
grep -o "save vpre vpre1 I56:Iout" netlist_template/raw/input.scs
```

If the run already produced PSF files before the patch, rerun Spectre because old PSFs probably do not contain the current:

```bash
find cases -mindepth 1 -maxdepth 2 \( -name psf -o -name output_signals.txt -o -name spectre.out \) -exec rm -rf {} +
./run_all_workers.sh
```
