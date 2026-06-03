# Plain Spectre frequency sweep reorg v12 — 2syn_2tail patch4

This bundle prepares a fresh frequency-sweep run for the `dynapsetb1` two-synapse / two-tail circuit and exports four columns:

```text
iout_172 iout_56 vpre vpre1
```

It keeps the v12 plain-Spectre structure and updates only the runtime/export handling needed for the two-current, two-voltage flow.

## Install

From the repository root:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
tar -xzf plain_spectre_frequency_sweep_reorg_v12_2syn_2tail_patch4.tar.gz
```

## Start a new run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase

NUM_JOBS=4 RUN_LABEL=2syn_2tail_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v12_2syn_2tail.sh prep
```

Then use the newly created run directory printed by the prep command:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase/database/<new_run_id>
./import_template.sh
./refresh_spectre_runtime.sh
./run_all_workers.sh
```

## What patch4 changes

1. `refresh_spectre_runtime.sh` no longer aborts the setup merely because the standalone `ocean` command is absent. It still checks Spectre and reports whether an export runner can be found.
2. `setup_spectre_env.sh` detects export runners in both direct non-interactive shells and BICS-style login/interactive shells. It checks, in order:
   - direct `ocean`
   - direct `virtuoso`
   - login-shell `ocean`
   - login-shell `virtuoso`
   - login-shell `v` alias
3. `run_export_case.sh` uses the detected mode. If only the BICS `v => virtuoso` alias exists, export is launched through:

```bash
bash -lic 'v -nograph -restore "$OCEAN_RESTORE_ARG"'
```

4. The simulation output remains full adaptive-output data; no `strobeperiod` is inserted.

## Optional manual override

If Cadence is installed under a non-standard wrapper on the machine, set one of these before `./run_all_workers.sh`:

```bash
export OCEAN_CMD=/full/path/to/ocean
```

or:

```bash
export OCEAN_CMD=/full/path/to/virtuoso
export OCEAN_RUNNER_MODE=direct_virtuoso
```
