#!/bin/bash

echo "========================================="
echo "Load Testing HAProxy"
echo "========================================="
echo ""
echo "Sending 100 concurrent requests..."
echo ""

start_time=$(date +%s)

for i in {1..100}; do
    curl -s http://localhost:8080 > /dev/null &
    if (( i % 10 == 0 )); then
        echo "Sent $i requests..."
    fi
done

wait

end_time=$(date +%s)
duration=$((end_time - start_time))

echo ""
echo "Load test completed in $duration seconds"
echo ""
echo "View detailed statistics at:"
echo "  http://localhost:8404/stats"
echo ""
echo "Or check from command line:"
echo "  echo 'show stat' | sudo socat stdio /var/run/haproxy.sock"
echo ""
echo "========================================="
