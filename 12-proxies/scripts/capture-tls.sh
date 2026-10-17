#!/usr/bin/env bash
# Capture one request on both sides of the reverse proxy and look for a marker.
#   Hop 1: client -> proxy on port 8443 (TLS)
#   Hop 2: proxy  -> users-service on port 5000 (plain HTTP)
# The sniffer container shares the proxy's network namespace, so it sees both.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"
MARKER="${1:-confidential-order-4111}"
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT

for tool in docker curl; do
    if ! command -v "$tool" &> /dev/null; then
        echo "ERROR: '$tool' is not installed."
        exit 1
    fi
done

if ! docker inspect -f '{{.State.Running}}' lab12-sniffer 2> /dev/null | grep -q true; then
    echo "ERROR: lab12-sniffer is not running. Run ./setup.sh first."
    exit 1
fi

capture() {
    local filter="$1" file="$2"
    docker exec lab12-sniffer timeout 5 tcpdump -i any -nn -A -s0 "$filter" > "$file" 2> "$file.err" &
}

# timeout stops tcpdump after 5 seconds. tcpdump exits cleanly on that signal, and BusyBox
# timeout passes its 0 through; GNU timeout reports 124. Any other status means the capture failed.
wait_capture() {
    local pid="$1" file="$2" status=0
    wait "$pid" || status=$?
    if [ "$status" -ne 0 ] && [ "$status" -ne 124 ]; then
        echo "ERROR: The capture into $(basename "$file") failed (exit status $status):"
        sed 's/^/  /' "$file.err"
        exit 1
    fi
}

echo "Marker sent in a request header: X-Lab-Marker: $MARKER"
echo ""

capture "tcp port 8443" "$OUT_DIR/client-hop.txt"
pid_client=$!
capture "tcp port 5000" "$OUT_DIR/backend-hop.txt"
pid_backend=$!
sleep 1

curl -s -o /dev/null --cacert "$LAB_DIR/certs/proxy.crt" \
    -H "X-Lab-Marker: $MARKER" https://localhost:8443/users/

wait_capture "$pid_client" "$OUT_DIR/client-hop.txt"
wait_capture "$pid_backend" "$OUT_DIR/backend-hop.txt"

client_hits=$(grep -c "$MARKER" "$OUT_DIR/client-hop.txt" || true)
backend_hits=$(grep -c "$MARKER" "$OUT_DIR/backend-hop.txt" || true)
client_packets=$(grep -cE '^[0-9]{2}:[0-9]{2}:' "$OUT_DIR/client-hop.txt" || true)
backend_packets=$(grep -cE '^[0-9]{2}:[0-9]{2}:' "$OUT_DIR/backend-hop.txt" || true)

printf '%-34s %8s %14s\n' "Hop" "Packets" "Marker found"
printf '%-34s %8s %14s\n' "client -> proxy  (port 8443, TLS)" "$client_packets" "$client_hits"
printf '%-34s %8s %14s\n' "proxy -> service (port 5000, HTTP)" "$backend_packets" "$backend_hits"
echo ""
echo "Plain-text lines on the service hop that carry the marker:"
# HTTP/2 lowercases header names, so match case-insensitively.
grep -iE "x-lab-marker|GET / HTTP" "$OUT_DIR/backend-hop.txt" \
    | sed -E 's/^.*(GET \/ HTTP)/\1/; s/^/  /' || echo "  (none)"
