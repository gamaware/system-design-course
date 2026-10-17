#!/usr/bin/env bash
# Cut or heal the network links between one node and the rest of the cluster.
#
#   bash scripts/partition.sh isolate node1   # node1 can no longer talk to node2 or node3
#   bash scripts/partition.sh heal            # remove every partition
#   bash scripts/partition.sh status          # show which replication links are cut
#
# Each replication link is a Toxiproxy proxy named repl-<from>-<to>. A partition adds a "timeout"
# toxic with timeout=0 to the upstream direction: requests are accepted but never delivered, which
# is how a real partition looks to the sender (silence, not an error).
set -euo pipefail

# MSYS_NO_PATHCONV=1 stops Git Bash on Windows from turning /toxiproxy-cli into a Windows path.
# It is ignored on macOS and Linux.
toxi() {
    MSYS_NO_PATHCONV=1 docker exec lab05-toxiproxy /toxiproxy-cli "$@"
}
LINKS=(repl-1-2 repl-1-3 repl-2-1 repl-2-3 repl-3-1 repl-3-2)

usage() {
    echo "Usage: $0 isolate <node1|node2|node3> | heal | status" >&2
    exit 1
}

# Capture the output first: a failed inspect (Toxiproxy stopped) must stop the script instead of
# looking like an open link, and grep -q must not close the pipe while docker exec is still writing.
link_cut() {
    local out
    out="$(toxi inspect "$1")" || {
        echo "error: cannot inspect $1 (is lab05-toxiproxy running?)" >&2
        exit 1
    }
    grep -q "partition" <<< "$out"
}

case "${1:-}" in
    isolate)
        node="${2:-}"
        [[ "$node" =~ ^node[123]$ ]] || usage
        n="${node#node}"
        for link in "${LINKS[@]}"; do
            # repl-1-2 touches node1 and node2: cut it when either end is the isolated node
            from="${link:5:1}"
            to="${link:7:1}"
            if [ "$from" = "$n" ] || [ "$to" = "$n" ]; then
                if link_cut "$link"; then
                    echo "  $link already cut"
                else
                    echo "  + toxiproxy-cli toxic add -t timeout -a timeout=0 -u -n partition $link"
                    toxi toxic add -t timeout -a timeout=0 -u -n partition "$link" > /dev/null
                fi
            fi
        done
        echo "Partition active: $node is isolated from the other nodes."
        ;;
    heal)
        for link in "${LINKS[@]}"; do
            if link_cut "$link"; then
                echo "  - toxiproxy-cli toxic remove -n partition $link"
                toxi toxic remove -n partition "$link" > /dev/null
            fi
        done
        echo "Partition healed: every replication link is open."
        ;;
    status)
        for link in "${LINKS[@]}"; do
            if link_cut "$link"; then
                echo "  $link  CUT"
            else
                echo "  $link  open"
            fi
        done
        ;;
    *)
        usage
        ;;
esac
