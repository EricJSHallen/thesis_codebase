#!/usr/bin/env bash
set -euo pipefail

# simprep_run_dir.sh
# Prepare a clean Cadence/OCEAN IPC batch run for the restructured thesis_codebase.
#
# Main change relative to the older script:
#   - every run gets a unique directory under thesis_database/;
#   - outputs, logs, ipc_work, and a run-specific OCEAN copy all live there;
#   - the original OCEAN file is not edited.
#
# Usage examples:
#   ./simprep_run_dir.sh
#   RUN_LABEL=1syn_600hz_step16 ./simprep_run_dir.sh
#   DRY_RUN=1 ./simprep_run_dir.sh
#   SKIP_KILL=1 SKIP_REGENERATE=1 ./simprep_run_dir.sh
#
# This script does NOT launch jobs automatically in CIW. It prints the CIW
# ipcBeginProcess(...) commands to copy/paste.

# -----------------------------
# User-configurable variables
# -----------------------------

REPO="${REPO:-/home/s5117909/Documents/thesis/thesis_codebase}"
GEN_DIR="${GEN_DIR:-$REPO/processing/sim_run_code}"
DATABASE_DIR="${DATABASE_DIR:-$REPO/thesis_database}"

OCN="${OCN:-$GEN_DIR/pwl_1syn.ocn}"
GENERATOR="${GENERATOR:-$GEN_DIR/sdgo_stepsize.py}"

RUN_LABEL="${RUN_LABEL:-1syn}"
RUN_LABEL_SAFE="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_//;s/_$//')"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_${RUN_LABEL_SAFE}}"
RUN_DIR="${RUN_DIR:-$DATABASE_DIR/$RUN_ID}"

OUTPUT_DIR="${OUTPUT_DIR:-$RUN_DIR/output_single_data}"
LOG_DIR="${LOG_DIR:-$RUN_DIR/logs}"
IPC_DIR="${IPC_DIR:-$RUN_DIR/ipc_work}"
RUN_OCN_DIR="${RUN_OCN_DIR:-$RUN_DIR/ocn}"
RUN_OCN="${RUN_OCN:-$RUN_OCN_DIR/$(basename "$OCN") }"
RUN_OCN="${RUN_OCN% }"  # trim intentional construction space

NUM_JOBS="${NUM_JOBS:-4}"
EXPECTED_ST_DIRS="${EXPECTED_ST_DIRS:-38}"
EXPECTED_PWL_FILES="${EXPECTED_PWL_FILES:-152}"
EXPECTED_CASES="${EXPECTED_CASES:-2888}"

DRY_RUN="${DRY_RUN:-0}"
SKIP_KILL="${SKIP_KILL:-0}"
SKIP_REGENERATE="${SKIP_REGENERATE:-0}"
SKIP_OCN_PATCH="${SKIP_OCN_PATCH:-0}"

# Cadence library mapping. These are written to each run-local ipc_work/job*/cds.lib.
CDS_INCLUDE="${CDS_INCLUDE:-/home/s5117909/eda_env/xp018/cds.lib}"
DESIGN_LIB_NAME="${DESIGN_LIB_NAME:-sebastian_thesis_pilot}"
DESIGN_LIB_PATH="${DESIGN_LIB_PATH:-/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot}"
XFAB_LIB_PATH="${XFAB_LIB_PATH:-/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs}"

# -----------------------------
# Helpers
# -----------------------------

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

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "$path" ]]; then
        echo "ERROR: $label not found: $path" >&2
        exit 1
    fi
}

# -----------------------------
# Intro and static checks
# -----------------------------

echo "=== Cadence/OCEAN run preparation ==="
echo "Repo:         $REPO"
echo "Generator:    $GENERATOR"
echo "Source OCN:   $OCN"
echo "Run label:    $RUN_LABEL"
echo "Run ID:       $RUN_ID"
echo "Run dir:      $RUN_DIR"
echo "Output dir:   $OUTPUT_DIR"
echo "Log dir:      $LOG_DIR"
echo "IPC dir:      $IPC_DIR"
echo "Run OCN:      $RUN_OCN"
echo

require_file "$OCN" "OCEAN script"
require_file "$GENERATOR" "Spike-train generator"

# -----------------------------
# 1. Stop stale batch processes
# -----------------------------

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

# -----------------------------
# 2. Create run directory layout
# -----------------------------

echo "=== 2. Creating unique run directory layout ==="
run mkdir -p "$RUN_DIR" "$OUTPUT_DIR" "$LOG_DIR" "$IPC_DIR" "$RUN_OCN_DIR"

if [[ "$DRY_RUN" != "1" && -e "$RUN_DIR/RUNINFO.txt" ]]; then
    echo "ERROR: Run directory already appears initialized: $RUN_DIR" >&2
    echo "Set RUN_ID to a different value or remove the old directory." >&2
    exit 1
fi

# -----------------------------
# 3. Regenerate inputs
# -----------------------------

echo "=== 3. Regenerating spike-train inputs ==="
if [[ "$SKIP_REGENERATE" == "1" ]]; then
    echo "SKIP_REGENERATE=1, not running generator."
