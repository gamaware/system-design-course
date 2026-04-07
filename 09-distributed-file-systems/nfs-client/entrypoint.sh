#!/usr/bin/env bash
set -euo pipefail

NFS_SERVER="${NFS_SERVER:-nfs-server}"

echo "=== NFS Client: Mounting exports from $NFS_SERVER ==="

# Wait for NFS server to be reachable
i=0
while [ "$i" -lt 30 ]; do
    i=$((i + 1))
    if showmount -e "$NFS_SERVER" > /dev/null 2>&1; then
        echo "NFS server is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: NFS server not reachable after 30 seconds."
        exit 1
    fi
    echo "Waiting for NFS server... ($i/30)"
    sleep 1
done

# Start rpcbind and rpc.statd for NFS file locking support (flock)
rpcbind 2>/dev/null || true
rpc.statd 2>/dev/null || true

# Mount NFS exports (vers=3 for Docker compatibility, locking enabled)
echo "Mounting /nfs/shared -> /mnt/shared"
mount -t nfs -o vers=3 "$NFS_SERVER":/nfs/shared /mnt/shared

echo "Mounting /nfs/data -> /mnt/data"
mount -t nfs -o vers=3 "$NFS_SERVER":/nfs/data /mnt/data

echo "Mounting /nfs/backup -> /mnt/backup"
mount -t nfs -o vers=3 "$NFS_SERVER":/nfs/backup /mnt/backup

echo "=== NFS mounts ready ==="
df -h | grep nfs
echo ""

# Run the provided command (default: sleep infinity)
exec "$@"
