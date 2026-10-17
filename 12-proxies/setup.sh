#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

CERT_DIR="$SCRIPT_DIR/certs"
CONTAINERS=(lab12-users lab12-orders lab12-proxy lab12-forward-proxy lab12-public-site)

echo "=== Lab 12: Proxies (nginx reverse proxy + Squid forward proxy) ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

for tool in docker openssl curl; do
    if ! command -v "$tool" &> /dev/null; then
        echo "ERROR: '$tool' is not installed."
        exit 1
    fi
done

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not available."
    echo "Docker Compose is included with Docker Desktop."
    exit 1
fi

echo "  Docker:         $(docker --version)"
echo "  Docker Compose: $(docker compose version --short)"
echo "  OpenSSL:        $(openssl version)"
echo ""

# Generate self-signed certificates. They live in certs/, which is ignored by git.
# nginx reads its certificates only at startup, so a regenerated certificate needs fresh containers.
CERTS_CHANGED=false
make_cert() {
    local name="$1" common_name="$2" san="$3"
    if [ -f "$CERT_DIR/$name.crt" ] && [ -f "$CERT_DIR/$name.key" ]; then
        if openssl x509 -checkend 0 -noout -in "$CERT_DIR/$name.crt" > /dev/null 2>&1; then
            echo "  $name.crt already exists, reusing it"
            return
        fi
        echo "  $name.crt has expired, generating a new one"
    fi
    # MSYS_NO_PATHCONV=1 stops Git Bash on Windows from turning "/O=..." into a Windows path.
    # With conversion off, the output paths must be relative (the script already runs in its own folder).
    MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -days 30 -sha256 \
        -keyout "certs/$name.key" -out "certs/$name.crt" \
        -subj "/O=Lab 12 Proxies/CN=$common_name" \
        -addext "subjectAltName=$san" > /dev/null 2>&1
    # The certificate is public; the private key is readable only by its owner.
    # The nginx master process reads it as root inside the container.
    chmod 644 "$CERT_DIR/$name.crt"
    chmod 600 "$CERT_DIR/$name.key"
    CERTS_CHANGED=true
    echo "  Created $name.crt (CN=$common_name)"
}

echo "Generating self-signed TLS certificates in certs/..."
mkdir -p "$CERT_DIR"
make_cert proxy localhost "DNS:localhost,DNS:shop.example.test,IP:127.0.0.1"
make_cert public-site news.example.test "DNS:news.example.test"
echo ""

echo "Building the backend image and starting all containers..."
if [ "$CERTS_CHANGED" = true ]; then
    docker compose up -d --build --force-recreate
else
    docker compose up -d --build
fi

echo ""
echo "Waiting for containers to be healthy..."
i=0
while true; do
    i=$((i + 1))
    pending=()
    for name in "${CONTAINERS[@]}"; do
        status=$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
        if [ "$status" != "healthy" ]; then
            pending+=("$name=$status")
        fi
    done

    if [ "${#pending[@]}" -eq 0 ]; then
        echo "  All containers healthy"
        break
    fi

    if [ "$i" -ge 60 ]; then
        echo "ERROR: Containers did not become healthy within 60 seconds: ${pending[*]}"
        echo "Run 'docker compose logs' to check for errors."
        exit 1
    fi
    sleep 1
done

echo ""
echo "Smoke test through the reverse proxy..."
if curl -sf --cacert "$CERT_DIR/proxy.crt" https://localhost:8443/users/ > /dev/null; then
    echo "  https://localhost:8443/users/ -> 200 OK"
else
    echo "ERROR: The reverse proxy did not answer on https://localhost:8443/users/"
    exit 1
fi

echo "Smoke test through the forward proxy..."
if docker exec lab12-workstation curl -sf -x http://forward-proxy:3128 \
    http://news.example.test/ > /dev/null; then
    echo "  workstation -> Squid -> http://news.example.test/ -> 200 OK"
else
    echo "ERROR: The workstation could not reach news.example.test through Squid"
    exit 1
fi

echo ""
echo "=== Environment ready ==="
echo ""
echo "Reverse proxy (nginx):"
echo "  curl --cacert certs/proxy.crt https://localhost:8443/users/"
echo "  curl -i http://localhost:8088/users/        # redirects to HTTPS"
echo ""
echo "Forward proxy (Squid), from the corporate workstation:"
echo "  docker exec -it lab12-workstation bash"
echo "  curl -x http://forward-proxy:3128 http://news.example.test/"
echo ""
echo "Follow the instructions in LAB.md for the full walkthrough."
