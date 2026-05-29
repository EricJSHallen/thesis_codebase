# Cadence Virtuoso / OCEAN Parallel-Run Debugging Runbook

_Last updated after the `pwl_xfab.ocn` one-case test._

## 1. Executive summary

We are trying to run a large batch of independent Cadence/Spectre transient simulations faster by splitting the sweep across several separate OCEAN processes. The target workflow is:

```text
64 independent simulation cases
→ 4 external OCEAN jobs
→ each job runs 16 cases
→ each job writes its own log and manifest
```

This is **not** done by one CIW `load(...)` command. Instead, we use Cadence SKILL's IPC mechanism:

```lisp
ipcBeginProcess("...")
```

to launch separate `ocean -nograph` processes from CIW. Each external job receives:

```bash
CAD_NUM_JOBS=4
CAD_JOB_INDEX=0   # or 1, 2, 3
```

The OCEAN script then runs only the subset of cases assigned to that job.

Current state: IPC launching works, the sweep-splitting logic works, `cds.lib` mapping was fixed, and the latest `pwl_xfab.ocn` script uses the ADE model-library paths from the GUI. The last filtered grep no longer showed the earlier missing-model errors, but `output_signals.txt` count was still zero at the time checked. The next decisive step is to inspect the unfiltered tail of `ocean_xfab_onecase.log` to see whether the one-case run is still running, failed at export, or failed with a different message.

---

## 2. Why IPC is needed

### CIW `load(...)`

```lisp
load("/path/to/script.ocn")
```

runs the script inside the current Virtuoso/CIW process. It blocks the CIW until the script finishes.

### IPC launch

```lisp
ipcBeginProcess("env CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 ocean -nograph -restore /path/to/script.ocn > /path/to/log.log 2>&1")
```

starts a separate operating-system process. The CIW remains available, so you can launch job 0, job 1, job 2, and job 3 independently.

IPC means **Inter-Process Communication**. In this use case, we are using it mainly as a process launcher.

---

## 3. What worked

### 3.1 Job splitting worked

When `CAD_NUM_JOBS=4` and `CAD_JOB_INDEX=0`, the script reported:

```text
Total valid cases seen by this process: 64
Cases assigned to this process: 16
Cases skipped by this process: 48
```

That means the round-robin splitting logic worked.

When `CAD_NUM_JOBS=64` and `CAD_JOB_INDEX=0`, the script assigned one case, which is useful for debugging.

### 3.2 IPC worked

A simple test:

```lisp
ipcBeginProcess("date > /path/to/ipc_test.log 2>&1")
```

returned a handle like:

```text
ipc:13
```

That means Cadence successfully launched a child process.

Later, `ipcBeginProcess(...)` successfully launched `ocean -nograph` jobs.

### 3.3 Live log monitoring worked

Instead of:

```bash
cat ocean_ipc_job0.log | less
```

use:

```bash
tail -f ocean_ipc_job0.log
```

or for multiple logs:

```bash
tail -f ocean_ipc_job*.log
```

Stop with:

```bash
Ctrl+C
```

### 3.4 We found the design library path

In CIW:

```lisp
ddGetObj("sebastian_thesis_pilot")~>readPath
```

returned:

```text
/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
```

and:

```lisp
ddGetObj("XFABLibs")~>readPath
```

returned:

```text
/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
```

### 3.5 A local `cds.lib` fixed the design-library mapping problem

For the isolated job directory:

```text
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0
```

we created:

```text
cds.lib
```

with:

```text
INCLUDE /home/s5117909/eda_env/xp018/cds.lib
DEFINE sebastian_thesis_pilot /home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
DEFINE XFABLibs /projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
```

This addressed errors such as:

```text
ADE-5726: Unable to open config
ADE-575: Unable to Simulate, either session is invalid or design is not specified
```

### 3.6 ADE Model Libraries gave the real model list

The crucial GUI discovery was the ADE Model Libraries view:

```text
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs   default
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs    3s
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs      tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs      tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs      tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs      tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs      tm
/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/xp018.scs    mc_g
```

The important correction was:

```text
xfab/xp018
```

not:

```text
fab/xp018
```

---

## 4. What failed and why

### 4.1 `load(...)` is not parallel

This can run a script, but it does not spawn multiple jobs and it blocks CIW:

```lisp
load("/path/to/script.ocn")
```

### 4.2 Shell commands do not belong inside `.ocn`

This is shell syntax, not OCEAN/SKILL:

```bash
CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 ocean -nograph -restore script.ocn &
```

It must be run from a shell or launched through IPC, not uncommented inside an `.ocn` file.

### 4.3 `system(...)` was opaque

Many `system(...)` calls returned only:

```text
0
```

This was just the shell exit status, not the command output. We therefore redirected output to files and inspected logs in the terminal.

### 4.4 Wrong `.ocn` paths caused early restore failures

Some early IPC launches failed because the `-restore` path was wrong. Once the path was corrected, `ocean -nograph` started.

### 4.5 Shared log / working directory problems occurred

Multiple Cadence processes fighting over the same logging context produced messages like:

```text
CDS.log file is already locked by some other process
CIW initialization failure
```

The mitigation was to use isolated job directories:

```text
ipc_work/job0
ipc_work/job1
ipc_work/job2
ipc_work/job3
```

### 4.6 `xp018_combine.lib` was not a Spectre model deck

We tried:

```text
/home/s5117909/eda_env/xp018/xp018_combine.lib
```

as a model file, but Spectre rejected it because it contained Cadence library-manager syntax such as:

```text
ASSIGN
DEFINE
COMBINE
```

