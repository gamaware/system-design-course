#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lab 11: Caching Patterns with Redis ==="
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

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo ""

# Build and start infrastructure
echo "Building and starting Redis + backend..."
docker compose up -d --build redis backend

echo ""
echo "Waiting for services to be healthy..."
for i in {1..30}; do
    redis_ok=false
    backend_ok=false

    if docker exec redis-cache redis-cli ping 2>/dev/null | grep -q PONG; then
        redis_ok=true
    fi

    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/health 2>/dev/null | grep -q 200; then
        backend_ok=true
    fi

    if [ "$redis_ok" = true ] && [ "$backend_ok" = true ]; then
        echo "  Redis:   ready"
        echo "  Backend: ready (100 products, 500ms delay per request)"
        break
    fi

    if [ "$i" -eq 30 ]; then
        echo "ERROR: Services did not become healthy within 30 seconds."
        echo "Run 'docker compose logs' to check for errors."
        exit 1
    fi

    sleep 1
done

# Verify data
echo ""
bash "$SCRIPT_DIR/scripts/seed-database.sh"

echo ""
echo "=== Environment ready ==="
echo ""
echo "Choose your language and start the lab:"
echo ""
echo "  C++:    docker compose --profile cpp up --build"
echo "  C#:     docker compose --profile csharp up --build"
echo "  Java:   docker compose --profile java up --build"
echo ""
echo "Redis CLI (for monitoring):"
echo "  docker exec -it redis-cache redis-cli"
echo "  docker exec -it redis-cache redis-cli MONITOR"
echo ""
echo "Follow the instructions in LAB-MACOS.md for the full walkthrough."
