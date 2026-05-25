#!/usr/bin/env bash
set -euo pipefail

# Prepare a Cadence/OCEAN IPC run in the restructured thesis_codebase.
# Creates one unique run directory under thesis_database and prints CIW commands.
# It does not generate spike trains and it does not archive old global logs.

REPO="${REPO:-/home/s5117909/Documents/thesis/thesis_codebase}"
CODE_DIR="${CODE_DIR:-$REPO/processing/sim_run_code}"
DATABASE_DIR="${DATABASE_DIR:-$REPO/thesis_database}"

SRC_OCN="${SRC_OCN:-$CODE_DIR/pwl_1syn.ocn}"
RUN_LABEL="${RUN_LABEL:-2channel_1syn}"
RUN_LABEL_SAFE="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_//;s/_$//')"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_${RUN_LABEL_SAFE}}"
RUN_DIR="${RUN_DIR:-$DATABASE_DIR/$RUN_ID}"

OUTPUT_NAME="${OUTPUT_NAME:-output_2channel_1syn_data}"
OUTPUT_DIR="${OUTPUT_DIR:-$RUN_DIR/$OUTPUT_NAME}"
LOG_DIR="${LOG_DIR:-$RUN_DIR/logs}"
IPC_DIR="${IPC_DIR:-$RUN_DIR/ipc_work}"
RUN_OCN_DIR="${RUN_OCN_DIR:-$RUN_DIR/ocn}"
RUN_OCN="${RUN_OCN:-$RUN_OCN_DIR/$(basename "$SRC_OCN")}"

NUM_JOBS="${NUM_JOBS:-4}"
EXPECTED_CASES="${EXPECTED_CASES:-2888}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_KILL="${SKIP_KILL:-0}"
SKIP_OCN_PATCH="${SKIP_OCN_PATCH:-0}"

CDS_INCLUDE="${CDS_INCLUDE:-/home/s5117909/eda_env/xp018/cds.lib}"
DESIGN_LIB_NAME="${DESIGN_LIB_NAME:-sebastian_thesis_pilot}"
DESIGN_LIB_PATH="${DESIGN_LIB_PATH:-/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot}"
XFAB_LIB_PATH="${XFAB_LIB_PATH:-/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs}"

run() {
    echo "+ $*"
    [[ "$DRY_RUN" == "1" ]] || "$@"
}

need_file() {
    [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }
}

patch_ocn_output_dir() {
    local file="$1"
    local outdir="$2"

    if ! grep -qE '^[[:space:]]*outputBaseDir[[:space:]]*=' "$file"; then
        echo "WARNING: no outputBaseDir assignment found in $file" >&2
        return 0
    fi

    perl -0pi -e 's#^[[:space:]]*outputBaseDir[[:space:]]*=.*$#outputBaseDir = "'"$outdir"'"#m' "$file"
}

