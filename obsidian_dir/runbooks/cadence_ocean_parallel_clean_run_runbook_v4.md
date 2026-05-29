# Cadence OCEAN Parallel IPC Runbook v4 — Clean Restart, Input Validation, and Large Sweep Prep

This runbook consolidates the working Cadence Virtuoso/OCEAN IPC workflow and adds the newer lessons from the large sweep attempt:

- how to stop stale batch simulations cleanly;
- how to back up partial results and logs before restarting;
- how to regenerate and validate the spike-train input directory;
- how to verify that OCEAN sees the intended number of cases before committing to a long run;
- how to launch four IPC jobs from the correct `job0`–`job3` directories;
- how to monitor progress and detect failures.

The current working assumption is that the simulation is launched from CIW with `ipcBeginProcess(...)`, while the actual simulation work is done by external `ocean -nograph -restore ...` processes.

---

## 1. Current important paths

```text
Repository base:
/home/s5117909/Documents/thesis/sebastian_thesis_repo

General code directory:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code

Current OCEAN script for 1-synapse run:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_1syn.ocn

Spike-train generator:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/sdgo_stepsize.py

Spike-train input directory read by OCEAN:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output

Cadence extraction directory:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction

Main output directory for single-output simulation:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data

IPC job directories:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job1
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job2
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job3

Job logs:
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job0.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job1.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job2.log
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log
```

---

## 2. Key fact: validate the input data before launching Cadence

The large-run issue was not initially a Cadence issue. A job reported:

```text
Total valid cases seen by this process: 64
Cases assigned to this process: 16
Cases skipped by this process: 48
```

That means the OCEAN script only saw the old 64-case input directory, not the intended large sweep. Before launching Cadence, always validate the generated `spike_train_output` directory.

The uploaded `sdgo_stepsize.py` settings were:

```python
num_spike_train_sets = 2
max_frequency_hz = 600
step_size = 16
trials_per_frequency = 2
```

This gives frequencies:

```text
1, 17, 33, ..., 593
```

That is 38 frequency values. Since OCEAN pairs all `st_1` frequencies with all `st_2` frequencies and uses 2 trials:

```text
38 × 38 × 2 = 2888 simulations
```

So the expected total is **2888**, not 2880, unless the generator or OCEAN pairing logic is changed.

---

## 3. Clean-stop all current batch jobs

Before any new serious run, stop stale OCEAN/Spectre processes.

### 3.1 List relevant processes

```bash
ps -fu "$USER" | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|pwl_apply_duo|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" | grep -v grep
```

This finds batch processes such as:

```text
sh -c ... CAD_JOB_INDEX=...
ocean -nograph -restore ...
virtuoso -ocean -nographE ...
cdsXvfb-run ...
spectre input.scs ...
spectre_encrypt ...
runSimulation
tail -f ocean_apply_job*.log
```

### 3.2 Kill normal batch processes

```bash
pkill -u "$USER" -f "CAD_JOB_INDEX"
pkill -u "$USER" -f "ocean -nograph"
pkill -u "$USER" -f "virtuoso -ocean"
pkill -u "$USER" -f "cdsXvfb-run"
pkill -u "$USER" -f "runSimulation"
pkill -u "$USER" -f "spectre input.scs"
pkill -u "$USER" -f "spectre_encrypt"
pkill -u "$USER" -f "tail -f .*ocean"
```

### 3.3 Re-check

```bash
ps -fu "$USER" | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|pwl_apply_duo|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" | grep -v grep
```

If anything remains, kill by PID:

```bash
kill <PID1> <PID2> <PID3>
```

If still present after a few seconds:

```bash
kill -9 <PID1> <PID2> <PID3>
```

### 3.4 Do not kill these unless restarting Cadence entirely

Avoid killing generic Cadence GUI/session processes unless you intend to close/restart Virtuoso:

```text
virtuoso
libManager
libSelect
cdsMsgServer
cdsServIpc
```

---

## 4. Back up partial outputs and logs before a fresh run

If a simulation was interrupted by logout, expired key, manual kill, or a wrong 64-case input set, preserve the partial data before restarting.

```bash
cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction

ts=$(date +%Y%m%d_%H%M%S)

mv output_single_data output_single_data_partial_$ts 2>/dev/null
mkdir -p output_single_data

mkdir -p archived_logs_$ts
mv ocean_apply_job*.log archived_logs_$ts/ 2>/dev/null
```

