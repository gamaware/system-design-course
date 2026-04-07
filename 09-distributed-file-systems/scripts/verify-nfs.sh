#!/usr/bin/env bash
set -euo pipefail

echo "--- Verifying NFS mounts ---"

# Check client-1 has all 3 mounts
client1_mounts=$(docker exec nfs-client-1 df -h)
if echo "$client1_mounts" | grep -q "/mnt/shared" \
    && echo "$client1_mounts" | grep -q "/mnt/data" \
    && echo "$client1_mounts" | grep -q "/mnt/backup"; then
    echo "  Client-1: all 3 NFS mounts OK"
else
    echo "  Client-1: ERROR - one or more NFS mounts missing"
    echo "$client1_mounts"
    exit 1
fi

# Check client-2 has all 3 mounts
client2_mounts=$(docker exec nfs-client-2 df -h)
if echo "$client2_mounts" | grep -q "/mnt/shared" \
    && echo "$client2_mounts" | grep -q "/mnt/data" \
    && echo "$client2_mounts" | grep -q "/mnt/backup"; then
    echo "  Client-2: all 3 NFS mounts OK"
else
    echo "  Client-2: ERROR - one or more NFS mounts missing"
    echo "$client2_mounts"
    exit 1
fi

# Cross-client write/read test
docker exec nfs-client-1 sh -c \
    'echo "cross-client-test" > /mnt/shared/verify-test.txt'

result=$(docker exec nfs-client-2 cat /mnt/shared/verify-test.txt)
if [ "$result" = "cross-client-test" ]; then
    echo "  Cross-client: write on client-1, read on client-2 OK"
else
    echo "  Cross-client: ERROR - file not visible across clients"
    exit 1
fi

# Clean up test file
docker exec nfs-client-1 rm -f /mnt/shared/verify-test.txt

echo "--- NFS verification passed ---"
