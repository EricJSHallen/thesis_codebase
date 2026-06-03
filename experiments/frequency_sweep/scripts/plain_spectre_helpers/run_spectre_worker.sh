#!/usr/bin/env bash
set -euo pipefail
job_idx="${1:?usage: run_spectre_worker.sh JOB_INDEX}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1090
source "$RUN_DIR/setup_spectre_env.sh"

log="$RUN_DIR/logs/spectre_worker_${job_idx}.log"
exec > >(tee -a "$log") 2>&1

echo "Worker $job_idx started at $(date)"
TEMPLATE="$RUN_DIR/netlist_template/raw"
[[ -f "$TEMPLATE/input.scs" ]] || { echo "ERROR: missing imported template: $TEMPLATE/input.scs"; exit 1; }

SPECTRE_BIN="${SPECTRE_CMD:-spectre}"
"$RUN_DIR/select_cases.py" "$RUN_DIR/cases.csv" "$job_idx" "$NUM_JOBS" | \
while IFS=$'\t' read -r case_id run_name st1_file st2_file case_dir; do
  [[ -n "${case_id:-}" ]] || continue
  out="$case_dir/output_signals.txt"
  if [[ -s "$out" ]]; then
    echo "DONE case_id=$case_id already run_name=$run_name"
    continue
  fi
  mkdir -p "$case_dir"
  rm -rf "$case_dir/netlist" "$case_dir/psf" "$case_dir/spectre.out" "$case_dir/export.log"
  cp -a "$TEMPLATE" "$case_dir/netlist"
  python3 - "$case_dir/netlist" "$st1_file" "$st2_file" <<'PY'
import pathlib, sys
netlist = pathlib.Path(sys.argv[1])
st1 = sys.argv[2]
st2 = sys.argv[3]
for p in netlist.rglob('*'):
    if not p.is_file():
        continue
    try:
        s = p.read_text(errors='ignore')
    except Exception:
        continue
    ns = s.replace('__ST1_PWL__', '"' + st1 + '"').replace('__ST2_PWL__', '"' + st2 + '"')
    if ns != s:
        p.write_text(ns)
PY
  echo "RUN case_id=$case_id run_name=$run_name"
  (
    cd "$case_dir"
    "$SPECTRE_BIN" +aps=moderate netlist/input.scs -format psfxl -raw psf > spectre.out 2>&1
  )
  if "$RUN_DIR/run_export_case.sh" "$case_dir"; then
    echo "DONE case_id=$case_id run_name=$run_name output_signals=$out"
  else
    echo "FAILED case_id=$case_id run_name=$run_name export_or_output_failed"
  fi
done

echo "Worker $job_idx finished at $(date)"