This creates, for example:

```text
output_single_data_partial_20260520_131500
archived_logs_20260520_131500
```

Advantages:

- no accidental mixing of old and new run outputs;
- old results are preserved;
- logs remain available for diagnosis;
- new output count starts from zero.

---

## 5. Regenerate the spike-train input directory

Run:

```bash
cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code
python3 sdgo_stepsize.py
```

The generator has `overwrite_output_directory = True`, so it should delete/recreate `spike_train_output` when run.

---

## 6. Validate the generated spike-train directory

Run these before launching Cadence.

### 6.1 Count frequency directories

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_1 \
  -mindepth 1 -maxdepth 1 -type d | wc -l

find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_2 \
  -mindepth 1 -maxdepth 1 -type d | wc -l
```

Expected with `max_frequency_hz=600`, `step_size=16`:

```text
38
38
```

### 6.2 Count PWL files

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output \
  -name "trial_*.pwl" | wc -l
```

Expected:

```text
152
```

because:

```text
2 spike-train sets × 38 frequencies × 2 trials = 152 PWL files
```

### 6.3 Inspect frequency range

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_1 \
  -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort -V | head

find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_1 \
  -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort -V | tail
```

Expected approximate output:

```text
1_hz
17_hz
33_hz
...
593_hz
```

### 6.4 Expected Cadence case count

For the current generator:

```text
38 × 38 × 2 = 2888 valid cases
```

Therefore each of four jobs should see:

```text
Total valid cases seen by this process: 2888
Cases assigned to this process: 722
Cases skipped by this process: 2166
```

If any job sees only 64 valid cases, it is reading stale or wrong input data.

---

## 7. Ensure IPC job directories have `cds.lib`

Each job should run from a distinct directory.

```bash
for i in 1 2 3
 do
    mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i
    cp /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib \
       /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib
 done
```

Verify:

```bash
for i in 0 1 2 3
 do
    echo "job$i:"
    ls -lh /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib
 done
```

If the copy command says job0 source and destination are the same file, that is harmless if the loop included `i=0`. The cleaner loop starts from `1`.

---

## 8. Correct four-job launch commands

Run these in CIW. Stagger launches by 10–20 seconds if possible.

### Job 0

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_1syn.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job0.log 2>&1'")
```

### Job 1

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job1 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=1 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_1syn.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job1.log 2>&1'")
```

### Job 2

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job2 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=2 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_1syn.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job2.log 2>&1'")
```

### Job 3

```lisp
ipcBeginProcess("sh -c 'cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job3 && env CAD_NUM_JOBS=4 CAD_JOB_INDEX=3 CAD_BATCH_EXIT=1 ocean -nograph -restore /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/pwl_1syn.ocn > /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job3.log 2>&1'")
```

Critical point:

```text
job0 must cd into ipc_work/job0
job1 must cd into ipc_work/job1
job2 must cd into ipc_work/job2
job3 must cd into ipc_work/job3
```

Do not run all four from `ipc_work/job0`.

---

## 9. Immediately verify that OCEAN sees the large sweep

After the jobs have started and logs have enough content, run:

```bash
grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Expected for current generator:

```text
Total valid cases seen by this process: 2888
Cases assigned to this process: 722
Cases skipped by this process: 2166
```

If a job says:

```text
Total valid cases seen by this process: 64
Cases assigned to this process: 16
Cases skipped by this process: 48
```

then it is not running the intended large sweep. Stop, regenerate/verify `spike_train_output`, and restart clean.

---

## 10. Live monitoring

### 10.1 Raw tail all logs

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

### 10.2 Condensed progress/error stream

```bash
tail -f /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log \
| grep -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired"
```

### 10.3 Non-live condensed log

```bash
grep -h -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log | tail -120
```

---

## 11. Count completed simulations

Main output-file count:

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -name output_signals.txt | wc -l
```

Expected final count for current large run:

```text
2888
```

Check job-level completion:

