# Cadence OCEAN IPC Parallel Simulation Debugging Runbook

This document summarizes the debugging path used to make a Cadence Virtuoso/OCEAN script run from the CIW through `ipcBeginProcess(...)`, with the eventual goal of launching multiple independent OCEAN jobs in parallel.

## 1. Goal

The original goal was to run a batch of independent transient simulations faster by splitting the sweep across several concurrent OCEAN/Spectre processes.

The intended final pattern is:

```text
CAD_NUM_JOBS=4
CAD_JOB_INDEX=0, 1, 2, 3
```

Each job runs a disjoint subset of the total sweep:

```text
job 0 -> cases 0, 4, 8, 12, ...
job 1 -> cases 1, 5, 9, 13, ...
job 2 -> cases 2, 6, 10, 14, ...
job 3 -> cases 3, 7, 11, 15, ...
```

For the 64-case test sweep, a four-job run should assign 16 cases per job.

## 2. Why `load(...)` was not sufficient

Running the script in the CIW with:

```lisp
load("/path/to/script.ocn")
```

works interactively, but it runs inside the current Virtuoso/CIW process. The CIW blocks until the script finishes, so it cannot launch several independent jobs at once.

To get parallelism, external background OCEAN processes need to be launched from CIW.

## 3. IPC mechanism used

The working mechanism was:

```lisp
ipcBeginProcess("shell command here")
```

`IPC` means **Inter-Process Communication**. In this context, it lets the current Virtuoso process start a separate operating-system process, such as:

```text
ocean -nograph -restore script.ocn
```

A successful test command returned something like:

```text
ipc:13
```

That is not an error. It is a Cadence IPC process handle.

## 4. Working IPC command shape

The basic working shape became:

```lisp
ipcBeginProcess("sh -c 'cd /some/working/directory && env CAD_NUM_JOBS=64 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /path/to/script.ocn > /path/to/log.log 2>&1'")
```

Important parts:

| Part | Purpose |
|---|---|
| `sh -c '...'` | Allows `cd`, environment variables, and redirection in one command |
| `cd /some/working/directory` | Ensures Cadence sees the correct `cds.lib` |
| `CAD_NUM_JOBS=64 CAD_JOB_INDEX=0` | Runs only one test case from a 64-case sweep |
| `CAD_BATCH_EXIT=1` | Allows OCEAN to exit cleanly after finishing |
| `> log.log 2>&1` | Sends stdout and stderr to a log file |

## 5. Stale session cleanup

Before launching new tests, stale `ocean -nograph`, `spectre`, or `tail -f ocean...` processes should be checked:

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|tail -f ocean" | grep -v grep
```

Kill stale batch jobs using the PID in the second column:

```bash
kill <PID>
```

If they do not stop:

```bash
kill -9 <PID>
```

Do **not** kill the main Virtuoso GUI infrastructure unless intentionally restarting Cadence. Avoid killing processes such as:

```text
virtuoso
libManager
libSelect
cdsMsgServer
cdsServIpc
```

## 6. `cds.lib` problem and fix

The external OCEAN process initially could not open the design:

```text
ERROR (ADE-5726): Unable to open config (...)
ERROR (ADE-575): Unable to Simulate, either session is invalid or design is not specified.
```

The reason was that the standalone IPC job did not know where the design library was.

Inside CIW, the design library path was found with:

```lisp
ddGetObj("sebastian_thesis_pilot")~>readPath
```

It returned:

```text
/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
```

The `XFABLibs` path was found with:

```lisp
ddGetObj("XFABLibs")~>readPath
```

A local `cds.lib` was then created in the IPC working directory:

```bash
mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0

cat > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib <<'CDSLIB'
INCLUDE /home/s5117909/eda_env/xp018/cds.lib
DEFINE sebastian_thesis_pilot /home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
DEFINE XFABLibs /projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
CDSLIB
```

This let the standalone OCEAN process find the schematic design.

Some warnings about missing `synopsys`, `ambit`, `std`, `ieee`, or `.oalib` files appeared, but these were not the final blocker for the analog Spectre run.

## 7. Incorrect model files tried

Several candidate model files were tried and rejected.

### `xp018_combine.lib`

This failed because it is not a Spectre model file. It contains Cadence library-manager syntax such as:

```text
ASSIGN
DEFINE
COMBINE
```

Spectre reported syntax errors such as:

```text
ERROR (SFE-874): syntax error `Unexpected end of line'
```

### `xp018.lib`

This also turned out to be a Cadence library-definition file, not a Spectre model deck. It contained mappings for `PRIMLIB`, `TECH_XP018`, `GATES`, etc.

