"""Rate limiter implementation for Lighter API."""
import time
from collections import defaultdict
from typing import Dict, Tuple
import asyncio
from enum import Enum


class RateLimitType(str, Enum):
    """Types of rate limits."""
    REST_USER = "rest_user"  # 2400 weighted per minute
    REST_IP = "rest_ip"  # 500 per 60 seconds
    WS_MESSAGES = "ws_messages"  # 100 burst limit
    TRANSACTION = "transaction"  # Various transaction limits


class RateLimiter:
    """Token bucket rate limiter for Lighter API."""
    
    def __init__(self):
        self.buckets: Dict[RateLimitType, Dict[str, Tuple[float, float, float]]] = defaultdict(dict)
        
        # Configuration for different rate limit types
        self.limits = {
            RateLimitType.REST_USER: {
                "capacity": 2400,  # weighted requests
                "refill_rate": 2400 / 60,  # per second
                "window": 60  # seconds
            },
            RateLimitType.REST_IP: {
                "capacity": 500,
                "refill_rate": 500 / 60,
                "window": 60
            },
            RateLimitType.WS_MESSAGES: {
                "capacity": 100,
                "refill_rate": 100,  # instant refill
                "window": 1
            },
            RateLimitType.TRANSACTION: {
                "capacity": 100,
                "refill_rate": 100,
                "window": 1
            }
        }
        
        # Endpoint weights for REST API
        self.endpoint_weights = {
            "/": 1,
            "/info": 1,
            "/sendTx": 1,
            "/publicPools": 5,
            "/candlesticks": 5,
            "/accountInactiveOrders": 10,
            "/apikeys": 15,
            # Default weight for unspecified endpoints
            "default": 30
        }
        
        # Transaction type limits
        self.transaction_limits = {
            "L2Withdraw": {"capacity": 2, "window": 60},
            "L2UpdateLeverage": {"capacity": 1, "window": 1},
            "L2CreateSubAccount": {"capacity": 2, "window": 60},
            "L2ChangePubKey": {"capacity": 2, "window": 10},
            "default": {"capacity": 100, "window": 1}
        }
    
    def _get_bucket(self, limit_type: RateLimitType, key: str) -> Tuple[float, float, float]:
        """Get or create a token bucket for the given limit type and key."""
        if key not in self.buckets[limit_type]:
            config = self.limits[limit_type]
            # Initialize bucket: (tokens, capacity, last_refill_time)
            self.buckets[limit_type][key] = (
                config["capacity"],
                config["capacity"],
                time.time()
            )
        return self.buckets[limit_type][key]
    
    def _refill_bucket(self, limit_type: RateLimitType, key: str) -> Tuple[float, float, float]:
        """Refill tokens in the bucket based on elapsed time."""
        tokens, capacity, last_refill = self._get_bucket(limit_type, key)
        config = self.limits[limit_type]
        
        now = time.time()
        elapsed = now - last_refill
        
        # Calculate tokens to add
        tokens_to_add = elapsed * config["refill_rate"]
        new_tokens = min(tokens + tokens_to_add, capacity)
        
        # Update bucket
        self.buckets[limit_type][key] = (new_tokens, capacity, now)
        return new_tokens, capacity, now
    
    def check_rate_limit(self, limit_type: RateLimitType, key: str, weight: float = 1.0) -> Tuple[bool, float]:
        """
        Check if request can proceed under rate limit.
        
        Returns:
            Tuple of (allowed, wait_time_seconds)
        """
        tokens, capacity, _ = self._refill_bucket(limit_type, key)
        
        if tokens >= weight:
            # Consume tokens
            self.buckets[limit_type][key] = (tokens - weight, capacity, time.time())
            return True, 0.0
        else:
            # Calculate wait time
            config = self.limits[limit_type]
            tokens_needed = weight - tokens
            wait_time = tokens_needed / config["refill_rate"]
            return False, wait_time
    
    async def wait_if_needed(self, limit_type: RateLimitType, key: str, weight: float = 1.0) -> None:
        """Wait if rate limit is exceeded."""
        allowed, wait_time = self.check_rate_limit(limit_type, key, weight)
        if not allowed and wait_time > 0:
            await asyncio.sleep(wait_time)
            # Retry after waiting
            await self.wait_if_needed(limit_type, key, weight)
    
    def get_endpoint_weight(self, endpoint: str) -> int:
        """Get the weight for a specific endpoint."""
        # Remove query parameters and normalize
        endpoint_path = endpoint.split("?")[0].rstrip("/")
        return self.endpoint_weights.get(endpoint_path, self.endpoint_weights["default"])
    
    def get_transaction_limit(self, tx_type: str) -> Dict[str, int]:
        """Get the rate limit configuration for a transaction type."""
        return self.transaction_limits.get(tx_type, self.transaction_limits["default"])
    
    async def check_rest_limit(self, user_id: str, ip_address: str, endpoint: str) -> None:
        """Check both user and IP rate limits for REST API."""
        weight = self.get_endpoint_weight(endpoint)
        
        # Check user limit
        await self.wait_if_needed(RateLimitType.REST_USER, user_id, weight)
        
        # Check IP limit (weight 1 for IP-based limit)
        await self.wait_if_needed(RateLimitType.REST_IP, ip_address, 1)
    
    async def check_transaction_limit(self, user_id: str, tx_type: str) -> None:
        """Check transaction-specific rate limits."""
        tx_config = self.get_transaction_limit(tx_type)
        
        # Create a custom limit configuration for this transaction type
        tx_limit_key = f"tx_{tx_type}"
        if tx_limit_key not in self.limits:
            self.limits[tx_limit_key] = {
                "capacity": tx_config["capacity"],
                "refill_rate": tx_config["capacity"] / tx_config["window"],
                "window": tx_config["window"]
            }
        
        await self.wait_if_needed(tx_limit_key, user_id, 1)
    
    def get_remaining_capacity(self, limit_type: RateLimitType, key: str) -> float:
        """Get remaining capacity for a rate limit."""
        tokens, _, _ = self._refill_bucket(limit_type, key)
        return tokens
    
    def reset_bucket(self, limit_type: RateLimitType, key: str) -> None:
        """Reset a specific bucket to full capacity."""
        if key in self.buckets[limit_type]:
            config = self.limits[limit_type]
            self.buckets[limit_type][key] = (
                config["capacity"],
                config["capacity"],
                time.time()
            )