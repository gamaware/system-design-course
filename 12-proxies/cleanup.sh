#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 12: Cleanup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

echo "Stopping and removing containers, networks, volumes and the backend image..."
docker compose down -v --rmi local --remove-orphans 2>/dev/null || true

# Remove anything left behind if the compose project was renamed or edited.
docker rm -f lab12-users lab12-orders lab12-proxy lab12-sniffer \
    lab12-forward-proxy lab12-public-site lab12-workstation > /dev/null 2>&1 || true
docker network rm lab12-backend lab12-corp lab12-internet > /dev/null 2>&1 || true

echo "Removing generated TLS certificates..."
rm -rf "$SCRIPT_DIR/certs"

echo ""
echo "Cleanup complete. Verify with: docker ps -a --filter name=lab12-"
