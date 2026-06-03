#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1090
source "$RUN_DIR/setup_spectre_env.sh"

export CAD_CASE_DIR="$case_dir"
export CAD_BATCH_EXIT=1

# OCEAN/Virtuoso uses shared user-level state and sometimes ADE/CDS.log state.
# Keep the export stage serialized; Spectre simulations still run in parallel.
# patch8 avoids the patch7 hang by using only real ocean/virtuoso executables.
# It deliberately does not run xp018v, xp018, xkit, or v aliases.
lock_dir="$RUN_DIR/worker_state/ocean_export.lock"
lock_poll_seconds="${OCEAN_LOCK_POLL_SECONDS:-2}"
lock_report_seconds="${OCEAN_LOCK_REPORT_SECONDS:-60}"
lock_wait_timeout="${OCEAN_LOCK_WAIT_TIMEOUT:-0}"   # 0 = wait indefinitely
lock_stale_seconds="${OCEAN_LOCK_STALE_SECONDS:-7200}"

delete_lock() { rm -rf "$lock_dir" 2>/dev/null || true; }

lock_owner_dead() {
  local pid_file="$lock_dir/owner.pid"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  kill -0 "$pid" 2>/dev/null && return 1 || return 0
}

lock_age_seconds() {
  local ts_file="$lock_dir/owner.start_epoch"
  local now ts
  now="$(date +%s)"
  ts="$(cat "$ts_file" 2>/dev/null || echo "$now")"
  [[ "$ts" =~ ^[0-9]+$ ]] || ts="$now"
  echo $(( now - ts ))
}

write_lock_metadata() {
  {
    echo "$$" > "$lock_dir/owner.pid"
    hostname > "$lock_dir/owner.host" 2>/dev/null || true
    date +%s > "$lock_dir/owner.start_epoch"
    date > "$lock_dir/owner.start_human"
    printf '%s\n' "$case_dir" > "$lock_dir/owner.case_dir"
  } 2>/dev/null || true
}

acquire_lock() {
  local waited=0 last_report=0
  mkdir -p "$RUN_DIR/worker_state"
  while ! mkdir "$lock_dir" 2>/dev/null; do
    if [[ -d "$lock_dir" ]] && lock_owner_dead; then
      echo "Removing stale OCEAN export lock owned by a dead PID: $lock_dir" >&2
      delete_lock
      continue
    fi
    sleep "$lock_poll_seconds"
    waited=$(( waited + lock_poll_seconds ))
    if (( lock_wait_timeout > 0 && waited > lock_wait_timeout )); then
      echo "ERROR: timed out waiting for OCEAN export lock after ${waited}s: $lock_dir" >&2
      return 124
    fi
    if (( waited - last_report >= lock_report_seconds )); then
      last_report="$waited"
      local age owner_case owner_pid
      age="$(lock_age_seconds 2>/dev/null || echo unknown)"
      owner_case="$(cat "$lock_dir/owner.case_dir" 2>/dev/null || echo unknown)"
      owner_pid="$(cat "$lock_dir/owner.pid" 2>/dev/null || echo unknown)"
      echo "Waiting for OCEAN export lock (${waited}s waited, lock age ${age}s, owner_pid=${owner_pid}, owner_case=${owner_case})" >&2
      if [[ "$age" =~ ^[0-9]+$ ]] && (( age > lock_stale_seconds )); then
        echo "Notice: OCEAN export lock is older than ${lock_stale_seconds}s; not stealing it while owner PID appears alive." >&2
      fi
    fi
  done
  write_lock_metadata
}

release_lock() { delete_lock; }

is_retryable_export_failure() {
  local log_file="$1"
  grep -qiE 'LMF-|FLEXnet|license.*failed|Cannot connect to license server|CDS\.log.*locked|ADE-6015|ELI-00111|timed out|timeout|killed|command not found|Shared lock|lock' "$log_file" 2>/dev/null
}

run_ocean_once() {
  local log_file="$1"
  local timeout_seconds="${OCEAN_EXPORT_TIMEOUT_SECONDS:-600}"
  local restore_arg="$RUN_DIR/ocn/export_psf_to_txt.ocn"

  find_ocean_runner >> "$log_file" 2>&1 || return $?

  local mode="${OCEAN_RUNNER_MODE:-direct_ocean}"
  local cmd="${OCEAN_CMD:-ocean}"
  export CAD_CASE_DIR CAD_BATCH_EXIT
  export OCEAN_RESTORE_ARG="$restore_arg"

  echo "OCEAN_EXPORT_RUNNER_MODE=$mode" >> "$log_file"
  echo "OCEAN_EXPORT_CMD=$cmd" >> "$log_file"

  case "$mode" in
    direct|direct_ocean|direct_virtuoso)
      if command -v timeout >/dev/null 2>&1; then
        timeout --preserve-status --kill-after=30s "${timeout_seconds}s" \
          "$cmd" -nograph -restore "$restore_arg" >> "$log_file" 2>&1
      else
        "$cmd" -nograph -restore "$restore_arg" >> "$log_file" 2>&1
      fi
      ;;
    *)
      echo "ERROR: unsupported OCEAN_RUNNER_MODE=$mode" >> "$log_file"
      return 127
      ;;
  esac
}

max_attempts="${EXPORT_MAX_ATTEMPTS:-4}"
base_sleep="${EXPORT_RETRY_SLEEP:-20}"
attempt=1
while (( attempt <= max_attempts )); do
  rm -f "$case_dir/output_signals.txt.tmp"
  echo "OCEAN export attempt $attempt/$max_attempts for $case_dir" > "$case_dir/export.log"

  acquire_lock
  set +e
  run_ocean_once "$case_dir/export.log"
  ocean_status=$?
  set -e
  release_lock

  if (( ocean_status == 0 )) && [[ -s "$case_dir/output_signals.txt" ]]; then
    exit 0
  fi

  if (( ocean_status == 124 || ocean_status == 137 )); then
    echo "Retryable OCEAN export timeout/kill status=$ocean_status." | tee -a "$case_dir/export.log" >&2
  fi

  if (( attempt < max_attempts )) && { (( ocean_status == 124 || ocean_status == 137 )) || is_retryable_export_failure "$case_dir/export.log"; }; then
    sleep_for=$(( base_sleep * attempt ))
    echo "Retryable OCEAN export failure; sleeping ${sleep_for}s before retry." | tee -a "$case_dir/export.log" >&2
    sleep "$sleep_for"
    attempt=$((attempt + 1))
    continue
  fi

  break
done

[[ -s "$case_dir/output_signals.txt" ]]