else
    run_shell "cd '$GEN_DIR' && python3 '$GENERATOR'"
fi
echo

# -----------------------------
# 4. Validate generated input counts
# -----------------------------

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
fi
echo

# -----------------------------
# 5. Create run-specific OCEAN copy and patch outputBaseDir
# -----------------------------

echo "=== 5. Creating run-specific OCEAN script copy ==="
run cp "$OCN" "$RUN_OCN"

if [[ "$SKIP_OCN_PATCH" == "1" ]]; then
    echo "SKIP_OCN_PATCH=1, not patching outputBaseDir in run OCEAN copy."
else
    if [[ "$DRY_RUN" != "1" ]]; then
        if grep -qE '^[[:space:]]*outputBaseDir[[:space:]]*=' "$RUN_OCN"; then
            perl -0pi -e 's#^[[:space:]]*outputBaseDir[[:space:]]*=.*$#outputBaseDir = "'"$OUTPUT_DIR"'"#m' "$RUN_OCN"
        else
            echo "WARNING: Could not find outputBaseDir assignment in $RUN_OCN" >&2
            echo "The OCEAN file may still write to its old hard-coded output directory." >&2
        fi
    else
        echo "+ patch outputBaseDir in $RUN_OCN to $OUTPUT_DIR"
    fi
fi

echo "Run OCEAN outputBaseDir line:"
grep -n "outputBaseDir" "$RUN_OCN" | head -5 || true
echo

# -----------------------------
# 6. Prepare IPC job directories and cds.lib files
# -----------------------------

echo "=== 6. Preparing IPC job directories and cds.lib files ==="
for i in $(seq 0 $((NUM_JOBS-1))); do
    jobdir="$IPC_DIR/job$i"
    run mkdir -p "$jobdir"

    if [[ "$DRY_RUN" != "1" ]]; then
        cat > "$jobdir/cds.lib" <<EOF_CDSLIB
INCLUDE $CDS_INCLUDE
DEFINE $DESIGN_LIB_NAME $DESIGN_LIB_PATH
DEFINE XFABLibs $XFAB_LIB_PATH
EOF_CDSLIB
    else
        echo "+ write $jobdir/cds.lib"
    fi

    echo "job$i cds.lib:"
    ls -lh "$jobdir/cds.lib"
done
echo

# -----------------------------
# 7. Write run metadata
# -----------------------------

echo "=== 7. Writing run metadata ==="
if [[ "$DRY_RUN" != "1" ]]; then
    cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUNINFO
Run ID: $RUN_ID
Run label: $RUN_LABEL
Created: $(date -Iseconds)
Repo: $REPO
Generator: $GENERATOR
Source OCN: $OCN
Run OCN: $RUN_OCN
Output dir: $OUTPUT_DIR
Log dir: $LOG_DIR
IPC dir: $IPC_DIR
NUM_JOBS: $NUM_JOBS
st_1 dirs: $st1_count
st_2 dirs: $st2_count
PWL files: $pwl_count
Expected cases: $case_count
EOF_RUNINFO
fi
run ls -lh "$RUN_DIR/RUNINFO.txt"
echo

# -----------------------------
# 8. Print CIW commands and monitoring helpers
# -----------------------------

echo "=== 8. Copy/paste these CIW commands, preferably 10-20 seconds apart ==="
for i in $(seq 0 $((NUM_JOBS-1))); do
    cat <<CMD
ipcBeginProcess("sh -c 'cd $IPC_DIR/job$i && env CAD_NUM_JOBS=$NUM_JOBS CAD_JOB_INDEX=$i CAD_BATCH_EXIT=1 CAD_RUN_DIR=$RUN_DIR CAD_OUTPUT_DIR=$OUTPUT_DIR ocean -nograph -restore $RUN_OCN > $LOG_DIR/ocean_apply_job$i.log 2>&1'")
CMD
    echo
done

cat <<EOF_HELP
=== Monitoring commands ===

Condensed live monitor:

tail -f $LOG_DIR/ocean_apply_job*.log \\
| grep -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired"

Check that each job sees the full sweep:

grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" \\
$LOG_DIR/ocean_apply_job*.log

Count completed outputs:

find $OUTPUT_DIR -name output_signals.txt | wc -l

Live progress bar:

watch -n 10 'n=\$(find "$OUTPUT_DIR" -name output_signals.txt | wc -l); total=$EXPECTED_CASES; width=60; filled=\$((n*width/total)); empty=\$((width-filled)); bar=\$(printf "%0.s#" \$(seq 1 \$filled)); space=\$(printf "%0.s-" \$(seq 1 \$empty)); pct=\$(awk -v n=\$n -v t=\$total "BEGIN {printf \\\"%.2f\\\", 100*n/t}"); printf "[%s%s] %s/%s complete (%s%%)\\n" "\$bar" "\$space" "\$n" "\$total" "\$pct"'

Expected final output count for current generator: $EXPECTED_CASES

Run directory:
$RUN_DIR
EOF_HELP
