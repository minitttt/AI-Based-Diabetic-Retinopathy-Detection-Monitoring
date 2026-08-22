#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  RetinaScan AI — One-click startup script
#  Starts the FastAPI backend and serves the frontend via Python.
# ──────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"
BACKEND="$PROJECT_DIR/deployment/backend"
FRONTEND="$PROJECT_DIR/deployment/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Colors
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    RetinaScan AI  —  Starting up     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"

# Activate virtual env
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    echo -e "${GREEN}✔ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}⚠ No venv found at $VENV — using system Python${NC}"
fi

# Kill any process using our ports
for PORT in $BACKEND_PORT $FRONTEND_PORT; do
    PID=$(lsof -ti tcp:$PORT)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}⚠ Killing process on port $PORT (PID $PID)${NC}"
        kill -9 $PID 2>/dev/null
        sleep 0.5
    fi
done

# ── Start backend ──────────────────────────────────────────────
echo -e "\n${CYAN}→ Starting FastAPI backend on port $BACKEND_PORT ...${NC}"
cd "$BACKEND"
uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!
echo -e "${GREEN}✔ Backend PID: $BACKEND_PID${NC}"

# Wait a moment for the model to load
sleep 2

# ── Start frontend ─────────────────────────────────────────────
echo -e "\n${CYAN}→ Serving frontend on port $FRONTEND_PORT ...${NC}"
cd "$FRONTEND"
python3 -m http.server $FRONTEND_PORT --bind 127.0.0.1 &
FRONTEND_PID=$!
echo -e "${GREEN}✔ Frontend PID: $FRONTEND_PID${NC}"

sleep 1

echo -e "\n${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  RetinaScan AI is running!                       ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  🌐  Frontend → http://localhost:$FRONTEND_PORT            ║${NC}"
echo -e "${GREEN}║  🔧  Backend  → http://localhost:$BACKEND_PORT            ║${NC}"
echo -e "${GREEN}║  📖  API docs → http://localhost:$BACKEND_PORT/docs       ║${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop all services                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"

# Open browser
sleep 1
open "http://localhost:$FRONTEND_PORT" 2>/dev/null || xdg-open "http://localhost:$FRONTEND_PORT" 2>/dev/null

# Wait and cleanup on Ctrl+C
trap "echo -e '\n${RED}Stopping services...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
