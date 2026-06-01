#!/usr/bin/env bash
# Source this from a prepared plain-Spectre run directory.
# Also loads cached Spectre and IC/OCEAN runtime paths when available.

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${IC_VERSION:=IC231}"
: "${IC_ROOT:=$CADENCE_INSTALL_ROOT/$IC_VERSION}"

choose_spectre_cmd() {
  local cand
  for cand in \
    "${SPECTRE_CMD:-}" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/bin/spectre" \
    "$(command -v spectre 2>/dev/null || true)" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"
  do
    if [[ -n "$cand" && -x "$cand" ]]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

export CADENCE_INSTALL_ROOT IC_VERSION IC_ROOT
export SPECTRE_CMD="$(choose_spectre_cmd || true)"
[[ -n "${SPECTRE_CMD:-}" ]] && export PATH="$(dirname "$SPECTRE_CMD"):${PATH:-}"

# Load generated runtime exports, if they exist.
[[ -f "$RUN_DIR/support/spectre_runtime.env" ]] && source "$RUN_DIR/support/spectre_runtime.env"
[[ -f "$RUN_DIR/support/cadence_ic_runtime.env" ]] && source "$RUN_DIR/support/cadence_ic_runtime.env"

_is_elf_binary() {
  file "$1" 2>/dev/null | grep -qi 'ELF'
}

check_spectre_runtime() {
  if [[ -z "${SPECTRE_CMD:-}" || ! -x "$SPECTRE_CMD" ]]; then
    echo "SPECTRE_CMD not executable: ${SPECTRE_CMD:-unset}"
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
  [[ -n "${SPECTRE_CMD:-}" && -x "$SPECTRE_CMD" ]] || return 1
  if _is_elf_binary "$SPECTRE_CMD"; then
    ! ldd "$SPECTRE_CMD" 2>/dev/null | grep -q 'not found'
  else
    return 0
  fi
}

check_export_runtime() {
  local launcher="${CADENCE_EXPORT_LAUNCHER:-}"
  if [[ -z "$launcher" || ! -x "$launcher" ]]; then
    echo "CADENCE_EXPORT_LAUNCHER not executable: ${launcher:-unset}"
    return 1
  fi
  echo "CADENCE_EXPORT_LAUNCHER=$launcher"
  file "$launcher" 2>/dev/null || true
  ldd "$launcher" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}' || true
}

export -f check_spectre_runtime 2>/dev/null || true
export -f spectre_runtime_ok 2>/dev/null || true
export -f check_export_runtime 2>/dev/null || true
