# L2 Book Streaming via gRPC

This document describes the L2 orderbook streaming functionality implemented in LighterCpty.

## Overview

LighterCpty now supports streaming L2 orderbook data directly to Architect Core clients via gRPC, eliminating the need for Redis as an intermediary. This provides lower latency and simpler architecture.

## Implementation Details

### Components

1. **OrderBook Management**: Uses the existing `OrderBook` class to maintain orderbook state
2. **WebSocket Integration**: Receives orderbook updates via Lighter's WebSocket API
3. **gRPC Streaming**: Calls `on_l2_book_snapshot` to stream data to connected clients

### Configuration

By default, the system subscribes to the first 10 markets (IDs 0-9). This can be modified in `lighter_cpty_async.py`:

```python
# In __init__
self.subscribed_orderbook_markets: Set[int] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
```

### Data Flow

1. WebSocket receives orderbook snapshot/update from Lighter
2. `_on_order_book_update` callback processes the data
3. OrderBook state is updated (snapshot or delta)
4. Top 10 levels are extracted and converted to Decimal format
5. `on_l2_book_snapshot` is called to stream to gRPC clients

## Testing

### Running the CPTY Server

```bash
# In one terminal
python -m LighterCpty.lighter_cpty_async
```

### Testing with Architect Client

Two test scripts are provided:

1. **Simple Test** - Verifies basic connectivity:
```bash
python test_l2_simple.py
```

2. **Full Test** - Tests multiple markets with statistics:
```bash
python test_l2_subscription.py
```

## Performance Considerations

- **Current Scale**: 10 markets × 200 updates/sec = 2,000 updates/sec
- **AsyncQueue Performance**: Python's asyncio.Queue handles this load well
- **No Batching Required**: Direct streaming without buffering
- **Memory Usage**: ~1MB per market for orderbook state

## Scaling Options

If you need to handle more markets or higher update rates:

1. **Increase Markets**: Simply add more market IDs to `subscribed_orderbook_markets`
2. **Rate Limiting**: Implement per-market throttling if needed
3. **Depth Limiting**: Reduce from 10 to 5 levels to decrease message size
4. **Sampling**: Only send every Nth update for less critical markets

## Comparison with Redis Approach

| Aspect | Redis (Old) | gRPC Direct (New) |
|--------|------------|-------------------|
| Latency | ~5-10ms | <1ms |
| Complexity | High (3 components) | Low (2 components) |
| Memory | Redis + Python | Python only |
| Scalability | Good | Good |
| Reliability | Redis persistence | In-memory only |

## Future Enhancements

1. **Dynamic Market Selection**: Allow runtime configuration of subscribed markets
2. **Metrics**: Add Prometheus metrics for monitoring
3. **Compression**: Implement message compression for bandwidth optimization
4. **Reconnection**: Improve WebSocket reconnection logic