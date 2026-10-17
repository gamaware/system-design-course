#!/usr/bin/env bash
# Request the slow report several times through the proxy and time each call.
# Usage: ./scripts/measure-cache.sh [requests]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"
REQUESTS="${1:-5}"
URL="https://localhost:8443/users/report"
BODY="$(mktemp)"
HEADERS="$(mktemp)"
trap 'rm -f "$BODY" "$HEADERS"' EXIT

if ! command -v curl &> /dev/null; then
    echo "ERROR: 'curl' is not installed."
    exit 1
fi

printf '%-4s %-14s %10s   %s\n' "#" "X-Cache-Status" "time (ms)" "generated_at (by the service)"
for ((i = 1; i <= REQUESTS; i++)); do
    seconds=$(curl -s --cacert "$LAB_DIR/certs/proxy.crt" -D "$HEADERS" -o "$BODY" \
        -w '%{time_total}' "$URL")
    ms=$(awk -v s="$seconds" 'BEGIN { printf "%.1f", s * 1000 }')
    status=$(grep -i '^x-cache-status:' "$HEADERS" | awk '{print $2}' | tr -d '\r')
    generated=$(grep '"generated_at"' "$BODY" | sed -E 's/.*: "([^"]+)".*/\1/')
    printf '%-4s %-14s %10s   %s\n' "$i" "${status:--}" "$ms" "$generated"
done
