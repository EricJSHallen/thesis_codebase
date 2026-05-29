# Cadence Virtuoso/OCEAN IPC Parallel Simulation — ChatGPT Handoff Runbook

This file is written for another ChatGPT/Clover instance, not primarily for a human. It records the working state, the important discoveries, and the exact reproducible recipe. The goal is to help continue or recreate the debug path without rediscovering every failure mode.

## 0. High-level objective

User wants to run a Cadence Virtuoso/OCEAN parameter sweep in parallel from CIW-only access. The working method is to launch multiple external `ocean -nograph -restore ...` processes from CIW using SKILL `ipcBeginProcess(...)`. Each external OCEAN process reads environment variables:

```bash
CAD_NUM_JOBS=<N>
CAD_JOB_INDEX=<0..N-1>
CAD_BATCH_EXIT=1
```

The `.ocn` script partitions the sweep so each process runs only cases where `caseIndex mod CAD_NUM_JOBS == CAD_JOB_INDEX` or equivalent logic already implemented in the script. Four jobs gives four workers, each processing roughly one quarter of the total cases.

The final validated small sweep produced `63/64` `output_signals.txt` files with four parallel jobs. One missing case was due to a transient shared-netlist race: Spectre could not open `ade_e.scs` for one run. The parallel mechanism itself works.

## 1. Environment and important paths

### User/repo paths

```text
User: s5117909
Repo base: /home/s5117909/Documents/thesis/sebastian_thesis_repo
OCEAN scripts: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code
Cadence extraction/log/output base: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction
Output data dir: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data
IPC working dirs: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 ... job3
Final working script name: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn
```

### Cadence design library mapping discovered from CIW

From CIW:

```lisp
ddGetObj("sebastian_thesis_pilot")~>readPath
```

returned:

```text
/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
```

From CIW:

```lisp
ddGetObj("XFABLibs")~>readPath
```

returned:

```text
/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
```

Note: this path sometimes emitted warnings saying it did not exist when in the job-local `cds.lib`. These warnings appeared non-fatal after the proper Spectre model libraries were included. If debugging library opening, verify the actual XFABLibs path in CIW again; prefer the CIW value over assumptions.

### Local XP018 environment

```text
/home/s5117909/eda_env/xp018/cds.lib
/home/s5117909/eda_env/xp018/xp018.lib
/home/s5117909/eda_env/xp018/xp018_combine.lib
/home/s5117909/eda_env/xp018/pvtech.lib
```

Important: `xp018.lib`, `xp018_combine.lib`, and `pvtech.lib` are NOT the final Spectre model deck for `modelFile(...)`. They are Cadence library-definition / mapping files. Do not pass them to Spectre modelFile as the main model solution.

## 2. IPC mechanism that worked

CIW `load("script.ocn")` blocks the interactive Virtuoso/CIW session. `ipcBeginProcess("...")` starts an external OS process and returns a handle like `ipc:13`, `ipc:20`, etc. That return value is not an error code; it is a process handle.

Initial working smoke test:

```lisp
ipcBeginProcess("date > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_test.log 2>&1")
```

Then check `/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_test.log`.

Batch OCEAN launch pattern:

```lisp
ipcBeginProcess("sh -c 'cd <job_work_dir> && env CAD_NUM_JOBS=<N> CAD_JOB_INDEX=<i> CAD_BATCH_EXIT=1 ocean -nograph -restore <ocn_script> > <log_file> 2>&1'")
```

Do not reuse one working directory/log for all jobs. Use separate `job0`, `job1`, `job2`, `job3` directories and separate logs.

## 3. Job-local `cds.lib` requirement

Standalone `ocean -nograph` initially failed with:

```text
ERROR (ADE-5726): Unable to open config (sebastian_thesis_pilot synapsedualinputtb schematic).
ERROR (ADE-575): Unable to Simulate, either session is invalid or design is not specified.
```

This was fixed by creating a local `cds.lib` in each IPC work directory.

Create `job0/cds.lib`:

```bash
mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0

cat > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib <<'EOF_CDSLIB'
INCLUDE /home/s5117909/eda_env/xp018/cds.lib
DEFINE sebastian_thesis_pilot /home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
DEFINE XFABLibs /projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
EOF_CDSLIB
```

Copy this to job1/job2/job3:

```bash
for i in 0 1 2 3
do
    mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i
    cp /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib \
       /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib
done
```

Check:

```bash
cat /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib
```

## 4. Final working OCEAN model-file setup

The decisive discovery: the ADE model libraries view gave the correct Spectre model files and sections. The paths must be from `xfab`, not `fab`. The files exist at:

```text
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs     section default
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs      section 3s
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs        section tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs        section tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs        section tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs        section tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs        section tm
```

ADE also showed:

```text
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/xp018.scs      section mc_g
```

But in the final working script, **do not include `xp018.scs`** because it created duplicate subcircuit/model definitions (`SFE-3`, `SFE-396`). Include only config/param/bip/cap/dio/mos/res.

