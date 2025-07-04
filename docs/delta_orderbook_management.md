# Delta Orderbook Management

## Overview

The LighterCpty now implements proper delta orderbook management to maintain accurate orderbook state from Lighter's WebSocket streams. This is critical because Lighter sends an initial snapshot followed by incremental updates (deltas) rather than full orderbooks with each message.

## Key Components

### 1. OrderBookManager (`LighterCpty/orderbook_manager.py`)

The `OrderBookManager` class handles:
- Maintaining orderbook state using `SortedDict` for efficient sorted bid/ask management
- Applying initial snapshots when subscribing to a market
- Processing delta updates to add, update, or remove price levels
- Writing the current orderbook state to Redis

Key features:
- **Sorted order**: Bids sorted descending (highest first), asks ascending (lowest first)
- **Delta handling**: Size of 0.0000 removes a price level, non-zero updates/adds
- **State tracking**: Tracks initialization state and last update offset

### 2. Market Loader (`LighterCpty/market_loader.py`)

Dynamically loads all market information from Lighter's API:
- Fetches market metadata from `https://mainnet.zklighter.elliot.ai/api/v1/orderBooks`
- Provides correct market ID to symbol mappings (e.g., 0=ETH, 1=BTC, 21=FARTCOIN)
- Caches market info for efficient access
- Falls back to hardcoded mappings if API is unavailable

### 3. Enhanced WebSocket Client

The `LighterWebSocketClient` now supports:
- Toggle between simple Redis writes and delta orderbook management via `use_delta_orderbook` parameter
- Automatic market info loading on connection
- Proper message type handling to distinguish snapshots from updates

## Usage

### Basic Usage with Delta Management

```python
from LighterCpty.lighter_ws import LighterWebSocketClient

# Create client with delta orderbook management enabled (default)
client = LighterWebSocketClient(
    url="wss://mainnet.zklighter.elliot.ai/stream",
    redis_url="redis://localhost:6379",
    use_delta_orderbook=True  # This is the default
)

# Subscribe to orderbooks
await client.subscribe_order_book(21)  # FARTCOIN
await client.subscribe_order_book(1)   # BTC

# Run the client
await client.run()
```

### Redis Storage Format

Orderbooks are stored in Redis with keys following the format:
```
l2_book:{BASE}-{QUOTE} LIGHTER Perpetual/{QUOTE} Crypto
```

Example keys:
- `l2_book:FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto`
- `l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto`
- `l2_book:ETH-USDC LIGHTER Perpetual/USDC Crypto`

### Stored Data Structure

```json
{
  "market_id": 21,
  "timestamp": 1989,
  "bids": [
    ["1.15744", "4978.9"],
    ["1.15702", "228.9"]
  ],
  "asks": [
    ["1.15790", "4977.0"],
    ["1.15804", "6222.0"]
  ],
  "bid_depth": 240,
  "ask_depth": 208
}
```

## Message Flow

1. **Initial Connection**: Client connects and loads market info from API
2. **Subscription**: Sends subscription request for specific market
3. **Snapshot**: Receives `subscribed/order_book` message with full orderbook
4. **Updates**: Receives `update/order_book` messages with deltas
5. **State Management**: OrderBookManager maintains accurate state
6. **Redis Write**: Current state written to Redis with each update

## Performance Characteristics

- **Message rates**: Typically 5-50 messages/second per market
- **Update ratio**: >95% of messages are deltas (not snapshots)
- **Memory efficient**: Only top 10 levels stored in Redis
- **Low latency**: Direct Redis writes without intermediate queuing

## Testing

Run the test script to verify delta orderbook management:

```bash
python test_cpty_delta_orderbook.py
```

This will:
- Subscribe to multiple markets
- Track snapshot vs update messages
- Verify orderbook accuracy
- Display real-time statistics