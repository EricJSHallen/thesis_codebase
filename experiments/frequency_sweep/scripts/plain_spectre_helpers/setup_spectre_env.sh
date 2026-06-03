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
  "$CADENCE_INSTALL_ROOT/IC*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/SPECTRE*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/MMSIM*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/EXT*/tools/bin"; do
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

check_export_runtime() {
  if ! command -v ocean >/dev/null 2>&1; then
    echo "ERROR: cannot find ocean in PATH." >&2
    echo "Source the correct Cadence environment before exporting PSF results." >&2
    return 127
  fi
  echo "ocean found: $(command -v ocean)"
}
