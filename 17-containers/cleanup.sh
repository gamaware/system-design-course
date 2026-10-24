#!/usr/bin/env bash
# Deletes everything Lab 17 created: the kind cluster, the lab17-* containers, the images built in the
# lab, and the "kind" Docker network when no other cluster uses it. The pinned base images stay in the
# local cache, as in the other labs, unless you ask for them to go.
#
#   ./cleanup.sh                   remove what the lab created, keep the pinned base images
#   ./cleanup.sh --remove-images   also remove the pinned base images
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

remove_images=false
case "${1:-}" in
    "") ;;
    --remove-images) remove_images=true ;;
    *)
        echo "Usage: ./cleanup.sh [--remove-images]" >&2
        exit 2
        ;;
esac

# Same list as setup.sh.
IMAGES=(
    "nginx:1.30.6-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951"
    "alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a"
    "golang:1.27.2-trixie@sha256:47667934874913a449b96faa7ef4777fa285d9ec29126ee80ed61c45b7cccf0e"
    "gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99"
    "registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
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

echo "Removing the lab containers..."
# Without kind, or after a half-created cluster, the node containers are removed here too.
docker ps -a --filter 'name=^lab17-' --format '{{.Names}}' | while read -r name; do
    if docker rm -f -v "$name" > /dev/null; then
        echo "  $name"
    fi
done

echo "Removing the images built in the lab..."
for repo in lab17-web localhost:5001/lab17-web; do
    docker images "$repo" --format '{{.Repository}}:{{.Tag}}' | while read -r image; do
        if docker image rm "$image" > /dev/null; then
            echo "  $image"
        fi
    done
done

kept=0
if [ "$remove_images" = true ]; then
    echo "Removing the pinned base images..."
    for image in "${IMAGES[@]}"; do
        if docker image inspect "$image" &> /dev/null; then
            # Docker refuses when a container still uses the image; show its reason and keep going.
            if docker image rm "$image" > /dev/null; then
                echo "  ${image%@*}"
            else
                echo "  ${image%@*}: kept"
                kept=$((kept + 1))
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
echo "Checking that nothing is left..."
leftovers=""
if command -v kind &> /dev/null && kind get clusters 2> /dev/null | grep -qx lab17; then
    leftovers="${leftovers}  kind cluster lab17"$'\n'
fi
while read -r name; do
    if [ "$name" != "" ]; then
        leftovers="${leftovers}  container $name"$'\n'
    fi
done < <(docker ps -a --filter 'name=^lab17-' --format '{{.Names}}')
while read -r image; do
    if [ "$image" != "" ]; then
        leftovers="${leftovers}  image $image"$'\n'
    fi
done < <(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^(localhost:5001/)?lab17-web:' || true)

if [ "$leftovers" != "" ]; then
    echo "ERROR: these lab resources are still there:"
    printf '%s' "$leftovers"
    echo "Remove them by hand (docker rm -f, docker image rm, kind delete cluster --name lab17)."
    exit 1
fi
echo "  nothing left"

if command -v kubectl &> /dev/null && ! kubectl config current-context &> /dev/null; then
    echo ""
    echo "kubectl has no current context now that kind-lab17 is gone. To return to another cluster:"
    echo "  kubectl config get-contexts"
    echo "  kubectl config use-context <name>"
fi

echo ""
if [ "$remove_images" = true ]; then
    if [ "$kept" -gt 0 ]; then
        echo "Cleanup complete. $kept pinned image(s) kept because other containers use them."
    else
        echo "Cleanup complete. The cluster, the containers, all the lab images and the kind network are gone."
    fi
else
    echo "Cleanup complete. The cluster, the containers, the lab images and the kind network are gone."
    echo "The pinned images stay in the local cache; remove them with './cleanup.sh --remove-images' if needed."
fi
