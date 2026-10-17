#!/usr/bin/env bash
# Fire a burst of requests at the orders API and tally the status codes.
# Usage: ./scripts/burst.sh [api-key] [requests]
#   ./scripts/burst.sh team-alpha 12
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"
API_KEY="${1:-team-alpha}"
REQUESTS="${2:-12}"
URL="https://localhost:8443/orders/"

if ! command -v curl &> /dev/null; then
    echo "ERROR: 'curl' is not installed."
    exit 1
fi

codes=()
for ((n = 1; n <= REQUESTS; n++)); do
    codes+=("$(curl -s -o /dev/null -w '%{http_code}' --cacert "$LAB_DIR/certs/proxy.crt" \
        -H "X-API-Key: $API_KEY" "$URL")")
done

echo "Key: $API_KEY   Requests: $REQUESTS"
echo "Sequence: ${codes[*]}"
printf '%s\n' "${codes[@]}" | sort | uniq -c | awk '{printf "  HTTP %s: %s\n", $2, $1}'
