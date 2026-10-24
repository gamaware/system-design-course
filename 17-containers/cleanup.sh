#!/usr/bin/env bash
# Deletes everything Lab 17 created: the kind cluster, the containers, the images built and pulled for
# the lab, and the "kind" Docker network when no other cluster uses it.
#
#   ./cleanup.sh                 remove everything
#   ./cleanup.sh --keep-images   keep the pinned base images, to repeat the lab without downloading them
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

keep_images=false
if [ "${1:-}" = "--keep-images" ]; then
    keep_images=true
fi

# Same list as setup.sh.
IMAGES=(
    "nginx:1.30.6-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951"
    "alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a"
    "golang:1.27.2-trixie@sha256:47667934874913a449b96faa7ef4777fa285d9ec29126ee80ed61c45b7cccf0e"
    "gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99"
    "registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
    "busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e"
    "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
)

echo "=== Lab 17: Cleanup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed, nothing to clean up."
    exit 1
fi

echo "Deleting the kind cluster lab17..."
if command -v kind &> /dev/null; then
    kind delete cluster --name lab17 2>&1 | sed 's/^/  /'
fi
# Without kind, or if the cluster was half created, remove the node containers directly.
docker rm -f -v lab17-control-plane lab17-worker lab17-worker2 &> /dev/null || true

echo "Removing the lab containers..."
docker ps -a --filter name=lab17- --format '{{.Names}}' | while read -r name; do
    docker rm -f -v "$name" > /dev/null
    echo "  $name"
done

echo "Removing the images built in the lab..."
for repo in lab17-web localhost:5001/lab17-web; do
    docker images "$repo" --format '{{.Repository}}:{{.Tag}}' | while read -r image; do
        docker image rm "$image" > /dev/null
        echo "  $image"
    done
done

if [ "$keep_images" = false ]; then
    echo "Removing the pinned base images..."
    for image in "${IMAGES[@]}"; do
        if docker image inspect "$image" &> /dev/null; then
            if docker image rm "$image" > /dev/null 2>&1; then
                echo "  ${image%@*}"
            else
                echo "  ${image%@*}: kept, another container still uses it"
            fi
        fi
    done
fi

# kind creates the "kind" network on the first cluster and never deletes it.
if docker network inspect kind &> /dev/null; then
    if [ "$(docker network inspect kind --format '{{len .Containers}}')" -eq 0 ]; then
        docker network rm kind > /dev/null
        echo "Removed the Docker network kind."
    else
        echo "Kept the Docker network kind: another kind cluster still uses it."
    fi
fi

echo ""
echo "Cleanup complete. The cluster, the containers, the lab images and the kind network are gone."
