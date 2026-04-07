#!/usr/bin/env bash
set -euo pipefail

# Handle shutdown gracefully
cleanup() {
    echo "Shutting down NFS server..."
    exportfs -ua 2>/dev/null || true
    kill 0 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "=== NFS Server: Initializing ==="

# Create export directories
mkdir -p /nfs/shared /nfs/data /nfs/backup

# Set permissions
chmod 755 /nfs/shared /nfs/data /nfs/backup

# Create sample files so students can verify mounts immediately
echo "Shared configuration file - created by NFS server" > /nfs/shared/welcome.txt
echo "Application data directory - created by NFS server" > /nfs/data/app-data.txt
echo "Backup directory (read-only) - created by NFS server" > /nfs/backup/backup-info.txt

# Start rpcbind (required for NFS)
echo "Starting rpcbind..."
rpcbind

# Export the configured directories
echo "Exporting NFS shares..."
exportfs -ra

# Start the NFS server in the foreground
echo "Starting NFS server..."
echo "Exported directories:"
exportfs -v

# Start NFS daemon and mountd in background, then wait for signals
rpc.nfsd 8
rpc.mountd
echo "NFS server is running."

# Wait for shutdown signal (trap handles SIGTERM/SIGINT)
while true; do
    sleep 1 &
    wait $! || break
done
