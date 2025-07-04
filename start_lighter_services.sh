#!/bin/bash
# Start Lighter CPTY and Orderbook Streamer services in tmux

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}Error: tmux is not installed. Please install it first.${NC}"
    echo "Run: sudo yum install -y tmux"
    exit 1
fi

# Session name
SESSION_NAME="lighter-services"

# Check if session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}Session '$SESSION_NAME' already exists.${NC}"
    echo "To attach: tmux attach -t $SESSION_NAME"
    echo "To kill existing session: tmux kill-session -t $SESSION_NAME"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    VENV_ACTIVATE="source venv/bin/activate"
elif [ -f "lighter_env/bin/activate" ]; then
    VENV_ACTIVATE="source lighter_env/bin/activate"
else
    echo -e "${RED}Error: No virtual environment found!${NC}"
    echo "Please create one with: python3.12 -m venv venv"
    exit 1
fi

echo -e "${GREEN}Starting Lighter services in tmux session: $SESSION_NAME${NC}"

# Create new tmux session with CPTY service
tmux new-session -d -s $SESSION_NAME -n "cpty" \
    "cd $SCRIPT_DIR && $VENV_ACTIVATE && python -m LighterCpty.lighter_cpty_async; bash"

# Create window for orderbook streamer (optimized version)
tmux new-window -t $SESSION_NAME:1 -n "orderbook" \
    "cd $SCRIPT_DIR && $VENV_ACTIVATE && python run_orderbook_streamer_optimized.py; bash"

# Create window for monitoring
tmux new-window -t $SESSION_NAME:2 -n "monitor" \
    "cd $SCRIPT_DIR && $VENV_ACTIVATE && bash"

# Split monitor window for Redis monitoring
tmux split-window -t $SESSION_NAME:2 -h \
    "cd $SCRIPT_DIR && watch -n 2 'redis6-cli -n 2 get \"l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto\" | jq -r \".bids[0:3][], .asks[0:3][]\" | head -6'; bash"

# Create window for logs
tmux new-window -t $SESSION_NAME:3 -n "logs" \
    "cd $SCRIPT_DIR && tail -f orderbook_streamer.log; bash"

echo -e "${GREEN}✓ Started CPTY service in window 0 (cpty)${NC}"
echo -e "${GREEN}✓ Started Orderbook streamer in window 1 (orderbook)${NC}"
echo -e "${GREEN}✓ Created monitor window 2 (monitor)${NC}"
echo -e "${GREEN}✓ Created logs window 3 (logs)${NC}"
echo ""
echo -e "${YELLOW}Useful tmux commands:${NC}"
echo "  Attach to session:  tmux attach -t $SESSION_NAME"
echo "  List windows:       Ctrl+b w"
echo "  Switch windows:     Ctrl+b [0-3]"
echo "  Detach:            Ctrl+b d"
echo "  Kill session:      tmux kill-session -t $SESSION_NAME"
echo ""
echo -e "${GREEN}Attaching to session...${NC}"

# Attach to the session
tmux attach -t $SESSION_NAME