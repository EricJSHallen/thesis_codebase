#!/usr/bin/env bash
# Runtime setup for the plain Spectre/OCEAN export workers.
# Safe to source from an interactive shell: this file deliberately does NOT set `set -e`.

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
RUNINFO="$THIS_DIR/RUNINFO.txt"
if [[ -f "$RUNINFO" ]]; then
  # shellcheck disable=SC1090
  source "$RUNINFO"
fi

export CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"

_add_path_dir() {
  local d="$1"
  [[ -d "$d" ]] || return 0
  case ":$PATH:" in
    *":$d:"*) ;;
    *) export PATH="$d:$PATH" ;;
  esac
}

# BICS site wrapper paths. These are useful for Spectre and site setup, but the
# OCEAN/Virtuoso exporter below requires a real executable, not aliases such as
# xp018v='xp018 ; xkit&'.
_add_path_dir "/projects/bics/NX/bin"
_add_path_dir "/projects/bics/bin"

_source_optional_bics_setup() {
  local setup
  for setup in \
    "/projects/bics/setup_centos_only.sh" \
    "/projects/bics/setup-centos-only.sh" \
    "/projects/bics/setup_centos.sh" \
    "/projects/bics/setup.sh" \
    "/projects/bics/NX/setup.sh"; do
    if [[ -r "$setup" ]]; then
      # shellcheck disable=SC1090
      source "$setup" >/dev/null 2>&1 || true
    fi
  done
}
_source_optional_bics_setup

# Add likely Cadence binary locations. The critical fix in patch8 is adding the
# dfII bin directories; Virtuoso/OCEAN commonly live there rather than in tools/bin.
for d in \
  "$CADENCE_INSTALL_ROOT"/*/tools/bin \
  "$CADENCE_INSTALL_ROOT"/*/tools.lnx86/bin \
  "$CADENCE_INSTALL_ROOT"/*/tools/dfII/bin \
  "$CADENCE_INSTALL_ROOT"/*/tools.lnx86/dfII/bin \
  "$CADENCE_INSTALL_ROOT"/*/tools/plot/bin \
  "$CADENCE_INSTALL_ROOT"/*/tools.lnx86/plot/bin; do
  _add_path_dir "$d"
done

# Return only real executable paths. `command -v` can return alias text in some
# BICS shells; `type -P` returns pathnames only.
_real_exe() { type -P "$1" 2>/dev/null || true; }

_find_cadence_exe_by_glob() {
  local name="$1"
  local p
  for p in \
    "$CADENCE_INSTALL_ROOT"/*/tools/bin/"$name" \
    "$CADENCE_INSTALL_ROOT"/*/tools.lnx86/bin/"$name" \
    "$CADENCE_INSTALL_ROOT"/*/tools/dfII/bin/"$name" \
    "$CADENCE_INSTALL_ROOT"/*/tools.lnx86/dfII/bin/"$name"; do
    [[ -x "$p" ]] && { printf '%s\n' "$p"; return 0; }
  done
  return 1
}

check_spectre_runtime() {
  local cmd="${SPECTRE_CMD:-spectre}"
  local p
  p="$(_real_exe "$cmd")"
  if [[ -z "$p" && ! -x "$cmd" ]]; then
    echo "ERROR: cannot find Spectre command: $cmd" >&2
    echo "Set SPECTRE_CMD or source the correct Cadence environment." >&2
    return 127
  fi
  "$cmd" -W 2>/dev/null | head -5 || true
  return 0
}

find_ocean_runner() {
  # Explicit override: require a real executable path or executable command name.
  # Do not accept alias text.
  if [[ -n "${OCEAN_CMD:-}" ]]; then
    local explicit_path
    explicit_path="$(_real_exe "$OCEAN_CMD")"
    if [[ -n "$explicit_path" ]]; then
      export OCEAN_CMD="$explicit_path"
      export OCEAN_RUNNER_MODE="direct"
      return 0
    elif [[ -x "$OCEAN_CMD" ]]; then
      export OCEAN_RUNNER_MODE="direct"
      return 0
    else
      echo "ERROR: OCEAN_CMD is set but is not a real executable: $OCEAN_CMD" >&2
      echo "Use a full path such as /path/to/ocean or /path/to/virtuoso, not an alias expansion." >&2
      return 127
    fi
  fi

  local name p
  # Prefer ocean if available; virtuoso -nograph -restore is the fallback.
  for name in ocean virtuoso; do
    p="$(_real_exe "$name")"
    [[ -z "$p" ]] && p="$(_find_cadence_exe_by_glob "$name" 2>/dev/null || true)"
    if [[ -n "$p" && -x "$p" ]]; then
      export OCEAN_CMD="$p"
      case "$name" in
        ocean) export OCEAN_RUNNER_MODE="direct_ocean" ;;
        virtuoso) export OCEAN_RUNNER_MODE="direct_virtuoso" ;;
      esac
      return 0
    fi
  done

  echo "ERROR: cannot find a real OCEAN/Virtuoso export executable." >&2
  echo "Checked PATH and $CADENCE_INSTALL_ROOT/*/tools/{bin,dfII/bin}." >&2
  echo "Set OCEAN_CMD to the full path of ocean or virtuoso before starting a new run." >&2
  return 127
}

check_export_runtime() {
  if find_ocean_runner; then
    echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
    return 0
  fi
  return 127
}
