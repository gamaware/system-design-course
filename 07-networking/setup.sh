#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

echo "Building and starting lab environment..."
docker compose up -d --build

echo "Waiting for containers to initialize..."
sleep 3

# Generate a random lab password and set it on the server container
LAB_PASSWORD="$(openssl rand -base64 12)"
docker exec devapp01 bash -c "echo 'bob:$LAB_PASSWORD' | chpasswd"

# Discover the frontend interface by IP (do not assume eth0)
frontend_if="$(
  docker exec devapp01 ip -o -4 addr show \
    | awk '$4 == "172.16.238.20/24" { print $2; exit }'
)"
if [[ -z "$frontend_if" ]]; then
  echo "ERROR: Could not find the interface with IP 172.16.238.20" >&2
  exit 1
fi

echo "Configuring lab scenario (introducing network issues)..."
docker exec devapp01 ip link set "$frontend_if" down
docker exec devapp01 ip route del default 2>/dev/null || true

echo ""
echo "Lab environment ready!"
echo ""
echo "SSH credentials for devapp01:"
echo "  Username: bob"
echo "  Password: $LAB_PASSWORD"
echo ""
echo "Connect to Bob's laptop:"
echo "  docker exec -it bob-laptop bash"
echo ""
echo "When finished, run ./cleanup.sh to tear down the environment."
