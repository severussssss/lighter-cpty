#!/usr/bin/env python3
"""Write orderbooks to Redis with CORRECT market mappings."""
import asyncio
import json
import logging
import websockets
from datetime import datetime
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CORRECT market mappings based on price discovery
MARKET_INFO = {
    0: {"base_asset": "ETH", "quote_asset": "USDC"},    # ETH ~$2500
    1: {"base_asset": "BTC", "quote_asset": "USDC"},    # BTC ~$108k
    2: {"base_asset": "SOL", "quote_asset": "USDC"},    # SOL ~$148
    # We'll need to discover the rest
}


def generate_market_key(market_id: int) -> str:
    """Generate Redis key for market."""
    info = MARKET_INFO.get(market_id, {})
    base = info.get('base_asset', f'MARKET_{market_id}')
    quote = info.get('quote_asset', 'USDC')
    return f"{base}-{quote} LIGHTER Perpetual/{quote} Crypto"


async def write_orderbooks():
    """Connect to WebSocket and write orderbooks to Redis."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    
    # Connect to Redis
    redis_client = redis.Redis.from_url("redis://localhost:6379", db=2, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis")
    
    # Clear old incorrect data
    old_keys = redis_client.keys("l2_book:*")
    if old_keys:
        redis_client.delete(*old_keys)
        logger.info(f"Cleared {len(old_keys)} old orderbook keys")
    
    # Connect to WebSocket
    logger.info(f"Connecting to {ws_url}...")
    
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        logger.info("Connected to WebSocket")
        
        # Wait for connected message
        await ws.recv()
        
        # Subscribe to known markets
        for market_id in MARKET_INFO.keys():
            subscription = {
                "type": "subscribe",
                "channel": f"order_book/{market_id}"
            }
            await ws.send(json.dumps(subscription))
            logger.info(f"Subscribed to market {market_id} ({MARKET_INFO[market_id]['base_asset']})")
            await asyncio.sleep(0.1)
        
        # Process messages
        message_count = 0
        start_time = datetime.now()
        
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data.get('type', '')
                
                if 'order_book' in msg_type and msg_type != 'subscribed/order_book':
                    channel = data.get('channel', '')
                    if ':' in channel:
                        market_id = int(channel.split(':')[-1])
                        
                        # Only process known markets
                        if market_id not in MARKET_INFO:
                            continue
                        
                        # Extract orderbook data
                        orderbook = data.get('order_book', {})
                        if orderbook and ('bids' in orderbook or 'asks' in orderbook):
                            # Convert to our format
                            bids = []
                            asks = []
                            
                            for bid in orderbook.get('bids', []):
                                if isinstance(bid, dict):
                                    bids.append([bid.get('price'), bid.get('size')])
                                else:
                                    bids.append(bid)
                                    
                            for ask in orderbook.get('asks', []):
                                if isinstance(ask, dict):
                                    asks.append([ask.get('price'), ask.get('size')])
                                else:
                                    asks.append(ask)
                            
                            # Create L2 orderbook data
                            l2_data = {
                                'market_id': market_id,
                                'timestamp': orderbook.get('offset'),
                                'bids': bids[:10],  # Top 10 levels
                                'asks': asks[:10],
                                'bid_depth': len(bids),
                                'ask_depth': len(asks)
                            }
                            
                            # Write to Redis with correct key
                            key = f"l2_book:{generate_market_key(market_id)}"
                            redis_client.set(key, json.dumps(l2_data))
                            redis_client.expire(key, 300)  # 5 minute TTL
                            
                            message_count += 1
                            
                            # Log first few orderbooks
                            if message_count <= 3:
                                asset = MARKET_INFO[market_id]['base_asset']
                                if bids:
                                    logger.info(f"{asset} Best Bid: ${bids[0][0]}")
                                if asks:
                                    logger.info(f"{asset} Best Ask: ${asks[0][0]}")
                            
                            # Stop after writing some data
                            if message_count >= 20:
                                logger.info("Wrote 20 orderbook updates. Stopping...")
                                break
                                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
        
        logger.info(f"Finished. Wrote {message_count} orderbook updates to Redis")


if __name__ == "__main__":
    asyncio.run(write_orderbooks())