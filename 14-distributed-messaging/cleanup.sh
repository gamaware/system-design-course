#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 14: Cleanup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed, nothing to clean up."
    exit 1
fi

echo "Stopping and removing all lab resources..."
docker compose --profile scale down -v --rmi local --remove-orphans 2>/dev/null || true

# Remove anything left behind if the compose project was renamed or partially started
docker rm -f lab14-rabbitmq lab14-worker-1 lab14-worker-2 lab14-tools 2>/dev/null || true
docker volume rm lab14_rabbitmq-data lab14_ledger-data 2>/dev/null || true
docker image rm lab14-app:local 2>/dev/null || true

echo ""
echo "Cleanup complete. All containers, volumes, the network, and the lab image removed."