```bash
grep -H "Finished assigned simulations" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

You want all four:

```text
Finished assigned simulations for job 0 of 4.
Finished assigned simulations for job 1 of 4.
Finished assigned simulations for job 2 of 4.
Finished assigned simulations for job 3 of 4.
```

---

## 12. Find missing outputs after all jobs finish

Only run this after all four jobs have finished. While simulations are still running, some “missing” entries may simply be in progress.

```bash
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data \
  -mindepth 1 -maxdepth 1 -type d | while read d
 do
    if [ ! -f "$d/output_signals.txt" ]; then
        echo "MISSING: $d"
    fi
 done
```

If missing cases exist, inspect logs:

```bash
grep -H -iE "SFE-868|SPECTRE-25|tran are not available|Cannot open|ERROR|FATAL" \
/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ocean_apply_job*.log
```

Common causes:

```text
SFE-868: Cannot open input file 'ade_e.scs'
```

Usually a parallel netlisting/shared-file race.

```text
SPECTRE-25: The simulation is stopped either by the user or ...
```

Usually manual kill, logout/key expiry, or wrapper termination.

---

## 13. Important known failure modes

| Symptom | Meaning | Action |
|---|---|---|
| `Total valid cases seen: 64` | OCEAN sees old small input directory | Regenerate/verify `spike_train_output`; restart clean |
| `Total valid cases seen: 2888` | OCEAN sees current large sweep | Continue |
| `Key has expired` in logs | University session/key expired; jobs may die | Restart after login; plan runs early in login window |
| `SFE-868 Cannot open ade_e.scs` | Race around shared netlist file | Stagger launches; use separate job dirs; rerun missing cases |
| `SPECTRE-25 stopped by user` | Process killed or session ended | Rerun affected cases/job |
| `SFE-23 undefined ne/pe/cmm4` | Model files not included | Ensure `apply('modelFile modelFileList)` model block is in OCEAN script |
| `SFE-59 redefinedparams` | Duplicate parameter definitions | Ensure `option('redefinedparams "warning")` is in OCEAN script |
| `SFE-3`/`SFE-396` duplicate subckt/model | Too many model files included | Do not include `xp018.scs` alongside individual model files |
| `CDS.log already locked` | Multiple Cadence processes writing logs | Usually tolerable |

---

## 14. Current recommended workflow for a long run

1. Log into the university system with a fresh session.
2. Clear stale batch processes.
3. Back up/rename old `output_single_data` and logs.
4. Run `python3 sdgo_stepsize.py`.
5. Confirm `st_1` count = 38, `st_2` count = 38, PWL count = 152.
6. Confirm each `ipc_work/job*` directory has `cds.lib`.
7. Launch jobs 0–3 from their respective directories, 10–20 seconds apart.
8. After logs begin, confirm each job sees 2888 total cases and 722 assigned cases.
9. Monitor count of `output_signals.txt`.
10. After all jobs finish, verify final count = 2888.
11. Scan missing outputs only after all four jobs have finished.

---

## 15. Minimal command block for clean restart

```bash
# Stop stale batch jobs
pkill -u "$USER" -f "CAD_JOB_INDEX"
pkill -u "$USER" -f "ocean -nograph"
pkill -u "$USER" -f "virtuoso -ocean"
pkill -u "$USER" -f "cdsXvfb-run"
pkill -u "$USER" -f "runSimulation"
pkill -u "$USER" -f "spectre input.scs"
pkill -u "$USER" -f "spectre_encrypt"
pkill -u "$USER" -f "tail -f .*ocean"

# Confirm clean
ps -fu "$USER" | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean" | grep -v grep

# Back up old outputs/logs
cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction
ts=$(date +%Y%m%d_%H%M%S)
mv output_single_data output_single_data_partial_$ts 2>/dev/null
mkdir -p output_single_data
mkdir -p archived_logs_$ts
mv ocean_apply_job*.log archived_logs_$ts/ 2>/dev/null

# Regenerate inputs
cd /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code
python3 sdgo_stepsize.py

# Validate input counts
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_1 -mindepth 1 -maxdepth 1 -type d | wc -l
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_2 -mindepth 1 -maxdepth 1 -type d | wc -l
find /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output -name "trial_*.pwl" | wc -l

# Prep job dirs
for i in 1 2 3
 do
    mkdir -p /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i
    cp /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job0/cds.lib \
       /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/ipc_work/job$i/cds.lib
 done
```

Then launch the four CIW commands from Section 8.
