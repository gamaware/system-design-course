#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 05: Cleanup ==="
echo ""

echo "Stopping and removing all lab resources..."
compose_ok=true
docker compose down -v --remove-orphans || compose_ok=false

# Force-remove anything left behind (for example, a container started by hand)
docker rm -f lab05-node1 lab05-node2 lab05-node3 lab05-toxiproxy lab05-haproxy lab05-client \
    > /dev/null 2>&1 || true

if [ "$compose_ok" = false ]; then
    echo "" >&2
    echo "ERROR: 'docker compose down' failed, so the lab network may still exist." >&2
    echo "Check that Docker Desktop is running, then run ./cleanup.sh again." >&2
    exit 1
fi

echo ""
echo "Cleanup complete. All lab containers and the lab network were removed."
echo "The pinned images stay in the local cache; remove them with 'docker image rm' if needed."
