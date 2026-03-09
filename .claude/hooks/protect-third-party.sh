#!/bin/bash
# Pre-edit hook: block edits to third-party directories
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || FILE_PATH=""

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Block edits to third-party ecsdemo directories
if [[ "$FILE_PATH" == ecsdemo-* || "$FILE_PATH" == */ecsdemo-* ]]; then
  echo "Blocked: $FILE_PATH is a third-party file (ecsdemo-*). Do not modify." >&2
  exit 2
fi
