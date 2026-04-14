#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 10A: MySQL Replication, ACID, and Indexing ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

if ! docker compose version &> /dev/null 2>&1; then
    echo "ERROR: Docker Compose is not available."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Start MySQL primary and replica
echo "Starting MySQL primary and replica..."
docker compose up -d --build

echo ""
echo "Waiting for MySQL primary to be healthy..."
i=0
while [ "$i" -lt 90 ]; do
    i=$((i + 1))
    if docker exec mysql-primary mysqladmin ping -u root -prootpass 2>/dev/null | grep -q "alive"; then
        echo "  MySQL primary: ready"
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "ERROR: MySQL primary did not start within 90 seconds."
        docker compose logs mysql-primary
        exit 1
    fi
    sleep 1
done

echo "Waiting for MySQL replica to be healthy..."
i=0
while [ "$i" -lt 90 ]; do
    i=$((i + 1))
    if docker exec mysql-replica mysqladmin ping -u root -prootpass 2>/dev/null | grep -q "alive"; then
        echo "  MySQL replica: ready"
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "ERROR: MySQL replica did not start within 90 seconds."
        docker compose logs mysql-replica
        exit 1
    fi
    sleep 1
done

# Configure replication
echo ""
echo "Configuring GTID-based replication..."

# Create replication user on primary
docker exec mysql-primary mysql -u root -prootpass \
    -e "CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED BY 'replpass'; GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%'; FLUSH PRIVILEGES;" \
    2>/dev/null

# Point replica to primary
docker exec mysql-replica mysql -u root -prootpass \
    -e "STOP REPLICA; CHANGE REPLICATION SOURCE TO SOURCE_HOST='mysql-primary', SOURCE_USER='repl', SOURCE_PASSWORD='replpass', SOURCE_AUTO_POSITION=1, GET_SOURCE_PUBLIC_KEY=1; START REPLICA;" \
    2>/dev/null

# Set replica to read-only after replication is configured
docker exec mysql-replica mysql -u root -prootpass \
    -e "SET GLOBAL read_only = ON; SET GLOBAL super_read_only = ON;" \
    2>/dev/null

# Wait for replication to catch up
echo "  Waiting for replication to initialize..."
i=0
while [ "$i" -lt 30 ]; do
    i=$((i + 1))
    if docker exec mysql-replica mysql -u root -prootpass \
        -e "SHOW REPLICA STATUS\G" 2>/dev/null | grep -q "Replica_IO_Running: Yes"; then
        break
    fi
    sleep 1
done

# Verify replication
replica_status=$(docker exec mysql-replica mysql -u root -prootpass \
    -e "SHOW REPLICA STATUS\G" 2>/dev/null || true)

if echo "$replica_status" | grep -q "Replica_IO_Running: Yes"; then
    echo "  Replication IO thread: running"
else
    echo "  WARNING: Replication IO thread not running yet"
fi

if echo "$replica_status" | grep -q "Replica_SQL_Running: Yes"; then
    echo "  Replication SQL thread: running"
else
    echo "  WARNING: Replication SQL thread not running yet"
fi

echo ""
echo "=== Environment ready ==="
echo ""
echo "Connect to primary:"
echo "  docker exec -it mysql-primary mysql -u root -prootpass university"
echo ""
echo "Connect to replica:"
echo "  docker exec -it mysql-replica mysql -u root -prootpass university"
echo ""
echo "Follow the instructions in LAB-MYSQL.md for the full walkthrough."
