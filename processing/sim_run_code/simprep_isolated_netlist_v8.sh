#!/usr/bin/env bash
set -euo pipefail

# Prepare a Cadence/OCEAN IPC run with run-local output/log/ipc directories
# and per-job Cadence project directories. The per-job projectDir() isolation
# prevents parallel OCEAN jobs from sharing/corrupting the same netlist/control
# files under ~/simulation/<cell>/spectre/schematic/netlist.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Prefer an explicitly provided REPO. Otherwise use git. If the script has been
# accidentally copied into a nested thesis_codebase/thesis_codebase tree, prefer
# the outer thesis_codebase when it contains the expected repository layout.
if [[ -z "${REPO:-}" ]]; then
  if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
    REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
  else
    REPO="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  fi
fi

if [[ "$(basename "$REPO")" == "thesis_codebase" && "$(basename "$(dirname "$REPO")")" == "thesis_codebase" ]]; then
  OUTER_REPO="$(dirname "$REPO")"
  if [[ -d "$OUTER_REPO/processing/sim_run_code" && -d "$OUTER_REPO/thesis_database" ]]; then
    echo "NOTE: detected nested thesis_codebase path; using outer repo: $OUTER_REPO" >&2
    REPO="$OUTER_REPO"
  fi
fi

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
CADENCE_PROJECT_DIR="${CADENCE_PROJECT_DIR:-$RUN_DIR/cadence_project}"
RUN_OCN_DIR="${RUN_OCN_DIR:-$RUN_DIR/ocn}"
RUN_OCN="$RUN_OCN_DIR/$(basename "$SRC_OCN")"

NUM_JOBS="${NUM_JOBS:-4}"
TOTAL_CASES="${TOTAL_CASES:-auto}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_KILL="${SKIP_KILL:-0}"

CDS_INCLUDE="${CDS_INCLUDE:-/home/s5117909/eda_env/xp018/cds.lib}"
DESIGN_LIB_NAME="${DESIGN_LIB_NAME:-sebastian_thesis_pilot}"
DESIGN_LIB_PATH="${DESIGN_LIB_PATH:-/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot}"
XFAB_LIB_PATH="${XFAB_LIB_PATH:-/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs}"

run() {
  echo "+ $*"
  [[ "$DRY_RUN" == "1" ]] || "$@"
}

