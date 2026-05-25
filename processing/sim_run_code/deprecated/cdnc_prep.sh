#!/usr/bin/env bash
set -euo pipefail

# Prepare a clean Cadence/OCEAN IPC batch run.
# This script:
#   1. kills stale batch OCEAN/Spectre/helper processes for the current user;
#   2. backs up old output_single_data and ocean_apply_job*.log files;
#   3. regenerates spike_train_output using sdgo_stepsize.py;
#   4. validates generated input counts;
#   5. ensures ipc_work/job1..job3 have cds.lib copied from job0;
#   6. prints the CIW ipcBeginProcess commands to launch jobs 0..3.
#
# It does NOT automatically launch jobs in CIW. Copy/paste the printed CIW commands.

REPO="/home/s5117909/Documents/thesis/sebastian_thesis_repo"
GEN_DIR="$REPO/processing/general_code"
EXTRACT_DIR="$REPO/processing/cadence_extraction"
OUTPUT_DIR="$EXTRACT_DIR/output_single_data"
IPC_DIR="$EXTRACT_DIR/ipc_work"
OCN="$GEN_DIR/pwl_1syn.ocn"
GENERATOR="$GEN_DIR/sdgo_stepsize.py"
LOG_PREFIX="$EXTRACT_DIR/ocean_apply_job"

EXPECTED_ST_DIRS="${EXPECTED_ST_DIRS:-38}"
EXPECTED_PWL_FILES="${EXPECTED_PWL_FILES:-152}"
EXPECTED_CASES="${EXPECTED_CASES:-2888}"
NUM_JOBS="${NUM_JOBS:-4}"

DRY_RUN="${DRY_RUN:-0}"
SKIP_KILL="${SKIP_KILL:-0}"
SKIP_REGENERATE="${SKIP_REGENERATE:-0}"

run() {
    echo "+ $*"
    if [[ "$DRY_RUN" != "1" ]]; then
        "$@"
    fi
}

run_shell() {
    echo "+ $*"
    if [[ "$DRY_RUN" != "1" ]]; then
        bash -lc "$*"
    fi
}

echo "=== Cadence/OCEAN clean-run preparation ==="
echo "Repo:        $REPO"
echo "OCEAN file:  $OCN"
echo "Generator:   $GENERATOR"
echo "Output dir:  $OUTPUT_DIR"
echo "IPC dir:     $IPC_DIR"
echo

if [[ ! -f "$OCN" ]]; then
    echo "ERROR: OCEAN script not found: $OCN" >&2
    exit 1
fi

if [[ ! -f "$GENERATOR" ]]; then
    echo "ERROR: Spike-train generator not found: $GENERATOR" >&2
    exit 1
fi

if [[ ! -f "$IPC_DIR/job0/cds.lib" ]]; then
    echo "ERROR: Missing template cds.lib: $IPC_DIR/job0/cds.lib" >&2
    echo "Create job0/cds.lib first, then rerun this script." >&2
    exit 1
fi

# 1. Stop stale batch processes.
echo "=== 1. Stopping stale batch OCEAN/Spectre/helper processes ==="
if [[ "$SKIP_KILL" == "1" ]]; then
    echo "SKIP_KILL=1, not killing processes."
else
    patterns=(
        "CAD_JOB_INDEX"
        "ocean -nograph"
        "virtuoso -ocean"
        "cdsXvfb-run"
        "runSimulation"
        "spectre input.scs"
        "spectre_encrypt"
        "tail -f .*ocean"
    )

    for pat in "${patterns[@]}"; do
        echo "+ pkill -u \"$USER\" -f \"$pat\""
        if [[ "$DRY_RUN" != "1" ]]; then
            pkill -u "$USER" -f "$pat" 2>/dev/null || true
        fi
    done

    sleep 2
fi

echo "Remaining matching batch processes, if any:"
ps -fu "$USER" | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|pwl_apply_duo|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" | grep -v grep || true
echo

# 2. Back up existing output/logs.
echo "=== 2. Backing up old output/logs ==="
ts="$(date +%Y%m%d_%H%M%S)"
run mkdir -p "$EXTRACT_DIR"

if [[ -d "$OUTPUT_DIR" ]]; then
    run mv "$OUTPUT_DIR" "$EXTRACT_DIR/output_single_data_partial_$ts"
fi
run mkdir -p "$OUTPUT_DIR"

