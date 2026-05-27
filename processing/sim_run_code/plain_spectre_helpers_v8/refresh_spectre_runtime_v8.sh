#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

: "${SPECTRE_BIN:=/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre}"
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${CADENCE_SEARCH_ROOT:=/projects/bics/cadence}"

OUT="$RUN_DIR/support/spectre_runtime.env"
TMP="$OUT.tmp"
mkdir -p "$RUN_DIR/support" "$RUN_DIR/logs"
LOG="$RUN_DIR/logs/refresh_spectre_runtime.log"
: > "$LOG"

if [ ! -x "$SPECTRE_BIN" ]; then
  echo "ERROR: SPECTRE_BIN not executable: $SPECTRE_BIN" | tee -a "$LOG" >&2
  exit 1
fi

SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
SPECTRE_ROOT="$(cd "$SPECTRE_BIN_DIR/../../.." 2>/dev/null && pwd || true)"

# Ordered directory set. Use a newline list and de-duplicate at the end.
DIR_LIST="$RUN_DIR/support/spectre_runtime_dirs.txt"
: > "$DIR_LIST"
add_dir() {
  [ -n "${1:-}" ] && [ -d "$1" ] && printf '%s\n' "$1" >> "$DIR_LIST"
}

# Conservative known-good candidates from the observed BIC/Cadence layout.
add_dir "$SPECTRE_BIN_DIR"
add_dir "$SPECTRE_BIN_DIR/../lib"
add_dir "$SPECTRE_BIN_DIR/../../lib"
add_dir "$SPECTRE_BIN_DIR/../../lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"
add_dir "$CADENCE_INSTALL_ROOT/XCELIUM2309/tools.lnx86/lib"
add_dir "$CADENCE_INSTALL_ROOT/XCELIUM2309/tools.lnx86/lib/64bit"

make_ld() {
  awk '!seen[$0]++' "$DIR_LIST" | paste -sd: -
}

for pass in 1 2 3 4 5 6 7 8; do
  LD="$(make_ld)"
  export LD_LIBRARY_PATH="${LD}${LD:+:}${LD_LIBRARY_PATH:-}"
  missing="$(ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)"
  echo "pass=$pass missing=$(echo "$missing" | tr '\n' ' ')" | tee -a "$LOG"
  [ -z "$missing" ] && break

  while read -r lib; do
    [ -z "$lib" ] && continue
    echo "searching for $lib under $CADENCE_SEARCH_ROOT" | tee -a "$LOG"
    # -print -quit returns the first match; this is deliberate to keep refresh finite.
    found="$(find "$CADENCE_SEARCH_ROOT" -name "$lib" -type f -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then
      dir="$(dirname "$found")"
      echo "found $lib at $found" | tee -a "$LOG"
      add_dir "$dir"
    else
      echo "not found: $lib" | tee -a "$LOG"
    fi
  done <<< "$missing"
done

LD="$(make_ld)"
{
  echo "# generated $(date -Is) by refresh_spectre_runtime_v8.sh"
  echo "export SPECTRE_BIN=\"$SPECTRE_BIN\""
  echo "export CADENCE_INSTALL_ROOT=\"$CADENCE_INSTALL_ROOT\""
  echo "export CADENCE_SEARCH_ROOT=\"$CADENCE_SEARCH_ROOT\""
  echo "export PATH=\"$SPECTRE_BIN_DIR:\${PATH:-}\""
  echo "export LD_LIBRARY_PATH=\"$LD:\${LD_LIBRARY_PATH:-}\""
} > "$TMP"
mv "$TMP" "$OUT"

# shellcheck disable=SC1090
source "$OUT"
echo "Wrote $OUT" | tee -a "$LOG"
echo "Final missing libraries, if any:" | tee -a "$LOG"
ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}' | tee -a "$LOG" || true
