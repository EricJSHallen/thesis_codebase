#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/logs"
for ((j=0; j<NUM_JOBS; j++)); do
  "$RUN_DIR/run_spectre_worker.sh" "$j" &
  echo $! > "$RUN_DIR/worker_state/worker_${j}.pid"
done
wait
