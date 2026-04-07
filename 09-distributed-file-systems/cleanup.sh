#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 09: Cleanup ==="
echo ""

echo "Stopping and removing all lab resources..."
# First try compose down (handles network + volumes + images)
docker compose --profile tools down -v --rmi local --remove-orphans 2>/dev/null || true

# Force-remove any remaining containers (privileged NFS containers may resist SIGTERM)
docker rm -f nfs-server nfs-client-1 nfs-client-2 minio-server minio-client 2>/dev/null || true

# Remove any remaining lab volumes
docker volume ls -q --filter "name=09-distributed-file-systems" \
    | while read -r vol; do docker volume rm "$vol" 2>/dev/null || true; done

echo ""
echo "Cleanup complete. All containers, volumes, and images removed."
