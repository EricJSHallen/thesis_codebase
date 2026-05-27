# Plain-Spectre Parallel Sweep Pipeline v1

This replaces the unstable parallel-OCEAN approach with a safer three-stage workflow:

1. Run **one** OCEAN/Virtuoso process to create a clean Spectre netlist template.
2. Copy that text netlist into independent case folders and run **plain Spectre** in parallel.
3. Export each finished PSF result to `output_signals.txt` with a small OCEAN script that does not call `design()`.

This avoids multiple OCEAN/Virtuoso processes opening the same OA schematic cellview at the same time.

## Install

From the local repo root:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

cp /mnt/data/spectre_sweep_plain_v1.sh \
  processing/sim_run_code/spectre_sweep_plain_v1.sh

cp /mnt/data/make_spectre_template_v1.ocn \
  processing/sim_run_code/ocn_scripts/make_spectre_template_v1.ocn

cp /mnt/data/export_psf_to_txt_v1.ocn \
  processing/sim_run_code/ocn_scripts/export_psf_to_txt_v1.ocn

chmod +x processing/sim_run_code/spectre_sweep_plain_v1.sh
```

## Create a run

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v1.sh prep
```

The script prints a new run directory, for example:

```text
/home/s5117909/Documents/thesis/thesis_codebase/thesis_database/20260526_210000_2channel_1syn_plain
```

Enter it:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase/thesis_database/<run_id>
```

## Stage 1: generate the template netlist

Run exactly one OCEAN process:

```bash
./run_template_ocean.sh
```

If you prefer launching this from CIW:

```bash
cat ciw_template_command.il
```

Paste the printed `ipcBeginProcess(...)` command into CIW.

## Stage 2: import the generated netlist

After `./run_template_ocean.sh` finishes successfully:

```bash
./import_template.sh
```

Check that placeholders exist:

```bash
grep -RniE '__ST1_PWL__|__ST2_PWL__|pwlFile|ade_e' netlist_template/raw | head -80
```

At least the PWL paths or `pwlFile_st1` / `pwlFile_st2` parameter assignments should be visible.

## Stage 3: run parallel plain-Spectre workers

```bash
./run_all_workers.sh
```

This starts `NUM_JOBS` shell workers. Each worker runs cases where:

```text
case_id % NUM_JOBS == JOB_INDEX
```

No worker should open the schematic OA database. They only run `spectre input.scs` from copied netlist folders.

## Monitor

```bash
./monitoring_commands.sh progress
```

Or one-shot summary:

```bash
./monitoring_commands.sh summary
```

Errors:

```bash
./monitoring_commands.sh errors
```

## Important files

```text
RUNINFO.txt                         run metadata
cases.csv                           all st1/st2/trial combinations
run_template_ocean.sh               one-time OCEAN/Virtuoso template generation
import_template.sh                  copies generated netlist into netlist_template/raw
run_spectre_worker.sh               one worker for plain Spectre cases
run_all_workers.sh                  launches all workers
monitoring_commands.sh              progress/error monitoring
ocn/make_spectre_template_v1.ocn    OCEAN script for template generation
ocn/export_psf_to_txt_v1.ocn        OCEAN script for PSF-to-text export only
netlist_template/raw/               reusable text netlist template
cases/<run_name>/                   each independent Spectre case
```

## Current caveats

The import script assumes the generated Spectre netlist contains either literal PWL paths under `st_1` / `st_2`, or parameter assignments such as `pwlFile_st1=...` and `pwlFile_st2=...`. If outputs fail, inspect:

```bash
grep -RniE 'pwl|st_1|st_2|trial|pwlFile|file=' netlist_template/raw | head -120
```

If needed, patch the substitution pattern in `run_spectre_worker.sh`.
