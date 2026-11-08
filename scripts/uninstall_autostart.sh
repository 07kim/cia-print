#!/bin/zsh
set -eu

PLIST_PATH="$HOME/Library/LaunchAgents/jp.cia.print.plist"
launchctl bootout "gui/$(id -u)/jp.cia.print" 2>/dev/null || true
if [ -f "$PLIST_PATH" ]; then
  mv "$PLIST_PATH" "$HOME/.Trash/jp.cia.print.plist"
fi
echo "自動起動を解除しました。"
