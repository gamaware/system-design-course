#!/usr/bin/env bash
set -euo pipefail

# Verify backend is reachable and seeded with product data.
# The backend generates 100 products in memory on startup,
# so this script only validates connectivity.

BACKEND_URL="${BACKEND_URL:-http://localhost:5050}"

echo "Verifying backend at $BACKEND_URL..."

for i in 1 50 100; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/products/$i")
    if [ "$response" != "200" ]; then
        echo "ERROR: Backend returned $response for product $i"
        exit 1
    fi
done

echo "Backend is running with product data (100 products available)."