run mkdir -p "$EXTRACT_DIR/archived_logs_$ts"
run_shell "shopt -s nullglob; mv '$EXTRACT_DIR'/ocean_apply_job*.log '$EXTRACT_DIR/archived_logs_$ts'/ 2>/dev/null || true"
echo "Archive timestamp: $ts"
echo

# 3. Regenerate inputs.
echo "=== 3. Regenerating spike-train inputs ==="
if [[ "$SKIP_REGENERATE" == "1" ]]; then
    echo "SKIP_REGENERATE=1, not running generator."
else
    run_shell "cd '$GEN_DIR' && python3 '$GENERATOR'"
fi
echo

# 4. Validate generated input counts.
echo "=== 4. Validating generated input counts ==="
ST1_DIR="$GEN_DIR/spike_train_output/st_1"
ST2_DIR="$GEN_DIR/spike_train_output/st_2"
PWL_ROOT="$GEN_DIR/spike_train_output"

if [[ ! -d "$ST1_DIR" || ! -d "$ST2_DIR" ]]; then
    echo "ERROR: Expected spike-train directories not found:" >&2
    echo "  $ST1_DIR" >&2
    echo "  $ST2_DIR" >&2
    exit 1
fi

st1_count=$(find "$ST1_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
st2_count=$(find "$ST2_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
pwl_count=$(find "$PWL_ROOT" -name "trial_*.pwl" | wc -l | tr -d ' ')
case_count=$(( st1_count * st2_count * 2 ))

printf "st_1 frequency dirs: %s\n" "$st1_count"
printf "st_2 frequency dirs: %s\n" "$st2_count"
printf "PWL trial files:     %s\n" "$pwl_count"
printf "Expected cases from st1*st2*2 trials: %s\n" "$case_count"

echo "First st_1 dirs:"
find "$ST1_DIR" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort -V | head || true

echo "Last st_1 dirs:"
find "$ST1_DIR" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort -V | tail || true

if [[ "$st1_count" != "$EXPECTED_ST_DIRS" || "$st2_count" != "$EXPECTED_ST_DIRS" || "$pwl_count" != "$EXPECTED_PWL_FILES" ]]; then
    echo "WARNING: Counts differ from expected defaults." >&2
    echo "Expected st dirs: $EXPECTED_ST_DIRS, PWL files: $EXPECTED_PWL_FILES" >&2
    echo "Set EXPECTED_ST_DIRS / EXPECTED_PWL_FILES if this is intentional." >&2
fi

if [[ "$case_count" != "$EXPECTED_CASES" ]]; then
    echo "WARNING: Computed case count $case_count differs from EXPECTED_CASES=$EXPECTED_CASES." >&2
    echo "For current sdgo_stepsize.py settings, 38*38*2 = 2888 is expected." >&2
fi
echo

# 5. Prepare IPC job directories.
echo "=== 5. Preparing IPC job directories and cds.lib files ==="
for i in $(seq 0 $((NUM_JOBS-1))); do
    run mkdir -p "$IPC_DIR/job$i"
    if [[ "$i" != "0" ]]; then
        run cp "$IPC_DIR/job0/cds.lib" "$IPC_DIR/job$i/cds.lib"
    fi
    echo "job$i cds.lib:"
    ls -lh "$IPC_DIR/job$i/cds.lib"
done
echo

# 6. Print CIW launch commands.
echo "=== 6. Copy/paste these CIW commands, preferably 10-20 seconds apart ==="
for i in $(seq 0 $((NUM_JOBS-1))); do
    cat <<CMD
ipcBeginProcess("sh -c 'cd $IPC_DIR/job$i && env CAD_NUM_JOBS=$NUM_JOBS CAD_JOB_INDEX=$i CAD_BATCH_EXIT=1 ocean -nograph -restore $OCN > ${LOG_PREFIX}${i}.log 2>&1'")
CMD
    echo
done

cat <<EOF2
=== Monitoring commands ===

Condensed live monitor:

tail -f $EXTRACT_DIR/ocean_apply_job*.log \\
| grep -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired"

Check that each job sees the full sweep:

grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" \\
$EXTRACT_DIR/ocean_apply_job*.log

Count completed outputs:

find $OUTPUT_DIR -name output_signals.txt | wc -l

Expected final output count for current generator: $EXPECTED_CASES
EOF2