Important OCEAN/SKILL subtlety: `modelFile(...)` must receive each model-file entry as a separate argument. A list-of-lists must be expanded with:

```lisp
apply('modelFile modelFileList)
```

Passing the list directly as `modelFile(modelFileList)` did not install the includes into the generated netlist. After using `apply`, `input.scs` correctly contained include lines for the model files.

Final model block to place after `simulator('spectre)` / `design(...)`, before `run()` calls:

```lisp
simulator('spectre)

; Critical: allow repeated parameter definitions from the XP018 model stack.
; This must appear in generated input.scs as redefinedparams=warning.
option('redefinedparams "warning")

design("sebastian_thesis_pilot" "synapsedualinputtb" "schematic")

; ADE model-library setup copied from working ADE Model Libraries window.
; Do NOT include xp018.scs here; it duplicates device/model definitions.

modelConfig = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs"
modelParam  = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs"
modelBip    = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs"
modelCap    = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs"
modelDio    = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs"
modelMos    = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs"
modelRes    = "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs"

foreach(modelPath list(modelConfig modelParam modelBip modelCap modelDio modelMos modelRes)
    unless(isFile(modelPath)
        error("Cannot find Spectre model file: %s\n" modelPath)
    )
)

printf("Using ADE Spectre model libraries from XP018 lp5mos via apply(modelFile ...).\n")

modelFileList = list(
    list(modelConfig "default")
    list(modelParam  "3s")
    list(modelBip    "tm")
    list(modelCap    "tm")
    list(modelDio    "tm")
    list(modelMos    "tm")
    list(modelRes    "tm")
)

apply('modelFile modelFileList)
```

At the end of the `.ocn` script, include guarded batch exit:

```lisp
batchExitStr = getShellEnvVar("CAD_BATCH_EXIT")

when(batchExitStr == "1"
    printf("CAD_BATCH_EXIT=1, exiting OCEAN.\n")
    exit()
)
```

Do not use unconditional `exit()` if the same script may be loaded interactively via CIW `load(...)`.

## 5. Historical failure modes and fixes

### Failure: `ocean` cannot restore script

```text
*WARNING* - restore </path/script.ocn> cannot access file for reading.
```

Cause: wrong script path or quoting issue. Fix exact absolute path.

### Failure: missing design/session

```text
ERROR (ADE-5726): Unable to open config (...)
ERROR (ADE-575): Unable to Simulate, either session is invalid or design is not specified.
```

Cause: external OCEAN process lacked library mapping. Fix job-local `cds.lib` as in section 3.

### Failure: missing `ne`, `pe`, `cmm4`

