#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/support" "$RUN_DIR/logs"
LOG="$RUN_DIR/logs/refresh_spectre_runtime.log"; : > "$LOG"
: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${IC_VERSION:=IC231}"; : "${IC_ROOT:=$CADENCE_INSTALL_ROOT/$IC_VERSION}"; : "${CADENCE_SEARCH_ROOT:=/projects/bics/cadence}"
choose() { for c in "$@"; do [[ -n "$c" && -x "$c" ]] && { printf '%s\n' "$c"; return 0; }; done; return 1; }
SPECTRE_CHOSEN="$(choose "${SPECTRE_CMD:-}" "$CADENCE_INSTALL_ROOT/SPECTRE231/tools/bin/spectre" "$CADENCE_INSTALL_ROOT/SPECTRE231/bin/spectre" "$(command -v spectre 2>/dev/null || true)" || true)"
[[ -n "$SPECTRE_CHOSEN" ]] || { echo "ERROR: no Spectre launcher found" | tee -a "$LOG"; exit 1; }
echo "Using Spectre wrapper: $SPECTRE_CHOSEN" | tee -a "$LOG"
cat > "$RUN_DIR/support/spectre_runtime.env" <<EOF_ENV
export CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
export CADENCE_SEARCH_ROOT="$CADENCE_SEARCH_ROOT"
export SPECTRE_CMD="$SPECTRE_CHOSEN"
export PATH="$(dirname "$SPECTRE_CHOSEN"):\${PATH:-}"
EOF_ENV
EXPORT_CHOSEN="$(choose "${CADENCE_EXPORT_LAUNCHER:-}" "$(command -v ocean 2>/dev/null || true)" "$IC_ROOT/tools.lnx86/dfII/bin/ocean" "$IC_ROOT/tools.lnx86/dfII/bin/64bit/ocean" "$(command -v virtuoso 2>/dev/null || true)" "$IC_ROOT/tools.lnx86/dfII/bin/64bit/virtuoso" || true)"
if [[ -z "$EXPORT_CHOSEN" ]]; then echo "WARNING: no ocean/virtuoso export launcher found" | tee -a "$LOG"; exit 0; fi
echo "Using export launcher: $EXPORT_CHOSEN" | tee -a "$LOG"
DIRS="$RUN_DIR/support/cadence_ic_runtime_dirs.txt"; : > "$DIRS"
add_dir(){ [[ -d "$1" ]] && printf '%s\n' "$1" >> "$DIRS"; }
add_dir "$(dirname "$EXPORT_CHOSEN")"; add_dir "$IC_ROOT/tools.lnx86/lib"; add_dir "$IC_ROOT/tools.lnx86/lib/64bit"; add_dir "$IC_ROOT/tools.lnx86/dfII/lib"; add_dir "$IC_ROOT/tools.lnx86/dfII/lib/64bit"; add_dir "$IC_ROOT/tools/lib"; add_dir "$IC_ROOT/tools/lib/64bit"
for pass in 1 2 3 4 5; do
  LD_NOW="$(awk '!seen[$0]++' "$DIRS" | paste -sd: -)"; export LD_LIBRARY_PATH="$LD_NOW:${LD_LIBRARY_PATH:-}"
  missing="$(ldd "$EXPORT_CHOSEN" 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)"
  echo "[cadence_ic] pass=$pass missing=$(echo "$missing" | tr '\n' ' ')" | tee -a "$LOG"
  [[ -z "$missing" ]] && break
  while IFS= read -r lib; do [[ -n "$lib" ]] || continue; f="$(find "$CADENCE_SEARCH_ROOT" "$CADENCE_INSTALL_ROOT" -name "$lib" -type f -print -quit 2>/dev/null || true)"; [[ -n "$f" ]] && add_dir "$(dirname "$f")"; done <<< "$missing"
done
LD_FINAL="$(awk '!seen[$0]++' "$DIRS" | paste -sd: -)"
cat > "$RUN_DIR/support/cadence_ic_runtime.env" <<EOF_ENV
export CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
export IC_VERSION="$IC_VERSION"
export IC_ROOT="$IC_ROOT"
export CADENCE_SEARCH_ROOT="$CADENCE_SEARCH_ROOT"
export CADENCE_EXPORT_LAUNCHER="$EXPORT_CHOSEN"
export PATH="$(dirname "$EXPORT_CHOSEN"):\${PATH:-}"
export LD_LIBRARY_PATH="$LD_FINAL:\${LD_LIBRARY_PATH:-}"
EOF_ENV
