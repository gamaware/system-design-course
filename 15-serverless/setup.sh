#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 15: Serverless (AWS Lambda on Docker) ==="
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
    echo "ERROR: curl is not installed. The lab uses it to call the gateway."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Build and start everything. Each function is its own image, built from its own directory.
# --wait returns when every container with a healthcheck reports healthy (the functions and the gateway).
echo "Building the function images and the gateway, then starting DynamoDB Local, three functions and the gateway..."
docker compose up -d --build --wait

echo ""
echo "Waiting for the gateway to be healthy..."
i=0
while [ "$i" -lt 60 ]; do
    i=$((i + 1))
    if curl -sf --max-time 5 http://localhost:8080/health > /dev/null 2>&1; then
        echo "  Gateway: ready (http://localhost:8080)"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: the gateway did not become healthy within 120 seconds."
        echo "Run 'docker compose logs gateway' to check for errors."
        exit 1
    fi
    sleep 2
done

echo ""
echo "Creating the DynamoDB table..."
docker exec lab15-gateway python table.py create

echo ""
echo "Containers:"
docker compose ps --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}'

echo ""
echo "=== Environment ready ==="
echo ""
echo "Invoke a function through the Lambda invoke API of the gateway:"
echo "  curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{\"echo\": true}'"
echo ""
echo "Call the REST API:"
echo "  curl -s -X POST http://localhost:8080/orders -d '{\"item\": \"book\", \"amount\": 12.5}'"
echo ""
echo "Follow the function logs:"
echo "  docker compose logs -f fn-orders fn-processor fn-work"
echo ""
echo "Follow the instructions in LAB.md for the full walkthrough."
