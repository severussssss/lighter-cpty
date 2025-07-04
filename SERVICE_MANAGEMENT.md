# Lighter Service Management

This guide explains how to manage the Lighter CPTY and Orderbook Streamer services.

## Quick Start

### Start All Services
```bash
./start_lighter_services.sh
```

This will start:
1. **CPTY Service** - The main gRPC server for order management
2. **Orderbook Streamer** - Streams L2 orderbooks to Redis with delta management

### Check Status
```bash
./check_lighter_status.sh
```

Shows:
- Tmux session status
- Running processes with CPU/memory usage
- Redis orderbook data availability
- Sample BTC orderbook data

### Stop All Services
```bash
./stop_lighter_services.sh
```

## Tmux Session Layout

The services run in a tmux session called `lighter-services` with these windows:

- **Window 0 (cpty)**: CPTY gRPC server
- **Window 1 (orderbook)**: Orderbook streamer
- **Window 2 (monitor)**: Split window for monitoring
  - Left: Shell for manual commands
  - Right: Live Redis orderbook monitoring
- **Window 3 (logs)**: Orderbook streamer logs

## Tmux Commands

### Attach to Session
```bash
tmux attach -t lighter-services
```

### Navigate Windows
- `Ctrl+b 0-3`: Switch to window 0-3
- `Ctrl+b w`: List all windows
- `Ctrl+b d`: Detach from session

### Kill Session (emergency)
```bash
tmux kill-session -t lighter-services
```

## Redis Orderbook Access

Orderbooks are stored in Redis database 2 with keys like:
```
l2_book:SYMBOL-USDC LIGHTER Perpetual/USDC Crypto
```

### Get BTC Orderbook
```bash
redis6-cli -n 2 get "l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto" | jq .
```

### List All Orderbook Keys
```bash
redis6-cli -n 2 keys "l2_book:*"
```

### Monitor Live Updates
```bash
watch -n 1 'redis6-cli -n 2 get "l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto" | jq -c "{bid: .bids[0], ask: .asks[0]}"'
```

## Subscribed Markets

The orderbook streamer subscribes to these markets by default:
- BTC (1), ETH (0), SOL (2)
- DOGE (3), 1000PEPE (4), WIF (5)
- XRP (7), LINK (8), AVAX (9)
- BERA (20), FARTCOIN (21), AI16Z (22)
- HYPE (24), BNB (25), UNI (30)
- SUI (16), TRUMP (15)

To modify subscribed markets, edit `run_orderbook_streamer.py`.

## Troubleshooting

### Services Won't Start
1. Check if session already exists: `tmux ls`
2. Kill existing session: `tmux kill-session -t lighter-services`
3. Check virtual environment: `ls venv/` or `ls lighter_env/`

### No Orderbook Data in Redis
1. Check if streamer is running: `./check_lighter_status.sh`
2. Check logs: `tail -f orderbook_streamer.log`
3. Verify Redis connection: `redis6-cli -n 2 ping`

### High CPU Usage
The orderbook streamer processes many messages per second. This is normal for active markets.
To reduce load, subscribe to fewer markets in `run_orderbook_streamer.py`.