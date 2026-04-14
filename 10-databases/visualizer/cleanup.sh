#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Cleaning up visualizer environment ==="
docker compose down -v --remove-orphans 2>/dev/null || true
echo "=== Cleanup complete ==="
