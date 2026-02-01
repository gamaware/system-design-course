#!/bin/bash

echo "========================================="
echo "HAProxy Load Balancing Demo - Setup"
echo "========================================="

# Install HAProxy and Python
echo "Installing HAProxy and Python..."
sudo dnf install haproxy python3 -y

# Create backend directories
echo "Creating backend server directories..."
mkdir -p ~/backend{1..5}

# Create unique content for each backend
echo "Setting up backend content..."
echo "<h1>🟢 Backend 1 - Servidor Principal</h1><p>Capacidad: Alta</p>" > ~/backend1/index.html
echo "<h1>🔵 Backend 2 - Servidor Secundario</h1><p>Capacidad: Media</p>" > ~/backend2/index.html
echo "<h1>🟡 Backend 3 - Servidor Terciario</h1><p>Capacidad: Baja</p>" > ~/backend3/index.html
echo "<h1>🟠 Backend 4 - Servidor de Respaldo</h1><p>Capacidad: Alta</p>" > ~/backend4/index.html
echo "<h1>🔴 Backend 5 - Servidor de Emergencia</h1><p>Capacidad: Muy Baja</p>" > ~/backend5/index.html

# Create content for URI hash testing
echo "Setting up URI-specific content..."
mkdir -p ~/backend{1..3}/{api,static,admin}

for i in {1..3}; do
    echo "{\"service\": \"api\", \"server\": \"backend$i\"}" > ~/backend$i/api/index.html
    echo "<h1>Static Content - Backend $i</h1>" > ~/backend$i/static/index.html
    echo "<h1>Admin Panel - Backend $i</h1>" > ~/backend$i/admin/index.html
done

# Start backend servers
echo "Starting backend servers..."
for port in {8001..8005}; do
    backend_num=$((port - 8000))
    nohup python3 -m http.server $port --directory ~/backend$backend_num --bind 0.0.0.0 > ~/backend$backend_num.log 2>&1 &
    echo "  ✓ Backend $backend_num started on port $port"
done

# Wait for backends to start
sleep 2

# Verify backends are running
echo "Verifying backend servers..."
all_ok=true
for port in {8001..8005}; do
    if curl -s http://localhost:$port > /dev/null; then
        echo "  ✓ Backend on port $port is responding"
    else
        echo "  ✗ Backend on port $port is NOT responding"
        all_ok=false
    fi
done

# Backup original HAProxy config
if [ -f /etc/haproxy/haproxy.cfg ]; then
    echo "Backing up original HAProxy configuration..."
    sudo cp /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.backup
fi

# Install initial configuration (Round Robin)
echo "Installing initial HAProxy configuration..."
sudo cp configs/01-roundrobin.cfg /etc/haproxy/haproxy.cfg

# Validate configuration
echo "Validating HAProxy configuration..."
if sudo haproxy -f /etc/haproxy/haproxy.cfg -c; then
    echo "  ✓ Configuration is valid"
else
    echo "  ✗ Configuration has errors"
    exit 1
fi

# Start HAProxy
echo "Starting HAProxy..."
sudo systemctl restart haproxy
sudo systemctl enable haproxy

# Check HAProxy status
if sudo systemctl is-active --quiet haproxy; then
    echo "  ✓ HAProxy is running"
else
    echo "  ✗ HAProxy failed to start"
    sudo systemctl status haproxy
    exit 1
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "HAProxy is running on port 8080"
echo "Statistics available at: http://localhost:8404/stats"
echo ""
echo "Test the setup:"
echo "  curl http://localhost:8080"
echo ""
echo "Run test scripts:"
echo "  ./scripts/test-roundrobin.sh"
echo "  ./scripts/test-leastconn.sh"
echo "  ./scripts/test-weighted.sh"
echo ""
