#!/bin/bash
cd "$(dirname "$0")"
echo "========================================="
echo "   MyTracker - Daily Goal Tracker"
echo "========================================="
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")

echo "Starting MyTracker..."
echo ""
echo "  Mac:   http://localhost:8080"
echo "  Phone: http://${LOCAL_IP}:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""
python3 app.py
