#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
missing=0
while IFS=, read -r case_id run_name st1_file st2_file case_dir; do
  [[ "$case_id" == "case_id" ]] && continue
  if [[ -d "$case_dir/psf" && ! -s "$case_dir/output_signals.txt" ]]; then
    echo "exporting missing output: $run_name"
    "$RUN_DIR/run_export_case.sh" "$case_dir" || missing=$((missing+1))
  fi
done < "$RUN_DIR/cases.csv"
exit "$missing"
