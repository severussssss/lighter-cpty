"""Lighter-specific data models for CPTY integration."""
import msgspec
from typing import Optional, Dict, List, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum


class LighterEnvironment(str, Enum):
    """Lighter environment configuration."""
    MAINNET = "mainnet"
    TESTNET = "testnet"


class LighterConfig(msgspec.Struct):
    """Configuration for Lighter CPTY connection."""
    environment: LighterEnvironment = LighterEnvironment.MAINNET
    api_key: str = ""
    api_secret: Optional[str] = None
    
    @property
    def rest_url(self) -> str:
        """Get REST API base URL based on environment."""
        if self.environment == LighterEnvironment.MAINNET:
            return "https://mainnet.zklighter.elliot.ai"
        else:
            # Assuming testnet URL follows similar pattern
            return "https://testnet.zklighter.elliot.ai"
    
    @property
    def ws_url(self) -> str:
        """Get WebSocket URL based on environment."""
        if self.environment == LighterEnvironment.MAINNET:
            return "wss://mainnet.zklighter.elliot.ai/stream"
        else:
            # Assuming testnet URL follows similar pattern
            return "wss://testnet.zklighter.elliot.ai/stream"


class LighterOrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class LighterOrderType(str, Enum):
    """Order type enumeration."""
    LIMIT = "limit"
    MARKET = "market"
    LIMIT_MAKER = "limit_maker"


class LighterTimeInForce(str, Enum):
    """Time in force enumeration."""
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class LighterOrderRequest(msgspec.Struct):
    """Request to place an order on Lighter."""
    market_id: int
    price: str  # String to preserve precision
    quantity: str  # String to preserve precision
    side: LighterOrderSide
    order_type: LighterOrderType = LighterOrderType.LIMIT
    time_in_force: LighterTimeInForce = LighterTimeInForce.GTC
    client_order_id: Optional[str] = None
    reduce_only: bool = False
    post_only: bool = False


class LighterOrderResponse(msgspec.Struct):
    """Response from Lighter order placement."""
    order_id: str
    market_id: int
    side: str
    price: str
    quantity: str
    created_at: int  # Unix timestamp
    client_order_id: Optional[str] = None
    filled_quantity: str = "0"
    status: str = "new"
    updated_at: Optional[int] = None


class LighterCancelRequest(msgspec.Struct):
    """Request to cancel an order."""
    order_id: str
    market_id: int


class LighterAccountBalance(msgspec.Struct):
    """Account balance information."""
    asset: str
    free: str
    locked: str
    total: str


class LighterPosition(msgspec.Struct):
    """Position information."""
    market_id: int
    side: str
    quantity: str
    entry_price: str
    mark_price: str
    pnl: str
    margin: str


class LighterAccountUpdate(msgspec.Struct):
    """Account update from WebSocket."""
    account_id: int
    balances: List[LighterAccountBalance]
    positions: List[LighterPosition]
    timestamp: int


class LighterOrderBookLevel(msgspec.Struct):
    """Single order book level."""
    price: str
    quantity: str
    order_count: int = 1


class LighterOrderBookUpdate(msgspec.Struct):
    """Order book update from WebSocket."""
    market_id: int
    bids: List[LighterOrderBookLevel]
    asks: List[LighterOrderBookLevel]
    timestamp: int
    sequence: int


class LighterTradeUpdate(msgspec.Struct):
    """Trade update from WebSocket."""
    market_id: int
    trade_id: str
    price: str
    quantity: str
    side: str
    timestamp: int
    maker_order_id: Optional[str] = None
    taker_order_id: Optional[str] = None


class LighterMarketInfo(msgspec.Struct):
    """Market information."""
    market_id: int
    base_asset: str
    quote_asset: str
    tick_size: str
    step_size: str
    min_order_size: str
    max_order_size: str
    is_active: bool = True


class LighterWSMessage(msgspec.Struct):
    """Base WebSocket message structure."""
    type: str
    channel: str
    data: Dict[str, Any]
    timestamp: Optional[int] = None


class LighterSubscription(msgspec.Struct):
    """WebSocket subscription message."""
    channel: str
    type: str = "subscribe"
    auth: Optional[str] = None


class LighterUnsubscription(msgspec.Struct):
    """WebSocket unsubscription message."""
    channel: str
    type: str = "unsubscribe"