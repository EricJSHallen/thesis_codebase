#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"

export CAD_CASE_DIR="$case_dir"
export CAD_BATCH_EXIT=1

# OCEAN/Virtuoso uses shared user-level state and an ADE license path. Running
# several OCEAN exporters concurrently can produce transient CDS.log locks and
# license-server failures. Serialize only the export stage; Spectre simulations
# still run in parallel.
lock_dir="$RUN_DIR/worker_state/ocean_export.lock"
acquire_lock() {
  local waited=0
  while ! mkdir "$lock_dir" 2>/dev/null; do
    sleep 2
    waited=$((waited + 2))
    if (( waited > 1800 )); then
      echo "ERROR: timed out waiting for OCEAN export lock: $lock_dir" >&2
      return 124
    fi
  done
  trap 'rm -rf "$lock_dir"' EXIT
}

is_retryable_export_failure() {
  local log_file="$1"
  grep -qiE 'LMF-|FLEXnet|license.*failed|Cannot connect to license server|CDS\.log.*locked|ADE-6015|ELI-00111' "$log_file" 2>/dev/null
}

acquire_lock

max_attempts="${EXPORT_MAX_ATTEMPTS:-8}"
base_sleep="${EXPORT_RETRY_SLEEP:-20}"
attempt=1
while (( attempt <= max_attempts )); do
  rm -f "$case_dir/output_signals.txt.tmp"
  echo "OCEAN export attempt $attempt/$max_attempts for $case_dir" > "$case_dir/export.log"
  if ocean -nograph -restore "$RUN_DIR/ocn/export_psf_to_txt.ocn" >> "$case_dir/export.log" 2>&1 && [[ -s "$case_dir/output_signals.txt" ]]; then
    exit 0
  fi

  if (( attempt < max_attempts )) && is_retryable_export_failure "$case_dir/export.log"; then
    sleep_for=$(( base_sleep * attempt ))
    echo "Retryable OCEAN export failure; sleeping ${sleep_for}s before retry." | tee -a "$case_dir/export.log" >&2
    sleep "$sleep_for"
    attempt=$((attempt + 1))
    continue
  fi

  break
done

[[ -s "$case_dir/output_signals.txt" ]]
