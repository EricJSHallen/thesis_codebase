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

if [[ ! -f "$OCN" ]]; then
  echo "ERROR: missing export OCN: $OCN" >&2
  exit 1
fi

if [[ -z "${CADENCE_EXPORT_LAUNCHER:-}" || ! -x "$CADENCE_EXPORT_LAUNCHER" ]]; then
  {
    echo "ERROR: CADENCE_EXPORT_LAUNCHER unavailable: ${CADENCE_EXPORT_LAUNCHER:-unset}"
    echo "Run ./refresh_spectre_runtime.sh, then source ./setup_spectre_env.sh before exporting."
  } > "$LOG"
  exit 127
fi

{
  echo "CASE_DIR=$CASE_DIR"
  echo "OCN=$OCN"
  echo "CADENCE_EXPORT_LAUNCHER=$CADENCE_EXPORT_LAUNCHER"
  echo "IC_ROOT=${IC_ROOT:-unset}"
  echo "PATH=$PATH"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
  echo "ldd missing before launch:"
  ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | awk '/not found/{print}' || true
} > "$LOG"

if ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | grep -q 'not found'; then
  echo "ERROR: export launcher still has missing shared libraries." >> "$LOG"
  exit 127
fi

CAD_CASE_DIR="$CASE_DIR" CAD_BATCH_EXIT=1 "$CADENCE_EXPORT_LAUNCHER" -nograph -restore "$OCN" >> "$LOG" 2>&1
rc=$?
if [[ "$rc" -ne 0 ]]; then
  echo "ERROR: export launcher failed with rc=$rc" >> "$LOG"
  exit "$rc"
fi

if [[ ! -f "$CASE_DIR/output_signals.txt" ]]; then
  echo "ERROR: export completed but did not create $CASE_DIR/output_signals.txt" >> "$LOG"
  exit 1
fi
