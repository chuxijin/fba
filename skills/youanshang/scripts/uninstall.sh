#!/usr/bin/env bash
set -euo pipefail
SCRIPT_PATH="${BASH_SOURCE[0]//\\//}"
SCRIPT_DIR="$(cd -- "${SCRIPT_PATH%/*}" && pwd)"
exec node "$SCRIPT_DIR/uninstall.cjs" "$@"
