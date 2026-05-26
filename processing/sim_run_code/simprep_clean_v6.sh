#!/usr/bin/env bash
set -euo pipefail

# Prepare a Cadence/OCEAN IPC run.
# Run from anywhere inside the repo, or set REPO=/path/to/thesis_codebase.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/../.." && pwd -P)}"
CODE_DIR="${CODE_DIR:-$REPO/processing/sim_run_code}"
DATABASE_DIR="${DATABASE_DIR:-$REPO/thesis_database}"

OCN_NAME="${OCN_NAME:-pwl_1synv3.ocn}"
SRC_OCN="${SRC_OCN:-$CODE_DIR/ocn_scripts/$OCN_NAME}"
SPIKE_ROOT="${SPIKE_ROOT:-$CODE_DIR/spike_train_output}"

RUN_LABEL="${RUN_LABEL:-2channel_1syn}"
RUN_LABEL_SAFE="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_//;s/_$//')"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_${RUN_LABEL_SAFE}}"
RUN_DIR="${RUN_DIR:-$DATABASE_DIR/$RUN_ID}"

OUTPUT_NAME="${OUTPUT_NAME:-output_2channel_1syn_data}"
OUTPUT_DIR="${OUTPUT_DIR:-$RUN_DIR/$OUTPUT_NAME}"
LOG_DIR="${LOG_DIR:-$RUN_DIR/logs}"
IPC_DIR="${IPC_DIR:-$RUN_DIR/ipc_work}"
RUN_OCN_DIR="${RUN_OCN_DIR:-$RUN_DIR/ocn}"
RUN_OCN="${RUN_OCN:-$RUN_OCN_DIR/$OCN_NAME}"

NUM_JOBS="${NUM_JOBS:-4}"
TOTAL_CASES="${TOTAL_CASES:-auto}"
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

need_dir() {
    [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }
}

resolve_source_ocn() {
    [[ -f "$SRC_OCN" ]] && return 0

    local candidate
    candidate="$(find "$CODE_DIR" -type f -name "$OCN_NAME" 2>/dev/null | sort | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
        echo "WARNING: configured OCN path not found; using discovered file:" >&2
        echo "  $candidate" >&2
        SRC_OCN="$candidate"
        RUN_OCN="$RUN_OCN_DIR/$(basename "$SRC_OCN")"
        return 0
    fi

    echo "ERROR: missing OCEAN script: $SRC_OCN" >&2
    echo "Checked CODE_DIR: $CODE_DIR" >&2
    echo "Repository may be stale. Try:" >&2
    echo "  cd $REPO && git pull" >&2
    echo "Or override explicitly:" >&2
    echo "  SRC_OCN=/full/path/to/$OCN_NAME $0" >&2
    exit 1
}

