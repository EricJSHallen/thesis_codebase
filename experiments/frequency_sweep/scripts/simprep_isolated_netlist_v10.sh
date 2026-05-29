#!/usr/bin/env bash
set -euo pipefail

# simprep_isolated_netlist_v10.sh
# Clean Cadence/OCEAN IPC run setup for thesis_codebase.
# Fixes v9 issue: projectDir must be set before design()/netlisting, not later.
# Also caches ade_e.scs into the run directory and runs a helper that copies it
# into any netlist directory containing input.scs.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

if [[ -z "${REPO:-}" ]]; then
  if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
    REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
  else
    REPO="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  fi
fi

# If accidentally inside thesis_codebase/thesis_codebase, prefer the outer repo if it looks valid.
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
SUPPORT_DIR="${SUPPORT_DIR:-$RUN_DIR/support}"
RUN_OCN="$RUN_OCN_DIR/$(basename "$SRC_OCN")"

NUM_JOBS="${NUM_JOBS:-4}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_KILL="${SKIP_KILL:-0}"

CDS_INCLUDE="${CDS_INCLUDE:-/home/s5117909/eda_env/xp018/cds.lib}"
DESIGN_LIB_NAME="${DESIGN_LIB_NAME:-sebastian_thesis_pilot}"
DESIGN_LIB_PATH="${DESIGN_LIB_PATH:-/home/s5117909/Desktop/cadence_lib/sebastian_thesis_pilot}"
XFAB_LIB_PATH="${XFAB_LIB_PATH:-/projects/bics/designkits/fab/x_all/cadence/xenv/v1_2_52/libs/XFABLibs}"

# Stable source preferred. This is copied into RUN_DIR/support/ade_e.scs before jobs start.
DEFAULT_ADE_E="/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs"
ADE_E_SOURCE="${ADE_E_SOURCE:-}"
GLOBAL_NETLIST_DIR="${GLOBAL_NETLIST_DIR:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"

run() {
  echo "+ $*"
  [[ "$DRY_RUN" == "1" ]] || "$@"
}

