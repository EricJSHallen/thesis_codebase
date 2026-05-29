#!/usr/bin/env bash
set -u -o pipefail
JOB_INDEX="${1:?usage: run_spectre_worker.sh JOB_INDEX}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1091
source "$RUN_DIR/setup_spectre_env.sh"

TEMPLATE="$RUN_DIR/netlist_template/raw"
LOG="$RUN_DIR/logs/spectre_worker_${JOB_INDEX}.log"
STATE="$RUN_DIR/worker_state/job_${JOB_INDEX}.state"
ASSIGNED_TSV="$RUN_DIR/worker_state/job_${JOB_INDEX}_cases.tsv"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/worker_state"

{
  echo "worker=$JOB_INDEX start=$(date -Is)"
  echo "SPECTRE_CMD=${SPECTRE_CMD:-unset}"
  echo "runtime_check:"
  check_spectre_runtime
} > "$LOG" 2>&1

if ! spectre_runtime_ok; then
  echo "FAILED: Spectre runtime unresolved. Run ./refresh_spectre_runtime.sh and source ./setup_spectre_env.sh." | tee -a "$LOG"
  exit 2
fi
if [ ! -f "$TEMPLATE/input.scs" ]; then
  echo "FAILED: missing template $TEMPLATE/input.scs" | tee -a "$LOG"
  exit 1
fi

python3 "$RUN_DIR/select_cases.py" "$RUN_DIR/cases.csv" "$JOB_INDEX" "$NUM_JOBS" > "$ASSIGNED_TSV"
echo "assigned_cases=$(wc -l < "$ASSIGNED_TSV")" | tee -a "$LOG" > "$STATE"

while IFS=$'\t' read -r case_id run_name st1_file st2_file case_dir; do
  {
    echo "========== case_id=$case_id run_name=$run_name =========="
    mkdir -p "$case_dir"
    if [ -f "$case_dir/output_signals.txt" ]; then
      echo "SKIP existing output_signals.txt"
      continue
    fi
    rm -rf "$case_dir/netlist" "$case_dir/psf"
    cp -a "$TEMPLATE" "$case_dir/netlist"
    python3 - "$case_dir/netlist" "$st1_file" "$st2_file" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]); st1=sys.argv[2]; st2=sys.argv[3]
for p in root.rglob('*'):
    if not p.is_file():
        continue
    try:
        s=p.read_text(errors='ignore')
    except Exception:
        continue
    ns=s.replace('__ST1_PWL__', st1).replace('__ST2_PWL__', st2)
    if ns != s:
        p.write_text(ns)
PY
    (
      cd "$case_dir/netlist" || exit 1
      "$SPECTRE_CMD" input.scs +escchars +log "$case_dir/spectre.out" -format psfxl -raw "$case_dir/psf"
    )
    rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "FAILED case_id=$case_id spectre_rc=$rc"
      echo "case_id=$case_id" >> "$RUN_DIR/worker_state/job_${JOB_INDEX}_failed.txt"
      continue
    fi
    echo "DONE case_id=$case_id"
    echo "$case_id" >> "$RUN_DIR/worker_state/job_${JOB_INDEX}_done.txt"
  } >> "$LOG" 2>&1
done < "$ASSIGNED_TSV"
echo "worker=$JOB_INDEX end=$(date -Is)" >> "$LOG"
