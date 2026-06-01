#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/support" "$RUN_DIR/logs"
LOG="$RUN_DIR/logs/refresh_spectre_runtime.log"
: > "$LOG"
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"

choose_cmd() {
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

SPECTRE_CMD="$(choose_cmd || true)"
if [[ -z "$SPECTRE_CMD" ]]; then
  echo "ERROR: could not find a Spectre launcher/binary." | tee -a "$LOG" >&2
  exit 1
fi

echo "Using Spectre wrapper: $SPECTRE_CMD" | tee -a "$LOG"
{
  echo "# generated $(date -Is) by refresh_spectre_runtime.sh"
  echo "export SPECTRE_CMD=\"$SPECTRE_CMD\""
  echo "export CADENCE_INSTALL_ROOT=\"$CADENCE_INSTALL_ROOT\""
  echo "export PATH=\"$(dirname "$SPECTRE_CMD"):\${PATH:-}\""
} > "$RUN_DIR/support/spectre_runtime.env"
