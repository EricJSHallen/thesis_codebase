# Cadence Virtuoso / OCEAN Parallel IPC Runbook v3

This runbook describes the working procedure for launching multiple Cadence OCEAN simulations from the CIW using `ipcBeginProcess(...)`. It is written from the final working debug path, not from the earlier failed attempts.

The goal is to split a parameter sweep across multiple independent batch OCEAN processes. Each process gets its own `CAD_JOB_INDEX`, and the OCEAN script only runs the cases assigned to that index.

---

## 1. Final working idea

A normal CIW command such as:

```lisp
load("/path/to/script.ocn")
```

runs inside the active CIW/Virtuoso process and blocks the CIW until completion.

Instead, use:

```lisp
ipcBeginProcess("sh -c 'cd /some/job/dir && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /path/to/script.ocn > /path/to/job0.log 2>&1'")
```

This starts an external OCEAN process while leaving CIW usable. Running four such commands with `CAD_JOB_INDEX=0,1,2,3` launches four parallel workers.

---

## 2. Files and directories used in the working setup

Current paths used during debugging:

```text
OCEAN script:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn

Output directory:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data

IPC working directories:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job1
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job2
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job3

Logs:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job0.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job1.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job2.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log
```

For future projects, change these paths systematically rather than editing commands piecemeal.

---

## 3. Required `cds.lib` setup for each IPC job directory

Each external OCEAN process needs a local `cds.lib` so it can find the design library and PDK libraries. The working `cds.lib` template was:

```text
INCLUDE /home/s5117909/eda_env/xp018/cds.lib
DEFINE sebastian_thesis_pilot /home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
DEFINE XFABLibs /projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
```

Create/copy this into every job directory:

```bash
for i in 0 1 2 3
 do
    mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i
    cp /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib \
       /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib
 done
```

For a new design, find the design library path in CIW:

```lisp
ddGetObj("YOUR_LIBRARY_NAME")~>readPath
```

Then update the `DEFINE YOUR_LIBRARY_NAME /path/to/library` line in `cds.lib`.

---

## 4. Required model-library setup inside the OCEAN script

The final fix was to copy the working ADE model library list and apply it correctly in OCEAN.

Important: `modelFile(...)` must receive each model-file entry as a separate argument. If you build a list of model-file entries, expand it with:

```lisp
apply('modelFile modelFileList)
```

Do **not** pass the list directly as `modelFile(modelFileList)`.

Working block:

