#!/bin/bash

echo "========================================="
echo "Testing URI Hash Algorithm"
echo "========================================="
echo ""
echo "Applying URI Hash configuration..."
sudo cp configs/06-uri-hash.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Expected: Same URI always routes to same backend"
echo ""

uris=("/api" "/static" "/admin" "/api/users" "/static/css" "/admin/config")

for uri in "${uris[@]}"; do
    echo "Testing URI: $uri"
    for i in {1..3}; do
        curl -s "http://localhost:8080$uri" | grep -o "Backend [0-9]" || echo "  (no match)"
    done
    echo "---"
done

echo ""
echo "Analysis: Each URI should consistently route to the same backend."
echo "This is useful for caching and content specialization."
echo "========================================="
