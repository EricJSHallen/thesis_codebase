#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/setup_spectre_env.sh"
check_spectre_runtime
if ! check_export_runtime; then
  echo "WARNING: export runner was not found during refresh." >&2
  echo "Workers will try the same detection again at export time." >&2
  echo "Set OCEAN_CMD=/full/path/to/ocean or /full/path/to/virtuoso if required." >&2
fi
