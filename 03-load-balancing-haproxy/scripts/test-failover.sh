#!/bin/bash

echo "========================================="
echo "Testing Failover and Health Checks"
echo "========================================="
echo ""
echo "Applying Failover configuration..."
sudo cp configs/07-failover.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sleep 2

echo "Phase 1: All servers healthy"
echo ""
for i in {1..6}; do
    echo -n "Request $i: "
    curl -s http://localhost:8080 | grep -o "Backend [0-9]"
done

echo ""
echo "Phase 2: Simulating Backend 1 failure..."
pkill -f "python3 -m http.server 8001"
echo "Waiting for HAProxy to detect failure (6 seconds)..."
sleep 6

echo ""
echo "Traffic after failure:"
for i in {1..6}; do
    echo -n "Request $i: "
    curl -s http://localhost:8080 | grep -o "Backend [0-9]"
done

echo ""
echo "Phase 3: Restoring Backend 1..."
nohup python3 -m http.server 8001 --directory ~/backend1 --bind 0.0.0.0 > ~/backend1.log 2>&1 &
echo "Waiting for recovery (4 seconds)..."
sleep 4

echo ""
echo "Traffic after recovery:"
for i in {1..6}; do
    echo -n "Request $i: "
    curl -s http://localhost:8080 | grep -o "Backend [0-9]"
done

echo ""
echo "Analysis: HAProxy automatically detects failures and recoveries."
echo "Backup servers (4 & 5) only activate when all primary servers fail."
echo "========================================="
