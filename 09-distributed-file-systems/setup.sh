#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 09: Distributed File Systems (NFS + MinIO) ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

if ! docker compose version &> /dev/null 2>&1; then
    echo "ERROR: Docker Compose is not available."
    echo "Docker Compose is included with Docker Desktop."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Build and start infrastructure
echo "Building and starting NFS server, NFS clients, and MinIO..."
docker compose up -d --build nfs-server nfs-client-1 nfs-client-2 minio

echo ""
echo "Waiting for services to be healthy..."
i=0
while [ "$i" -lt 60 ]; do
    i=$((i + 1))
    nfs_ok=false
    minio_ok=false

    nfs_exports=$(docker exec nfs-server showmount -e localhost 2>/dev/null || true)
    if echo "$nfs_exports" | grep -q "/nfs/shared" \
        && echo "$nfs_exports" | grep -q "/nfs/data" \
        && echo "$nfs_exports" | grep -q "/nfs/backup"; then
        nfs_ok=true
    fi

    if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        minio_ok=true
    fi

    if [ "$nfs_ok" = true ] && [ "$minio_ok" = true ]; then
        echo "  NFS Server: ready (3 exports configured)"
        echo "  MinIO:      ready (4-drive erasure coding)"
        break
    fi

    if [ "$i" -eq 60 ]; then
        echo "ERROR: Services did not become healthy within 60 seconds."
        echo "Run 'docker compose logs' to check for errors."
        exit 1
    fi

    sleep 1
done

# Verify NFS mounts on clients
echo ""
echo "Verifying NFS client mounts..."
bash "$SCRIPT_DIR/scripts/verify-nfs.sh"

# Verify MinIO
echo ""
echo "Verifying MinIO server..."
bash "$SCRIPT_DIR/scripts/verify-minio.sh"

echo ""
echo "=== Environment ready ==="
echo ""
echo "NFS operations (exec into clients):"
echo "  docker exec -it nfs-client-1 bash"
echo "  docker exec -it nfs-client-2 bash"
echo ""
echo "MinIO operations (interactive mc client):"
echo "  docker compose --profile tools run --rm mc"
echo ""
echo "MinIO web console:"
echo "  http://localhost:9001"
echo "  User: minioadmin / Password: minioadmin123"
echo ""
echo "Follow the instructions in LAB.md for the full walkthrough."
