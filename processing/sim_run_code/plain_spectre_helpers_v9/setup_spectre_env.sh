#!/usr/bin/env bash
# Source this from a prepared plain-Spectre run directory.
# v9 deliberately uses the site Spectre launcher/wrapper when available,
# instead of invoking the raw tools.lnx86/spectre/bin/64bit/spectre ELF binary.

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${CADENCE_SEARCH_ROOT:=/projects/bics/cadence}"

# Prefer a wrapper/launcher, because the raw 64bit ELF has unresolved shared-library deps
# unless the full Cadence runtime environment is preloaded.
if [ -z "${SPECTRE_CMD:-}" ]; then
  for cand in \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/bin/spectre" \
    "$(command -v spectre 2>/dev/null || true)" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"
  do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
      export SPECTRE_CMD="$cand"
      break
    fi
  done
fi

export CADENCE_INSTALL_ROOT CADENCE_SEARCH_ROOT SPECTRE_CMD
[ -n "${SPECTRE_CMD:-}" ] && export PATH="$(dirname "$SPECTRE_CMD"):${PATH:-}"

# Optional cached runtime path, only needed if SPECTRE_CMD falls back to a raw ELF binary.
if [ -f "$RUN_DIR/support/spectre_runtime.env" ]; then
  # shellcheck disable=SC1091
  source "$RUN_DIR/support/spectre_runtime.env"
fi

_is_elf_binary() {
  file "$1" 2>/dev/null | grep -qi 'ELF'
}

check_spectre_runtime() {
  if [ -z "${SPECTRE_CMD:-}" ]; then
    echo "SPECTRE_CMD is unset."
    return 1
  fi
  if [ ! -x "$SPECTRE_CMD" ]; then
    echo "SPECTRE_CMD not executable: $SPECTRE_CMD"
    return 1
  fi

  echo "SPECTRE_CMD=$SPECTRE_CMD"
  file "$SPECTRE_CMD" 2>/dev/null || true

  if _is_elf_binary "$SPECTRE_CMD"; then
    ldd "$SPECTRE_CMD" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}'
  else
    echo "Using wrapper/script launcher; skipping ldd on wrapper."
  fi
}

spectre_runtime_ok() {
  [ -n "${SPECTRE_CMD:-}" ] && [ -x "$SPECTRE_CMD" ] || return 1
  if _is_elf_binary "$SPECTRE_CMD"; then
    ! ldd "$SPECTRE_CMD" 2>/dev/null | grep -q 'not found'
  else
    return 0
  fi
}

export -f check_spectre_runtime 2>/dev/null || true
export -f spectre_runtime_ok 2>/dev/null || true
