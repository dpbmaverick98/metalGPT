#!/bin/bash

echo "🚀 Starting MetalGPT..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r backend/requirements.txt

# Create uploads directory
mkdir -p uploads

# Start backend
echo "🔧 Starting backend server..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Open browser
echo "🌐 Opening browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000
elif command -v open &> /dev/null; then
    open http://localhost:8000
else
    echo "Please open http://localhost:8000 in your browser"
fi

echo ""
echo "✅ MetalGPT is running!"
echo "📁 Backend: http://localhost:8000"
echo "🌐 Frontend: http://localhost:8000 (served by FastAPI)"
echo ""
echo "Press Ctrl+C to stop"

# Wait for interrupt
trap "kill $BACKEND_PID; exit" INT
wait
