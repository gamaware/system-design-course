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
    if [ -z "$first_backend" ]; then
        first_backend="$result"
    fi
done

echo ""
echo "Test 2: Different IPs should distribute across backends"
echo ""
for ip in "192.168.1.10" "192.168.1.20" "192.168.1.30"; do
    echo "IP $ip:"
    for i in {1..3}; do
        curl -s -H "X-Forwarded-For: $ip" http://localhost:8080 | grep -o "Backend [0-9]"
    done
    echo "---"
done

echo ""
echo "Analysis: Same IP = same backend, different IPs = different backends."
echo "========================================="
