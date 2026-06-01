#!/usr/bin/env bash
set -u -o pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1091
source "$RUN_DIR/setup_spectre_env.sh"

if [[ -z "${CADENCE_EXPORT_LAUNCHER:-}" || ! -x "$CADENCE_EXPORT_LAUNCHER" ]]; then
  echo "ERROR: export launcher not configured. Run ./refresh_spectre_runtime.sh and source ./setup_spectre_env.sh first." >&2
  exit 1
fi

count=0
failed=0
while IFS= read -r psf; do
  case_dir="$(dirname "$psf")"
  if [[ -f "$case_dir/output_signals.txt" ]]; then
    continue
  fi
  echo "exporting $case_dir"
  if "$RUN_DIR/run_export_case.sh" "$case_dir"; then
    count=$((count + 1))
  else
    failed=$((failed + 1))
    echo "FAILED export: $case_dir" >&2
  fi
done < <(find "$RUN_DIR/cases" -mindepth 2 -maxdepth 2 -type d -name psf -print | sort)

echo "exported=$count failed=$failed"
[[ "$failed" -eq 0 ]]
