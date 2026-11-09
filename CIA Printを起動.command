#!/bin/zsh
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

printf '\e]0;CIA Print\a'
clear
echo "CIA Printを起動しています…"
echo

exec "$PROJECT_DIR/scripts/start_local.sh"
