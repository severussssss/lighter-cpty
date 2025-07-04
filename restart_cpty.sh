#!/bin/bash
# Script to restart the Lighter CPTY server with updated code

echo "=== Restarting Lighter CPTY Server ==="

# Kill any process listening on port 50051
echo "Checking for processes on port 50051..."
PIDS=$(lsof -ti:50051)
if [ ! -z "$PIDS" ]; then
    echo "Killing processes on port 50051: $PIDS"
    kill $PIDS 2>/dev/null
    sleep 2
    # Force kill if still running
    lsof -ti:50051 | xargs -r kill -9 2>/dev/null
fi

# Also kill by process name
pkill -f "lighter_cpty_server_async.py" 2>/dev/null

# Kill existing tmux session
tmux kill-session -t lighter-cpty 2>/dev/null || true

# Wait for port to be free
sleep 1

# Start new server
echo "Starting CPTY server with updated code..."
cd /home/ec2-user/lighter-cpty

# Start in tmux for easy monitoring
tmux new-session -d -s lighter-cpty "python lighter_cpty_server_async.py"

# Wait and verify
sleep 2
if lsof -i:50051 >/dev/null 2>&1; then
    echo "✅ CPTY server restarted successfully"
    echo ""
    echo "To view logs:"
    echo "  tmux attach -t lighter-cpty"
    echo ""
    echo "To check status:"
    echo "  lsof -i:50051"
else
    echo "❌ Failed to start CPTY server"
    echo "Check logs: tmux attach -t lighter-cpty"
fi