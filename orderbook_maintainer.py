#!/usr/bin/env python3
"""Maintain Lighter orderbooks with proper delta updates."""
import asyncio
import json
import logging
import websockets
from typing import Dict, List, Tuple
from sortedcontainers import SortedDict
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrderBook:
    """Maintains orderbook state with delta updates."""
    
    def __init__(self, market_id: int):
        self.market_id = market_id
        self.bids = SortedDict(lambda x: -float(x))  # Reverse sort for bids (highest first)
        self.asks = SortedDict(lambda x: float(x))   # Normal sort for asks (lowest first)
        self.last_offset = 0
        
    def apply_snapshot(self, data: Dict):
        """Apply initial snapshot."""
        self.bids.clear()
        self.asks.clear()
        
        # Load bids
        for bid in data.get('bids', []):
            price = bid.get('price')
            size = bid.get('size')
            if price and float(size) > 0:
                self.bids[price] = size
                
        # Load asks
        for ask in data.get('asks', []):
            price = ask.get('price')
            size = ask.get('size')
            if price and float(size) > 0:
                self.asks[price] = size
                
        self.last_offset = data.get('offset', 0)
        logger.info(f"Market {self.market_id}: Loaded snapshot with {len(self.bids)} bids, {len(self.asks)} asks")
        
    def apply_update(self, data: Dict):
        """Apply delta update."""
        # Update bids
        for bid in data.get('bids', []):
            price = bid.get('price')
            size = bid.get('size')
            if price:
                if float(size) == 0:
                    # Remove price level
                    self.bids.pop(price, None)
                else:
                    # Add/update price level
                    self.bids[price] = size
                    
        # Update asks
        for ask in data.get('asks', []):
            price = ask.get('price')
            size = ask.get('size')
            if price:
                if float(size) == 0:
                    # Remove price level
                    self.asks.pop(price, None)
                else:
                    # Add/update price level
                    self.asks[price] = size
                    
        self.last_offset = data.get('offset', self.last_offset)
        
    def get_top_levels(self, depth: int = 10) -> Tuple[List, List]:
        """Get top N levels of bids and asks."""
        top_bids = []
        for i, (price, size) in enumerate(self.bids.items()):
            if i >= depth:
                break
            top_bids.append([price, size])
            
        top_asks = []
        for i, (price, size) in enumerate(self.asks.items()):
            if i >= depth:
                break
            top_asks.append([price, size])
            
        return top_bids, top_asks
    
    def get_best_bid_ask(self):
        """Get best bid and ask."""
        best_bid = None
        best_ask = None
        
        if self.bids:
            price, size = next(iter(self.bids.items()))
            best_bid = (float(price), float(size))
            
        if self.asks:
            price, size = next(iter(self.asks.items()))
            best_ask = (float(price), float(size))
            
        return best_bid, best_ask


class OrderBookManager:
    """Manages multiple orderbooks with Redis storage."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.orderbooks: Dict[int, OrderBook] = {}
        self.redis_client = redis.Redis.from_url(redis_url, db=2, decode_responses=True)
        self.market_info = {
            0: {"base_asset": "ETH", "quote_asset": "USDC"},
            1: {"base_asset": "BTC", "quote_asset": "USDC"},
            2: {"base_asset": "SOL", "quote_asset": "USDC"},
        }
        
    def get_market_key(self, market_id: int) -> str:
        """Generate market key."""
        info = self.market_info.get(market_id, {})
        base = info.get('base_asset', f'MARKET_{market_id}')
        quote = info.get('quote_asset', 'USDC')
        return f"{base}-{quote} LIGHTER Perpetual/{quote} Crypto"
        
    def handle_message(self, data: Dict):
        """Handle WebSocket message."""
        msg_type = data.get('type', '')
        channel = data.get('channel', '')
        
        if ':' not in channel:
            return
            
        market_id = int(channel.split(':')[-1])
        orderbook_data = data.get('order_book', {})
        
        if not orderbook_data:
            return
            
        # Get or create orderbook
        if market_id not in self.orderbooks:
            self.orderbooks[market_id] = OrderBook(market_id)
            
        orderbook = self.orderbooks[market_id]
        
        # Apply snapshot or update
        if 'subscribed' in msg_type:
            orderbook.apply_snapshot(orderbook_data)
        else:
            orderbook.apply_update(orderbook_data)
            
        # Write to Redis
        self.write_to_redis(market_id, orderbook)
        
    def write_to_redis(self, market_id: int, orderbook: OrderBook):
        """Write orderbook state to Redis."""
        top_bids, top_asks = orderbook.get_top_levels(10)
        
        l2_data = {
            'market_id': market_id,
            'timestamp': orderbook.last_offset,
            'bids': top_bids,
            'asks': top_asks,
            'bid_depth': len(orderbook.bids),
            'ask_depth': len(orderbook.asks)
        }
        
        key = f"l2_book:{self.get_market_key(market_id)}"
        self.redis_client.set(key, json.dumps(l2_data))
        self.redis_client.expire(key, 300)
        
        # Log best bid/ask
        best_bid, best_ask = orderbook.get_best_bid_ask()
        if best_bid and best_ask:
            spread = best_ask[0] - best_bid[0]
            logger.debug(f"{self.market_info.get(market_id, {}).get('base_asset', f'Market{market_id}')}: "
                        f"Bid=${best_bid[0]:.2f} Ask=${best_ask[0]:.2f} Spread=${spread:.2f}")


async def maintain_orderbooks():
    """Connect to WebSocket and maintain orderbooks."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    manager = OrderBookManager()
    
    logger.info("Connecting to WebSocket...")
    
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        logger.info("Connected!")
        
        # Wait for connected message
        await ws.recv()
        
        # Subscribe to markets
        for market_id in manager.market_info.keys():
            sub = {"type": "subscribe", "channel": f"order_book/{market_id}"}
            await ws.send(json.dumps(sub))
            logger.info(f"Subscribed to market {market_id}")
            await asyncio.sleep(0.1)
            
        # Process messages
        message_count = 0
        async for message in ws:
            try:
                data = json.loads(message)
                
                if 'order_book' in data.get('type', ''):
                    manager.handle_message(data)
                    message_count += 1
                    
                    if message_count % 100 == 0:
                        logger.info(f"Processed {message_count} messages")
                        
                        # Show current state
                        for market_id, ob in manager.orderbooks.items():
                            best_bid, best_ask = ob.get_best_bid_ask()
                            if best_bid and best_ask:
                                asset = manager.market_info[market_id]['base_asset']
                                logger.info(f"{asset}: Bid=${best_bid[0]:.2f} Ask=${best_ask[0]:.2f} "
                                          f"({len(ob.bids)} bids, {len(ob.asks)} asks)")
                                          
            except Exception as e:
                logger.error(f"Error processing message: {e}")


if __name__ == "__main__":
    # Install sortedcontainers if needed
    try:
        from sortedcontainers import SortedDict
    except ImportError:
        import subprocess
        subprocess.check_call(["pip", "install", "sortedcontainers"])
        from sortedcontainers import SortedDict
        
    asyncio.run(maintain_orderbooks())