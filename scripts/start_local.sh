#!/bin/zsh
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

exec /usr/bin/caffeinate -dimsu "$(command -v python3)" "$PROJECT_DIR/local_server.py"
