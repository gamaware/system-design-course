#!/usr/bin/env bash
# Switch the replication mode of all three nodes at runtime.
#
#   bash scripts/set-mode.sh cp   # writes need a quorum (2 of 3), minority side refuses requests
#   bash scripts/set-mode.sh ap   # writes are accepted locally and replicated in the background
#
# The mode lives in memory: a node that restarts comes back in its default mode (ap).
set -euo pipefail

mode="${1:-}"
if [ "$mode" != "ap" ] && [ "$mode" != "cp" ]; then
    echo "Usage: $0 ap|cp" >&2
    exit 1
fi

for port in 18001 18002 18003; do
    curl -sf -X POST --data "$mode" "http://localhost:$port/admin/mode"
done
