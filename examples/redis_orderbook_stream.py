#!/usr/bin/env python3
"""Example of streaming Lighter orderbooks to Redis."""
import asyncio
import logging
import os
from dotenv import load_dotenv
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LighterCpty.lighter_ws import LighterWebSocketClient
from LighterCpty.market_info import fetch_market_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def main():
    """Main function to run orderbook streaming to Redis."""
    # Configuration
    ws_url = os.getenv("LIGHTER_WS_URL", "wss://mainnet.zklighter.elliot.ai/stream")
    api_url = os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Markets to subscribe to
    target_markets = ["HYPE", "BERA", "WDEGEN", "SONIC", "FARTCOIN"]  # Add your target assets
    
    logger.info("Starting Lighter orderbook Redis streaming...")
    logger.info(f"WebSocket URL: {ws_url}")
    logger.info(f"Redis URL: {redis_url}")
    
    # Fetch market info first
    logger.info("Fetching market information...")
    market_info = await fetch_market_info(api_url)
    
    if not market_info:
        logger.error("Failed to fetch market information")
        return
    
    # Find market IDs for target assets
    market_ids_to_subscribe = []
    for market_id, info in market_info.items():
        base_asset = info.get('base_asset', '').upper()
        if base_asset in target_markets and info.get('is_active', False):
            market_ids_to_subscribe.append(market_id)
            logger.info(f"Will subscribe to {base_asset}/{info.get('quote_asset')} (Market ID: {market_id})")
    
    if not market_ids_to_subscribe:
        logger.warning("No active markets found for target assets")
        return
    
    # Create WebSocket client with Redis
    client = LighterWebSocketClient(ws_url, redis_url=redis_url)
    
    # Set market info for proper Redis key generation
    for market_id, info in market_info.items():
        client.set_market_info(market_id, info)
    
    # Define callbacks
    async def on_order_book(market_id: int, order_book: dict):
        """Handle orderbook updates."""
        info = market_info.get(market_id, {})
        base = info.get('base_asset', 'UNKNOWN')
        quote = info.get('quote_asset', 'USDC')
        
        # Log orderbook summary
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        if bids and asks:
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread = best_ask - best_bid
            
            logger.info(
                f"{base}/{quote} - "
                f"Bid: ${best_bid:.4f} | "
                f"Ask: ${best_ask:.4f} | "
                f"Spread: ${spread:.4f} ({spread/best_ask*100:.2f}%)"
            )
    
    # Set callbacks
    client.on_order_book = on_order_book
    client.on_connected = lambda: logger.info("Connected to Lighter WebSocket")
    client.on_disconnected = lambda: logger.info("Disconnected from Lighter WebSocket")
    client.on_error = lambda e: logger.error(f"WebSocket error: {e}")
    
    # Connect and subscribe
    try:
        # Start the client
        asyncio.create_task(client.run())
        
        # Wait for connection
        await asyncio.sleep(2)
        
        # Subscribe to orderbooks
        for market_id in market_ids_to_subscribe:
            await client.subscribe_order_book(market_id)
            await asyncio.sleep(0.1)  # Small delay between subscriptions
        
        logger.info(f"Subscribed to {len(market_ids_to_subscribe)} markets")
        logger.info("Streaming orderbooks to Redis... Press Ctrl+C to stop")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.disconnect()


async def check_redis_data():
    """Check what's in Redis (for debugging)."""
    import redis.asyncio as redis
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get all keys
        keys = await r.keys("*book:*")
        logger.info(f"Found {len(keys)} orderbook keys in Redis:")
        
        for key in sorted(keys)[:10]:  # Show first 10
            data = await r.get(key)
            if data:
                parsed = json.loads(data)
                logger.info(f"  {key}: {len(parsed.get('bids', []))} bids, {len(parsed.get('asks', []))} asks")
    finally:
        await r.close()


if __name__ == "__main__":
    # Run main streaming
    asyncio.run(main())
    
    # Optionally check Redis data
    # asyncio.run(check_redis_data())