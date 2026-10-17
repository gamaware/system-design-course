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

# Both removal paths above hide their errors, so check the result before deleting anything else.
# Each query is checked on its own: a failed docker ps must not pass because docker network ls worked.
if ! containers="$(docker ps -aq --filter name=lab12-)" \
    || ! networks="$(docker network ls -q --filter name=lab12-)" \
    || [ -n "$containers$networks" ]; then
    echo "ERROR: The lab containers or networks could not be removed. Is the Docker daemon running?"
    echo "certs/ was kept. Check with: docker ps -a --filter name=lab12-"
    exit 1
fi

echo "Removing generated TLS certificates..."
rm -rf "$SCRIPT_DIR/certs"

echo ""
echo "Cleanup complete. Verify with: docker ps -a --filter name=lab12-"
