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
# This intentionally uses broad globs because BICS machines may expose different
# Cadence releases on different nodes.
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

find_ocean_runner() {
  # Preferred: native ocean binary.
  if [[ -n "${OCEAN_CMD:-}" ]]; then
    if command -v "$OCEAN_CMD" >/dev/null 2>&1; then
      export OCEAN_CMD="$(command -v "$OCEAN_CMD")"
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-ocean}"
      return 0
    elif [[ -x "$OCEAN_CMD" ]]; then
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-ocean}"
      return 0
    else
      echo "ERROR: OCEAN_CMD is set but not executable/found: $OCEAN_CMD" >&2
      return 127
    fi
  fi

  if command -v ocean >/dev/null 2>&1; then
    export OCEAN_CMD="$(command -v ocean)"
    export OCEAN_RUNNER_MODE="ocean"
    return 0
  fi

  # Some BICS/Cadence shells expose Virtuoso but not a standalone ocean command.
  # OCEAN scripts can be restored through Virtuoso in non-graphical mode.
  if command -v virtuoso >/dev/null 2>&1; then
    export OCEAN_CMD="$(command -v virtuoso)"
    export OCEAN_RUNNER_MODE="virtuoso"
    return 0
  fi

  # The BICS login banner often advertises alias "v => virtuoso". Aliases are not
  # visible in non-interactive scripts, so probe for a literal v command as a last
  # resort. This is not preferred, but it gives a clearer diagnostic.
  if command -v v >/dev/null 2>&1; then
    export OCEAN_CMD="$(command -v v)"
    export OCEAN_RUNNER_MODE="virtuoso"
    return 0
  fi

  echo "ERROR: cannot find an OCEAN export runner in PATH." >&2
  echo "Tried: ocean, virtuoso, and v." >&2
  echo "If your Cadence environment uses a different command, run:" >&2
  echo "  export OCEAN_CMD=/full/path/to/ocean" >&2
  echo "or, if ocean is unavailable but Virtuoso is present:" >&2
  echo "  export OCEAN_CMD=/full/path/to/virtuoso" >&2
  echo "  export OCEAN_RUNNER_MODE=virtuoso" >&2
  return 127
}

check_export_runtime() {
  find_ocean_runner
  echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
}
