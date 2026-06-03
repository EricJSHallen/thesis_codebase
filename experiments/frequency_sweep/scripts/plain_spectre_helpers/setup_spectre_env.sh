#!/usr/bin/env bash
# Runtime setup for the plain Spectre/OCEAN export workers.
# Source this file from a generated run directory.

set -euo pipefail

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

# BICS site paths. Keep them before generic Cadence install paths so the site
# wrappers can set the correct XP018/PDK environment.
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
      set +u
      # shellcheck disable=SC1090
      source "$setup" >/dev/null 2>&1 || true
      set -u
    fi
  done
}
_source_optional_bics_setup

# Add likely Cadence binary locations only if present.
for d in \
  "$CADENCE_INSTALL_ROOT/ICADVM*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/ICADVM*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/IC*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/IC*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/SPECTRE*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/SPECTRE*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/MMSIM*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/MMSIM*/tools.lnx86/bin" \
  "$CADENCE_INSTALL_ROOT/EXT*/tools/bin" \
  "$CADENCE_INSTALL_ROOT/EXT*/tools.lnx86/bin"; do
  for reald in $d; do
    _add_path_dir "$reald"
  done
done

# Return only real executable paths. command -v/type can return alias text such
# as: alias xp018v='xp018 ; xkit&'. That string is not executable and caused the
# patch5 immediate export failures.
_real_exe() {
  type -P "$1" 2>/dev/null || true
}

check_spectre_runtime() {
  local cmd="${SPECTRE_CMD:-spectre}"
  if [[ -z "$(_real_exe "$cmd")" && ! -x "$cmd" ]]; then
    echo "ERROR: cannot find Spectre command: $cmd" >&2
    echo "Set SPECTRE_CMD or source the correct Cadence environment." >&2
    return 127
  fi
  "$cmd" -W 2>/dev/null | head -5 || true
}

_login_shell_has() {
  local probe="$1"
  bash -lic "$probe" >/dev/null 2>&1
}

find_ocean_runner() {
  # Explicit override. This must be a true executable or a command name that
  # resolves to a true executable path. Alias text is rejected deliberately.
  if [[ -n "${OCEAN_CMD:-}" ]]; then
    local explicit_path
    explicit_path="$(_real_exe "$OCEAN_CMD")"
    if [[ -n "$explicit_path" ]]; then
      export OCEAN_CMD="$explicit_path"
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-direct}"
      return 0
    elif [[ -x "$OCEAN_CMD" ]]; then
      export OCEAN_RUNNER_MODE="${OCEAN_RUNNER_MODE:-direct}"
      return 0
    else
      echo "ERROR: OCEAN_CMD is set but is not a real executable: $OCEAN_CMD" >&2
      echo "Do not set OCEAN_CMD to alias output such as alias xp018v='xp018 ; xkit&'." >&2
      return 127
    fi
  fi

  # Direct executables available to non-interactive scripts.
  local p
  for name in ocean virtuoso xkit; do
    p="$(_real_exe "$name")"
    if [[ -n "$p" ]]; then
      export OCEAN_CMD="$p"
      case "$name" in
        ocean) export OCEAN_RUNNER_MODE="direct_ocean" ;;
        virtuoso) export OCEAN_RUNNER_MODE="direct_virtuoso" ;;
        xkit) export OCEAN_RUNNER_MODE="direct_xkit" ;;
      esac
      return 0
    fi
  done

  # Login/interactive shell probes. These are intentionally separate from the
  # direct executable path because BICS commonly exposes XP018 as aliases.
  if _login_shell_has 'type -P ocean'; then
    export OCEAN_CMD="ocean"
    export OCEAN_RUNNER_MODE="login_ocean"
    return 0
  fi
  if _login_shell_has 'type -P virtuoso'; then
    export OCEAN_CMD="virtuoso"
    export OCEAN_RUNNER_MODE="login_virtuoso"
    return 0
  fi
  if _login_shell_has 'type -P xkit'; then
    export OCEAN_CMD="xkit"
    export OCEAN_RUNNER_MODE="login_xkit"
    return 0
  fi

  # XP018 alias path observed on BICS: xp018v='xp018 ; xkit&'. Do not execute
  # xp018v with -nograph arguments. Instead run xp018 first, then run xkit with
  # the OCEAN restore arguments in the same login shell.
  if _login_shell_has 'type xp018 >/dev/null 2>&1 && type -P xkit >/dev/null 2>&1'; then
    export OCEAN_CMD="xp018_then_xkit"
    export OCEAN_RUNNER_MODE="login_xp018_then_xkit"
    return 0
  fi
  if _login_shell_has 'type xp018 >/dev/null 2>&1 && type v >/dev/null 2>&1'; then
    export OCEAN_CMD="xp018_then_v"
    export OCEAN_RUNNER_MODE="login_xp018_then_v"
    return 0
  fi

  echo "ERROR: cannot find an OCEAN export runner." >&2
  echo "Tried real executables ocean/virtuoso/xkit and BICS login-shell variants." >&2
  echo "If needed, set OCEAN_CMD to a full executable path, not to an alias." >&2
  return 127
}

check_export_runtime() {
  find_ocean_runner
  echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
}
