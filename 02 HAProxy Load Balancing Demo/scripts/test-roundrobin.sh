#!/bin/bash

echo "========================================="
echo "Testing Round Robin Algorithm"
echo "========================================="
echo ""
echo "Applying Round Robin configuration..."
sudo cp configs/01-roundrobin.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Expected: Sequential distribution (1→2→3→1→2→3...)"
echo ""

for i in {1..9}; do
    echo -n "Request $i: "
    curl -s http://localhost:8080 | grep -o "Backend [0-9]"
done

echo ""
echo "Analysis: Requests should be distributed evenly in sequence."
echo "========================================="
