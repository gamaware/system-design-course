#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Database Scalability Visualizer ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running."
    exit 1
fi

if ! docker compose version &> /dev/null 2>&1; then
    echo "ERROR: Docker Compose is not available."
    exit 1
fi

echo "Starting MySQL primary, replica, and visualizer..."
docker compose up -d --build

echo ""
echo "Waiting for MySQL to be healthy..."
i=0
while [ "$i" -lt 90 ]; do
    i=$((i + 1))
    if docker exec mysql-primary mysqladmin ping -u root -prootpass 2>/dev/null | grep -q "alive" \
        && docker exec mysql-replica mysqladmin ping -u root -prootpass 2>/dev/null | grep -q "alive"; then
        echo "  MySQL primary: ready"
        echo "  MySQL replica: ready"
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "ERROR: MySQL did not start within 90 seconds."
        exit 1
    fi
    sleep 1
done

# Configure replication
echo ""
echo "Configuring replication..."
docker exec mysql-primary mysql -u root -prootpass \
    -e "CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED BY 'replpass'; GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%'; FLUSH PRIVILEGES;" \
    2>/dev/null

docker exec mysql-replica mysql -u root -prootpass \
    -e "STOP REPLICA; CHANGE REPLICATION SOURCE TO SOURCE_HOST='mysql-primary', SOURCE_USER='repl', SOURCE_PASSWORD='replpass', SOURCE_AUTO_POSITION=1, GET_SOURCE_PUBLIC_KEY=1; START REPLICA;" \
    2>/dev/null

docker exec mysql-replica mysql -u root -prootpass \
    -e "SET GLOBAL read_only = ON; SET GLOBAL super_read_only = ON;" \
    2>/dev/null

echo "  Replication configured."

echo ""
echo "=== Visualizer ready ==="
echo ""
echo "Open http://localhost:8081 in your browser."
echo ""
echo "Three tabs: Replication | Consistency (ACID) | Schema & Indexing"
