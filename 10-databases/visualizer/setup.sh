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

# Run SQL as root inside a container. The password goes through MYSQL_PWD so
# the client does not print its command-line password warning, and real
# errors still reach the terminal.
mysql_in() {
    local container="$1" sql="$2"
    docker exec -e MYSQL_PWD=rootpass "$container" mysql -uroot -e "$sql"
}

echo "Starting MySQL primary, replica, and visualizer..."
docker compose up -d --build

echo ""
echo "Waiting for MySQL to be healthy..."
# Ping over TCP (127.0.0.1), not the socket: during the first start the image
# runs a temporary init server with networking off that already answers on the
# socket, and replication would be configured before the primary is reachable.
i=0
while [ "$i" -lt 120 ]; do
    i=$((i + 1))
    if docker exec -e MYSQL_PWD=rootpass mysql-primary mysqladmin ping -h 127.0.0.1 -uroot 2>/dev/null | grep -q "alive" \
        && docker exec -e MYSQL_PWD=rootpass mysql-replica mysqladmin ping -h 127.0.0.1 -uroot 2>/dev/null | grep -q "alive"; then
        echo "  MySQL primary: ready"
        echo "  MySQL replica: ready"
        break
    fi
    if [ "$i" -eq 120 ]; then
        echo "ERROR: MySQL did not start within 120 seconds."
        echo "Check the logs with: docker compose logs mysql-primary mysql-replica"
        exit 1
    fi
    sleep 1
done

# Configure replication
echo ""
echo "Configuring replication..."
mysql_in mysql-primary \
    "CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED BY 'replpass'; GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%'; FLUSH PRIVILEGES;"

# RESET REPLICA ALL discards old relay logs, which a recreated container can no
# longer open (ERROR 1872). GTID auto-positioning resumes from the right place.
mysql_in mysql-replica \
    "STOP REPLICA; RESET REPLICA ALL; CHANGE REPLICATION SOURCE TO SOURCE_HOST='mysql-primary', SOURCE_USER='repl', SOURCE_PASSWORD='replpass', SOURCE_AUTO_POSITION=1, GET_SOURCE_PUBLIC_KEY=1, SOURCE_CONNECT_RETRY=5; START REPLICA;"

# PERSIST keeps the replica read-only after a container or Docker restart.
mysql_in mysql-replica \
    "SET PERSIST read_only = ON; SET PERSIST super_read_only = ON;"

# START REPLICA succeeds even if the replica cannot reach the primary, so wait
# until both replication threads are actually running.
i=0
while [ "$i" -lt 60 ]; do
    i=$((i + 1))
    status=$(mysql_in mysql-replica "SHOW REPLICA STATUS\G")
    if grep -q "Replica_IO_Running: Yes" <<< "$status" \
        && grep -q "Replica_SQL_Running: Yes" <<< "$status"; then
        echo "  Replication configured and running."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: replication did not start within 60 seconds."
        grep -E "Running:|Last_.*Error:" <<< "$status" || true
        echo "Run ./cleanup.sh and then ./setup.sh again."
        exit 1
    fi
    sleep 1
done

echo ""
echo "=== Visualizer ready ==="
echo ""
echo "Open http://localhost:8081 in your browser."
echo ""
echo "Six tabs: Replication | Consistency (ACID) | Schema & Indexing |"
echo "          CAP Theorem | Materialized Views | Vertical Scaling"
