#!/usr/bin/env python3
"""Write Lighter orderbooks to Redis."""
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

# Known markets
MARKET_INFO = {
    0: {"base_asset": "BTC", "quote_asset": "USDC"},
    1: {"base_asset": "ETH", "quote_asset": "USDC"},
    20: {"base_asset": "BERA", "quote_asset": "USDC"},
    21: {"base_asset": "FARTCOIN", "quote_asset": "USDC"},
    24: {"base_asset": "HYPE", "quote_asset": "USDC"},
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
    
    # Connect to WebSocket
    logger.info(f"Connecting to {ws_url}...")
    
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        logger.info("Connected to WebSocket")
        
        # Subscribe to known markets
        for market_id in MARKET_INFO.keys():
            subscription = {
                "type": "subscribe",
                "channel": f"order_book/{market_id}"
            }
            await ws.send(json.dumps(subscription))
            logger.info(f"Subscribed to market {market_id}")
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
                        
                        # Extract orderbook data
                        orderbook = data.get('order_book', {})
                        if orderbook and 'bids' in orderbook and 'asks' in orderbook:
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
                            
                            # Write to Redis
                            key = f"l2_book:{generate_market_key(market_id)}"
                            redis_client.set(key, json.dumps(l2_data))
                            redis_client.expire(key, 300)  # 5 minute TTL
                            
                            message_count += 1
                            
                            # Log progress
                            if message_count % 10 == 0:
                                elapsed = (datetime.now() - start_time).total_seconds()
                                rate = message_count / elapsed if elapsed > 0 else 0
                                logger.info(f"Written {message_count} orderbooks ({rate:.1f} msg/s)")
                            
                            # Stop after writing some data
                            if message_count >= 50:
                                logger.info("Wrote 50 orderbook updates. Stopping...")
                                break
                                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
        
        logger.info(f"Finished. Wrote {message_count} orderbook updates to Redis")


if __name__ == "__main__":
    asyncio.run(write_orderbooks())