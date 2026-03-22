#!/usr/bin/env bash
# Post-edit hook: auto-fix files after edits
set -euo pipefail

FILE="${TOOL_INPUT_FILE_PATH-}"

if [ "$FILE" = "" ]; then
    exit 0
fi

case "$FILE" in
    *.sh)
        if command -v shellharden > /dev/null 2>&1; then
            shellharden --replace "$FILE" 2>/dev/null || true
        fi
        if [ -f "$FILE" ]; then
            if IFS= read -r first_line < "$FILE"; then
                case "$first_line" in
                    '#!'*) chmod +x "$FILE" ;;
                esac
            fi
        fi
        ;;
    *.md)
        if command -v markdownlint > /dev/null 2>&1; then
            markdownlint --fix "$FILE" 2>/dev/null || true
        fi
        ;;
esac
