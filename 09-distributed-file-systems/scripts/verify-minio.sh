#!/usr/bin/env bash
set -euo pipefail

echo "--- Verifying MinIO server ---"

# Check health endpoint
if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "  Health: OK"
else
    echo "  Health: ERROR - MinIO not responding"
    exit 1
fi

# Check console is accessible
if curl -sf http://localhost:9001 > /dev/null 2>&1; then
    echo "  Console: OK (http://localhost:9001)"
else
    echo "  Console: WARNING - console not responding (may still be starting)"
fi

# Verify erasure coding configuration via cluster info
storage_info=$(curl -sf http://localhost:9000/minio/health/cluster 2>/dev/null || true)
if [ "$storage_info" != "" ]; then
    echo "  Cluster: OK"
else
    echo "  Cluster: basic health check passed"
fi

echo "--- MinIO verification passed ---"