rather than Spectre model syntax.

### 4.7 `xp018.lib` was also not the model deck

We inspected:

```text
/home/s5117909/eda_env/xp018/xp018.lib
```

and found it was another Cadence library-definition file, not the device model deck.

### 4.8 `ade_e.scs` did not solve the missing models

We tried including:

```text
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs
```

but Spectre still reported missing:

```text
ne
pe
cmm4
```

### 4.9 `pvtech.lib` was not the model deck

We tried:

```text
/home/s5117909/eda_env/xp018/pvtech.lib
```

but it was another small setup/library mapping file, not the device model deck.

### 4.10 The first ADE model script had a path typo

The first model-file script used:

```text
/projects/bics/designkits/fab/xp018/...
```

but the ADE Model Libraries view showed:

```text
/projects/bics/designkits/xfab/xp018/...
```

This was corrected in:

```text
pwl_xfab.ocn
```

---

## 5. Current best script

The current best script is:

```text
pwl_xfab.ocn
```

It should contain a `modelFile(...)` block like:

```lisp
modelFile(
    list(
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/config.scs" "default")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/param.scs"  "3s")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/bip.scs"    "tm")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/cap.scs"    "tm")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/dio.scs"    "tm")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/mos.scs"    "tm")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/res.scs"    "tm")
        list("/projects/bics/designkits/xfab/xp018/cadence/v8_0/spectre/v8_0_1/lp5mos/xp018.scs"  "mc_g")
    )
)
```

The one-case CIW command is:

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=64 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_xfab.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_onecase.log 2>&1'")
```

---

## 6. Last known state

After running `pwl_xfab.ocn`, the filtered grep showed only `OA Exception` warnings and did not show the previous severe messages:

```text
SFE-23
undefined model
SFE-874
Cannot find Spectre model file
```

That is promising.

However, the output count was still:

```text
0
```

from:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data -name output_signals.txt | wc -l
```

This means the next task is to determine whether:

1. the simulation was still running,
2. the simulation completed but export failed,
3. the simulation failed with a message not caught by the filtered grep.

---

## 7. What to do when back at the machine

### 7.1 Kill stale batch processes

```bash
ps -fu "$USER" | grep -E "ocean -nograph|spectre|tail -f ocean" | grep -v grep
```

Kill stale batch jobs only:

```bash
kill <PID>
```

Force only if needed:

```bash
kill -9 <PID>
```

Do **not** kill the main GUI/session infrastructure unless restarting Cadence deliberately:

```text
virtuoso
libManager
libSelect
cdsMsgServer
cdsServIpc
```

### 7.2 Check whether the one-case job is still running

```bash
ps -fu "$USER" | grep -E "ocean_xfab_onecase|pwl_xfab|spectre|ocean -nograph" | grep -v grep
```

### 7.3 Inspect the unfiltered log tail

```bash
tail -200 /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_onecase.log
```

### 7.4 Search for broader clues

```bash
grep -iE "spectre|tran|completed|successful|ocnPrint|selectResult|results|not available|output_signals|Finished assigned|CAD_BATCH_EXIT" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_onecase.log
```

### 7.5 Check the run directory

Likely one-case run directory:

```text
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_81_hz__st2_81_hz__trial_1
```

Check:

```bash
ls -lh /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_81_hz__st2_81_hz__trial_1
```

and:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_81_hz__st2_81_hz__trial_1 -maxdepth 3 -type f | sort
```

If PSF data exists but `output_signals.txt` does not, the problem is likely in `selectResult(...)`, `ocnPrint(...)`, or result-directory handling rather than in Spectre model setup.

### 7.6 Check output count

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data -name output_signals.txt | wc -l
```

For a one-case test, this should increase by 1. For the full 64-case run, it should eventually be 64.

---

## 8. If one case works, launch four parallel jobs

### 8.1 Prepare job directories

```bash
for i in 0 1 2 3
do
    mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i
    cat > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib <<'CDSLIB_EOF'
INCLUDE /home/s5117909/eda_env/xp018/cds.lib
DEFINE sebastian_thesis_pilot /home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot
DEFINE XFABLibs /projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs
CDSLIB_EOF
done
```

### 8.2 Launch four jobs from CIW

```lisp
foreach(i '(0 1 2 3)
  ipcBeginProcess(
    sprintf(nil
      "sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job%d && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=%d CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_xfab.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_job%d.log 2>&1'"
      i i i
    )
  )
)
```

### 8.3 Monitor

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_job*.log
```

### 8.4 Check completion

```bash
grep "Finished assigned simulations" /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_job*.log
```

### 8.5 Count outputs

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data -name output_signals.txt | wc -l
```

Expected after all four jobs:

```text
64
```

---

## 9. Important caution

Do not trust this line alone:

```text
Finished: st1_...
```

The script may print `Finished:` even after Spectre fails. The stronger success indicators are:

```text
INFO (ADE-3071): Simulation completed successfully
```

and the existence of:

```text
output_signals.txt
```

---

## 10. Minimal restart checklist

```bash
# 1. Check stale jobs
ps -fu "$USER" | grep -E "ocean -nograph|spectre|tail -f ocean" | grep -v grep

# 2. Inspect latest one-case log
tail -200 /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_onecase.log

# 3. Search important messages
grep -iE "SFE-23|SFE-874|undefined model|ERROR|FATAL|Cannot open|completed successfully|output_signals|Finished assigned|CAD_BATCH_EXIT" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_xfab_onecase.log

# 4. Check output count
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data -name output_signals.txt | wc -l
```

If the one-case test works, move to the four-job launch.
