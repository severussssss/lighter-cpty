"""Redis client for storing Lighter orderbook data."""
import json
import logging
from typing import Dict, Any, Optional, Tuple
import asyncio
import redis

logger = logging.getLogger(__name__)


class RedisOrderbookClient:
    """Async Redis client for storing L1/L2 orderbook data."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 2):
        """Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL
            db: Redis database number
        """
        self.redis_url = redis_url
        self.db = db
        self.redis: Optional[redis.Redis] = None
        self._market_info_cache: Dict[int, Dict[str, Any]] = {}
        
    def connect(self):
        """Connect to Redis."""
        try:
            self.redis = redis.Redis.from_url(
                self.redis_url, 
                db=self.db,
                decode_responses=True
            )
            self.redis.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            self.redis.close()
            logger.info("Disconnected from Redis")
    
    def set_market_info(self, market_id: int, market_info: Dict[str, Any]):
        """Cache market info for generating readable keys.
        
        Args:
            market_id: Market ID
            market_info: Market information including base_asset, quote_asset, etc.
        """
        self._market_info_cache[market_id] = market_info
    
    def _generate_market_key(self, market_id: int) -> str:
        """Generate a readable market key from market ID.
        
        Args:
            market_id: Market ID
            
        Returns:
            Market key like "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
        """
        if market_id in self._market_info_cache:
            info = self._market_info_cache[market_id]
            base = info.get('base_asset', 'UNKNOWN')
            quote = info.get('quote_asset', 'USDC')
            # Format: BASE-QUOTE LIGHTER Perpetual/QUOTE Crypto
            return f"{base}-{quote} LIGHTER Perpetual/{quote} Crypto"
        else:
            # Fallback if market info not cached
            return f"MARKET_{market_id} LIGHTER Perpetual/USDC Crypto"
    
    def write_l2_orderbook(self, market_id: int, orderbook: Dict[str, Any], depth: int = 10):
        """Write L2 (full depth) orderbook data to Redis.
        
        Args:
            market_id: Market ID
            orderbook: Orderbook data containing bids and asks
            depth: Maximum depth to store (default 10 levels)
        """
        if not self.redis:
            logger.error("Redis not connected")
            return
        
        try:
            # Extract orderbook data up to specified depth
            bids_raw = orderbook.get('bids', [])[:depth]
            asks_raw = orderbook.get('asks', [])[:depth]
            
            # Convert to consistent array format
            bids = []
            for bid in bids_raw:
                if isinstance(bid, dict):
                    bids.append([bid.get('price'), bid.get('size')])
                else:
                    bids.append(bid)
                    
            asks = []
            for ask in asks_raw:
                if isinstance(ask, dict):
                    asks.append([ask.get('price'), ask.get('size')])
                else:
                    asks.append(ask)
            
            l2_data = {
                'market_id': market_id,
                'timestamp': orderbook.get('timestamp') or orderbook.get('offset'),
                'bids': bids,
                'asks': asks,
                'bid_depth': len(bids),
                'ask_depth': len(asks)
            }
            
            # Generate key and store
            key = f"l2_book:{self._generate_market_key(market_id)}"
            self.redis.set(key, json.dumps(l2_data))
            
            # Set expiry (optional - 5 minutes)
            self.redis.expire(key, 300)
            
            logger.debug(f"Wrote L2 orderbook for market {market_id} to {key}")
            
        except Exception as e:
            logger.error(f"Failed to write L2 orderbook: {e}")
    
    def write_orderbook(self, market_id: int, orderbook: Dict[str, Any], depth: int = 10):
        """Write orderbook data to Redis.
        
        Args:
            market_id: Market ID
            orderbook: Orderbook data containing bids and asks
            depth: Maximum depth to store (default 10 levels)
        """
        self.write_l2_orderbook(market_id, orderbook, depth)
    
    def get_orderbook(self, market_key: str) -> Optional[Dict[str, Any]]:
        """Get orderbook data from Redis.
        
        Args:
            market_key: Market key (e.g., "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto")
            
        Returns:
            Orderbook data or None
        """
        if not self.redis:
            return None
        
        try:
            key = f"l2_book:{market_key}"
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return None
