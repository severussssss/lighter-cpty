#!/bin/bash
# Stop Lighter CPTY and Orderbook Streamer services

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SESSION_NAME="lighter-services"

# Check if session exists
if ! tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}Session '$SESSION_NAME' is not running.${NC}"
    exit 0
fi

echo -e "${YELLOW}Stopping Lighter services...${NC}"

# Kill the tmux session
tmux kill-session -t $SESSION_NAME

echo -e "${GREEN}✓ Stopped all Lighter services${NC}"

# Check for any remaining python processes
REMAINING=$(ps aux | grep -E "(lighter_cpty_async|orderbook_streamer)" | grep -v grep | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo -e "${YELLOW}Warning: Found $REMAINING remaining processes${NC}"
    ps aux | grep -E "(lighter_cpty_async|orderbook_streamer)" | grep -v grep
fi