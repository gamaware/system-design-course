#!/usr/bin/env bash
# Post-edit hook: auto-fix files after edits
set -euo pipefail

FILE="$TOOL_INPUT_FILE_PATH"

case "$FILE" in
    *.sh)
        if command -v shellharden > /dev/null 2>&1; then
            shellharden --replace "$FILE" 2>/dev/null || true
        fi
        if [ -f "$FILE" ] && head -1 "$FILE" | grep -q '^#!'; then
            chmod +x "$FILE"
        fi
        ;;
    *.md)
        if command -v markdownlint > /dev/null 2>&1; then
            markdownlint --fix "$FILE" 2>/dev/null || true
        fi
        ;;
esac
