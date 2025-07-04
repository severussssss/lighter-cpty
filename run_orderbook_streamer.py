#!/usr/bin/env python3
"""Run Lighter orderbook streamer with delta management."""
import asyncio
import logging
from LighterCpty.lighter_ws import LighterWebSocketClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


async def run_orderbook_streamer():
    """Stream orderbooks to Redis."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    redis_url = "redis://localhost:6379"
    
    # Create WebSocket client with delta orderbook enabled
    client = LighterWebSocketClient(
        url=ws_url,
        redis_url=redis_url,
        use_delta_orderbook=True
    )
    
    # Track some stats
    message_count = 0
    last_report = asyncio.get_event_loop().time()
    
    def on_orderbook(market_id: int, orderbook: dict):
        """Count messages."""
        nonlocal message_count, last_report
        message_count += 1
        
        # Report every 30 seconds
        now = asyncio.get_event_loop().time()
        if now - last_report >= 30:
            last_report = now
            logger.info(f"Processed {message_count} orderbook updates")
    
    client.on_order_book = on_orderbook
    
    # Connect
    logger.info("Starting orderbook streamer...")
    connect_task = asyncio.create_task(client.connect())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Subscribe to major markets
    markets_to_stream = [
        0,   # ETH
        1,   # BTC
        2,   # SOL
        3,   # DOGE
        4,   # 1000PEPE
        5,   # WIF
        7,   # XRP
        8,   # LINK
        9,   # AVAX
        20,  # BERA
        21,  # FARTCOIN
        22,  # AI16Z
        24,  # HYPE
        25,  # BNB
        30,  # UNI
        16,  # SUI
        15,  # TRUMP
    ]
    
    logger.info(f"Subscribing to {len(markets_to_stream)} markets...")
    for market_id in markets_to_stream:
        await client.subscribe_order_book(market_id)
        await asyncio.sleep(0.1)
    
    logger.info("Streaming orderbooks to Redis. Press Ctrl+C to stop.")
    
    try:
        # Run forever
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        client.running = False
        await client.disconnect()
        connect_task.cancel()
        
    logger.info(f"Streamed {message_count} total orderbook updates")


if __name__ == "__main__":
    try:
        asyncio.run(run_orderbook_streamer())
    except KeyboardInterrupt:
        print("\nStopped by user")