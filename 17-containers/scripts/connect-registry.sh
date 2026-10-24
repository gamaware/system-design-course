#!/usr/bin/env bash
# Lets the nodes of the lab17 kind cluster pull images from the lab17-registry container (Task 4).
#
# Inside a node, "localhost" is the node container itself, not your machine. This script tells containerd
# on every node that "localhost:5001" means the registry container, and puts the registry on the "kind"
# Docker network so that the nodes can reach it by name. Based on the kind local registry guide:
# https://kind.sigs.k8s.io/docs/user/local-registry/
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths; the paths below belong to the nodes.
export MSYS_NO_PATHCONV=1

CLUSTER="lab17"
REGISTRY="lab17-registry"
REGISTRY_PORT="5001"

if [ "$(docker inspect -f '{{.State.Running}}' "$REGISTRY" 2>/dev/null || true)" != "true" ]; then
    echo "ERROR: the $REGISTRY container is not running. Start it as shown in Task 3." >&2
    exit 1
fi

nodes=()
while IFS= read -r node; do
    nodes+=("$node")
done < <(kind get nodes --name "$CLUSTER")
if [ "${#nodes[@]}" -eq 0 ]; then
    echo "ERROR: kind cluster '$CLUSTER' not found. Create it as shown in Task 4." >&2
    exit 1
fi

registry_dir="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"
for node in "${nodes[@]}"; do
    docker exec "$node" mkdir -p "$registry_dir"
    printf '[host."http://%s:5000"]\n' "$REGISTRY" | docker exec -i "$node" cp /dev/stdin "$registry_dir/hosts.toml"
    echo "  $node: localhost:${REGISTRY_PORT} -> http://${REGISTRY}:5000"
done

if [ "$(docker inspect -f '{{json .NetworkSettings.Networks.kind}}' "$REGISTRY")" = "null" ]; then
    docker network connect kind "$REGISTRY"
fi
echo "  $REGISTRY joined the 'kind' Docker network"

# Advertise the registry to tools that look for it (KEP-1755).
kubectl --context "kind-${CLUSTER}" apply -f - <<YAML
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
YAML
