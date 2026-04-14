#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Cleaning up MySQL lab environment ==="
echo ""

echo "Stopping containers..."
docker compose down -v --remove-orphans 2>/dev/null || true

echo "Removing volumes..."
docker volume rm mysql_primary-data mysql_replica-data 2>/dev/null || true

echo ""
echo "=== Cleanup complete ==="
