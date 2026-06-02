#!/usr/bin/env bash
set -u -o pipefail
CASE_DIR="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1091
source "$RUN_DIR/setup_spectre_env.sh"
OCN="$RUN_DIR/ocn/export_psf_to_txt.ocn"
LOG="$CASE_DIR/export_ocean.log"
mkdir -p "$CASE_DIR"
[[ -f "$OCN" ]] || { echo "ERROR: missing export OCN: $OCN" > "$LOG"; exit 1; }
[[ -n "${CADENCE_EXPORT_LAUNCHER:-}" && -x "$CADENCE_EXPORT_LAUNCHER" ]] || { echo "ERROR: CADENCE_EXPORT_LAUNCHER unavailable" > "$LOG"; exit 127; }
{
  echo "CASE_DIR=$CASE_DIR"; echo "OCN=$OCN"; echo "CADENCE_EXPORT_LAUNCHER=$CADENCE_EXPORT_LAUNCHER"; echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"; echo "ldd missing before launch:"; ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | awk '/not found/{print}' || true
} > "$LOG"
if ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | grep -q 'not found'; then echo "ERROR: export launcher still has missing libraries" >> "$LOG"; exit 127; fi
EXPORT_TIMEOUT_SECONDS="${EXPORT_TIMEOUT_SECONDS:-45}"
CAD_CASE_DIR="$CASE_DIR" CAD_BATCH_EXIT=1 timeout "${EXPORT_TIMEOUT_SECONDS}s" "$CADENCE_EXPORT_LAUNCHER" -nograph -restore "$OCN" < /dev/null >> "$LOG" 2>&1
rc=$?
if [[ "$rc" -ne 0 ]]; then
  echo "ERROR: export launcher failed with rc=$rc" >> "$LOG"
  if [[ "$rc" -eq 124 ]]; then echo "ERROR: export timed out after ${EXPORT_TIMEOUT_SECONDS}s" >> "$LOG"; fi
  exit "$rc"
fi
[[ -f "$CASE_DIR/output_signals.txt" ]] || { echo "ERROR: export completed but did not create output_signals.txt" >> "$LOG"; exit 1; }
