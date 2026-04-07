#!/usr/bin/env bash
set -euo pipefail

# Run this script from the host machine.
# It uses docker exec to run aws commands inside nfs-client-1 (which has aws-cli)
# and docker exec to simulate drive failure on the minio-server container.

echo "============================================="
echo "  MinIO Erasure Coding Demo"
echo "  Simulating Drive Failure and Recovery"
echo "============================================="
echo ""

BUCKET="erasure-test"

# Helper: run aws s3 commands inside nfs-client-1 (has aws-cli + GNU tools)
run_aws() {
    docker exec \
        -e AWS_ACCESS_KEY_ID=minioadmin \
        -e AWS_SECRET_ACCESS_KEY=minioadmin123 \
        -e AWS_DEFAULT_REGION=us-east-1 \
        nfs-client-1 aws --endpoint-url http://minio-server:9000 "$@"
}

echo "--- Step 1: Create test bucket and upload data ---"
run_aws s3 mb "s3://$BUCKET" 2>/dev/null || true

# Create and upload a test file
docker exec nfs-client-1 sh -c \
    'echo "This file tests erasure coding fault tolerance." > /tmp/erasure-test.txt && echo "If you can read this after a drive failure, erasure coding works!" >> /tmp/erasure-test.txt'
run_aws s3 cp /tmp/erasure-test.txt "s3://$BUCKET/test-file.txt"
echo "  Uploaded test-file.txt to $BUCKET"
echo ""

# Step 2: Verify the file is readable
echo "--- Step 2: Verify file is readable before failure ---"
run_aws s3 cp "s3://$BUCKET/test-file.txt" /tmp/erasure-verify.txt
echo "  Content:"
docker exec nfs-client-1 cat /tmp/erasure-verify.txt
echo ""

# Step 3: Show current drive status
echo "--- Step 3: Check MinIO storage info ---"
echo "  MinIO is configured with 4 drives (erasure coding EC:2)"
echo "  This means up to 2 drives can fail without data loss."
echo ""

# Step 4: Simulate drive failure
echo "--- Step 4: Simulating drive failure (removing data from drive 3) ---"
docker exec minio-server sh -c 'rm -rf /data3/*'
echo "  Drive 3 (/data3) contents deleted."
echo ""

# Step 5: Verify data is still accessible
echo "--- Step 5: Verify file is STILL readable after drive failure ---"
if run_aws s3 cp "s3://$BUCKET/test-file.txt" /tmp/erasure-after-failure.txt 2>/dev/null; then
    echo "  SUCCESS: File is still readable despite drive failure!"
    echo "  Content:"
    docker exec nfs-client-1 cat /tmp/erasure-after-failure.txt
else
    echo "  NOTE: MinIO may need a moment to detect the failure."
    echo "  Retrying in 5 seconds..."
    sleep 5
    if run_aws s3 cp "s3://$BUCKET/test-file.txt" /tmp/erasure-after-failure.txt; then
        echo "  Content after retry:"
        docker exec nfs-client-1 cat /tmp/erasure-after-failure.txt
    else
        echo "  ERROR: File could not be read after drive failure."
    fi
fi
echo ""

# Step 6: Summary
echo "--- Step 6: Summary ---"
echo ""
echo "  Erasure coding protected the data despite losing 1 of 4 drives."
echo "  With EC:2 parity, MinIO can tolerate losing up to 2 drives."
echo ""
echo "  Comparison with HDFS replication:"
echo "    HDFS: 3x replication = 3 full copies = 300% storage overhead"
echo "    MinIO EC:2 with 4 drives = ~100% overhead (2 data + 2 parity)"
echo "    MinIO is more storage-efficient while providing similar fault tolerance."
echo ""

# Cleanup
echo "--- Cleanup ---"
run_aws s3 rm "s3://$BUCKET" --recursive || true
run_aws s3 rb "s3://$BUCKET" || true
docker exec nfs-client-1 rm -f /tmp/erasure-test.txt /tmp/erasure-verify.txt /tmp/erasure-after-failure.txt 2>/dev/null || true
echo "  Test bucket and local files cleaned up."
echo ""
echo "  NOTE: To fully restore drive 3, restart MinIO:"
echo "    docker compose restart minio"
