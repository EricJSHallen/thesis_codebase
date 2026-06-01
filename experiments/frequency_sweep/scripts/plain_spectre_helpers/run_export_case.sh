#!/usr/bin/env bash
set -u -o pipefail

CASE_DIR="${1:?usage: run_export_case.sh CASE_DIR}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
OCN="$RUN_DIR/ocn/export_psf_to_txt.ocn"
LOG="$CASE_DIR/export_ocean.log"

: "${CADENCE_INSTALL_ROOT:=/projects/bics/cadence/installs}"
: "${IC_VERSION:=IC231}"
IC_ROOT="${IC_ROOT:-$CADENCE_INSTALL_ROOT/$IC_VERSION}"

if [[ ! -f "$OCN" ]]; then
  echo "ERROR: missing export OCN: $OCN" >&2
  exit 1
fi

prepend_path() {
  local d="$1"
  [[ -d "$d" ]] || return 0
  case ":${PATH:-}:" in
    *":$d:"*) ;;
    *) export PATH="$d:${PATH:-}" ;;
  esac
}

prepend_ld_library_path() {
  local d="$1"
  [[ -d "$d" ]] || return 0
  case ":${LD_LIBRARY_PATH:-}:" in
    *":$d:"*) ;;
    *) export LD_LIBRARY_PATH="$d:${LD_LIBRARY_PATH:-}" ;;
  esac
}

setup_cadence_ic_env() {
  export CADENCE_INSTALL_ROOT
  export IC_ROOT
  export CDS_AUTO_64BIT="${CDS_AUTO_64BIT:-ALL}"

  prepend_path "$IC_ROOT/tools/bin"
  prepend_path "$IC_ROOT/bin"
  prepend_path "$IC_ROOT/tools.lnx86/dfII/bin"
  prepend_path "$IC_ROOT/tools.lnx86/dfII/bin/64bit"

  prepend_ld_library_path "$IC_ROOT/tools/lib"
  prepend_ld_library_path "$IC_ROOT/tools/lib/64bit"
  prepend_ld_library_path "$IC_ROOT/tools.lnx86/lib"
  prepend_ld_library_path "$IC_ROOT/tools.lnx86/lib/64bit"
  prepend_ld_library_path "$IC_ROOT/tools.lnx86/dfII/lib"
  prepend_ld_library_path "$IC_ROOT/tools.lnx86/dfII/lib/64bit"
  prepend_ld_library_path "$IC_ROOT/tools/dfII/lib"
  prepend_ld_library_path "$IC_ROOT/tools/dfII/lib/64bit"
}

choose_export_launcher() {
  local cand

  for cand in \
    "$(command -v ocean 2>/dev/null || true)" \
    "$IC_ROOT/tools/bin/ocean" \
    "$IC_ROOT/bin/ocean" \
    "$IC_ROOT/tools.lnx86/dfII/bin/ocean"
  do
    if [[ -n "$cand" && -x "$cand" ]]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  for cand in \
    "$(command -v virtuoso 2>/dev/null || true)" \
    "$IC_ROOT/tools/bin/virtuoso" \
    "$IC_ROOT/bin/virtuoso" \
    "$IC_ROOT/tools.lnx86/dfII/bin/virtuoso" \
    "$IC_ROOT/tools.lnx86/dfII/bin/64bit/virtuoso"
  do
    if [[ -n "$cand" && -x "$cand" ]]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  return 1
}

setup_cadence_ic_env

{
  echo "CASE_DIR=$CASE_DIR"
  echo "OCN=$OCN"
  echo "CADENCE_INSTALL_ROOT=$CADENCE_INSTALL_ROOT"
  echo "IC_ROOT=$IC_ROOT"
  echo "PATH=$PATH"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
} > "$LOG"

LAUNCHER="$(choose_export_launcher || true)"

if [[ -z "$LAUNCHER" ]]; then
  {
    echo "ERROR: neither ocean nor a usable Virtuoso launcher is available for PSF export."
    echo "Checked IC_ROOT=$IC_ROOT"
  } >> "$LOG"
  exit 127
fi

echo "Using export launcher: $LAUNCHER" >> "$LOG"

CAD_CASE_DIR="$CASE_DIR" CAD_BATCH_EXIT=1 "$LAUNCHER" -nograph -restore "$OCN" >> "$LOG" 2>&1
rc=$?

if [[ "$rc" -ne 0 ]]; then
  echo "ERROR: export launcher failed with rc=$rc" >> "$LOG"
  exit "$rc"
fi

if [[ ! -f "$CASE_DIR/output_signals.txt" ]]; then
  echo "ERROR: export completed but did not create $CASE_DIR/output_signals.txt" >> "$LOG"
  exit 1
fi