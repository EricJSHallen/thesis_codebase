#!/usr/bin/env bash
# Runtime setup for the plain Spectre/OCEAN export workers.
# Source this file from a generated run directory.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
RUNINFO="$THIS_DIR/RUNINFO.txt"
if [[ -f "$RUNINFO" ]]; then
  # shellcheck disable=SC1090
  source "$RUNINFO"
fi

export CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"

# Keep user PATH first. Add likely Cadence binary locations only if present.
for d in \
  "$CADENCE_INSTALL_ROOT/ICADVM*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/ICADVM*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/IC*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/IC*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/SPECTRE*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/SPECTRE*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/MMSIM*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/MMSIM*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/EXT*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/EXT*/tools.lnx86/bin"; do
  for reald in $d; do
    [[ -d "$reald" ]] || continue
    case ":$PATH:" in
      *":$reald:"*) ;;
      *) export PATH="$reald:$PATH" ;;
    esac
  done
done

check_spectre_runtime() {
  local cmd="${SPECTRE_CMD:-spectre}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: cannot find Spectre command: $cmd" >&2
    echo "Set SPECTRE_CMD or source the correct Cadence environment." >&2
    return 127
  fi
  "$cmd" -W 2>/dev/null | head -5 || true
}

_login_shell_has() {
  local probe="$1"
  bash -lic "$probe" >/dev/null 2>&1
}

find_ocean_runner() {
  # Explicit override. Use this if your site exposes a custom wrapper.
  if [[ -n "${OCEAN_CMD:-}" ]]; then
    if command -v "$OCEAN_CMD" >/dev/null 2>&1; then
      export OCEAN_CMD="$(command -v "$OCEAN_CMD")"
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-direct}"
      return 0
    elif [[ -x "$OCEAN_CMD" ]]; then
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-direct}"
      return 0
    else
      echo "ERROR: OCEAN_CMD is set but not executable/found: $OCEAN_CMD" >&2
      return 127
    fi
  fi

  # Direct executables available to non-interactive scripts.
  if command -v ocean >/dev/null 2>&1; then
    export OCEAN_CMD="$(command -v ocean)"
    export OCEAN_RUNNER_MODE="direct_ocean"
    return 0
  fi
  if command -v virtuoso >/dev/null 2>&1; then
    export OCEAN_CMD="$(command -v virtuoso)"
    export OCEAN_RUNNER_MODE="direct_virtuoso"
    return 0
  fi

  # BICS shells can expose Cadence launchers as login/interactive aliases. Those
  # aliases are usually invisible to a normal non-interactive bash script. Probe
  # a login interactive shell and, if found, run export through that shell.
  if _login_shell_has 'command -v ocean'; then
    export OCEAN_CMD="ocean"
    export OCEAN_RUNNER_MODE="login_ocean"
    return 0
  fi
  if _login_shell_has 'command -v virtuoso'; then
    export OCEAN_CMD="virtuoso"
    export OCEAN_RUNNER_MODE="login_virtuoso"
    return 0
  fi
  if _login_shell_has 'type v'; then
    export OCEAN_CMD="v"
    export OCEAN_RUNNER_MODE="login_v_alias"
    return 0
  fi

  echo "ERROR: cannot find an OCEAN export runner." >&2
  echo "Tried direct commands ocean/virtuoso and login-shell commands ocean/virtuoso/v." >&2
  echo "If needed, set OCEAN_CMD to a full executable path before starting the run." >&2
  return 127
}

check_export_runtime() {
  find_ocean_runner
  echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
}