patch_ocn_output_dir() {
    local file="$1" outdir="$2"
    if ! grep -qE '^[[:space:]]*outputBaseDir[[:space:]]*=' "$file"; then
        echo "WARNING: no outputBaseDir assignment found in $file; not patched." >&2
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

process_check() {
    ps -fu "$USER" \
    | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_2syn|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" \
    | grep -v grep || true
}

compute_total_cases() {
    local st1_dir="$SPIKE_ROOT/st_1"
    local st2_dir="$SPIKE_ROOT/st_2"
    need_dir "$st1_dir" "st_1 spike-train directory"
    need_dir "$st2_dir" "st_2 spike-train directory"

    ST1_COUNT="$(find "$st1_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
    ST2_COUNT="$(find "$st2_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"

    local first_st1
    first_st1="$(find "$st1_dir" -mindepth 1 -maxdepth 1 -type d | sort -V | head -n 1)"
    [[ -n "$first_st1" ]] || { echo "ERROR: no frequency directories in $st1_dir" >&2; exit 1; }

    TRIALS_PER_FREQ="$(find "$first_st1" -maxdepth 1 -type f -name 'trial_*.pwl' | wc -l | tr -d ' ')"
    [[ "$TRIALS_PER_FREQ" -gt 0 ]] || { echo "ERROR: no trial_*.pwl files in $first_st1" >&2; exit 1; }

    COMPUTED_CASES=$(( ST1_COUNT * ST2_COUNT * TRIALS_PER_FREQ ))
}

write_cds_lib() {
    local out="$1"
    cat > "$out" <<EOF_CDSLIB
INCLUDE $CDS_INCLUDE
DEFINE $DESIGN_LIB_NAME $DESIGN_LIB_PATH
DEFINE XFABLibs $XFAB_LIB_PATH
EOF_CDSLIB
}

write_ciw_commands() {
    local out="$1"
    : > "$out"
    {
        echo "; CIW launch commands for $RUN_ID"
        echo "; Copy/paste into CIW, preferably 10-20 seconds apart."
        echo
        for i in $(seq 0 $((NUM_JOBS - 1))); do
            printf 'ipcBeginProcess("sh -c '\''cd %s/job%d && env CAD_NUM_JOBS=%s CAD_JOB_INDEX=%d CAD_BATCH_EXIT=1 CAD_RUN_DIR=%s CAD_OUTPUT_DIR=%s ocean -nograph -restore %s > %s/ocean_apply_job%d.log 2>&1'\''")\n\n' \
                "$IPC_DIR" "$i" "$NUM_JOBS" "$i" "$RUN_DIR" "$OUTPUT_DIR" "$RUN_OCN" "$LOG_DIR" "$i"
        done
    } > "$out"
}

write_monitoring_script() {
    local out="$1"
    cat > "$out" <<EOF_MONITOR
#!/usr/bin/env bash
set -euo pipefail
LOG_DIR="$LOG_DIR"
OUTPUT_DIR="$OUTPUT_DIR"
TOTAL_CASES="$TOTAL_CASES"

echo "Completed outputs:"
find "\$OUTPUT_DIR" -name output_signals.txt | wc -l

echo
echo "Job partition summaries:"
grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" "\$LOG_DIR"/ocean_apply_job*.log 2>/dev/null || true

echo
echo "Recent condensed log lines:"
grep -h -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired" "\$LOG_DIR"/ocean_apply_job*.log 2>/dev/null | tail -120 || true

echo
echo "Progress bar:"
echo "watch -n 10 'n=\$(find \"$OUTPUT_DIR\" -name output_signals.txt | wc -l); total=$TOTAL_CASES; width=60; filled=\$((n*width/total)); empty=\$((width-filled)); bar=\$(printf \"%0.s#\" \$(seq 1 \$filled)); space=\$(printf \"%0.s-\" \$(seq 1 \$empty)); pct=\$(awk -v n=\$n -v t=\$total \"BEGIN {printf \\\"%.2f\\\", 100*n/t}\"); printf \"[%s%s] %s/%s complete (%s%%)\\n\" \"\$bar\" \"\$space\" \"\$n\" \"\$total\" \"\$pct\"'"
EOF_MONITOR
    chmod +x "$out"
}

resolve_source_ocn
compute_total_cases
[[ "$TOTAL_CASES" == "auto" ]] && TOTAL_CASES="$COMPUTED_CASES"

if ! [[ "$NUM_JOBS" =~ ^[0-9]+$ ]] || [[ "$NUM_JOBS" -lt 1 ]]; then
    echo "ERROR: NUM_JOBS must be a positive integer." >&2
    exit 1
fi

if [[ -e "$RUN_DIR" ]]; then
    echo "ERROR: run directory already exists: $RUN_DIR" >&2
    exit 1
fi

cat <<EOF_SUMMARY
=== Cadence/OCEAN run setup ===
Repo:        $REPO
Source OCN:  $SRC_OCN
Spike root:  $SPIKE_ROOT
Run dir:     $RUN_DIR
Output dir:  $OUTPUT_DIR
Log dir:     $LOG_DIR
IPC dir:     $IPC_DIR
NUM_JOBS:    $NUM_JOBS
Total cases: $TOTAL_CASES
EOF_SUMMARY

echo
if [[ "$SKIP_KILL" != "1" ]]; then
    echo "=== Killing stale batch processes ==="
    kill_stale_processes
    sleep 2
else
    echo "=== Skipping stale process cleanup ==="
fi

echo "Remaining matching batch processes, if any:"
process_check

echo
echo "=== Input summary ==="
printf "st_1 frequency dirs: %s\n" "$ST1_COUNT"
printf "st_2 frequency dirs: %s\n" "$ST2_COUNT"
printf "trials per frequency: %s\n" "$TRIALS_PER_FREQ"
printf "computed cases: %s\n" "$COMPUTED_CASES"
printf "approx. cases/job: %s\n" "$(( (TOTAL_CASES + NUM_JOBS - 1) / NUM_JOBS ))"

if (( TOTAL_CASES % NUM_JOBS != 0 )); then
    echo "WARNING: TOTAL_CASES=$TOTAL_CASES is not divisible by NUM_JOBS=$NUM_JOBS." >&2
fi

echo
echo "=== Creating run directory layout ==="
run mkdir -p "$OUTPUT_DIR" "$LOG_DIR" "$IPC_DIR" "$RUN_OCN_DIR"

echo "=== Creating run-local OCEAN copy ==="
run cp "$SRC_OCN" "$RUN_OCN"
if [[ "$SKIP_OCN_PATCH" != "1" && "$DRY_RUN" != "1" ]]; then
    patch_ocn_output_dir "$RUN_OCN" "$OUTPUT_DIR"
elif [[ "$SKIP_OCN_PATCH" == "1" ]]; then
    echo "SKIP_OCN_PATCH=1, outputBaseDir unchanged."
else
    echo "+ patch outputBaseDir in $RUN_OCN -> $OUTPUT_DIR"
fi
grep -n "outputBaseDir" "$RUN_OCN" 2>/dev/null | head -5 || true

echo
echo "=== Preparing IPC job directories ==="
for i in $(seq 0 $((NUM_JOBS - 1))); do
    jobdir="$IPC_DIR/job$i"
    run mkdir -p "$jobdir"
    if [[ "$DRY_RUN" == "1" ]]; then
        echo "+ write $jobdir/cds.lib"
    else
        write_cds_lib "$jobdir/cds.lib"
    fi
done

CIW_COMMANDS_FILE="$RUN_DIR/ciw_commands.il"
MONITOR_FILE="$RUN_DIR/monitoring_commands.sh"

echo
echo "=== Writing metadata and helper files ==="
if [[ "$DRY_RUN" == "1" ]]; then
    echo "+ write $RUN_DIR/RUNINFO.txt"
    echo "+ write $CIW_COMMANDS_FILE"
    echo "+ write $MONITOR_FILE"
else
    cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUNINFO
Run ID: $RUN_ID
Run label: $RUN_LABEL
Created: $(date -Iseconds)
Repo: $REPO
Source OCN: $SRC_OCN
Run OCN: $RUN_OCN
Spike root: $SPIKE_ROOT
st_1 frequency dirs: $ST1_COUNT
st_2 frequency dirs: $ST2_COUNT
Trials per frequency: $TRIALS_PER_FREQ
Computed cases: $COMPUTED_CASES
Total cases used for progress: $TOTAL_CASES
Output dir: $OUTPUT_DIR
Log dir: $LOG_DIR
IPC dir: $IPC_DIR
NUM_JOBS: $NUM_JOBS
EOF_RUNINFO
    write_ciw_commands "$CIW_COMMANDS_FILE"
    write_monitoring_script "$MONITOR_FILE"
fi

echo
echo "=== CIW command file ==="
echo "$CIW_COMMANDS_FILE"
[[ "$DRY_RUN" == "1" ]] || cat "$CIW_COMMANDS_FILE"

echo "=== Monitoring helper ==="
echo "$MONITOR_FILE"
echo
echo "Run directory: $RUN_DIR"
