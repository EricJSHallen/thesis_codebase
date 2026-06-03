#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
# shellcheck disable=SC1090
source "$RUN_DIR/setup_spectre_env.sh"

# Resolve and persist Spectre and OCEAN/Virtuoso runtime details for this run.
check_spectre_runtime >/dev/null
check_export_runtime >/dev/null

cat > "$RUN_DIR/setup_spectre_env.resolved" <<RESOLVED
export SPECTRE_CMD="${SPECTRE_CMD:-spectre}"
export CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"
export OCEAN_CMD="${OCEAN_CMD:-}"
export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-}"
RESOLVED

cat >> "$RUN_DIR/setup_spectre_env.sh" <<'RESOLVED_APPEND'
# Resolved by refresh_spectre_runtime.sh for this run.
if [[ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/setup_spectre_env.resolved" ]]; then
  # shellcheck disable=SC1090
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/setup_spectre_env.resolved"
fi
RESOLVED_APPEND

echo "Spectre runtime and OCEAN/Virtuoso export runtime resolved."
echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