kill_stale_processes() {
    local patterns=(
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
        [[ "$DRY_RUN" == "1" ]] || pkill -u "$USER" -f "$pat" 2>/dev/null || true
    done
}

echo "=== Cadence/OCEAN run setup ==="
echo "Repo:       $REPO"
echo "Source OCN: $SRC_OCN"
echo "Run dir:    $RUN_DIR"
echo "Output dir: $OUTPUT_DIR"
echo "Log dir:    $LOG_DIR"
echo "IPC dir:    $IPC_DIR"
echo

need_file "$SRC_OCN" "OCEAN script"

if [[ -e "$RUN_DIR" ]]; then
    echo "ERROR: run directory already exists: $RUN_DIR" >&2
    echo "Use a new RUN_ID/RUN_LABEL or remove the existing directory." >&2
    exit 1
fi

if [[ "$SKIP_KILL" == "1" ]]; then
    echo "=== Skipping stale process cleanup ==="
else
    echo "=== Killing stale batch processes ==="
    kill_stale_processes
    sleep 2
fi

echo "Remaining matching batch processes, if any:"
ps -fu "$USER" | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|pwl_apply_duo|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" | grep -v grep || true
echo

echo "=== Creating run directory layout ==="
run mkdir -p "$OUTPUT_DIR" "$LOG_DIR" "$IPC_DIR" "$RUN_OCN_DIR"

echo "=== Creating run-local OCEAN copy ==="
run cp "$SRC_OCN" "$RUN_OCN"
if [[ "$SKIP_OCN_PATCH" == "1" ]]; then
    echo "SKIP_OCN_PATCH=1, leaving outputBaseDir unchanged in $RUN_OCN"
elif [[ "$DRY_RUN" == "1" ]]; then
    echo "+ patch outputBaseDir in $RUN_OCN -> $OUTPUT_DIR"
else
    patch_ocn_output_dir "$RUN_OCN" "$OUTPUT_DIR"
fi

echo "Run OCEAN outputBaseDir line:"
grep -n "outputBaseDir" "$RUN_OCN" | head -5 || true
echo

echo "=== Preparing IPC job directories ==="
for i in $(seq 0 $((NUM_JOBS - 1))); do
    jobdir="$IPC_DIR/job$i"
    run mkdir -p "$jobdir"

    if [[ "$DRY_RUN" == "1" ]]; then
        echo "+ write $jobdir/cds.lib"
    else
        cat > "$jobdir/cds.lib" <<EOF_CDSLIB
INCLUDE $CDS_INCLUDE
DEFINE $DESIGN_LIB_NAME $DESIGN_LIB_PATH
DEFINE XFABLibs $XFAB_LIB_PATH
EOF_CDSLIB
    fi

    echo "job$i cds.lib:"
    ls -lh "$jobdir/cds.lib"
done
echo

echo "=== Writing run metadata ==="
if [[ "$DRY_RUN" == "1" ]]; then
    echo "+ write $RUN_DIR/RUNINFO.txt"
else
    cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUNINFO
Run ID: $RUN_ID
Run label: $RUN_LABEL
Created: $(date -Iseconds)
Repo: $REPO
Source OCN: $SRC_OCN
Run OCN: $RUN_OCN
Output dir: $OUTPUT_DIR
Log dir: $LOG_DIR
IPC dir: $IPC_DIR
NUM_JOBS: $NUM_JOBS
Expected output count: $EXPECTED_CASES
EOF_RUNINFO
fi
ls -lh "$RUN_DIR/RUNINFO.txt" 2>/dev/null || true
echo

echo "=== Copy/paste these CIW commands, preferably 10-20 seconds apart ==="
for i in $(seq 0 $((NUM_JOBS - 1))); do
    cat <<CMD
ipcBeginProcess("sh -c 'cd $IPC_DIR/job$i && env CAD_NUM_JOBS=$NUM_JOBS CAD_JOB_INDEX=$i CAD_BATCH_EXIT=1 CAD_RUN_DIR=$RUN_DIR CAD_OUTPUT_DIR=$OUTPUT_DIR ocean -nograph -restore $RUN_OCN > $LOG_DIR/ocean_apply_job$i.log 2>&1'")
CMD
    echo
done

cat <<EOF_HELP
=== Monitoring ===

Condensed live monitor:

tail -f $LOG_DIR/ocean_apply_job*.log \\
| grep -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired"

Check job partition summaries:

grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" \\
$LOG_DIR/ocean_apply_job*.log

Count completed outputs:

find $OUTPUT_DIR -name output_signals.txt | wc -l

Live progress bar:

watch -n 10 'n=\$(find "$OUTPUT_DIR" -name output_signals.txt | wc -l); total=$EXPECTED_CASES; width=60; filled=\$((n*width/total)); empty=\$((width-filled)); bar=\$(printf "%0.s#" \$(seq 1 \$filled)); space=\$(printf "%0.s-" \$(seq 1 \$empty)); pct=\$(awk -v n=\$n -v t=\$total "BEGIN {printf \\\"%.2f\\\", 100*n/t}"); printf "[%s%s] %s/%s complete (%s%%)\\n" "\$bar" "\$space" "\$n" "\$total" "\$pct"'

Run directory:
$RUN_DIR
EOF_HELP
