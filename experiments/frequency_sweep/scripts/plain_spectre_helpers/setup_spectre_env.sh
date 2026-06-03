#!/usr/bin/env bash
# Runtime setup for the plain Spectre/OCEAN export workers.
# Safe to source from an interactive shell: this file deliberately does NOT set
# `set -e`. Earlier patches enabled errexit when sourced; then a failed
# check_export_runtime could close the user's tmux/shell pane.

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
      # shellcheck disable=SC1090
      source "$setup" >/dev/null 2>&1 || true
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
# as: alias xp018v='xp018 ; xkit&'. That string is not executable.
_real_exe() {
  type -P "$1" 2>/dev/null || true
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

_login_shell_probe() {
  local probe="$1"
  bash -lic "$probe" >/dev/null 2>&1
}

find_ocean_runner() {
  # Explicit override: require a real executable path or executable command name.
  # Do not accept alias text.
  if [[ -n "${OCEAN_CMD:-}" && "${OCEAN_CMD}" != "auto_bics" ]]; then
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
      echo "Use a full path such as /path/to/virtuoso, not an alias expansion." >&2
      return 127
    fi
  fi

  local name p
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

  # BICS/NX environment often exposes commands/aliases only in an interactive
  # login shell. Do not use xp018v, because it expands to `xp018 ; xkit&` and
  # can launch a background GUI or return alias text. Instead use an automatic
  # login-shell launcher that first runs `xp018` if present, then tries real
  # OCEAN-capable commands/aliases inside that same shell.
  if _login_shell_probe 'type xp018 >/dev/null 2>&1 || type xkit >/dev/null 2>&1 || type v >/dev/null 2>&1 || type virtuoso >/dev/null 2>&1 || type ocean >/dev/null 2>&1'; then
    export OCEAN_CMD="auto_bics"
    export OCEAN_RUNNER_MODE="auto_bics_login"
    return 0
  fi

  # Final fallback: allow worker-side export to try auto_bics even if preflight
  # cannot prove the aliases exist. This prevents setup from blocking a fresh
  # Spectre run merely because the export launcher is visible only after xp018.
  export OCEAN_CMD="auto_bics"
  export OCEAN_RUNNER_MODE="auto_bics_login_unverified"
  return 0
}

check_export_runtime() {
  if find_ocean_runner; then
    echo "OCEAN export runner: ${OCEAN_RUNNER_MODE:-unknown} via ${OCEAN_CMD:-unknown}"
    return 0
  fi
  echo "WARNING: no OCEAN export runner detected at preflight." >&2
  echo "Workers will still try the auto BICS launcher at export time." >&2
  return 0
}
