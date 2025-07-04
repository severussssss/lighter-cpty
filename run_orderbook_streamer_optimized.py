#!/usr/bin/env python3
"""Optimized Lighter orderbook streamer with improved performance."""
import asyncio
import logging
import json
import time
from typing import Dict, Set
from collections import defaultdict
import redis.asyncio as redis
from LighterCpty.lighter_ws import LighterWebSocketClient
from LighterCpty.orderbook_manager import OrderBook
from LighterCpty.market_loader import load_market_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('LighterCpty.orderbook_manager').setLevel(logging.WARNING)


class OptimizedOrderBookManager:
    """Optimized orderbook manager with batched Redis writes."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 batch_interval: float = 0.1,
                 max_batch_size: int = 50):
        self.orderbooks: Dict[int, OrderBook] = {}
        self.redis_url = redis_url
        self.redis_client = None
        self._market_info_cache: Dict[int, Dict[str, str]] = {}
        
        # Batching configuration
        self.batch_interval = batch_interval  # Write to Redis every N seconds
        self.max_batch_size = max_batch_size  # Max updates per batch
        
        # Pending updates
        self.pending_updates: Set[int] = set()
        self.last_write_time: Dict[int, float] = defaultdict(float)
        
        # Performance tracking
        self.message_count = 0
        self.redis_write_count = 0
        self.last_report_time = time.time()
        
    async def connect(self):
        """Connect to Redis with async client."""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url, 
                db=2, 
                decode_responses=True,
                socket_keepalive=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis (async)")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")
    
    def set_market_info(self, market_id: int, market_info: Dict[str, str]):
        """Set market info for generating readable keys."""
        self._market_info_cache[market_id] = market_info
        
    def get_market_key(self, market_id: int) -> str:
        """Generate market key."""
        if market_id in self._market_info_cache:
            info = self._market_info_cache[market_id]
            base = info.get('base_asset', 'UNKNOWN')
            quote = info.get('quote_asset', 'USDC')
            return f"{base}-{quote} LIGHTER Perpetual/{quote} Crypto"
        else:
            return f"MARKET_{market_id} LIGHTER Perpetual/USDC Crypto"
    
    def handle_orderbook_message(self, msg_type: str, market_id: int, orderbook_data: Dict):
        """Handle orderbook message without immediate Redis write."""
        if not orderbook_data:
            return
        
        self.message_count += 1
        
        # Get or create orderbook
        if market_id not in self.orderbooks:
            self.orderbooks[market_id] = OrderBook(market_id)
            
        orderbook = self.orderbooks[market_id]
        
        # Apply snapshot or update
        if 'subscribed' in msg_type:
            orderbook.apply_snapshot(orderbook_data)
        else:
            orderbook.apply_update(orderbook_data)
        
        # Mark for batch write
        self.pending_updates.add(market_id)
    
    async def write_batch_to_redis(self):
        """Write pending updates to Redis in batch."""
        if not self.pending_updates or not self.redis_client:
            return
        
        # Get updates to process
        updates_to_write = list(self.pending_updates)[:self.max_batch_size]
        self.pending_updates -= set(updates_to_write)
        
        # Prepare pipeline
        pipe = self.redis_client.pipeline(transaction=False)
        
        for market_id in updates_to_write:
            if market_id not in self.orderbooks:
                continue
                
            orderbook = self.orderbooks[market_id]
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
            pipe.setex(key, 300, json.dumps(l2_data))  # 5 minute TTL
            
            self.last_write_time[market_id] = time.time()
        
        # Execute pipeline
        try:
            await pipe.execute()
            self.redis_write_count += len(updates_to_write)
        except Exception as e:
            logger.error(f"Redis write error: {e}")
    
    async def run_batch_writer(self):
        """Background task to write batches to Redis."""
        while True:
            try:
                await asyncio.sleep(self.batch_interval)
                await self.write_batch_to_redis()
                
                # Report stats every 30 seconds
                now = time.time()
                if now - self.last_report_time >= 30:
                    elapsed = now - self.last_report_time
                    msg_rate = self.message_count / elapsed
                    write_rate = self.redis_write_count / elapsed
                    
                    logger.info(
                        f"Stats: {self.message_count} messages ({msg_rate:.1f}/s), "
                        f"{self.redis_write_count} Redis writes ({write_rate:.1f}/s), "
                        f"Compression ratio: {self.message_count/max(1, self.redis_write_count):.1f}:1"
                    )
                    
                    self.message_count = 0
                    self.redis_write_count = 0
                    self.last_report_time = now
                    
            except Exception as e:
                logger.error(f"Batch writer error: {e}")
                await asyncio.sleep(1)


async def run_optimized_streamer():
    """Run optimized orderbook streamer."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    redis_url = "redis://localhost:6379"
    
    # Create optimized manager
    manager = OptimizedOrderBookManager(
        redis_url=redis_url,
        batch_interval=0.1,  # Write every 100ms
        max_batch_size=50    # Max 50 markets per batch
    )
    
    # Connect to Redis
    await manager.connect()
    
    # Load market info
    market_info = load_market_info()
    for market_id, info in market_info.items():
        manager.set_market_info(market_id, info)
    logger.info(f"Loaded {len(market_info)} market definitions")
    
    # Create WebSocket client without built-in Redis
    client = LighterWebSocketClient(
        url=ws_url,
        redis_url=None,  # We handle Redis ourselves
        use_delta_orderbook=False
    )
    
    # Hook into orderbook messages
    def on_message_hook(original_handle):
        async def handle_with_manager(data):
            msg_type = data.get("type", "")
            channel = data.get("channel", "")
            
            if "order_book" in msg_type and ":" in channel:
                try:
                    market_id = int(channel.split(":")[-1])
                    orderbook_data = data.get("order_book", {})
                    if orderbook_data:
                        manager.handle_orderbook_message(msg_type, market_id, orderbook_data)
                except:
                    pass
            
            # Call original handler
            await original_handle(data)
        
        return handle_with_manager
    
    # Replace message handler
    client._handle_message = on_message_hook(client._handle_message)
    
    # Start batch writer
    batch_writer_task = asyncio.create_task(manager.run_batch_writer())
    
    # Connect
    logger.info("Starting optimized orderbook streamer...")
    connect_task = asyncio.create_task(client.connect())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Subscribe to markets (can subscribe to more with optimized version)
    markets_to_stream = list(range(45))  # All markets!
    
    logger.info(f"Subscribing to {len(markets_to_stream)} markets...")
    
    # Subscribe in batches to avoid overwhelming
    for i in range(0, len(markets_to_stream), 5):
        batch = markets_to_stream[i:i+5]
        for market_id in batch:
            await client.subscribe_order_book(market_id)
        await asyncio.sleep(0.1)
    
    logger.info("Streaming all orderbooks to Redis with optimized batching.")
    
    try:
        # Run forever
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        client.running = False
        batch_writer_task.cancel()
        await client.disconnect()
        await manager.disconnect()
        connect_task.cancel()


if __name__ == "__main__":
    try:
        # Use uvloop if available for better performance
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("Using uvloop for better performance")
        except ImportError:
            pass
            
        asyncio.run(run_optimized_streamer())
    except KeyboardInterrupt:
        print("\nStopped by user")