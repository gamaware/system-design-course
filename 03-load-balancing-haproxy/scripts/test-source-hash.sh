#!/bin/bash

echo "========================================="
echo "Testing Source IP Hash Algorithm"
echo "========================================="
echo ""
echo "Applying Source IP Hash configuration..."
sudo cp configs/05-source-hash.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 1

echo "Test 1: Same IP should always go to same backend"
echo ""
first_backend=""
for i in {1..10}; do
    result=$(curl -s http://localhost:8080 | grep -o "Backend [0-9]")
    echo "Request $i: $result"
    if [ "$first_backend" = "" ]; then
        first_backend="$result"
    fi
done

echo ""
echo "Test 2: Different source IPs are hashed independently"
echo ""

for ip in "127.0.0.2" "127.0.0.3" "127.0.0.4"; do
    echo "Source IP $ip:"
    for i in {1..3}; do
        curl -s --interface "$ip" http://127.0.0.1:8080 | grep -o "Backend [0-9]"
    done
    echo "---"
done

echo ""
echo "Analysis: Same source IP should consistently map to the same backend."
echo "========================================="
