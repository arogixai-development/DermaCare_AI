#!/bin/bash
# DermaCare AI - Unix/Mac Launcher Script
# ========================================
# This script starts Ollama, Backend, and Frontend servers

echo "========================================"
echo "DermaCare AI - Starting Services"
echo "========================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
echo "Checking dependencies..."
pip install -q -r requirements.txt

# Step 1: Start Ollama (if not running)
echo ""
echo "[1/3] Checking Ollama..."
if ! nc -z localhost 11434 2>/dev/null; then
    echo "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 5
else
    echo "Ollama already running on port 11434"
fi

# Step 2: Start Backend
echo ""
echo "[2/3] Starting Backend (FastAPI on port 8000)..."
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 3

# Step 3: Start Frontend
echo ""
echo "[3/3] Starting Frontend (Static server on port 3000)..."
python -m http.server 3000 > frontend.log 2>&1 &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "DermaCare AI Services Started"
echo "========================================"
echo ""
echo "Backend API:  http://127.0.0.1:8000"
echo "Frontend:     http://localhost:3000"
echo "Health:       http://127.0.0.1:8000/health"
echo ""
echo "Default admin credentials:"
echo "  Username: admin"
echo "  Password: (check terminal output on first run)"
echo ""
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Logs: backend.log, frontend.log"
echo ""
echo "Press Ctrl+C to stop all services."

# Open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
else
    xdg-open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 manually"
fi

# Wait for interrupt
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
