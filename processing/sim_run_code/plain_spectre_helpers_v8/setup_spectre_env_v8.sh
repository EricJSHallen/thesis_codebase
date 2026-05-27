#!/usr/bin/env bash
# Source this from a prepared plain-Spectre run directory.
# It intentionally does not perform expensive filesystem searches.

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

: "${SPECTRE_BIN:=/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre}"
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${CADENCE_SEARCH_ROOT:=/projects/bics/cadence}"

SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
export SPECTRE_BIN CADENCE_INSTALL_ROOT CADENCE_SEARCH_ROOT
export PATH="$SPECTRE_BIN_DIR:${PATH:-}"

# Load the cached runtime path produced by refresh_spectre_runtime.sh.
if [ -f "$RUN_DIR/support/spectre_runtime.env" ]; then
  # shellcheck disable=SC1091
  source "$RUN_DIR/support/spectre_runtime.env"
fi

check_spectre_runtime() {
  if [ ! -x "$SPECTRE_BIN" ]; then
    echo "SPECTRE_BIN not executable: $SPECTRE_BIN" >&2
    return 1
  fi
  ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}'
}

spectre_runtime_ok() {
  [ -x "$SPECTRE_BIN" ] && ! ldd "$SPECTRE_BIN" 2>/dev/null | grep -q 'not found'
}

export -f check_spectre_runtime 2>/dev/null || true
export -f spectre_runtime_ok 2>/dev/null || true
