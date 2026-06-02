#!/usr/bin/env bash
# Source from a prepared run directory.
RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${IC_VERSION:=IC231}"
: "${IC_ROOT:=$CADENCE_INSTALL_ROOT/$IC_VERSION}"
[[ -f "$RUN_DIR/support/spectre_runtime.env" ]] && source "$RUN_DIR/support/spectre_runtime.env"
[[ -f "$RUN_DIR/support/cadence_ic_runtime.env" ]] && source "$RUN_DIR/support/cadence_ic_runtime.env"
choose_spectre_cmd() {
  for cand in "${SPECTRE_CMD:-}" "$CADENCE_INSTALL_ROOT/SPECTRE231/tools/bin/spectre" "$CADENCE_INSTALL_ROOT/SPECTRE231/bin/spectre" "$(command -v spectre 2>/dev/null || true)"; do
    [[ -n "$cand" && -x "$cand" ]] && { printf '%s\n' "$cand"; return 0; }
  done
  return 1
}
[[ -z "${SPECTRE_CMD:-}" ]] && SPECTRE_CMD="$(choose_spectre_cmd || true)"
export CADENCE_INSTALL_ROOT IC_VERSION IC_ROOT SPECTRE_CMD
[[ -n "${SPECTRE_CMD:-}" ]] && export PATH="$(dirname "$SPECTRE_CMD"):${PATH:-}"
_is_elf_binary() { file "$1" 2>/dev/null | grep -qi 'ELF'; }
check_spectre_runtime() {
  [[ -n "${SPECTRE_CMD:-}" && -x "$SPECTRE_CMD" ]] || { echo "SPECTRE_CMD not executable: ${SPECTRE_CMD:-unset}"; return 1; }
  echo "SPECTRE_CMD=$SPECTRE_CMD"; file "$SPECTRE_CMD" 2>/dev/null || true
  if _is_elf_binary "$SPECTRE_CMD"; then ldd "$SPECTRE_CMD" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}'; else echo "Using wrapper/script launcher; skipping ldd on wrapper."; fi
}
spectre_runtime_ok() { [[ -n "${SPECTRE_CMD:-}" && -x "$SPECTRE_CMD" ]] || return 1; _is_elf_binary "$SPECTRE_CMD" && ! ldd "$SPECTRE_CMD" 2>/dev/null | grep -q 'not found' || return 0; }
check_export_runtime() {
  local launcher="${CADENCE_EXPORT_LAUNCHER:-}"
  [[ -n "$launcher" && -x "$launcher" ]] || { echo "CADENCE_EXPORT_LAUNCHER not executable: ${launcher:-unset}"; return 1; }
  echo "CADENCE_EXPORT_LAUNCHER=$launcher"; file "$launcher" 2>/dev/null || true; ldd "$launcher" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}' || true
}
export -f check_spectre_runtime spectre_runtime_ok check_export_runtime 2>/dev/null || true
