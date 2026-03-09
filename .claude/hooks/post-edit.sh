#!/bin/bash
# Post-edit hook: auto-fix shell scripts and markdown files after edits
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Auto-fix shell scripts with shellharden and restore executable permissions
if [[ "$FILE_PATH" =~ \.sh$ ]]; then
  shellharden --replace "$FILE_PATH" 2>/dev/null || true
  chmod +x "$FILE_PATH"
fi

# Auto-fix markdown with markdownlint
if [[ "$FILE_PATH" =~ \.md$ ]]; then
  npx markdownlint-cli2 --fix "$FILE_PATH" 2>/dev/null || true
fi
