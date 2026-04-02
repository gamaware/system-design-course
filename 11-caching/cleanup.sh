#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 11: Cleanup ==="
echo ""

echo "Stopping all containers..."
docker compose --profile cpp --profile csharp --profile java down -v 2>/dev/null || true

echo "Removing locally built images..."
docker compose --profile cpp --profile csharp --profile java down --rmi local 2>/dev/null || true

echo ""
echo "Cleanup complete. All containers, volumes, and images removed."
