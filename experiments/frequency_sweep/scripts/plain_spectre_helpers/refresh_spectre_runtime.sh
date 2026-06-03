#!/usr/bin/env bash
set -u
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/setup_spectre_env.sh"
check_spectre_runtime || exit $?
check_export_runtime || true
