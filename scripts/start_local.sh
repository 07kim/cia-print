#!/bin/zsh
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

"$PROJECT_DIR/scripts/setup_printer.sh" || true

exec /usr/bin/caffeinate -dimsu "$(command -v python3)" "$PROJECT_DIR/local_server.py"