need_file() { [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_dir()  { [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

kill_stale_processes() {
  local patterns=(
    "CAD_JOB_INDEX"
    "ocean_apply_job"
    "ocean -nograph"
    "virtuoso.*-ocean"
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

show_matching_processes() {
  ps -fu "$USER" \
    | grep -E "CAD_JOB_INDEX|ocean_apply_job|pwl_1syn|pwl_apply|spectre input.scs|spectre_encrypt|runSimulation|cdsXvfb-run|virtuoso.*-ocean|tail -f .*ocean" \
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

resolve_ade_e_source() {
  if [[ -n "$ADE_E_SOURCE" ]]; then
    need_file "$ADE_E_SOURCE" "ADE_E_SOURCE"
    return
  fi

  if [[ -f "$DEFAULT_ADE_E" ]]; then
    ADE_E_SOURCE="$DEFAULT_ADE_E"
    return
  fi

  ADE_E_SOURCE="$(find /home/s5117909/simulation -path '*synapsedualinputtb*spectre/schematic/netlist/ade_e.scs' -print 2>/dev/null | head -n 1 || true)"
  if [[ -z "$ADE_E_SOURCE" ]]; then
    ADE_E_SOURCE="$(find /home/s5117909/simulation -name ade_e.scs -print 2>/dev/null | head -n 1 || true)"
  fi
  if [[ -z "$ADE_E_SOURCE" || ! -f "$ADE_E_SOURCE" ]]; then
    echo "ERROR: could not find ade_e.scs automatically." >&2
    echo "Set ADE_E_SOURCE=/full/path/to/ade_e.scs and rerun." >&2
    exit 1
  fi
}

patch_run_ocn() {
  local file="$1"
  local repo="$2"
  local output_dir="$3"

  python3 - "$file" "$repo" "$output_dir" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
repo, output_dir = sys.argv[2:4]
text = path.read_text()

# Remove prior injected blocks from old prep versions.
text = re.sub(
    r'\n?; --- BEGIN shell-prep early projectDir override ---.*?; --- END shell-prep early projectDir override ---\s*',
    '\n',
    text,
    flags=re.S,
)
text = re.sub(
    r'\n?; --- BEGIN shell-prep path and projectDir overrides ---.*?; --- END shell-prep path and projectDir overrides ---\s*',
    '\n',
    text,
    flags=re.S,
)
text = re.sub(
    r'\n?; --- BEGIN shell-prep path overrides ---.*?; --- END shell-prep path overrides ---\s*',
    '\n',
    text,
    flags=re.S,
)

# Patch manual defaults for direct inspection.
text = re.sub(r'baseRepoDir\s*=\s*"[^"]*"', f'baseRepoDir = "{repo}"', text, count=1)
text = re.sub(r'outputBaseDir\s*=\s*strcat\([^\)]*\)', f'outputBaseDir = "{output_dir}"', text, count=1)

# Critical: set projectDir before simulator/design/netlisting setup.
early = r'''; --- BEGIN shell-prep early projectDir override ---
; Must run before design()/netlisting. Supplied by simprep_isolated_netlist_v10.sh.
cadProjectDir = getShellEnvVar("CAD_PROJECT_DIR")
when(cadProjectDir
  envSetVal("asimenv.startup" "projectDir" 'string cadProjectDir)
  printf("Using isolated Cadence projectDir early: %s\n" cadProjectDir)
)
; --- END shell-prep early projectDir override ---

'''
text = early + text.lstrip()

# Late path overrides after pwlBaseDir/outputBaseDir variables exist.
late = r'''; --- BEGIN shell-prep path overrides ---
; Supplied by simprep_isolated_netlist_v10.sh in generated wrapper commands.

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
  printf("CAD_RUN_DIR=%s\n" cadRunDir)
)

printf("Using PWL base directory: %s\n" pwlBaseDir)
printf("Using output base directory: %s\n" outputBaseDir)
; --- END shell-prep path overrides ---
'''

if '; Sanity checks' in text:
    text = text.replace('; Sanity checks', late + '\n; Sanity checks', 1)
elif 'unless(isDir(st1BaseDir)' in text:
    text = text.replace('unless(isDir(st1BaseDir)', late + '\nunless(isDir(st1BaseDir)', 1)
elif "analysis('tran" in text:
    text = text.replace("analysis('tran", late + "\nanalysis('tran", 1)
else:
    raise SystemExit('Could not find insertion point for path override block.')

path.write_text(text)
PY
}

write_cds_lib() {
  local jobdir="$1"
  cat > "$jobdir/cds.lib" <<EOF_CDS
INCLUDE $CDS_INCLUDE
DEFINE $DESIGN_LIB_NAME $DESIGN_LIB_PATH
SOFTINCLUDE $XFAB_LIB_PATH/cds.lib
EOF_CDS
}

write_run_wrapper() {
  local wrapper="$RUN_DIR/run_ocean_job.sh"
  cat > "$wrapper" <<EOF_WRAP
#!/usr/bin/env bash
set -euo pipefail

job_index="\${1:?usage: \$0 JOB_INDEX}"

RUN_DIR="$RUN_DIR"
LOG_DIR="$LOG_DIR"
IPC_DIR="$IPC_DIR"
RUN_OCN="$RUN_OCN"
OUTPUT_DIR="$OUTPUT_DIR"
SPIKE_ROOT="$SPIKE_ROOT"
CADENCE_PROJECT_DIR="$CADENCE_PROJECT_DIR"
ADE_E_CACHE="$SUPPORT_DIR/ade_e.scs"
GLOBAL_NETLIST_DIR="$GLOBAL_NETLIST_DIR"
NUM_JOBS="$NUM_JOBS"

jobdir="\$IPC_DIR/job\$job_index"
projdir="\$CADENCE_PROJECT_DIR/job\$job_index"
log="\$LOG_DIR/ocean_apply_job\$job_index.log"

mkdir -p "\$jobdir" "\$projdir" "\$LOG_DIR"

# Copy cached ade_e.scs into every current/future directory containing input.scs.
# This includes the desired per-job project directory and the legacy/global Cadence
# netlist directory if this Cadence environment still uses it despite projectDir.
ade_helper() {
  while true; do
    for root in "\$projdir" "\$RUN_DIR" "\$GLOBAL_NETLIST_DIR"; do
      [ -d "\$root" ] || continue
      find "\$root" -name input.scs -type f 2>/dev/null | while read -r input; do
        d=\$(dirname "\$input")
        cp -f "\$ADE_E_CACHE" "\$d/ade_e.scs" 2>/dev/null || true
      done
      # Also seed obvious netlist dirs before input.scs appears.
      find "\$root" -type d \( -name netlist -o -path '*spectre/schematic/netlist' \) 2>/dev/null | while read -r d; do
        cp -f "\$ADE_E_CACHE" "\$d/ade_e.scs" 2>/dev/null || true
      done
    done
    sleep 0.2
  done
}

ade_helper &
helper_pid=\$!
cleanup() {
  kill "\$helper_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "\$jobdir"

env CAD_NUM_JOBS="\$NUM_JOBS" \
    CAD_JOB_INDEX="\$job_index" \
    CAD_BATCH_EXIT=1 \
    CAD_RUN_DIR="\$RUN_DIR" \
    CAD_OUTPUT_DIR="\$OUTPUT_DIR" \
    CAD_SPIKE_DIR="\$SPIKE_ROOT" \
    CAD_PROJECT_DIR="\$projdir" \
    ADE_E_CACHE="\$ADE_E_CACHE" \
    ocean -nograph -restore "\$RUN_OCN" > "\$log" 2>&1
EOF_WRAP
  chmod +x "$wrapper"
}

write_ciw_commands() {
  local ciw="$RUN_DIR/ciw_commands.il"
  {
    echo "; CIW launch commands for $RUN_ID"
    echo "; Paste into CIW, preferably 10-20 seconds apart while testing."
    echo "; Per-job wrapper handles CAD_PROJECT_DIR and ade_e.scs seeding."
    for i in $(seq 0 $((NUM_JOBS - 1))); do
      printf 'ipcBeginProcess("sh -c '\''%s/run_ocean_job.sh %d'\''")\n' "$RUN_DIR" "$i"
    done
  } > "$ciw"
}

write_monitoring_commands() {
  local mon="$RUN_DIR/monitoring_commands.sh"
  cat > "$mon" <<EOF_MON
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$RUN_DIR"
OUTPUT_DIR="$OUTPUT_DIR"
LOG_DIR="$LOG_DIR"
TOTAL_CASES="$COMPUTED_CASES"
cd "\$RUN_DIR"

case "\${1:-summary}" in
  tail)
    tail -f "\$LOG_DIR"/ocean_apply_job*.log ;;
  condensed)
    tail -f "\$LOG_DIR"/ocean_apply_job*.log | grep -iE "Using isolated Cadence projectDir|spectre completes|Simulation completed successfully|Finished:|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot find|Cannot open|syntax error|lineread|eval: not a function|undefined function|Key has expired" ;;
  count)
    find "\$OUTPUT_DIR" -name output_signals.txt | wc -l ;;
  jobs)
    for j in \\$(seq 0 $((NUM_JOBS - 1))); do
      log="\$LOG_DIR/ocean_apply_job\$j.log"
      finished=\$(grep -c "^Finished:" "\$log" 2>/dev/null || echo 0)
      total_seen=\$(grep -m1 "Total valid cases seen" "\$log" 2>/dev/null | grep -oE "[0-9]+" | tail -1)
      assigned=\$(grep -m1 "Cases assigned to this process" "\$log" 2>/dev/null | grep -oE "[0-9]+" | tail -1)
      mtime=\$(stat -c "%y" "\$log" 2>/dev/null | cut -d. -f1)
      [ -z "\$total_seen" ] && total_seen="not_printed_yet"
      [ -z "\$assigned" ] && assigned="not_printed_yet"
      printf "job%s  finished=%-5s assigned=%-16s total_seen=%-16s last_write=%s\\n" "\$j" "\$finished" "\$assigned" "\$total_seen" "\$mtime"
    done ;;
  progress)
    watch -n 10 'for j in $(seq 0 $((NUM_JOBS - 1))); do log="logs/ocean_apply_job$j.log"; finished=$(grep -c "^Finished:" "$log" 2>/dev/null || echo 0); total_seen=$(grep -m1 "Total valid cases seen" "$log" 2>/dev/null | grep -oE "[0-9]+" | tail -1); assigned=$(grep -m1 "Cases assigned to this process" "$log" 2>/dev/null | grep -oE "[0-9]+" | tail -1); mtime=$(stat -c "%y" "$log" 2>/dev/null | cut -d. -f1); [ -z "$total_seen" ] && total_seen="not_printed_yet"; [ -z "$assigned" ] && assigned="not_printed_yet"; printf "job%s  finished=%-5s assigned=%-16s total_seen=%-16s last_write=%s\n" "$j" "$finished" "$assigned" "$total_seen" "$mtime"; done; echo; echo -n "outputs: "; find output_2channel_1syn_data -name output_signals.txt | wc -l; echo -n "ade_e failures: "; grep -H "Cannot open the input file '\''ade_e.scs'\''" logs/ocean_apply_job*.log 2>/dev/null | wc -l; echo; grep -H -E "Using isolated Cadence projectDir|Finished assigned|ERROR|FATAL|SFE-|SPECTRE-|Cannot find|Cannot open|syntax error|lineread|eval: not a function|undefined function|Key has expired" logs/ocean_apply_job*.log 2>/dev/null | tail -20' ;;
  *)
    echo "Run directory: \$RUN_DIR"
    echo "Use: $mon jobs|progress|count|tail|condensed" ;;
esac
EOF_MON
  chmod +x "$mon"
}

main() {
  need_dir "$REPO" "repository root"
  need_dir "$CODE_DIR" "processing/sim_run_code directory"
  need_file "$SRC_OCN" "source OCN script"
  need_dir "$SPIKE_ROOT" "spike_train_output directory"
  need_file "$CDS_INCLUDE" "cds.lib include"
  resolve_ade_e_source
  compute_total_cases

  echo "=== Cadence/OCEAN run setup v10 ==="
  echo "Repo:        $REPO"
  echo "Source OCN:  $SRC_OCN"
  echo "Spike root:  $SPIKE_ROOT"
  echo "Run dir:     $RUN_DIR"
  echo "Output dir:  $OUTPUT_DIR"
  echo "Log dir:     $LOG_DIR"
  echo "IPC dir:     $IPC_DIR"
  echo "Project dir: $CADENCE_PROJECT_DIR"
  echo "ADE_E src:   $ADE_E_SOURCE"
  echo "NUM_JOBS:    $NUM_JOBS"
  echo "Total cases: $COMPUTED_CASES"

  if [[ "$SKIP_KILL" != "1" ]]; then
    echo "=== Clearing stale Cadence/OCEAN processes ==="
    kill_stale_processes
    echo "Remaining matching processes, if any:"
    show_matching_processes
  fi

  echo "=== Creating run directories ==="
  run mkdir -p "$OUTPUT_DIR" "$LOG_DIR" "$IPC_DIR" "$CADENCE_PROJECT_DIR" "$RUN_OCN_DIR" "$SUPPORT_DIR"

  echo "=== Caching ade_e.scs into run support directory ==="
  run cp -f "$ADE_E_SOURCE" "$SUPPORT_DIR/ade_e.scs"

  echo "=== Copying and patching OCN ==="
  run cp "$SRC_OCN" "$RUN_OCN"
  [[ "$DRY_RUN" == "1" ]] || patch_run_ocn "$RUN_OCN" "$REPO" "$OUTPUT_DIR"

  echo "=== Preparing IPC job dirs and isolated project dirs ==="
  for i in $(seq 0 $((NUM_JOBS - 1))); do
    jobdir="$IPC_DIR/job$i"
    projdir="$CADENCE_PROJECT_DIR/job$i"
    run mkdir -p "$jobdir" "$projdir"
    [[ "$DRY_RUN" == "1" ]] || write_cds_lib "$jobdir"
  done

  [[ "$DRY_RUN" == "1" ]] || write_run_wrapper
  [[ "$DRY_RUN" == "1" ]] || write_ciw_commands
  [[ "$DRY_RUN" == "1" ]] || write_monitoring_commands

  cat > "$RUN_DIR/RUNINFO.txt" <<EOF_INFO
RUN_ID=$RUN_ID
REPO=$REPO
SRC_OCN=$SRC_OCN
RUN_OCN=$RUN_OCN
SPIKE_ROOT=$SPIKE_ROOT
OUTPUT_DIR=$OUTPUT_DIR
LOG_DIR=$LOG_DIR
IPC_DIR=$IPC_DIR
CADENCE_PROJECT_DIR=$CADENCE_PROJECT_DIR
ADE_E_SOURCE=$ADE_E_SOURCE
ADE_E_CACHE=$SUPPORT_DIR/ade_e.scs
NUM_JOBS=$NUM_JOBS
ST1_COUNT=$ST1_COUNT
ST2_COUNT=$ST2_COUNT
TRIALS_PER_FREQ=$TRIALS_PER_FREQ
COMPUTED_CASES=$COMPUTED_CASES
EOF_INFO

  echo "=== Done ==="
  echo "Run dir: $RUN_DIR"
  echo "CIW commands: $RUN_DIR/ciw_commands.il"
  echo "Monitoring: $RUN_DIR/monitoring_commands.sh"
  echo
  echo "Next:"
  echo "  cd $RUN_DIR"
  echo "  cat ciw_commands.il"
  echo "  # paste generated ipcBeginProcess(...) commands into CIW"
}

main "$@"
