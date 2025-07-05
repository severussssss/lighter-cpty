#!/usr/bin/env python3
"""Test delta orderbook management with LighterCpty."""
import asyncio
import logging
import json
from datetime import datetime
from LighterCpty.lighter_ws import LighterWebSocketClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable debug logs from websockets
logging.getLogger('websockets').setLevel(logging.WARNING)

# Known market mappings from discovery
MARKET_MAPPINGS = {
    0: {"base_asset": "BTC", "quote_asset": "USDC"},
    1: {"base_asset": "ETH", "quote_asset": "USDC"},
    2: {"base_asset": "SOL", "quote_asset": "USDC"},
    20: {"base_asset": "BERA", "quote_asset": "USDC"},
    21: {"base_asset": "FARTCOIN", "quote_asset": "USDC"},
    24: {"base_asset": "HYPE", "quote_asset": "USDC"},
}


async def test_delta_orderbook():
    """Test delta orderbook management."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    redis_url = "redis://localhost:6379"
    
    # Create WebSocket client with delta orderbook enabled
    client = LighterWebSocketClient(
        url=ws_url,
        redis_url=redis_url,
        use_delta_orderbook=True  # Enable delta orderbook management
    )
    
    # Set market info for readable Redis keys
    for market_id, info in MARKET_MAPPINGS.items():
        client.set_market_info(market_id, info)
    
    # Track message counts
    message_counts = {}
    snapshot_counts = {}
    update_counts = {}
    
    # Define orderbook callback
    def on_orderbook(market_id: int, orderbook: dict):
        """Handle orderbook updates."""
        # Track message counts
        if market_id not in message_counts:
            message_counts[market_id] = 0
            snapshot_counts[market_id] = 0
            update_counts[market_id] = 0
        message_counts[market_id] += 1
    
    # Define message handler to track message types
    original_handle_message = client._handle_message
    
    async def track_message_types(data):
        """Track message types."""
        msg_type = data.get("type", "")
        channel = data.get("channel", "")
        
        if "order_book" in msg_type and ":" in channel:
            market_id = int(channel.split(":")[-1])
            if market_id in MARKET_MAPPINGS:
                if "subscribed" in msg_type:
                    snapshot_counts[market_id] = snapshot_counts.get(market_id, 0) + 1
                elif "update" in msg_type:
                    update_counts[market_id] = update_counts.get(market_id, 0) + 1
        
        # Call original handler
        await original_handle_message(data)
    
    client._handle_message = track_message_types
    client.on_order_book = on_orderbook
    
    # Start the client
    connect_task = asyncio.create_task(client.connect())
    
    # Wait a bit for connection
    await asyncio.sleep(2)
    
    # Subscribe to markets
    logger.info("Subscribing to markets...")
    for market_id in MARKET_MAPPINGS.keys():
        await client.subscribe_order_book(market_id)
        await asyncio.sleep(0.1)
    
    # Monitor for 30 seconds
    logger.info("Monitoring orderbook updates for 30 seconds...")
    start_time = datetime.now()
    
    for i in range(6):  # 6 x 5 seconds = 30 seconds
        await asyncio.sleep(5)
        
        # Check Redis for current orderbook state
        if client.orderbook_manager:
            logger.info(f"\n--- Status after {(i+1)*5} seconds ---")
            
            for market_id, info in MARKET_MAPPINGS.items():
                if market_id in message_counts:
                    market_key = f"{info['base_asset']}-{info['quote_asset']} LIGHTER Perpetual/{info['quote_asset']} Crypto"
                    orderbook_data = client.orderbook_manager.get_orderbook(market_key)
                    
                    if orderbook_data:
                        bids = orderbook_data.get('bids', [])
                        asks = orderbook_data.get('asks', [])
                        
                        if bids and asks:
                            best_bid = float(bids[0][0])
                            best_ask = float(asks[0][0])
                            spread = best_ask - best_bid
                            
                            logger.info(
                                f"{info['base_asset']:>10}: "
                                f"Bid=${best_bid:>10,.2f} Ask=${best_ask:>10,.2f} "
                                f"Spread=${spread:>8,.2f} | "
                                f"Msgs={message_counts[market_id]:>4} "
                                f"(Snap={snapshot_counts.get(market_id, 0)} "
                                f"Updates={update_counts.get(market_id, 0)})"
                            )
                        else:
                            logger.info(f"{info['base_asset']:>10}: No orderbook data")
                    else:
                        logger.info(f"{info['base_asset']:>10}: Not in Redis")
    
    # Final summary
    logger.info("\n=== FINAL SUMMARY ===")
    total_messages = sum(message_counts.values())
    total_snapshots = sum(snapshot_counts.values())
    total_updates = sum(update_counts.values())
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"Total messages: {total_messages} ({total_messages/elapsed:.1f} msg/s)")
    logger.info(f"Total snapshots: {total_snapshots}")
    logger.info(f"Total updates: {total_updates}")
    logger.info(f"Update ratio: {total_updates/total_messages*100:.1f}%")
    
    # Verify delta handling
    logger.info("\n=== DELTA HANDLING VERIFICATION ===")
    if client.orderbook_manager:
        for market_id, ob in client.orderbook_manager.orderbooks.items():
            if market_id in MARKET_MAPPINGS:
                info = MARKET_MAPPINGS[market_id]
                logger.info(
                    f"{info['base_asset']:>10}: "
                    f"Bid levels={len(ob.bids)} Ask levels={len(ob.asks)} "
                    f"Initialized={ob.is_initialized}"
                )
    
    # Disconnect
    client.running = False
    await client.disconnect()
    connect_task.cancel()
    
    logger.info("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(test_delta_orderbook())