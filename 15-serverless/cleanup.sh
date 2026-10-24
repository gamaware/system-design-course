#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 15: Cleanup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed, nothing to clean up."
    exit 1
fi

echo "Stopping and removing all lab resources..."
docker compose down -v --rmi local --remove-orphans 2>/dev/null || true

# Remove anything left behind if the compose project was renamed or partially started,
# including every copy of fn-work that Task 7 started with --scale.
docker ps -aq --filter label=com.docker.compose.project=lab15 | while read -r container; do
    docker rm -f "$container" > /dev/null 2>&1 || true
done
docker rm -f lab15-dynamodb lab15-fn-orders lab15-fn-processor lab15-gateway 2>/dev/null || true
docker network rm lab15_default 2>/dev/null || true
docker image rm lab15-fn-orders:local lab15-fn-processor:local lab15-fn-work:local lab15-gateway:local 2>/dev/null || true

echo ""
echo "Cleanup complete. All containers, the network, and the lab images removed."
