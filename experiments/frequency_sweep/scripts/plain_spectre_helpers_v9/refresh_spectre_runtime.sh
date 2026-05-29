#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/support" "$RUN_DIR/logs"
LOG="$RUN_DIR/logs/refresh_spectre_runtime.log"
: > "$LOG"

# v9 prefers the Spectre wrapper. This refresh script is only a fallback for raw ELF use.
# It also writes SPECTRE_CMD if a wrapper is found.
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${CADENCE_SEARCH_ROOT:=/projects/bics/cadence}"

choose_cmd() {
  for cand in \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/bin/spectre" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/bin/spectre" \
    "$(command -v spectre 2>/dev/null || true)" \
    "${SPECTRE_CMD:-}" \
    "${SPECTRE_BIN:-}" \
    "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"
  do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

SPECTRE_CMD="$(choose_cmd || true)"
if [ -z "$SPECTRE_CMD" ]; then
  echo "ERROR: could not find any Spectre launcher/binary." | tee -a "$LOG" >&2
  exit 1
fi

echo "chosen SPECTRE_CMD=$SPECTRE_CMD" | tee -a "$LOG"
file "$SPECTRE_CMD" 2>/dev/null | tee -a "$LOG" || true

OUT="$RUN_DIR/support/spectre_runtime.env"
TMP="$OUT.tmp"

# If this is a wrapper/script, no LD_LIBRARY_PATH search is required here.
if ! file "$SPECTRE_CMD" 2>/dev/null | grep -qi 'ELF'; then
  {
    echo "# generated $(date -Is) by refresh_spectre_runtime_v9.sh"
    echo "export SPECTRE_CMD=\"$SPECTRE_CMD\""
    echo "export CADENCE_INSTALL_ROOT=\"$CADENCE_INSTALL_ROOT\""
    echo "export CADENCE_SEARCH_ROOT=\"$CADENCE_SEARCH_ROOT\""
    echo "export PATH=\"$(dirname "$SPECTRE_CMD"):\${PATH:-}\""
  } > "$TMP"
  mv "$TMP" "$OUT"
  echo "Wrapper/script launcher selected; wrote $OUT" | tee -a "$LOG"
  exit 0
fi

# Fallback for raw ELF binary.
DIR_LIST="$RUN_DIR/support/spectre_runtime_dirs.txt"
: > "$DIR_LIST"
add_dir() { [ -n "${1:-}" ] && [ -d "$1" ] && printf '%s\n' "$1" >> "$DIR_LIST"; }
BIN_DIR="$(cd "$(dirname "$SPECTRE_CMD")" && pwd)"
add_dir "$BIN_DIR"
for d in \
  "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib" \
  "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib/64bit" \
  "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib" \
  "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib/64bit" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib/64bit" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib/64bit"
do add_dir "$d"; done
make_ld() { awk '!seen[$0]++' "$DIR_LIST" | paste -sd: -; }

for pass in 1 2 3; do
  LD="$(make_ld)"; export LD_LIBRARY_PATH="$LD:${LD_LIBRARY_PATH:-}"
  missing="$(ldd "$SPECTRE_CMD" 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)"
  echo "pass=$pass missing=$(echo "$missing" | tr '\n' ' ')" | tee -a "$LOG"
  [ -z "$missing" ] && break
  while read -r lib; do
    [ -z "$lib" ] && continue
    found="$(find "$CADENCE_SEARCH_ROOT" -name "$lib" -type f -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then add_dir "$(dirname "$found")"; echo "found $lib at $found" | tee -a "$LOG"; else echo "not found: $lib" | tee -a "$LOG"; fi
  done <<< "$missing"
done
LD="$(make_ld)"
{
  echo "# generated $(date -Is) by refresh_spectre_runtime_v9.sh"
  echo "export SPECTRE_CMD=\"$SPECTRE_CMD\""
  echo "export CADENCE_INSTALL_ROOT=\"$CADENCE_INSTALL_ROOT\""
  echo "export CADENCE_SEARCH_ROOT=\"$CADENCE_SEARCH_ROOT\""
  echo "export PATH=\"$BIN_DIR:\${PATH:-}\""
  echo "export LD_LIBRARY_PATH=\"$LD:\${LD_LIBRARY_PATH:-}\""
} > "$TMP"
mv "$TMP" "$OUT"
echo "Wrote $OUT" | tee -a "$LOG"