### `pvtech.lib`

This file existed but was also not the correct device model deck. It did not resolve the missing `ne`, `pe`, or `cmm4` definitions.

### `ade_e.scs`

Including the generated `ade_e.scs` did not solve the missing model problem by itself.

## 8. Correct model library source

The correct model library list was found in the ADE Model Libraries GUI.

The relevant entries were:

| Model file | Section |
|---|---|
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs` | `default` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs` | `3s` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs` | `tm` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs` | `tm` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs` | `tm` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs` | `tm` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs` | `tm` |
| `/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/xp018.scs` | `mc_g` |

Important correction:

```text
Correct:   /projects/bics/designkits/xfab/...
Incorrect: /projects/bics/designkits/fab/...
```

## 9. `modelFile(...)` syntax problem and fix

A crucial issue was the OCEAN `modelFile(...)` call shape.

Passing a list-of-lists directly did not work properly. The model files did not appear in `input.scs`.

The working pattern was:

```lisp
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

After this, the generated `input.scs` correctly showed lines such as:

```spectre
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs" section=default
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs" section=3s
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs" section=tm
include "/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs" section=tm
```

## 10. Why `xp018.scs` was removed

Including `xp018.scs` together with the individual model files caused duplicate model and subcircuit definitions:

```text
ERROR (SFE-3): cannot create subcircuit definition `ne` because a subcircuit with the same name has already been defined
ERROR (SFE-396): Model `...` has already been defined
```

The fix was to remove this entry:

```lisp
list(modelXp018 "mc_g")
```

The final working model list used:

```text
config.scs
param.scs
bip.scs
cap.scs
dio.scs
mos.scs
res.scs
```

but **not** `xp018.scs`.

## 11. Redefined parameters fix

Once the model files were included correctly, Spectre reported repeated parameter definitions:

```text
ERROR (SFE-59): ... redefinedparams ...
```

The working fix was to add:

```lisp
option('redefinedparams "warning")
```

This made the generated netlist contain:

```spectre
redefinedparams=warning
```

and allowed Spectre to proceed without aborting on repeated parameter definitions.

## 12. Final successful one-case result

The one-case test was launched with:

```text
CAD_NUM_JOBS=64
CAD_JOB_INDEX=0
```

This intentionally runs only one case out of the 64-case sweep.

The successful output was:

```text
spectre completes with 0 errors, 13 warnings, and 15 notices.
Finished assigned simulations for job 0 of 64.
CAD_BATCH_EXIT=1, exiting OCEAN.
```

The output file count became:

```text
1
```

from:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

That confirmed that the standalone IPC-launched OCEAN flow worked for one assigned case.

## 13. Final one-case command

The successful test command shape was:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=64 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_apply.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log 2>&1'")
```

## 14. Checks used after each run

### Check for major Spectre/OCEAN errors

```bash
grep -iE "SFE-3|SFE-396|SFE-23|SFE-59|SFE-874|undefined model|ERROR|FATAL|spectre completes|Finished assigned|CAD_BATCH_EXIT" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_onecase.log
```

### Check generated model includes

```bash
grep -nE "config.scs|param.scs|bip.scs|cap.scs|dio.scs|mos.scs|res.scs|xp018.scs|include|library" \
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

### Check `redefinedparams`

```bash
grep -n "redefinedparams" \
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/input.scs
```

### Check exported waveform files

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

## 15. Next step: four parallel jobs

Now that one standalone case works, the next step is to create four working directories:

```text
ipc_work/job0
ipc_work/job1
ipc_work/job2
ipc_work/job3
```

Each should contain a suitable `cds.lib`.

Then launch four IPC jobs with:

```text
CAD_NUM_JOBS=4
CAD_JOB_INDEX=0
CAD_JOB_INDEX=1
CAD_JOB_INDEX=2
CAD_JOB_INDEX=3
```

The expected result for a 64-case sweep is:

```text
job 0 -> 16 cases
job 1 -> 16 cases
job 2 -> 16 cases
job 3 -> 16 cases
```

Total expected output count:

```text
64 output_signals.txt files
```

## 16. Final conceptual summary

The major lesson is that parallelism was not the hard part. The hard part was making a standalone `ocean -nograph` process reproduce the same environment that the interactive ADE/CIW session already had.

The final working ingredients were:

```text
IPC launch from CIW
+ local cds.lib for design-library mapping
+ exact ADE model libraries
+ apply('modelFile modelFileList)
+ no duplicate xp018.scs include
+ option('redefinedparams "warning")
+ CAD_BATCH_EXIT=1
```

Once these were in place, the standalone one-case simulation succeeded and exported `output_signals.txt`.
