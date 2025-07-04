#!/bin/bash
# Check status of Lighter services

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SESSION_NAME="lighter-services"

echo -e "${YELLOW}=== Lighter Services Status ===${NC}"
echo ""

# Check tmux session
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${GREEN}✓ Tmux session '$SESSION_NAME' is running${NC}"
    echo ""
    echo "Windows:"
    tmux list-windows -t $SESSION_NAME | sed 's/^/  /'
else
    echo -e "${RED}✗ Tmux session '$SESSION_NAME' is not running${NC}"
fi

echo ""

# Check processes
echo -e "${YELLOW}Running processes:${NC}"

# Check CPTY
if ps aux | grep -q "[p]ython -m LighterCpty.lighter_cpty_async"; then
    echo -e "${GREEN}✓ CPTY service is running${NC}"
    ps aux | grep "[p]ython -m LighterCpty.lighter_cpty_async" | awk '{print "  PID:", $2, "CPU:", $3"%", "MEM:", $4"%"}'
else
    echo -e "${RED}✗ CPTY service is not running${NC}"
fi

# Check Orderbook Streamer
if ps aux | grep -q "[p]ython run_orderbook_streamer.py"; then
    echo -e "${GREEN}✓ Orderbook streamer is running${NC}"
    ps aux | grep "[p]ython run_orderbook_streamer.py" | awk '{print "  PID:", $2, "CPU:", $3"%", "MEM:", $4"%"}'
else
    echo -e "${RED}✗ Orderbook streamer is not running${NC}"
fi

echo ""

# Check Redis
echo -e "${YELLOW}Redis orderbook data:${NC}"

# Count orderbook keys
BOOK_COUNT=$(redis6-cli -n 2 keys "l2_book:*" 2>/dev/null | wc -l)
if [ $BOOK_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Found $BOOK_COUNT orderbook keys in Redis${NC}"
    
    # Show BTC orderbook if exists
    BTC_DATA=$(redis6-cli -n 2 get "l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto" 2>/dev/null)
    if [ ! -z "$BTC_DATA" ]; then
        echo ""
        echo "BTC-USDC Orderbook (top level):"
        echo "$BTC_DATA" | jq -r '
            "  Best Bid: $" + .bids[0][0] + " x " + .bids[0][1],
            "  Best Ask: $" + .asks[0][0] + " x " + .asks[0][1],
            "  Spread: $" + ((.asks[0][0] | tonumber) - (.bids[0][0] | tonumber) | tostring)
        ' 2>/dev/null || echo "  (Unable to parse orderbook data)"
    fi
else
    echo -e "${RED}✗ No orderbook data found in Redis${NC}"
fi

echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  Start services:  ./start_lighter_services.sh"
echo "  Stop services:   ./stop_lighter_services.sh"
echo "  Attach to tmux:  tmux attach -t $SESSION_NAME"