#!/bin/bash

echo "========================================="
echo "Cleaning up HAProxy Demo"
echo "========================================="

# Stop all backend servers
echo "Stopping backend servers..."
pkill -f "python3 -m http.server"
echo "  ✓ Backend servers stopped"

# Stop HAProxy
echo "Stopping HAProxy..."
sudo systemctl stop haproxy
echo "  ✓ HAProxy stopped"

# Clean up backend directories and logs
echo "Removing temporary files..."
rm -rf ~/backend{1..5}
rm -f ~/backend*.log
echo "  ✓ Temporary files removed"

# Restore original HAProxy config if backup exists
if [ -f /etc/haproxy/haproxy.cfg.backup ]; then
    echo "Restoring original HAProxy configuration..."
    sudo cp /etc/haproxy/haproxy.cfg.backup /etc/haproxy/haproxy.cfg
    echo "  ✓ Configuration restored"
fi

echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo "To restart the demo, run: ./setup.sh"
echo ""
