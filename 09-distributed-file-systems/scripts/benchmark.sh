#!/usr/bin/env bash
set -euo pipefail

# Run this script inside nfs-client-1:
#   docker exec -it nfs-client-1 bash /scripts/benchmark.sh

echo "============================================="
echo "  Storage Performance Benchmark"
echo "  NFS vs MinIO (Object Storage)"
echo "============================================="
echo ""

# --- NFS Sequential Write ---
echo "--- NFS: Sequential Write (256 MB, 1 MB blocks) ---"
fio --name=nfs-seq-write \
    --directory=/mnt/data \
    --rw=write \
    --bs=1m \
    --size=256m \
    --numjobs=1 \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --output-format=terse \
    --minimal 2>/dev/null | awk -F';' '{printf "  Write BW: %s KB/s\n", $48}'

# --- NFS Sequential Read ---
echo "--- NFS: Sequential Read ---"
fio --name=nfs-seq-read \
    --directory=/mnt/data \
    --rw=read \
    --bs=1m \
    --size=256m \
    --numjobs=1 \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --output-format=terse \
    --minimal 2>/dev/null | awk -F';' '{printf "  Read BW:  %s KB/s\n", $7}'

# --- NFS Random Read/Write (4K) ---
echo "--- NFS: Random 4K Read/Write (70/30 mix) ---"
fio --name=nfs-rand-rw \
    --directory=/mnt/data \
    --rw=randrw \
    --rwmixread=70 \
    --bs=4k \
    --size=64m \
    --numjobs=4 \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --output-format=terse \
    --minimal 2>/dev/null | awk -F';' '{printf "  Read IOPS:  %s\n  Write IOPS: %s\n", $8, $49}'

# Clean up fio files
rm -f /mnt/data/nfs-seq-write* /mnt/data/nfs-seq-read* /mnt/data/nfs-rand-rw*

echo ""

# --- MinIO: Configure credentials ---
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin123
export AWS_DEFAULT_REGION=us-east-1

# --- MinIO: Timed Upload ---
echo "--- MinIO: Timed Upload (256 MB file) ---"
dd if=/dev/urandom of=/tmp/bench-256m.bin bs=1m count=256 2>/dev/null

aws --endpoint-url http://minio-server:9000 \
    s3 mb s3://benchmark-test 2>/dev/null || true

start_time=$(date +%s%N)
aws --endpoint-url http://minio-server:9000 \
    s3 cp /tmp/bench-256m.bin s3://benchmark-test/bench-256m.bin 2>/dev/null
end_time=$(date +%s%N)
upload_ms=$(( (end_time - start_time) / 1000000 ))
echo "  Upload time: ${upload_ms} ms"

# --- MinIO: Timed Download ---
echo "--- MinIO: Timed Download (256 MB file) ---"
start_time=$(date +%s%N)
aws --endpoint-url http://minio-server:9000 \
    s3 cp s3://benchmark-test/bench-256m.bin /tmp/bench-download.bin 2>/dev/null
end_time=$(date +%s%N)
download_ms=$(( (end_time - start_time) / 1000000 ))
echo "  Download time: ${download_ms} ms"

# Clean up
rm -f /tmp/bench-256m.bin /tmp/bench-download.bin
aws --endpoint-url http://minio-server:9000 \
    s3 rm s3://benchmark-test/bench-256m.bin 2>/dev/null || true
aws --endpoint-url http://minio-server:9000 \
    s3 rb s3://benchmark-test 2>/dev/null || true

echo ""
echo "============================================="
echo "  Benchmark Complete"
echo "============================================="
echo ""
echo "Compare the results above. Key observations:"
echo "  - NFS excels at small random I/O (POSIX semantics)"
echo "  - Object storage excels at large sequential transfers"
echo "  - NFS provides file locking; object storage does not"
echo "  - Object storage scales horizontally; NFS is single-server"
