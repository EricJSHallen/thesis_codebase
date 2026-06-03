# Plain Spectre frequency sweep v12, 2syn_2tail, patch5

This archive is for a **new run only**. Do not apply it to continue a failed run.

## What this flow exports

Each completed case should export four columns:

```text
iout_172 iout_56 vpre vpre1
```

The generated netlist has no transient `strobeperiod` option, so Spectre exports the full adaptive transient output.

## Patch5 change

Patch5 keeps the patch4 behaviour but fixes the Cadence/OCEAN launcher detection for the RUG BICS environment where:

- `ocean`, `virtuoso`, and `v` may not exist as shell commands;
- `/projects/bics/NX/bin` is on `PATH`;
- the XP018 site launcher is normally `xp018v`.

The export runner search order is now:

1. `OCEAN_CMD`, if explicitly set;
2. direct `ocean`;
3. direct `virtuoso`;
4. direct `xp018v`;
5. login-shell `ocean`;
6. login-shell `virtuoso`;
7. login-shell `xp018v`;
8. login-shell `v` alias/function.

## Install from the repository root

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
tar -xzf plain_spectre_frequency_sweep_reorg_v12_2syn_2tail_patch5.tar.gz
```

## Start a new run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
NUM_JOBS=4 RUN_LABEL=2syn_2tail_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v12_2syn_2tail.sh prep
```

Then use the newly printed run directory:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase/database/<new_run_id>
./import_template.sh
./refresh_spectre_runtime.sh
```

If `refresh_spectre_runtime.sh` reports an export runner such as `direct_xp018v`, then run:

```bash
./run_all_workers.sh
```

If no export runner is found, do not start workers. Run:

```bash
ls -l /projects/bics/NX/bin | grep -E 'xp018|ocean|virtuoso|^v$'
type -a xp018v
```

and set `OCEAN_CMD` manually if needed, for example:

```bash
export OCEAN_CMD=/projects/bics/NX/bin/xp018v
```


## Patch6 note

Patch6 fixes the immediate export failure seen in `20260603_190010_2syn_2tail_plain`.
The failed run selected `xp018v` through `command -v`, but on BICS this can expand to
alias text such as `alias xp018v='xp018 ; xkit&'`. That alias string is not an
executable and cannot be passed to `timeout`, so all workers retried OCEAN export
immediately.

Patch6 only accepts true executable paths for direct commands. For the BICS XP018
alias case it runs an interactive login shell, executes `xp018`, and then launches
`xkit -nograph -restore ...` for the OCEAN export. Use this archive only for a new
run.


## Patch7 notes

Patch7 is for fresh runs only. It fixes two setup/export-launcher issues found on the BICS NX environment:

1. `setup_spectre_env.sh` is now safe to source in an interactive shell. It does not enable `errexit`, so a failed/export-runner check will not close a tmux pane.
2. The export launcher no longer uses `xp018v`. On this system `xp018v` can expand to `xp018 ; xkit&`, which is an alias/background-GUI form, not a safe non-graphical executable. Workers now use an `auto_bics` launcher that runs `xp018` inside a login shell and then tries `ocean`, `virtuoso`, `xkit`, and `v` with `-nograph -restore`.

Use only a new run directory created after installing this archive.
