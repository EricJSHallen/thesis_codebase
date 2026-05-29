#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/logs"
for j in $(seq 0 $((NUM_JOBS - 1))); do
  echo "launching worker $j"
  (cd "$RUN_DIR" && ./run_spectre_worker.sh "$j") > "$RUN_DIR/logs/worker_${j}.launcher.log" 2>&1 &
done
wait
