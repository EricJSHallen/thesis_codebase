#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1091
source "$RUN_DIR/setup_spectre_env.sh"

if ! spectre_runtime_ok; then
  echo "ERROR: Spectre runtime unresolved. Run ./refresh_spectre_runtime.sh first." >&2
  check_spectre_runtime >&2 || true
  exit 1
fi

if [[ -z "${CADENCE_EXPORT_LAUNCHER:-}" || ! -x "$CADENCE_EXPORT_LAUNCHER" ]]; then
  echo "ERROR: export launcher is not configured. Run ./refresh_spectre_runtime.sh first." >&2
  exit 1
fi

if ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | grep -q 'not found'; then
  echo "ERROR: export launcher still has missing libraries:" >&2
  ldd "$CADENCE_EXPORT_LAUNCHER" 2>/dev/null | grep 'not found' >&2 || true
  exit 1
fi

for j in $(seq 0 $((NUM_JOBS - 1))); do
  echo "launching worker $j"
  bash "$RUN_DIR/run_spectre_worker.sh" "$j" > "$RUN_DIR/logs/worker_${j}.launcher.log" 2>&1 &
done
wait
