#!/bin/bash

echo "========================================="
echo "Testing Random Algorithm"
echo "========================================="
echo ""
echo "Applying Random configuration..."
sudo cp configs/03-random.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Expected behavior:"
echo "  Requests are distributed randomly across backends."
echo "  No predictable pattern, but roughly even over many requests."
echo ""

declare -A counter
for _ in {1..20}; do
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
echo "Analysis: Distribution should be roughly even but not perfectly predictable."
echo "========================================="
