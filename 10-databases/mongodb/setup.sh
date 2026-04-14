#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 10B: MongoDB Replica Set, Consistency, and Schema Design ==="
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
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Start MongoDB nodes
echo "Starting 3-node MongoDB replica set..."
docker compose up -d

echo ""
echo "Waiting for all MongoDB nodes to be healthy..."

for node in mongo1 mongo2 mongo3; do
    i=0
    while [ "$i" -lt 60 ]; do
        i=$((i + 1))
        if docker exec "$node" mongosh --quiet --eval "db.adminCommand('ping')" 2>/dev/null | grep -q "ok"; then
            echo "  $node: ready"
            break
        fi
        if [ "$i" -eq 60 ]; then
            echo "ERROR: $node did not start within 60 seconds."
            docker compose logs "$node"
            exit 1
        fi
        sleep 1
    done
done

# Initialize replica set and seed data
echo ""
echo "Initializing replica set and seeding data..."
docker cp init/rs-init.js mongo1:/tmp/rs-init.js
if ! docker exec mongo1 mongosh --quiet --file /tmp/rs-init.js 2>/dev/null; then
    echo "ERROR: Replica set initialization failed."
    docker compose logs mongo1 | tail -20
    exit 1
fi

# Wait for replica set to stabilize
echo "  Waiting for primary election..."
i=0
while [ "$i" -lt 30 ]; do
    i=$((i + 1))
    if docker exec mongo1 mongosh --quiet --eval "rs.status().members.find(m => m.stateStr === 'PRIMARY') ? 'ok' : ''" 2>/dev/null | grep -q "ok"; then
        break
    fi
    sleep 1
done

# Verify replica set
rs_status=$(docker exec mongo1 mongosh --quiet --eval "
const s = rs.status();
s.members.forEach(m => print(m.name + ': ' + m.stateStr));
" 2>/dev/null || true)

echo "  Replica set members:"
echo "$rs_status" | while IFS= read -r line; do
    if [ "$line" != "" ]; then
        echo "    $line"
    fi
done

echo ""
echo "=== Environment ready ==="
echo ""
echo "Connect to primary:"
echo "  docker exec -it mongo1 mongosh"
echo ""
echo "Follow the instructions in LAB-MONGODB.md for the full walkthrough."
