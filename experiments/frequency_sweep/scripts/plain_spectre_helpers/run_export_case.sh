#!/usr/bin/env bash
set -euo pipefail
CASE_DIR="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
OCN="$RUN_DIR/ocn/export_psf_to_txt.ocn"
LOG="$CASE_DIR/export_ocean.log"
if [[ ! -f "$OCN" ]]; then
  echo "ERROR: missing export OCN: $OCN" >&2
  exit 1
fi
if command -v ocean >/dev/null 2>&1; then
  CAD_CASE_DIR="$CASE_DIR" CAD_BATCH_EXIT=1 ocean -nograph -restore "$OCN" > "$LOG" 2>&1
elif [[ -x /projects/bics/cadence/installs/IC231/tools.lnx86/dfII/bin/64bit/virtuoso ]]; then
  CAD_CASE_DIR="$CASE_DIR" CAD_BATCH_EXIT=1 /projects/bics/cadence/installs/IC231/tools.lnx86/dfII/bin/64bit/virtuoso -nograph -restore "$OCN" > "$LOG" 2>&1
else
  echo "ERROR: neither ocean nor the IC231 virtuoso binary is available for PSF export." > "$LOG"
  exit 127
fi
[[ -f "$CASE_DIR/output_signals.txt" ]]
