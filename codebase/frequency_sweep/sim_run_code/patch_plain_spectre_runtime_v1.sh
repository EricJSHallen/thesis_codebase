#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RUN_DIR"

if [ ! -f RUNINFO.txt ]; then
  echo "ERROR: RUNINFO.txt not found. Run this from the plain-spectre run directory." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

mkdir -p "$RUN_DIR/support"

cat > "$RUN_DIR/setup_spectre_env.sh" <<'EOS'
#!/usr/bin/env bash
# Source this file from a plain-spectre run directory:
#   source ./setup_spectre_env.sh

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

if [ -f "$RUN_DIR/support/spectre_runtime.env" ]; then
  # shellcheck disable=SC1091
  source "$RUN_DIR/support/spectre_runtime.env"
fi

export SPECTRE_BIN

check_spectre_runtime() {
  if [ ! -x "$SPECTRE_BIN" ]; then
    echo "SPECTRE_BIN is not executable: $SPECTRE_BIN" >&2
    return 2
  fi
  ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}' || true
}

export -f check_spectre_runtime 2>/dev/null || true
EOS

cat > "$RUN_DIR/refresh_spectre_runtime.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"

OUT="$RUN_DIR/support/spectre_runtime.env"
TMP="$OUT.tmp"
mkdir -p "$RUN_DIR/support"

if [ ! -x "$SPECTRE_BIN" ]; then
  echo "ERROR: SPECTRE_BIN is not executable: $SPECTRE_BIN" >&2
  exit 1
fi

CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"
SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
SPECTRE_TREE="$(cd "$SPECTRE_BIN_DIR/../../.." 2>/dev/null && pwd || true)"

# Candidate library roots. Keep this list explicit and finite; avoid expensive searches during source/worker startup.
DIRS=()
add_dir() { [ -n "${1:-}" ] && [ -d "$1" ] && DIRS+=("$1"); }

add_dir "$SPECTRE_BIN_DIR"
add_dir "$SPECTRE_TREE/lib/64bit"
add_dir "$SPECTRE_TREE/lib"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib/64bit"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib"
add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"
add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"

# Resolve missing direct dependencies iteratively. This script may take a little time, but it is run manually once.
for pass in 1 2 3 4 5; do
  LD_NOW="$(IFS=:; echo "${DIRS[*]}"):${LD_LIBRARY_PATH:-}"
  missing="$(LD_LIBRARY_PATH="$LD_NOW" ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)"
  [ -z "$missing" ] && break

  while IFS= read -r lib; do
    [ -z "$lib" ] && continue
    found="$(find "$CADENCE_INSTALL_ROOT" -name "$lib" -type f -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then
      add_dir "$(dirname "$found")"
    else
      echo "WARNING: could not locate missing library: $lib" >&2
    fi
  done <<< "$missing"
done

# De-duplicate while preserving order.
LD=""
for d in "${DIRS[@]}"; do
  [ -d "$d" ] || continue
  case ":$LD:" in
    *":$d:"*) ;;
    *) LD="${LD:+$LD:}$d" ;;
  esac
done

{
  echo "# generated $(date -Is)"
  echo "export SPECTRE_BIN=\"$SPECTRE_BIN\""
  echo "export PATH=\"$SPECTRE_BIN_DIR:\${PATH:-}\""
  echo "export LD_LIBRARY_PATH=\"$LD:\${LD_LIBRARY_PATH:-}\""
} > "$TMP"
mv "$TMP" "$OUT"

# shellcheck disable=SC1090
source "$OUT"

echo "Wrote $OUT"
echo "Missing after refresh, if any:"
ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print "  " $1 " => not found"}' || true
EOS

chmod +x "$RUN_DIR/setup_spectre_env.sh" "$RUN_DIR/refresh_spectre_runtime.sh"

echo "Patched setup_spectre_env.sh and refresh_spectre_runtime.sh in: $RUN_DIR"
echo "Next: ./refresh_spectre_runtime.sh && source ./setup_spectre_env.sh && check_spectre_runtime"
