#!/usr/bin/env bash
set -euo pipefail

# This script runs identical S3 operations against MinIO and AWS S3,
# comparing behavior, latency, and API compatibility.
#
# Run inside nfs-client-1 (has aws-cli and GNU coreutils):
#   docker exec -it nfs-client-1 bash /scripts/compare-s3.sh
#
# Or from the host (requires aws-cli installed):
#   bash scripts/compare-s3.sh
#
# Prerequisites:
#   - MinIO running (docker compose up)
#   - AWS credentials in environment variables

echo "============================================="
echo "  MinIO vs AWS S3: Side-by-Side Comparison"
echo "============================================="
echo ""

# Detect whether running inside a container or on the host
if [ -f /.dockerenv ]; then
    MINIO_ENDPOINT="http://minio-server:9000"
else
    MINIO_ENDPOINT="http://localhost:9000"
fi
MINIO_BUCKET="lab09-minio-test-$(date +%s)"

# Wrapper for MinIO calls using its own credentials
minio_aws() {
    AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin123 AWS_SESSION_TOKEN='' \
        aws --endpoint-url "$MINIO_ENDPOINT" "$@"
}

# Initialize timing variables (prevents unbound errors if a step fails)
minio_create=0 s3_create=0
minio_upload=0 s3_upload=0
minio_list=0 s3_list=0
minio_sync=0 s3_sync=0
S3_BUCKET="lab09-s3-test-$(date +%s)"

# Check if AWS credentials are available
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "ERROR: AWS credentials not configured."
    echo ""
    echo "Configure your AWS Academy credentials:"
    echo "  export AWS_ACCESS_KEY_ID=your-key"
    echo "  export AWS_SECRET_ACCESS_KEY=your-secret"
    echo "  export AWS_SESSION_TOKEN=your-token"
    echo "  export AWS_DEFAULT_REGION=us-east-1"
    exit 1
fi

echo "AWS Identity:"
aws sts get-caller-identity --output table
echo ""

# Create test files
echo "Creating test files..."
echo "Test content for S3 comparison" > /tmp/s3-test-file.txt
mkdir -p /tmp/s3-sync-test
i=0
while [ "$i" -lt 5 ]; do
    i=$((i + 1))
    echo "Sync file $i - created at $(date -Iseconds)" > "/tmp/s3-sync-test/file-$i.txt"
done
echo ""

# --- Operation 1: Create Bucket ---
echo "=== Operation 1: Create Bucket ==="
echo ""

echo "  MinIO:"
time_start=$(date +%s%N)
minio_aws s3 mb "s3://$MINIO_BUCKET" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
minio_create=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${minio_create} ms"
echo ""

echo "  AWS S3:"
time_start=$(date +%s%N)
aws s3 mb "s3://$S3_BUCKET" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
s3_create=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${s3_create} ms"
echo ""

# --- Operation 2: Upload File ---
echo "=== Operation 2: Upload File ==="
echo ""

echo "  MinIO:"
time_start=$(date +%s%N)
minio_aws s3 cp /tmp/s3-test-file.txt \
    "s3://$MINIO_BUCKET/test-file.txt" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
minio_upload=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${minio_upload} ms"
echo ""

echo "  AWS S3:"
time_start=$(date +%s%N)
aws s3 cp /tmp/s3-test-file.txt "s3://$S3_BUCKET/test-file.txt" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
s3_upload=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${s3_upload} ms"
echo ""

# --- Operation 3: List Objects ---
echo "=== Operation 3: List Objects ==="
echo ""

echo "  MinIO:"
time_start=$(date +%s%N)
minio_aws s3 ls "s3://$MINIO_BUCKET/" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
minio_list=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${minio_list} ms"
echo ""

echo "  AWS S3:"
time_start=$(date +%s%N)
aws s3 ls "s3://$S3_BUCKET/" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
s3_list=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${s3_list} ms"
echo ""

# --- Operation 4: Sync Directory ---
echo "=== Operation 4: Sync Directory ==="
echo ""

echo "  MinIO:"
time_start=$(date +%s%N)
minio_aws s3 sync /tmp/s3-sync-test/ \
    "s3://$MINIO_BUCKET/synced/" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
minio_sync=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${minio_sync} ms"
echo ""

echo "  AWS S3:"
time_start=$(date +%s%N)
aws s3 sync /tmp/s3-sync-test/ "s3://$S3_BUCKET/synced/" 2>&1 | sed 's/^/    /'
time_end=$(date +%s%N)
s3_sync=$(( (time_end - time_start) / 1000000 ))
echo "    Time: ${s3_sync} ms"
echo ""

# --- Operation 5: Presigned URL ---
echo "=== Operation 5: Generate Presigned URL ==="
echo ""

echo "  MinIO:"
minio_aws s3 presign \
    "s3://$MINIO_BUCKET/test-file.txt" --expires-in 3600 2>&1 | sed 's/^/    /'
echo ""

echo "  AWS S3:"
aws s3 presign "s3://$S3_BUCKET/test-file.txt" --expires-in 3600 2>&1 | sed 's/^/    /'
echo ""

# --- Cleanup ---
echo "=== Cleanup ==="
echo ""

echo "  Cleaning MinIO..."
minio_aws s3 rm "s3://$MINIO_BUCKET" --recursive || true
minio_aws s3 rb "s3://$MINIO_BUCKET" || true
echo "    Done."

echo "  Cleaning AWS S3..."
aws s3 rm "s3://$S3_BUCKET" --recursive || true
aws s3 rb "s3://$S3_BUCKET" || true
echo "    Done."

rm -rf /tmp/s3-test-file.txt /tmp/s3-sync-test

echo ""

# --- Results Summary ---
echo "============================================="
echo "  Latency Comparison (milliseconds)"
echo "============================================="
printf "  %-20s %10s %10s\n" "Operation" "MinIO" "AWS S3"
printf "  %-20s %10s %10s\n" "--------------------" "----------" "----------"
printf "  %-20s %10d %10d\n" "Create Bucket" "$minio_create" "$s3_create"
printf "  %-20s %10d %10d\n" "Upload File" "$minio_upload" "$s3_upload"
printf "  %-20s %10d %10d\n" "List Objects" "$minio_list" "$s3_list"
printf "  %-20s %10d %10d\n" "Sync Directory" "$minio_sync" "$s3_sync"
echo ""
echo "  Key observations:"
echo "  - MinIO (local) should be faster due to network proximity"
echo "  - AWS S3 provides 11 9s durability across multiple AZs"
echo "  - Both use identical API commands (S3-compatible)"
echo "  - MinIO: you manage infrastructure; S3: AWS manages it"
