#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 14: Distributed Messaging (RabbitMQ) ==="
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
    echo "Docker Compose is included with Docker Desktop."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is not installed. It is used to check the RabbitMQ management API."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Build and start infrastructure
echo "Building the Python image and starting RabbitMQ, worker-1 and the tools container..."
docker compose up -d --build rabbitmq worker-1 tools

echo ""
echo "Waiting for RabbitMQ to be healthy..."
# Lab-only credentials, fixed in docker-compose.yml; a host RABBITMQ_USER/RABBITMQ_PASS must not override them.
BROKER_USER="lab14"
BROKER_PASS="lab14-pass"

i=0
while [ "$i" -lt 60 ]; do
    i=$((i + 1))
    broker_ok=false
    console_ok=false

    if docker exec lab14-rabbitmq rabbitmq-diagnostics -q check_port_connectivity &> /dev/null; then
        broker_ok=true
    fi

    if curl -sf --max-time 5 -u "$BROKER_USER:$BROKER_PASS" http://localhost:15672/api/overview > /dev/null 2>&1; then
        console_ok=true
    fi

    if [ "$broker_ok" = true ] && [ "$console_ok" = true ]; then
        echo "  RabbitMQ AMQP:     ready (localhost:5672)"
        echo "  RabbitMQ console:  ready (http://localhost:15672)"
        break
    fi

    if [ "$i" -eq 60 ]; then
        echo "ERROR: RabbitMQ did not become healthy within 120 seconds."
        echo "Run 'docker compose logs rabbitmq' to check for errors."
        exit 1
    fi

    sleep 2
done

echo ""
echo "Declaring exchanges, queues and bindings..."
docker exec lab14-tools python topology.py

echo ""
echo "Queues:"
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name type durable messages consumers

echo ""
echo "=== Environment ready ==="
echo ""
echo "RabbitMQ management console:"
echo "  http://localhost:15672"
echo "  User: lab14 / Password: lab14-pass"
echo ""
echo "Run the lab scripts inside the tools container, for example:"
echo "  docker exec lab14-tools python producer.py --count 10"
echo ""
echo "Follow the worker logs:"
echo "  docker compose logs -f worker-1"
echo ""
echo "Follow the instructions in LAB.md for the full walkthrough."
