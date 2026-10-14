#!/usr/bin/env bash
set -euo pipefail
SCRIPT_PATH="${BASH_SOURCE[0]//\\//}"
SCRIPT_DIR="$(cd -- "${SCRIPT_PATH%/*}" && pwd)"
case "$OSTYPE" in
  linux*|darwin*|cygwin*|msys*|mingw*) ;;
  *) printf '[error] 不支持的操作系统\n' >&2; exit 1 ;;
esac
if ! command -v node >/dev/null 2>&1; then
  printf '[error] 未检测到 Node.js，请安装 Node.js 22+：https://nodejs.org/\n' >&2
  exit 1
fi
# 系统 Node 不满足版本时明确失败；不静默 sudo、不修改全局运行环境。
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { console.error("请安装 Node.js 22+"); process.exit(1); }'
exec node "$SCRIPT_DIR/install.cjs" "$@"
