#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 10C: Cassandra Multi-node, Consistency, and Partition Keys ==="
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

# Start Cassandra cluster (nodes start sequentially due to depends_on)
echo "Starting 3-node Cassandra cluster..."
echo "  (This takes 2-4 minutes -- each node must join the ring)"
docker compose up -d

# Wait for all nodes to be healthy
for node in cass1 cass2 cass3; do
    echo ""
    echo "Waiting for $node to join the cluster..."
    i=0
    while [ "$i" -lt 180 ]; do
        i=$((i + 1))
        if docker exec "$node" cqlsh -e "SELECT now() FROM system.local" > /dev/null 2>&1; then
            echo "  $node: ready"
            break
        fi
        if [ "$i" -eq 180 ]; then
            echo "ERROR: $node did not start within 3 minutes."
            docker compose logs "$node" | tail -20
            exit 1
        fi
        sleep 1
    done
done

# Check cluster status
echo ""
echo "Cluster status:"
docker exec cass1 nodetool status 2>/dev/null | grep -E "^(UN|DN|Datacenter|=)" || true

# Load schema and seed data
echo ""
echo "Loading schema and seed data..."
docker cp init/schema.cql cass1:/tmp/schema.cql
docker exec cass1 cqlsh -f /tmp/schema.cql 2>/dev/null

echo "  Schema created and data seeded."

echo ""
echo "=== Environment ready ==="
echo ""
echo "Connect to Cassandra:"
echo "  docker exec -it cass1 cqlsh"
echo ""
echo "Check cluster health:"
echo "  docker exec cass1 nodetool status"
echo ""
echo "Follow the instructions in LAB-CASSANDRA.md for the full walkthrough."
