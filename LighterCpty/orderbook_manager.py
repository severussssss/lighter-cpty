"""Orderbook manager with proper delta update handling for Lighter."""
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from sortedcontainers import SortedDict
import redis

logger = logging.getLogger(__name__)


class OrderBook:
    """Maintains orderbook state with delta updates."""
    
    def __init__(self, market_id: int):
        self.market_id = market_id
        self.bids = SortedDict(lambda x: -float(x))  # Reverse sort for bids (highest first)
        self.asks = SortedDict(lambda x: float(x))   # Normal sort for asks (lowest first)
        self.last_offset = 0
        self.is_initialized = False
        
    def apply_snapshot(self, data: Dict):
        """Apply initial snapshot."""
        self.bids.clear()
        self.asks.clear()
        
        # Load bids
        for bid in data.get('bids', []):
            if isinstance(bid, dict):
                price = bid.get('price')
                size = bid.get('size')
            elif isinstance(bid, list) and len(bid) >= 2:
                price = bid[0]
                size = bid[1]
            else:
                continue
                
            if price and float(size) > 0:
                self.bids[str(price)] = str(size)
                
        # Load asks
        for ask in data.get('asks', []):
            if isinstance(ask, dict):
                price = ask.get('price')
                size = ask.get('size')
            elif isinstance(ask, list) and len(ask) >= 2:
                price = ask[0]
                size = ask[1]
            else:
                continue
                
            if price and float(size) > 0:
                self.asks[str(price)] = str(size)
                
        self.last_offset = data.get('offset', 0)
        self.is_initialized = True
        logger.info(f"Market {self.market_id}: Loaded snapshot with {len(self.bids)} bids, {len(self.asks)} asks")
        
    def apply_update(self, data: Dict):
        """Apply delta update."""
        if not self.is_initialized:
            logger.warning(f"Market {self.market_id}: Applying update without snapshot - treating as snapshot")
            self.apply_snapshot(data)
            return
            
        # Update bids
        for bid in data.get('bids', []):
            if isinstance(bid, dict):
                price = bid.get('price')
                size = bid.get('size')
            elif isinstance(bid, list) and len(bid) >= 2:
                price = bid[0]
                size = bid[1]
            else:
                continue
                
            if price:
                price_str = str(price)
                if float(size) == 0:
                    # Remove price level
                    self.bids.pop(price_str, None)
                else:
                    # Add/update price level
                    self.bids[price_str] = str(size)
                    
        # Update asks
        for ask in data.get('asks', []):
            if isinstance(ask, dict):
                price = ask.get('price')
                size = ask.get('size')
            elif isinstance(ask, list) and len(ask) >= 2:
                price = ask[0]
                size = ask[1]
            else:
                continue
                
            if price:
                price_str = str(price)
                if float(size) == 0:
                    # Remove price level
                    self.asks.pop(price_str, None)
                else:
                    # Add/update price level
                    self.asks[price_str] = str(size)
                    
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
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 2):
        self.orderbooks: Dict[int, OrderBook] = {}
        self.redis_client = redis.Redis.from_url(redis_url, db=db, decode_responses=True)
        self._market_info_cache: Dict[int, Dict[str, Any]] = {}
        
    def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client.ping()
            logger.info("OrderBookManager connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("OrderBookManager disconnected from Redis")
    
    def set_market_info(self, market_id: int, market_info: Dict[str, Any]):
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
        
    def handle_orderbook_message(self, msg_type: str, market_id: int, orderbook_data: Dict[str, Any]):
        """Handle orderbook message - either snapshot or update."""
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
        self.redis_client.expire(key, 300)  # 5 minute TTL
        
        # Log best bid/ask for debugging
        best_bid, best_ask = orderbook.get_best_bid_ask()
        if best_bid and best_ask:
            spread = best_ask[0] - best_bid[0]
            market_name = self._market_info_cache.get(market_id, {}).get('base_asset', f'Market{market_id}')
            logger.debug(f"{market_name}: Bid=${best_bid[0]:.2f} Ask=${best_ask[0]:.2f} Spread=${spread:.2f}")
    
    def get_orderbook(self, market_key: str) -> Optional[Dict[str, Any]]:
        """Get orderbook data from Redis."""
        try:
            key = f"l2_book:{market_key}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return None