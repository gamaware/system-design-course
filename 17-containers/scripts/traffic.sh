#!/usr/bin/env bash
# Sends a steady stream of requests to lab17-web and counts the answers (Tasks 5 to 8).
#
#   scripts/traffic.sh            60 seconds against the Kubernetes Service on 127.0.0.1:30080
#   scripts/traffic.sh 20         20 seconds
#   URL=http://127.0.0.1:8172/ scripts/traffic.sh 5     against the container of Task 2
#
# Every request opens a new connection, so the Service picks a pod for each one. Each second prints one
# line; Ctrl+C stops early. The summary at the end counts errors, versions and the pods that answered.
set -euo pipefail

url="${URL:-http://127.0.0.1:30080/}"
duration="${1:-60}"
interval="${INTERVAL:-0.1}"

log="$(mktemp)"
start=$SECONDS
sent=0
errors=0

summary() {
    echo ""
    echo "=== Summary: $sent requests in $((SECONDS - start)) s, $errors errors ==="
    echo "By version:"
    grep -o 'version=[^ ]*' "$log" | sort | uniq -c | sed 's/^/  /' || echo "  (no answers)"
    echo "By pod:"
    grep -o 'host=[^ ]*' "$log" | sort | uniq -c | sed 's/^/  /' || echo "  (no answers)"
    if grep -q '^ERROR' "$log"; then
        echo "Errors:"
        grep '^ERROR' "$log" | sort | uniq -c | sed 's/^/  /'
    fi
    rm -f "$log"
}
trap summary EXIT
trap 'exit 130' INT

echo "Sending requests to $url for $duration s (one every $interval s)..."
last=$SECONDS
while [ $((SECONDS - start)) -lt "$duration" ]; do
    sent=$((sent + 1))
    if answer="$(curl -s --max-time 1 -w ' code=%{http_code}' "$url")"; then
        rc=0
    else
        rc=$?
    fi
    answer="${answer//$'\n'/}"
    if [ "$rc" -eq 0 ] && [[ "$answer" == *"code=200" ]]; then
        echo "$answer" >> "$log"
    else
        errors=$((errors + 1))
        case "$rc" in
            0) reason="HTTP ${answer##*code=}" ;;
            7) reason="connection refused" ;;
            28) reason="timeout (no answer within 1 s)" ;;
            52) reason="connection closed without an answer" ;;
            56) reason="connection reset" ;;
            *) reason="curl exit code $rc" ;;
        esac
        echo "ERROR $reason" >> "$log"
    fi
    if [ "$SECONDS" -ne "$last" ]; then
        last=$SECONDS
        latest="$(tail -1 "$log")"
        if [[ "$latest" != ERROR* ]]; then
            latest="$(echo "$latest" | cut -d' ' -f1-2)"
        fi
        printf '  t=%3ss  sent=%-5s errors=%-4s last: %s\n' "$((SECONDS - start))" "$sent" "$errors" "$latest"
    fi
    sleep "$interval"
done
