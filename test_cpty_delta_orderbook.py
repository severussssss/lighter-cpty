#!/usr/bin/env python3
"""Test CPTY delta orderbook management with Redis."""
import asyncio
import logging
import json
import redis
from datetime import datetime
from LighterCpty.lighter_ws import LighterWebSocketClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


async def monitor_orderbooks():
    """Monitor orderbook updates via CPTY."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    redis_url = "redis://localhost:6379"
    
    # Create WebSocket client with delta orderbook enabled
    client = LighterWebSocketClient(
        url=ws_url,
        redis_url=redis_url,
        use_delta_orderbook=True  # Enable delta orderbook management
    )
    
    # Track statistics
    stats = {
        'snapshots': {},
        'updates': {},
        'total': {}
    }
    
    # Override message handler to track message types
    original_handle = client._handle_message
    
    async def track_messages(data):
        msg_type = data.get("type", "")
        channel = data.get("channel", "")
        
        if "order_book" in msg_type and ":" in channel:
            try:
                market_id = int(channel.split(":")[-1])
                
                if market_id not in stats['total']:
                    stats['total'][market_id] = 0
                    stats['snapshots'][market_id] = 0
                    stats['updates'][market_id] = 0
                
                stats['total'][market_id] += 1
                
                if "subscribed" in msg_type:
                    stats['snapshots'][market_id] += 1
                elif "update" in msg_type:
                    stats['updates'][market_id] += 1
                    
            except:
                pass
        
        # Call original handler
        await original_handle(data)
    
    client._handle_message = track_messages
    
    # Start the client
    connect_task = asyncio.create_task(client.connect())
    
    # Wait for connection
    await asyncio.sleep(3)
    
    # Subscribe to some interesting markets
    markets_to_monitor = [
        0,   # ETH
        1,   # BTC
        2,   # SOL
        21,  # FARTCOIN
        24,  # HYPE
    ]
    
    logger.info("Subscribing to markets...")
    for market_id in markets_to_monitor:
        await client.subscribe_order_book(market_id)
        await asyncio.sleep(0.1)
    
    # Monitor for 20 seconds
    logger.info("\nMonitoring orderbook updates for 20 seconds...")
    start_time = datetime.now()
    
    # Create direct Redis connection for checking
    redis_client = redis.Redis.from_url(redis_url, db=2, decode_responses=True)
    
    for i in range(4):  # 4 x 5 seconds = 20 seconds
        await asyncio.sleep(5)
        
        logger.info(f"\n=== Status Report {i+1}/4 ===")
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Check each market
        for market_id in markets_to_monitor:
            # Get market info from orderbook manager
            if client.orderbook_manager and market_id in client.orderbook_manager._market_info_cache:
                info = client.orderbook_manager._market_info_cache[market_id]
                symbol = info.get('base_asset', f'Market{market_id}')
                
                # Get orderbook from Redis
                redis_key = f"l2_book:{symbol}-USDC LIGHTER Perpetual/USDC Crypto"
                orderbook_json = redis_client.get(redis_key)
                
                if orderbook_json:
                    orderbook = json.loads(orderbook_json)
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    
                    if bids and asks:
                        best_bid = float(bids[0][0])
                        best_ask = float(asks[0][0])
                        spread = best_ask - best_bid
                        
                        # Get stats
                        total_msgs = stats['total'].get(market_id, 0)
                        snapshots = stats['snapshots'].get(market_id, 0)
                        updates = stats['updates'].get(market_id, 0)
                        msg_rate = total_msgs / elapsed if elapsed > 0 else 0
                        
                        logger.info(
                            f"{symbol:>10}: Bid=${best_bid:>10,.2f} Ask=${best_ask:>10,.2f} "
                            f"Spread=${spread:>8,.4f} | "
                            f"Msgs={total_msgs:>4} ({msg_rate:.1f}/s) "
                            f"[Snap={snapshots} Updates={updates}]"
                        )
                        
                        # Check orderbook state
                        if client.orderbook_manager and market_id in client.orderbook_manager.orderbooks:
                            ob = client.orderbook_manager.orderbooks[market_id]
                            logger.debug(
                                f"  Internal state: {len(ob.bids)} bids, {len(ob.asks)} asks, "
                                f"initialized={ob.is_initialized}"
                            )
                    else:
                        logger.warning(f"{symbol:>10}: Empty orderbook")
                else:
                    logger.warning(f"{symbol:>10}: Not found in Redis (key: {redis_key})")
    
    # Final summary
    logger.info("\n=== FINAL SUMMARY ===")
    total_messages = sum(stats['total'].values())
    total_snapshots = sum(stats['snapshots'].values())
    total_updates = sum(stats['updates'].values())
    
    logger.info(f"Total messages: {total_messages}")
    logger.info(f"Total snapshots: {total_snapshots}")
    logger.info(f"Total updates: {total_updates}")
    
    if total_messages > 0:
        update_ratio = (total_updates / total_messages) * 100
        logger.info(f"Update ratio: {update_ratio:.1f}% (shows delta handling is working)")
    
    # Verify Redis keys
    logger.info("\n=== REDIS VERIFICATION ===")
    all_keys = redis_client.keys("l2_book:*")
    logger.info(f"Found {len(all_keys)} orderbook keys in Redis:")
    for key in sorted(all_keys)[:10]:  # Show first 10
        logger.info(f"  - {key}")
    
    # Cleanup
    client.running = False
    await client.disconnect()
    connect_task.cancel()
    redis_client.close()
    
    logger.info("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(monitor_orderbooks())