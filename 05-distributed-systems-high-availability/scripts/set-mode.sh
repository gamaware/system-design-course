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

# Try every node even if one fails, so a single restarting node is reported instead of silently
# leaving the cluster in mixed modes.
failed=0
for port in 18001 18002 18003; do
    if ! curl -sSf -X POST --data "$mode" "http://localhost:$port/admin/mode"; then
        echo "error: could not set mode $mode on port $port; wait for the node and run this again" >&2
        failed=1
    fi
done
exit "$failed"
