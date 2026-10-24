#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 15: Cleanup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed, nothing to clean up."
    exit 1
fi

echo "Stopping and removing all lab resources..."
if ! docker compose down -v --rmi local --remove-orphans; then
    echo "WARNING: 'docker compose down' failed; removing the remaining lab resources one by one."
fi

# Remove anything left behind if the compose project was renamed or partially started,
# including every copy of fn-work that Task 7 started with --scale.
docker ps -aq --filter label=com.docker.compose.project=lab15 | while read -r container; do
    docker rm -f "$container" > /dev/null || echo "WARNING: could not remove container $container"
done
if docker network inspect lab15_default &> /dev/null; then
    docker network rm lab15_default > /dev/null || echo "WARNING: could not remove network lab15_default"
fi
for image in lab15-fn-orders:local lab15-fn-processor:local lab15-fn-work:local lab15-gateway:local; do
    if docker image inspect "$image" &> /dev/null; then
        docker image rm "$image" > /dev/null || echo "WARNING: could not remove image $image"
    fi
done

# Verify: report anything that is still there instead of claiming success.
left_containers="$(docker ps -a --filter label=com.docker.compose.project=lab15 --format '{{.Names}}')"
left_networks="$(docker network ls --filter name=lab15_ --format '{{.Name}}')"
left_images="$(docker images --format '{{.Repository}}:{{.Tag}}' 'lab15-*')"
if [ "$left_containers$left_networks$left_images" != "" ]; then
    echo ""
    echo "ERROR: some lab resources are still present:"
    echo "  containers: ${left_containers:-none}"
    echo "  networks:   ${left_networks:-none}"
    echo "  images:     ${left_images:-none}"
    echo "Remove them with 'docker rm -f', 'docker network rm' and 'docker image rm'."
    exit 1
fi

echo ""
echo "Cleanup complete. All containers, the network, and the lab images removed."
