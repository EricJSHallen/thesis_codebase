#!/usr/bin/env bash
set -euo pipefail
case_dir="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
export CAD_CASE_DIR="$case_dir"
export CAD_BATCH_EXIT=1
ocean -nograph -restore "$RUN_DIR/ocn/export_psf_to_txt.ocn" > "$case_dir/export.log" 2>&1
[[ -s "$case_dir/output_signals.txt" ]]
