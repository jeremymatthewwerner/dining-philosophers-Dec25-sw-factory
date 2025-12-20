#!/bin/bash
# Development script to run both backend and frontend

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Dining Philosophers Development Environment${NC}"
echo ""

# Check if we're in the project root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend on http://localhost:8000${NC}"
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend on http://localhost:3000${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Dining Philosophers is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Backend:  ${YELLOW}http://localhost:8000${NC}"
echo -e "Frontend: ${YELLOW}http://localhost:3000${NC}"
echo -e "API Docs: ${YELLOW}http://localhost:8000/docs${NC}"
echo ""
echo -e "Press ${RED}Ctrl+C${NC} to stop all services"
echo ""

# Wait for both processes
wait
