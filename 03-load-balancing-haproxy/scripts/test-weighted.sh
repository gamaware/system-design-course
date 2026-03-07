#!/bin/bash

echo "========================================="
echo "Testing Weighted Round Robin Algorithm"
echo "========================================="
echo ""
echo "Applying Weighted configuration..."
sudo cp configs/04-weighted.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Expected distribution:"
echo "  Backend 1: 50% (weight 50)"
echo "  Backend 2: 30% (weight 30)"
echo "  Backend 3: 20% (weight 20)"
echo ""

declare -A counter
for i in {1..20}; do
    result=$(curl -s http://localhost:8080 | grep -o "Backend [0-9]")
    counter[$result]=$((${counter[$result]} + 1))
done

echo "Results:"
for backend in "Backend 1" "Backend 2" "Backend 3"; do
    count=${counter[$backend]:-0}
    percentage=$((count * 100 / 20))
    echo "  $backend: $count/20 requests ($percentage%)"
done

echo ""
echo "Analysis: Distribution should match configured weights."
echo "========================================="