need_file() { [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_dir()  { [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

kill_stale_processes() {
  local patterns=(
    "CAD_JOB_INDEX" "ocean -nograph" "virtuoso -ocean" "cdsXvfb-run"
    "runSimulation" "spectre input.scs" "spectre_encrypt" "tail -f .*ocean"
  )
  for pat in "${patterns[@]}"; do
    echo "+ pkill -u \"$USER\" -f \"$pat\""
    [[ "$DRY_RUN" == "1" ]] || pkill -u "$USER" -f "$pat" 2>/dev/null || true
  done
}

show_matching_processes() {
  ps -fu "$USER" \
    | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso -ocean|tail -f .*ocean" \
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
  [[ -n "$first_st1" ]] || { echo "ERROR: no frequency directories found in $st1_dir" >&2; exit 1; }

  TRIALS_PER_FREQ="$(find "$first_st1" -maxdepth 1 -type f -name 'trial_*.pwl' | wc -l | tr -d ' ')"
  [[ "$TRIALS_PER_FREQ" -gt 0 ]] || { echo "ERROR: no trial_*.pwl files found in $first_st1" >&2; exit 1; }

  COMPUTED_CASES=$(( ST1_COUNT * ST2_COUNT * TRIALS_PER_FREQ ))
}

patch_run_ocn() {
  local file="$1"
  local repo="$2"
  local spike_root="$3"
  local output_dir="$4"

  python3 - "$file" "$repo" "$spike_root" "$output_dir" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
repo, spike_root, output_dir = sys.argv[2:5]
text = path.read_text()

# Keep the run-local copy deterministic and inspectable.
text = re.sub(r'baseRepoDir\s*=\s*"[^"]*"', f'baseRepoDir = "{repo}"', text, count=1)
text = re.sub(r'outputBaseDir\s*=\s*strcat\([^\)]*\)', f'outputBaseDir = "{output_dir}"', text, count=1)

injection = f'''
; --- BEGIN shell-prep path and projectDir overrides ---
; Supplied by simprep_isolated_netlist_v8.sh in the generated CIW commands.
; CAD_PROJECT_DIR is job-specific. This is the critical parallel-netlisting fix.

cadSpikeDir = getShellEnvVar("CAD_SPIKE_DIR")
when(cadSpikeDir
  pwlBaseDir = cadSpikeDir
  st1BaseDir = strcat(pwlBaseDir "/st_1")
  st2BaseDir = strcat(pwlBaseDir "/st_2")
)

cadOutputDir = getShellEnvVar("CAD_OUTPUT_DIR")
when(cadOutputDir
  outputBaseDir = cadOutputDir
)

cadRunDir = getShellEnvVar("CAD_RUN_DIR")
when(cadRunDir
  printf("CAD_RUN_DIR=%s\\n" cadRunDir)
)

cadProjectDir = getShellEnvVar("CAD_PROJECT_DIR")
when(cadProjectDir
  system(strcat("mkdir -p \"" cadProjectDir "\""))
  projectDir(cadProjectDir)
  printf("Using isolated Cadence projectDir: %s\\n" cadProjectDir)
)

printf("Using PWL base directory: %s\\n" pwlBaseDir)
printf("Using output base directory: %s\\n" outputBaseDir)
; --- END shell-prep path and projectDir overrides ---
'''

if 'BEGIN shell-prep path and projectDir overrides' not in text:
    if '; Sanity checks' in text:
        text = text.replace('; Sanity checks', injection + '\n; Sanity checks', 1)
    elif 'unless(isDir(st1BaseDir)' in text:
        text = text.replace('unless(isDir(st1BaseDir)', injection + '\nunless(isDir(st1BaseDir)', 1)
    elif "analysis('tran" in text:
        text = text.replace("analysis('tran", injection + "\nanalysis('tran", 1)
    else:
        raise SystemExit('Could not find insertion point for path/projectDir override block.')

path.write_text(text)
PY
}

echo "=== Cadence/OCEAN isolated-netlist run setup ==="
echo "Repo:                $REPO"
echo "Code dir:            $CODE_DIR"
echo "Source OCN:          $SRC_OCN"
echo "Spike root:          $SPIKE_ROOT"
echo "Run dir:             $RUN_DIR"
echo "Output dir:          $OUTPUT_DIR"
echo "Log dir:             $LOG_DIR"
echo "IPC dir:             $IPC_DIR"
echo "Cadence project dir: $CADENCE_PROJECT_DIR"
echo "NUM_JOBS:            $NUM_JOBS"
echo

need_file "$SRC_OCN" "OCEAN script"
need_dir "$SPIKE_ROOT" "spike_train_output root"
compute_total_cases
[[ "$TOTAL_CASES" == "auto" ]] && TOTAL_CASES="$COMPUTED_CASES"

if [[ "$NUM_JOBS" -le 0 ]]; then
  echo "ERROR: NUM_JOBS must be positive." >&2
  exit 1
fi

if [[ -e "$RUN_DIR" ]]; then
  echo "ERROR: run directory already exists: $RUN_DIR" >&2
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
show_matching_processes
echo

echo "=== Input summary ==="
printf "st_1 frequency dirs: %s\n" "$ST1_COUNT"
printf "st_2 frequency dirs: %s\n" "$ST2_COUNT"
printf "trials per frequency: %s\n" "$TRIALS_PER_FREQ"
printf "computed cases: %s\n" "$COMPUTED_CASES"
printf "total cases used for monitoring: %s\n" "$TOTAL_CASES"
printf "approx. cases/job: %s\n" "$(( (TOTAL_CASES + NUM_JOBS - 1) / NUM_JOBS ))"
echo

echo "=== Creating run layout ==="
run mkdir -p "$OUTPUT_DIR" "$LOG_DIR" "$IPC_DIR" "$RUN_OCN_DIR" "$CADENCE_PROJECT_DIR"

run cp "$SRC_OCN" "$RUN_OCN"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "+ patch run-local OCN paths/projectDir in $RUN_OCN"
else
  patch_run_ocn "$RUN_OCN" "$REPO" "$SPIKE_ROOT" "$OUTPUT_DIR"
fi

echo "Run-local OCN patch lines:"
grep -nE "CAD_SPIKE_DIR|CAD_OUTPUT_DIR|CAD_PROJECT_DIR|projectDir|pwlBaseDir|st1BaseDir|st2BaseDir|outputBaseDir" "$RUN_OCN" | head -50 || true
echo

echo "=== Preparing IPC job directories and isolated Cadence project directories ==="
for i in $(seq 0 $((NUM_JOBS - 1))); do
  jobdir="$IPC_DIR/job$i"
  projdir="$CADENCE_PROJECT_DIR/job$i"
  run mkdir -p "$jobdir" "$projdir"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "+ write $jobdir/cds.lib"
  else
    cat > "$jobdir/cds.lib" <<EOF_CDS
INCLUDE $CDS_INCLUDE
DEFINE $DESIGN_LIB_NAME $DESIGN_LIB_PATH
SOFTINCLUDE $XFAB_LIB_PATH/cds.lib
EOF_CDS
  fi
done

RUNINFO="$RUN_DIR/RUNINFO.txt"
CIW_COMMANDS="$RUN_DIR/ciw_commands.il"
MONITOR="$RUN_DIR/monitoring_commands.sh"

if [[ "$DRY_RUN" != "1" ]]; then
  cat > "$RUNINFO" <<EOF_INFO
RUN_ID=$RUN_ID
RUN_LABEL=$RUN_LABEL
REPO=$REPO
SRC_OCN=$SRC_OCN
RUN_OCN=$RUN_OCN
SPIKE_ROOT=$SPIKE_ROOT
OUTPUT_DIR=$OUTPUT_DIR
LOG_DIR=$LOG_DIR
IPC_DIR=$IPC_DIR
CADENCE_PROJECT_DIR=$CADENCE_PROJECT_DIR
NUM_JOBS=$NUM_JOBS
ST1_COUNT=$ST1_COUNT
ST2_COUNT=$ST2_COUNT
TRIALS_PER_FREQ=$TRIALS_PER_FREQ
TOTAL_CASES=$TOTAL_CASES
CREATED_AT=$(date -Is)
EOF_INFO

  {
    echo "; CIW launch commands for $RUN_ID"
    echo "; Paste into CIW, preferably 10-20 seconds apart."
    echo "; Each job gets its own CAD_PROJECT_DIR to isolate netlisting/control files."
    echo
    for i in $(seq 0 $((NUM_JOBS - 1))); do
      printf 'ipcBeginProcess("sh -c '\''cd %s/job%d && env CAD_NUM_JOBS=%s CAD_JOB_INDEX=%d CAD_BATCH_EXIT=1 CAD_RUN_DIR=%s CAD_OUTPUT_DIR=%s CAD_SPIKE_DIR=%s CAD_PROJECT_DIR=%s/job%d ocean -nograph -restore %s > %s/ocean_apply_job%d.log 2>&1'\''")\n\n' \
        "$IPC_DIR" "$i" "$NUM_JOBS" "$i" "$RUN_DIR" "$OUTPUT_DIR" "$SPIKE_ROOT" "$CADENCE_PROJECT_DIR" "$i" "$RUN_OCN" "$LOG_DIR" "$i"
    done
  } > "$CIW_COMMANDS"

  cat > "$MONITOR" <<EOF_MON
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$RUN_DIR"
OUTPUT_DIR="$OUTPUT_DIR"
LOG_DIR="$LOG_DIR"
TOTAL_CASES="$TOTAL_CASES"
NUM_JOBS="$NUM_JOBS"

expected_for_job() {
  local j="\$1"
  if (( j >= TOTAL_CASES )); then
    echo 0
  else
    echo \$(( (TOTAL_CASES - 1 - j) / NUM_JOBS + 1 ))
  fi
}

case "\${1:-summary}" in
  tail)
    tail -f "\$LOG_DIR"/ocean_apply_job*.log ;;
  condensed)
    tail -f "\$LOG_DIR"/ocean_apply_job*.log \
      | grep -iE "spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|tran are not available|CAD_BATCH_EXIT|Key has expired|Total valid cases seen|Cases assigned|Cases skipped|syntax error|eval: not a function" ;;
  count)
    find "\$OUTPUT_DIR" -name output_signals.txt | wc -l ;;
  jobs)
    for j in \$(seq 0 \$((NUM_JOBS - 1))); do
      log="\$LOG_DIR/ocean_apply_job\$j.log"
      done_count=0
      last_write="missing"
      [[ -f "\$log" ]] && done_count=\$(grep -c "^Finished:" "\$log" || true)
      [[ -f "\$log" ]] && last_write=\$(stat -c "%y" "\$log" | cut -d. -f1)
      expected=\$(expected_for_job "\$j")
      printf "job%-3s %5s / %-5s finished   last_write=%s\\n" "\$j" "\$done_count" "\$expected" "\$last_write"
    done ;;
  progress)
    watch -n 10 "n=\$(find '$OUTPUT_DIR' -name output_signals.txt | wc -l); total=$TOTAL_CASES; width=50; filled=\$((n*width/total)); empty=\$((width-filled)); bar=\$(printf '%0.s#' \$(seq 1 \$filled)); space=\$(printf '%0.s-' \$(seq 1 \$empty)); pct=\$(awk -v n=\$n -v t=\$total 'BEGIN {printf \"%.2f\", 100*n/t}'); printf '[%s%s] %s/%s complete (%s%%)\\n' \"\$bar\" \"\$space\" \"\$n\" \"\$total\" \"\$pct\"; echo; '$MONITOR' jobs" ;;
  *)
    echo "RUN_DIR=\$RUN_DIR"
    echo "output count: \$(find "\$OUTPUT_DIR" -name output_signals.txt | wc -l) / \$TOTAL_CASES"
    echo
    "\$0" jobs
    echo
    grep -H -E "Total valid cases seen|Cases assigned|Cases skipped|Finished assigned" "\$LOG_DIR"/ocean_apply_job*.log 2>/dev/null || true ;;
esac
EOF_MON
  chmod +x "$MONITOR"
fi

echo "=== Created ==="
echo "Run dir:       $RUN_DIR"
echo "Run OCN:       $RUN_OCN"
echo "CIW commands:  $CIW_COMMANDS"
echo "Monitor:       $MONITOR"
echo

echo "=== Paste these into CIW ==="
if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1; CIW file not written."
else
  cat "$CIW_COMMANDS"
fi
