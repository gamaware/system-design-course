#!/usr/bin/env bash
set -euo pipefail

# Run this script from the host machine (not inside a container).
# It demonstrates MinIO erasure coding fault tolerance.

echo "============================================="
echo "  MinIO Erasure Coding Demo"
echo "  Simulating Drive Failure and Recovery"
echo "============================================="
echo ""

ENDPOINT="http://localhost:9000"
BUCKET="erasure-test"

# Step 1: Configure AWS CLI for MinIO
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin123
export AWS_DEFAULT_REGION=us-east-1

echo "--- Step 1: Create test bucket and upload data ---"
aws --endpoint-url "$ENDPOINT" s3 mb "s3://$BUCKET" 2>/dev/null || true

# Create a test file with known content
echo "This file tests erasure coding fault tolerance." > /tmp/erasure-test.txt
echo "If you can read this after a drive failure, erasure coding works!" >> /tmp/erasure-test.txt

aws --endpoint-url "$ENDPOINT" s3 cp /tmp/erasure-test.txt "s3://$BUCKET/test-file.txt"
echo "  Uploaded test-file.txt to $BUCKET"
echo ""

# Step 2: Verify the file is readable
echo "--- Step 2: Verify file is readable before failure ---"
aws --endpoint-url "$ENDPOINT" s3 cp "s3://$BUCKET/test-file.txt" /tmp/erasure-verify.txt
echo "  Content:"
cat /tmp/erasure-verify.txt
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
if aws --endpoint-url "$ENDPOINT" s3 cp "s3://$BUCKET/test-file.txt" \
    /tmp/erasure-after-failure.txt 2>/dev/null; then
    echo "  SUCCESS: File is still readable despite drive failure!"
    echo "  Content:"
    cat /tmp/erasure-after-failure.txt
else
    echo "  NOTE: MinIO may need a moment to detect the failure."
    echo "  Retrying in 5 seconds..."
    sleep 5
    aws --endpoint-url "$ENDPOINT" s3 cp "s3://$BUCKET/test-file.txt" \
        /tmp/erasure-after-failure.txt
    echo "  Content after retry:"
    cat /tmp/erasure-after-failure.txt
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
aws --endpoint-url "$ENDPOINT" s3 rm "s3://$BUCKET" --recursive 2>/dev/null || true
aws --endpoint-url "$ENDPOINT" s3 rb "s3://$BUCKET" 2>/dev/null || true
rm -f /tmp/erasure-test.txt /tmp/erasure-verify.txt /tmp/erasure-after-failure.txt
echo "  Test bucket and local files cleaned up."
echo ""
echo "  NOTE: To fully restore drive 3, restart MinIO:"
echo "    docker compose restart minio"
