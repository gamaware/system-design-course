#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

echo "Building and starting lab environment..."
docker compose up -d --build

echo "Waiting for containers to initialize..."
sleep 3

echo "Configuring lab scenario (introducing network issues)..."
docker exec devapp01 ip link set eth0 down
docker exec devapp01 ip route del default 2>/dev/null || true

echo ""
echo "Lab environment ready!"
echo ""
echo "Connect to Bob's laptop:"
echo "  docker exec -it bob-laptop bash"
echo ""
echo "When finished, run ./cleanup.sh to tear down the environment."