```text
ERROR (SFE-23): undefined model or subcircuit `ne'
ERROR (SFE-23): undefined model or subcircuit `pe'
ERROR (SFE-23): undefined model or subcircuit `cmm4'
```

Cause: Spectre model libraries not included. Fix using ADE model files and `apply('modelFile modelFileList)`. The old logs showed these missing models before model setup was fixed.

### Failure: including wrong files as model decks

Do not include these in `modelFile(...)`:

```text
/home/s5117909/eda_env/xp018/xp018_combine.lib
/home/s5117909/eda_env/xp018/xp018.lib
/home/s5117909/eda_env/xp018/pvtech.lib
```

They are Cadence library-definition/mapping files, not the final Spectre model deck. `xp018_combine.lib` caused syntax errors such as `SFE-874` because Spectre could not parse `ASSIGN`, `DEFINE`, etc.

### Failure: modelFile syntax silently not applied

Symptom: generated `input.scs` contains only:

```spectre
include "ade_e.scs"
```

and does not include the ADE model libraries.

Cause: `modelFile(modelFileList)` passed the list incorrectly.

Fix:

```lisp
apply('modelFile modelFileList)
```

Verify:

```bash
grep -nE "config.scs|param.scs|bip.scs|cap.scs|dio.scs|mos.scs|res.scs|include|library" \
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

Expected includes:

```spectre
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs" section=default
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs" section=3s
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs" section=tm
```

### Failure: `SFE-59` redefined parameters

Cause: repeated parameter definitions in model stack.

Fix:

```lisp
option('redefinedparams "warning")
```

Verify:

```bash
grep -n "redefinedparams" /home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

Expected:

```text
redefinedparams=warning
```

### Failure: `SFE-3`, `SFE-396` duplicate subcircuit/model definitions

Cause: included `xp018.scs` section `mc_g` in addition to individual `mos.scs`, `cap.scs`, `res.scs`, etc. Spectre saw duplicate definitions.

Fix: remove `xp018.scs` from `modelFileList`.

### Failure: one case missing due to `ade_e.scs` race

Observed final four-job run produced `63/64` output files. Missing case:

```text
st1_161_hz__st2_1_hz__trial_1
```

Error:

```text
ERROR (SFE-868): "input.scs" 7: Cannot open the input file 'ade_e.scs'
```

Likely cause: multiple OCEAN jobs share the same netlist dir:

```text
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist
```

One process regenerated/rewrote/locked `ade_e.scs` while another tried to read it. Mitigations: stagger launches by 10–20 seconds; if feasible later, configure separate simulator/netlist directories per worker. For test data this was accepted.

## 6. Clearing stale processes before running

Before launching jobs, check for stale batch Cadence processes. Do not kill the main Virtuoso GUI unless intentionally restarting Cadence.

List suspicious batch jobs:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|tail -f ocean|pwl_apply|ocean_apply_job" | grep -v grep
```

Kill only stale batch PIDs from the second column, e.g.:

```bash
kill <PID1> <PID2> <PID3>
```

Wait a few seconds, recheck:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|tail -f ocean|pwl_apply|ocean_apply_job" | grep -v grep
```

If stale process persists:

```bash
kill -9 <PID>
```

Safe to kill if stale:

```text
sh -c ... ocean -nograph -restore ...
ocean -nograph -restore ...
spectre ...
spectre_encrypt ...
tail -f ocean_apply_job*.log
```

Avoid killing unless intentionally restarting Cadence:

```text
virtuoso main GUI
libManager
libSelect
cdsMsgServer
cdsServIpc
```

If job3 or any job hangs around `spectre_encrypt`, it may be a stale/hung Cadence helper. In the debug session, killing and relaunching job3 made it progress.

## 7. One-case validation procedure

Before full parallel run, validate one assigned case.

CIW command:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=64 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log 2>&1'")
```

Check:

```bash
grep -iE "SFE-3|SFE-23|SFE-59|SFE-396|SFE-868|SFE-874|undefined model|ERROR|FATAL|spectre completes|Finished assigned|CAD_BATCH_EXIT" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log
```

Good output should contain:

```text
spectre completes with 0 errors, ...
Finished assigned simulations for job 0 of 64.
CAD_BATCH_EXIT=1, exiting OCEAN.
```

Check output count:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data -name output_signals.txt | wc -l
```

For a clean one-case test, count increases by 1.

## 8. Four-job launch procedure

First ensure `cds.lib` exists in all job directories as in section 3.

Recommended: launch jobs staggered by 10–20 seconds to reduce encrypted-model/netlist races.

CIW job0:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job0.log 2>&1'")
```

CIW job1:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job1 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=1 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job1.log 2>&1'")
```

CIW job2:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job2 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=2 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job2.log 2>&1'")
```

CIW job3:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job3 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=3 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log 2>&1'")
```

Monitor live:

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Stop tail view with `Ctrl+C`; that does not kill simulations.

## 9. Success and diagnostics commands

Completion summary:

```bash
grep -H "Finished assigned simulations" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Spectre completion summary:

```bash
grep -H "spectre completes with" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Output file count:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

Expected full sweep count: `64` for current test sweep. Observed validated run: `63` due to one transient `ade_e.scs` race.

Find missing output directories:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -mindepth 1 -maxdepth 1 -type d | while read d
do
    if [ ! -f "$d/output_signals.txt" ]; then
        echo "MISSING: $d"
    fi
done
```

Search serious errors:

```bash
grep -iE "SFE-|ERROR|FATAL|undefined model|Cannot open|license|checkout|denied|waiting|queue" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Check model includes in netlist:

```bash
grep -nE "config.scs|param.scs|bip.scs|cap.scs|dio.scs|mos.scs|res.scs|include|library" \
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

Check redefinedparams reached netlist:

```bash
grep -n "redefinedparams" /home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

Check active batch jobs:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|pwl_apply|ocean_apply_job" | grep -v grep
```

## 10. Notes for future scaling

1. The current setup parallelizes by launching multiple independent OCEAN processes, not by making one simulation use many cores.
2. Each OCEAN process may also make Spectre use multiple threads. Avoid oversubscription if larger simulations are CPU/memory heavy.
3. Four workers worked but caused one shared-netlist race. For large datasets, prefer staggered launch, fewer workers if unstable, or configure separate simulator/netlist directories per worker if possible.
4. Do not trust `Finished:` per case alone; the script may print it after `run()` even when Spectre failed. The robust output success criterion is presence of each run directory’s `output_signals.txt`.
5. `grep "Finished assigned simulations"` means the script loop finished; it does not guarantee all simulations succeeded.
6. If job stalls around `Loading ...` or `spectre_encrypt`, check stale processes and consider killing/relaunching only that job.
7. The word `license` in Cadence legal banner is not license denial. Look specifically for `checkout denied`, `waiting`, `queued`, etc.

## 11. Minimal final recipe

1. Ensure `/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn` has:
   - `option('redefinedparams "warning")`
   - ADE model files config/param/bip/cap/dio/mos/res using `/projects/bics/designkits/xfab/...`
   - `apply('modelFile modelFileList)`
   - no `xp018.scs` in `modelFileList`
   - guarded `CAD_BATCH_EXIT` block at end.
2. Ensure each `ipc_work/job$i/cds.lib` exists.
3. Clear stale batch processes.
4. Launch job0..job3 from CIW with separate dirs/logs and 10–20 s stagger.
5. Monitor `ocean_apply_job*.log`.
6. Validate with output count and missing-output scan.

