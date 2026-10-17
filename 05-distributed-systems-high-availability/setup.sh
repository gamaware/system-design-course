#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 05: Key Characteristics of Distributed Systems ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not available."
    echo "Docker Compose is included with Docker Desktop."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is not installed."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Start infrastructure
echo "Starting three nodes, Toxiproxy, HAProxy, and the client container..."
docker compose up -d --remove-orphans

echo ""
echo "Waiting for services to be healthy..."
i=0
while [ "$i" -lt 60 ]; do
    i=$((i + 1))
    ready=0
    for port in 18001 18002 18003; do
        if curl -sf "http://localhost:$port/health/ready" > /dev/null 2>&1; then
            ready=$((ready + 1))
        fi
    done

    toxi_ok=false
    if curl -sf http://localhost:8474/version > /dev/null 2>&1; then
        toxi_ok=true
    fi

    haproxy_ok=false
    up=$(curl -sf "http://localhost:18090/stats;csv" 2>/dev/null \
        | cut -d, -f1,2,18 | grep -c "^be_checks,node[123],UP$" || true)
    if [ "$up" -eq 3 ]; then
        haproxy_ok=true
    fi

    if [ "$ready" -eq 3 ] && [ "$toxi_ok" = true ] && [ "$haproxy_ok" = true ]; then
        echo "  Nodes:     ready (node1, node2, node3)"
        echo "  Toxiproxy: ready (9 proxies)"
        echo "  HAProxy:   ready (health checks passing)"
        break
    fi

    if [ "$i" -eq 60 ]; then
        echo "ERROR: Services did not become healthy within 60 seconds."
        echo "Run 'docker compose ps' and 'docker compose logs' to check for errors."
        exit 1
    fi

    sleep 1
done

# Seed one key so every task starts from the same data
echo ""
echo "Seeding key 'greeting'..."
curl -sf -X PUT --data "hello" http://localhost:18001/kv/greeting > /dev/null
sleep 2
for port in 18001 18002 18003; do
    echo "  $(curl -sf "http://localhost:$port/kv/greeting")"
done

echo ""
echo "=== Environment ready ==="
echo ""
echo "Load balancer (HAProxy):"
echo "  With health checks:    http://localhost:18080/kv/greeting"
echo "  Without health checks: http://localhost:18081/kv/greeting"
echo "  Stats page:            http://localhost:18090/stats"
echo ""
echo "Nodes (direct): http://localhost:18001  http://localhost:18002  http://localhost:18003"
echo "Toxiproxy API:  http://localhost:8474/proxies"
echo ""
echo "Measurement scripts (run inside the client container):"
echo "  docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting"
echo "  docker exec lab05-client python /scripts/failover.py --node node2"
echo ""
echo "Follow the instructions in LAB.md for the full walkthrough."
