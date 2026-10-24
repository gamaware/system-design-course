#!/usr/bin/env bash
# Checks the tools Lab 17 needs and downloads the pinned images that Docker uses ahead of time, so that
# no task waits on them. It starts nothing: you run every container and create the cluster in LAB.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Versions this lab was tested with.
KIND_TESTED="v0.33.0"
KUBECTL_MINOR_TESTED="37"

# Every image Docker pulls on your machine, pinned by digest. kind/cluster.yaml pins the node image the same way.
IMAGES=(
    "nginx:1.30.6-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951"
    "alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a"
    "golang:1.27.2-trixie@sha256:47667934874913a449b96faa7ef4777fa285d9ec29126ee80ed61c45b7cccf0e"
    "gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99"
    "registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
    "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
)

# Ports published on 127.0.0.1: first container, app container, registry, Kubernetes Service.
PORTS=(8171 8172 5001 30080)

echo "=== Lab 17: Containers (Docker and kind) ==="
echo ""
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

if ! command -v kind &> /dev/null; then
    echo "ERROR: kind is not installed. See the Prerequisites section of LAB.md."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed. See the Prerequisites section of LAB.md."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is not installed. The lab uses it to call the containers."
    exit 1
fi

kind_version="$(kind version | awk '{print $2}')"
kubectl_version="$(kubectl version --client -o yaml | awk '/gitVersion/ {print $2}')"
kubectl_minor="$(echo "$kubectl_version" | cut -d. -f2)"
docker_mem_gib="$(docker info --format '{{.MemTotal}}' | awk '{printf "%.1f", $1 / 1073741824}')"

echo "  Docker:  $(docker --version)"
echo "  Memory:  ${docker_mem_gib} GiB available to Docker"
echo "  kind:    $kind_version"
echo "  kubectl: $kubectl_version"

if [ "$kind_version" != "$KIND_TESTED" ]; then
    echo "  NOTE: this lab was tested with kind $KIND_TESTED. Other versions usually work because"
    echo "        kind/cluster.yaml pins the node image, but your output may differ."
fi
if [ "$kubectl_minor" -lt $((KUBECTL_MINOR_TESTED - 1)) ] || [ "$kubectl_minor" -gt $((KUBECTL_MINOR_TESTED + 1)) ]; then
    echo "  WARNING: kubectl should be within one minor version of the cluster (v1.$KUBECTL_MINOR_TESTED)."
fi
if awk -v m="$docker_mem_gib" 'BEGIN { exit !(m < 4) }'; then
    echo "  WARNING: give Docker at least 4 GiB of memory (Docker Desktop > Settings > Resources)."
fi

echo ""
echo "Checking for leftovers of an earlier run..."
leftovers="$(docker ps -a --filter 'name=^lab17-' --format '{{.Names}}')"
if [ "$leftovers" != "" ]; then
    echo "ERROR: these containers already exist:"
    echo "$leftovers" | sed 's/^/  /'
    echo "Run ./cleanup.sh first, then run ./setup.sh again."
    exit 1
fi
echo "  none"

echo ""
echo "Checking that the lab ports are free..."
busy=0
for port in "${PORTS[@]}"; do
    # curl exit code 7 means "connection refused": nothing listens on the port.
    rc=0
    curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$port/" || rc=$?
    if [ "$rc" -ne 7 ]; then
        echo "  port $port: IN USE"
        busy=1
    else
        echo "  port $port: free"
    fi
done
if [ "$busy" -ne 0 ]; then
    echo "ERROR: stop whatever uses the ports marked IN USE, then run ./setup.sh again."
    exit 1
fi

echo ""
echo "Downloading the pinned images (about 1.5 GB the first time)..."
for image in "${IMAGES[@]}"; do
    echo "  $image"
    docker pull -q "$image" > /dev/null
done

echo ""
echo "=== Environment ready ==="
echo ""
echo "Nothing is running yet. Start with Task 1 in LAB.md:"
echo "  docker run -d --name lab17-first -p 127.0.0.1:8171:80 ..."
echo ""
echo "When you finish, run ./cleanup.sh to delete the cluster, the registry and the images."
