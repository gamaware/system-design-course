#!/bin/bash

echo "========================================="
echo "Testing Least Connections Algorithm"
echo "========================================="
echo ""
echo "Applying Least Connections configuration..."
sudo cp configs/02-leastconn.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Simulating load on Backend 1..."
for i in {1..3}; do
    curl -s http://localhost:8001 > /dev/null &
done

sleep 1
echo "Expected: New requests should avoid Backend 1 (busy)"
echo ""

for i in {1..6}; do
    echo -n "Request $i: "
    curl -s http://localhost:8080 | grep -o "Backend [0-9]"
done

echo ""
echo "Analysis: Backend 1 should receive fewer requests due to existing load."
echo "========================================="