```lisp
; Spectre model-library setup copied from ADE Model Libraries.

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

Notes:

- `xp018.scs` was **removed** from the final model list because including it caused duplicate model/subcircuit definitions.
- `xp018.lib`, `xp018_combine.lib`, and `pvtech.lib` are Cadence library-definition/setup files, not the correct Spectre model deck for this OCEAN setup.
- The old model-missing errors were `ne`, `pe`, and `cmm4` undefined. Those were solved by the model block above.

Also include this option after `simulator('spectre)`:

```lisp
option('redefinedparams "warning")
```

This prevents duplicated parameter definitions in the PDK stack from aborting the Spectre run.

---

## 5. Clean batch exit in the OCEAN script

At the end of the OCEAN script, include:

```lisp
batchExitStr = getShellEnvVar("CAD_BATCH_EXIT")

when(batchExitStr == "1"
    printf("CAD_BATCH_EXIT=1, exiting OCEAN.\n")
    exit()
)
```

Then launch standalone jobs with:

```bash
CAD_BATCH_EXIT=1
```

This prevents `ocean -nograph` processes from lingering after the script completes.

Do not set `CAD_BATCH_EXIT=1` if loading the script manually in CIW with `load(...)`.

---

## 6. Clearing stale processes before running

Before launching a new batch, inspect old OCEAN/Spectre processes:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|tail -f ocean|pwl_apply|ocean_apply_job" | grep -v grep
```

Kill only stale batch jobs, not the main Virtuoso GUI/session infrastructure.

Safe targets to kill:

```text
ocean -nograph -restore ...
sh -c ... ocean -nograph ...
spectre ...
spectre_encrypt ...
tail -f ocean_*.log
```

Avoid killing unless you intend to close/restart Cadence:

```text
virtuoso
libManager
libSelect
cdsMsgServer
cdsServIpc
```

Example cleanup:

```bash
kill <PID1> <PID2> <PID3>
```

If a stale process does not terminate after a few seconds:

```bash
kill -9 <PID>
```

Check again:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|tail -f ocean|pwl_apply|ocean_apply_job" | grep -v grep
```

If this returns nothing relevant, the batch environment is clean.

---

## 7. One-case validation before a large run

Before running 4 workers, test one case only. With 64 total cases, use:

```text
CAD_NUM_JOBS=64
CAD_JOB_INDEX=0
```

CIW command:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=64 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log 2>&1'")
```

Check for errors:

```bash
grep -iE "SFE-|ERROR|FATAL|spectre completes|Finished assigned|CAD_BATCH_EXIT" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log
```

Check output count:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

Success signs:

```text
spectre completes with 0 errors
Finished assigned simulations for job 0 of 64.
CAD_BATCH_EXIT=1, exiting OCEAN.
```

For the one-case test, the output count should increase by 1.

---

## 8. Four-job parallel launch

After one-case validation succeeds, create/copy job directories and run:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job0.log 2>&1'")
```

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job1 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=1 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job1.log 2>&1'")
```

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job2 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=2 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job2.log 2>&1'")
```

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job3 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=3 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log 2>&1'")
```

More robust practice: launch job 0, wait 10-20 seconds, launch job 1, wait again, and so on. This reduces collisions during Cadence startup, encrypted model handling, and netlist file creation.

---

## 9. Monitoring live logs

Watch all logs:

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Watch a single job:

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log
```

Stop watching with:

```text
Ctrl+C
```

This stops the log viewer, not the simulation.

---

## 10. Final success checks

Check that all jobs ended:

```bash
grep -H "Finished assigned simulations" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Expected:

```text
Finished assigned simulations for job 0 of 4.
Finished assigned simulations for job 1 of 4.
Finished assigned simulations for job 2 of 4.
Finished assigned simulations for job 3 of 4.
```

Check Spectre outcomes:

```bash
grep -H "spectre completes with" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Count exported outputs:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

For a 64-case sweep, expected ideal output:

```text
64
```

In the test run, 63/64 were produced. The missing case was caused by a transient failure to open `ade_e.scs`, likely due to shared netlist file access during parallel execution.

---

## 11. Diagnosing missing outputs

Find run directories missing `output_signals.txt`:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -mindepth 1 -maxdepth 1 -type d | while read d
 do
    if [ ! -f "$d/output_signals.txt" ]; then
        echo "MISSING: $d"
    fi
 done
```

Find failed Spectre runs:

```bash
grep -n -A12 -B12 "spectre completes with 1 error" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Search for serious errors:

```bash
grep -iE "SFE-|ERROR|FATAL|Cannot open|undefined model|license|checkout|denied|waiting|queue" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

---

## 12. Common failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ipcBeginProcess(...)` returns `ipc:N` | Process launched successfully | Normal |
| `system(...)` returns `0` only | CIW reports shell exit status, not stdout | Redirect output to log files |
| `ocean: command not found` | OCEAN not in spawned process PATH | Use full OCEAN path or launch from Cadence environment |
| `restore cannot access file for reading` | Wrong `.ocn` path | Use exact absolute path |
| `ADE-5726 Unable to open config` | Standalone process cannot find design library | Add proper `cds.lib` in job directory |
| `SFE-23 undefined ne/pe/cmm4` | Missing Spectre model files | Add ADE Model Libraries via `apply('modelFile modelFileList)` |
| Model files not appearing in `input.scs` | Wrong `modelFile(...)` call shape | Use `apply('modelFile modelFileList)` |
| `SFE-59 redefinedparams` | Duplicate parameter definitions | Add `option('redefinedparams "warning")` |
| `SFE-3` or `SFE-396` duplicate subckt/model | Included too many model files | Remove `xp018.scs` from model list |
| `Cannot open ade_e.scs` in one case | Parallel netlist race / shared netlist dir | Rerun missing case, stagger launches, consider separate netlist dirs |
| Job stuck near `spectre_encrypt` | Hung helper/encrypted model process | Kill stale job and relaunch only that job |
| `CDS.log already locked` warnings | Several Cadence jobs share user-level logs | Usually tolerable; use separate job dirs and clean stale processes |

---

## 13. Generalizing to future larger sweeps

For a new run:

1. Copy the working OCEAN script and rename it.
2. Update the sweep variables and output directory in the script.
3. Confirm the design library path with `ddGetObj("library")~>readPath`.
4. Create job directories and `cds.lib` files.
5. Run a one-case test using `CAD_NUM_JOBS=<total_cases>` and `CAD_JOB_INDEX=0`.
6. Check for `spectre completes with 0 errors` and one output file.
7. Clear stale processes.
8. Launch `N` jobs with `CAD_NUM_JOBS=N` and `CAD_JOB_INDEX=0..N-1`.
9. Stagger launches by 10-20 seconds.
10. Verify final output count and inspect missing cases.

For larger data sets, consider starting with `CAD_NUM_JOBS=2` before using 4 or more. The limiting factors may be licenses, memory, shared netlist files, or encrypted-model helper processes.

---

## 14. Minimal final checklist

Before launch:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|spectre_encrypt|tail -f ocean|pwl_apply|ocean_apply_job" | grep -v grep
```

One-case test:

```text
CAD_NUM_JOBS=total_cases
CAD_JOB_INDEX=0
```

Parallel run:

```text
CAD_NUM_JOBS=number_of_parallel_workers
CAD_JOB_INDEX=0..number_of_parallel_workers-1
```

After run:

```bash
grep -H "Finished assigned simulations" ocean_apply_job*.log
find output_single_data -name output_signals.txt | wc -l
```
