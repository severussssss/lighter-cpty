"""Lighter CPTY implementation using architect-py's AsyncCpty base class."""
import asyncio
import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Sequence
from dotenv import load_dotenv

# Suppress debug logs from architect_py by default
logging.getLogger('architect_py').setLevel(logging.INFO)

# Architect imports
from architect_py import (
    Cancel,
    CptyLoginRequest,
    CptyLogoutRequest,
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    OrderRejectReason,
    ExecutionInfo,
    AccountPosition,
)
from architect_py.async_cpty import AsyncCpty
import grpc

# Lighter SDK imports
import lighter
from lighter import SignerClient, ApiClient, Configuration
from lighter.exceptions import ApiException

# Local imports
from .lighter_ws import LighterWebSocketClient
from .balance_fetcher import LighterBalanceFetcher

logger = logging.getLogger(__name__)


class LighterCpty(AsyncCpty):
    """Lighter CPTY implementation using AsyncCpty base class."""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize Lighter CPTY."""
        super().__init__("LIGHTER")
        logger.info("LighterCpty initialized")
        
        self.config = config or self._load_config_from_env()
        
        # Initialize SDK clients
        self.signer_client: Optional[SignerClient] = None
        self.ws_client: Optional[LighterWebSocketClient] = None
        self.api_client: Optional[ApiClient] = None
        self.balance_fetcher: Optional[LighterBalanceFetcher] = None
        
        # Session management
        self.logged_in = False
        self.user_id: Optional[str] = None
        self.account_id: Optional[str] = None
        self.account_index: Optional[int] = None
        
        # Market information
        self.symbol_to_market_id: Dict[str, int] = {}
        self.market_id_to_symbol: Dict[int, str] = {}
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.client_to_exchange_id: Dict[str, str] = {}
        self.exchange_to_client_id: Dict[str, str] = {}
        self._processed_fills: set = set()  # Track processed fills to avoid duplicates
        self._order_filled_quantities: Dict[str, Decimal] = {}  # Track filled quantities per order
        
        # WebSocket state
        self.ws_connected = False
        self.latest_account_data: Optional[Dict] = None
        self.latest_balance: Optional[Decimal] = None
        
        # Initialize execution info
        self._init_execution_info()
    
    def _put_orderflow_event(self, event):
        """Override to add logging for debugging."""
        logger.debug(f"Putting orderflow event: {type(event).__name__} - {event}")
        logger.debug(f"Number of orderflow subscriptions: {len(self.orderflow_subscriptions)}")
        
        if len(self.orderflow_subscriptions) == 0:
            logger.warning("No orderflow subscriptions active! Architect Core may not be connected.")
        else:
            # Log details about each subscription and queue
            for sub_id, sub in self.orderflow_subscriptions.items():
                logger.debug(f"  Subscription #{sub_id}: Queue size = {sub.queue.qsize()}")
                
                # Log the event details based on type
                if hasattr(event, '__dict__'):
                    logger.debug(f"  Event details: {vars(event)}")
                
                # For reject events, log specific fields
                if type(event).__name__ == 'TaggedOrderReject':
                    logger.debug(f"  → Order ID: {event.id}")
                    logger.debug(f"  → Reject reason: {event.reject_reason}")
                    logger.debug(f"  → Reject message: {event.message}")
                elif type(event).__name__ == 'TaggedOrderAck':
                    logger.debug(f"  → Order ID: {event.order_id}")
                    logger.debug(f"  → Exchange order ID: {event.exchange_order_id}")
                elif type(event).__name__ == 'TaggedFill':
                    logger.debug(f"  → Order ID: {event.order_id}")
                    logger.debug(f"  → Fill quantity: {event.quantity}")
                    logger.debug(f"  → Fill price: {event.price}")
        
        # Call parent method to actually put the event
        super()._put_orderflow_event(event)
        
        # After putting the event, check if it's actually in the queue
        for sub_id, sub in self.orderflow_subscriptions.items():
            logger.debug(f"  After put: Subscription #{sub_id} queue size = {sub.queue.qsize()}")
    
    async def SubscribeOrderflow(self, request, context):
        """Override to add logging when Architect Core subscribes."""
        logger.info(f"Architect Core subscribing to orderflow: {request}")
        logger.info(f"Subscription request details: {vars(request) if hasattr(request, '__dict__') else request}")
        
        # Don't call super() - implement the subscription ourselves to properly intercept events
        from architect_py.async_cpty import OrderflowSubscription
        
        context.set_code(grpc.StatusCode.OK)
        await context.send_initial_metadata([])
        
        subscription_id = self.next_subscription_id
        self.next_subscription_id += 1
        logger.info(f"Created orderflow subscription #{subscription_id}")
        
        def cleanup_subscription(_context):
            if subscription_id in self.orderflow_subscriptions:
                del self.orderflow_subscriptions[subscription_id]
                logger.info(f"Cleaned up orderflow subscription #{subscription_id}")
        
        context.add_done_callback(cleanup_subscription)
        subscription = OrderflowSubscription(request)
        self.orderflow_subscriptions[subscription_id] = subscription
        
        event_count = 0
        while True:
            next_item = await subscription.queue.get()
            event_count += 1
            logger.debug(f"=== YIELDING ORDERFLOW EVENT #{event_count} ===")
            logger.debug(f"  Event type: {type(next_item).__name__}")
            logger.debug(f"  Event content: {next_item}")
            yield next_item
    
    def _load_config_from_env(self) -> Dict:
        """Load configuration from environment variables."""
        env_path = Path(__file__).parent.parent.parent.parent.parent.parent / "lighter-python" / "examples" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
        
        return {
            "url": os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai"),
            "private_key": os.getenv("LIGHTER_API_KEY_PRIVATE_KEY", ""),
            "account_index": int(os.getenv("LIGHTER_ACCOUNT_INDEX", "0")),
            "api_key_index": int(os.getenv("LIGHTER_API_KEY_INDEX", "1"))
        }
    
    def _init_execution_info(self):
        """Initialize execution info for known markets."""
        # Default markets
        default_markets = [
            (21, "FARTCOIN", "USDC"),
            (24, "HYPE", "USDC"),
            (20, "BERA", "USDC"),
        ]
        
        for market_id, base, quote in default_markets:
            architect_symbol = f"{base}-{quote} LIGHTER Perpetual/{quote} Crypto"
            self.symbol_to_market_id[architect_symbol] = market_id
            self.market_id_to_symbol[market_id] = architect_symbol
            
            # Add execution info
            exec_info = ExecutionInfo(
                execution_venue="LIGHTER",
                exchange_symbol=f"{base}-{quote}",
                tick_size={"simple": "0.00001"},
                step_size="0.1",
                min_order_quantity="0.1",
                min_order_quantity_unit={"unit": "base"},
                is_delisted=False,
                initial_margin=None,
                maintenance_margin=None,
            )

            self.add_execution_info(architect_symbol, exec_info)
    
    async def _init_clients(self) -> bool:
        """Initialize Lighter SDK clients."""
        try:
            # Initialize API client
            configuration = Configuration(host=self.config["url"])
            self.api_client = ApiClient(configuration=configuration)
            
            # Initialize balance fetcher
            self.balance_fetcher = LighterBalanceFetcher(self.api_client)
            
            # Initialize signer client
            self.signer_client = SignerClient(
                url=self.config["url"],
                private_key=self.config["private_key"],
                account_index=self.account_index or self.config["account_index"],
                api_key_index=self.config["api_key_index"]
            )
            
            # Check client validity
            err = self.signer_client.check_client()
            if err is not None:
                logger.error(f"Signer client check failed: {err}")
                return False
            
            logger.info("Lighter SDK clients initialized successfully")
            
            # Initialize WebSocket
            await self._init_websocket()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return False
    
    async def _init_websocket(self):
        """Initialize WebSocket connection."""
        try:
            # WebSocket URL
            ws_url = self.config["url"].replace("https://", "wss://").replace("http://", "ws://")
            ws_url = f"{ws_url}/stream"
            
            # Initialize WebSocket client
            self.ws_client = LighterWebSocketClient(ws_url)
            
            # Set up callbacks
            self.ws_client.on_account = self._on_account_update
            # Don't subscribe to market-wide trades - we only need our fills from account updates
            # self.ws_client.on_trade = self._on_trade_update
            self.ws_client.on_connected = self._on_ws_connected
            self.ws_client.on_disconnected = self._on_ws_disconnected
            self.ws_client.on_error = self._on_ws_error
            
            # Run WebSocket in background
            asyncio.create_task(self._run_websocket())
            
            # Subscribe to account updates after a short delay
            asyncio.create_task(self._initial_subscriptions())
            
            logger.info("WebSocket client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket: {e}")
    
    async def _initial_subscriptions(self):
        """Set up initial WebSocket subscriptions."""
        try:
            # Wait for WebSocket to connect
            for _ in range(10):  # Wait up to 5 seconds
                if self.ws_connected:
                    break
                await asyncio.sleep(0.5)
            
            if self.ws_connected and self.ws_client and self.account_index:
                # Subscribe to account updates
                await self.ws_client.subscribe_account(self.account_index)
                logger.info(f"Subscribed to account_all/{self.account_index}")
                
        except Exception as e:
            logger.error(f"Failed to set up subscriptions: {e}")
    
    async def _run_websocket(self):
        """Run WebSocket client."""
        try:
            await self.ws_client.run()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.ws_connected = False
    
    def _on_ws_connected(self):
        """Handle WebSocket connection."""
        logger.info("WebSocket connected")
        self.ws_connected = True
        # Note: The WebSocket will automatically subscribe to account updates
        # after connection via _resubscribe_all() in the WebSocket handler
    
    async def _subscribe_market_specific(self, market_id: int):
        """Subscribe to account updates for a specific market."""
        if self.ws_client and self.account_index is not None:
            # Subscribe to market-specific account updates
            channel = f"account_market/{market_id}/{self.account_index}"
            subscription = {
                "type": "subscribe",
                "channel": channel
            }
            await self.ws_client.pending_subscriptions.put(subscription)
            self.ws_client.subscriptions.add(channel)
            logger.info(f"Subscribed to account_market for market {market_id}")
    
    def _on_ws_disconnected(self):
        """Handle WebSocket disconnection."""
        logger.warning("WebSocket disconnected")
        self.ws_connected = False
    
    def _on_ws_error(self, error: Exception):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
    
    def _on_trade_update(self, market_id: int, trade: Dict):
        """Handle trade updates from WebSocket."""
        try:
            logger.info(f"Trade update for market {market_id}: {trade}")
            
            # Process the trade as a fill
            self._process_single_fill(trade)
            
        except Exception as e:
            logger.error(f"Error processing trade update: {e}")
    
    def _on_account_update(self, account_id: int, account: Dict):
        """Handle account updates from WebSocket."""
        try:
            logger.info(f"Account update for {account_id}")
            self.latest_account_data = account
            
            # Log trades field for debugging
            trades = account.get("trades", {})
            if trades:
                logger.info(f"Trades in account update: {len(trades)} markets with trades")
                # Only process trades if we have active orders
                if self.orders:
                    logger.info(f"Processing trades for {len(self.orders)} active orders")
                    self._process_order_fills(account)
                else:
                    logger.debug(f"Skipping trade processing - no active orders")
            else:
                logger.debug(f"Empty trades field in account update")
                # Log what fields are present
                logger.debug(f"Account update fields: {list(account.keys())}")
            
            # Check if trade counts changed
            new_total_trades = account.get("total_trades_count", 0)
            new_daily_trades = account.get("daily_trades_count", 0)
            
            # Store previous counts to detect changes
            if not hasattr(self, '_last_trade_counts'):
                self._last_trade_counts = {'total': 0, 'daily': 0}
            
            if new_total_trades > self._last_trade_counts['total']:
                logger.info(f"New trades detected! Total: {self._last_trade_counts['total']} -> {new_total_trades}")
                # Fetch recent trades via API
                asyncio.create_task(self._fetch_and_process_recent_trades())
            
            self._last_trade_counts['total'] = new_total_trades
            self._last_trade_counts['daily'] = new_daily_trades
            
            # Log any trade-related fields
            for key in account:
                if "trade" in key.lower() or "fill" in key.lower():
                    logger.debug(f"{key}: {account[key]}")
            
            # Extract balance
            balance = LighterBalanceFetcher.parse_ws_account_update(account)
            if balance is not None:
                self.latest_balance = balance
                logger.info(f"Updated balance: {balance}")
            else:
                # Try to calculate equity
                equity = LighterBalanceFetcher.calculate_account_equity(account)
                if equity is not None:
                    self.latest_balance = equity
                    logger.info(f"Calculated equity: {equity}")
            
            # Process any order fills in the account data
            self._process_order_fills(account)
            
            # Broadcast update using AsyncCpty method
            asyncio.create_task(self._broadcast_account_update())
            
        except Exception as e:
            logger.error(f"Error processing account update: {e}")
    
    async def _broadcast_account_update(self):
        """Broadcast account update to all connections."""
        if not self.latest_account_data:
            return
        
        # Parse balances
        balances = {}
        if self.latest_balance is not None:
            balances["USDC Crypto"] = self.latest_balance
        
        # Parse positions
        positions = {}
        if "positions" in self.latest_account_data:
            positions_data = self.latest_account_data["positions"]
            # Handle both list and dict formats
            if isinstance(positions_data, list):
                for pos_data in positions_data:
                    if isinstance(pos_data, dict):
                        market_id = pos_data.get("market_id", pos_data.get("marketId"))
                        if market_id is not None:
                            symbol = self.market_id_to_symbol.get(int(market_id), f"Unknown-{market_id}")
                            positions[symbol] = AccountPosition(
                                quantity=Decimal(str(pos_data.get("quantity", 0))),
                                break_even_price=Decimal(str(pos_data.get("entryPrice", 0)))
                            )
            elif isinstance(positions_data, dict):
                for market_id_str, pos_data in positions_data.items():
                    if isinstance(pos_data, dict):
                        market_id = int(market_id_str) if market_id_str.isdigit() else None
                        if market_id is not None:
                            symbol = self.market_id_to_symbol.get(market_id, f"Unknown-{market_id}")
                            positions[symbol] = AccountPosition(
                                quantity=Decimal(str(pos_data.get("quantity", 0))),
                                break_even_price=Decimal(str(pos_data.get("entryPrice", 0)))
                            )
        
        # Use AsyncCpty's update_account_summary method
        self.update_account_summary(
            account=str(self.account_id or self.account_index),
            is_snapshot=True,
            timestamp=datetime.now(),
            balances=balances,
            positions=positions,
        )
    
    async def Cpty(self, request_iterator, context):
        """Override to add logging when Architect Core connects."""
        logger.info("========== ARCHITECT CORE CONNECTED TO CPTY STREAM ==========")
        async for response in super().Cpty(request_iterator, context):
            yield response
    
    async def on_login(self, request: CptyLoginRequest):
        """Handle login request."""
        logger.info("========== LOGIN REQUEST RECEIVED ==========")
        logger.info(f"Login request from trader={request.trader}, account={request.account}")
        
        self.user_id = request.trader
        self.account_id = request.account
        if request.account and request.account.isdigit():
            self.account_index = int(request.account)
        else:
            self.account_index = self.config["account_index"]
        
        # Initialize clients if needed
        if not self.signer_client:
            success = await self._init_clients()
            if not success:
                raise Exception("Failed to initialize Lighter clients")
        
        self.logged_in = True
        logger.info(f"Login successful for user {self.user_id}")

        # Start periodic updates
        # DISABLED: Causing 429 rate limit errors - WebSocket updates are sufficient
        # asyncio.create_task(self._periodic_account_updates())
    
    async def on_logout(self, request: CptyLogoutRequest):
        """Handle logout request."""
        logger.info("Logout request received")
        self.logged_in = False
        self.user_id = None
        self.account_id = None
    
    async def on_place_order(self, order: Order):
        """Handle place order request."""
        logger.info(f"Place order: {order}")
        
        if not self.logged_in or not self.signer_client:
            self.reject_order(
                order.id,
                reject_reason=OrderRejectReason.NotLoggedIn,
                reject_message="Not logged in or client not initialized"
            )
            return
        
        try:
            # Get market ID
            market_id = self.symbol_to_market_id.get(order.symbol)
            if market_id is None:
                self.reject_order(
                    order.id,
                    reject_reason=OrderRejectReason.UnknownSymbol,
                    reject_message=f"Unknown symbol: {order.symbol}"
                )
                return
            
            # Convert price and quantity based on market
            if market_id == 21:  # FARTCOIN
                price_int = int(float(order.limit_price) * 100000) if order.limit_price else 0  # 5 decimals
                base_amount = int(float(order.quantity) * 10)  # 1 decimal
            else:
                price_int = int(float(order.limit_price) * 100) if order.limit_price else 0
                base_amount = int(float(order.quantity) * 1e6)
            
            # Place order on Lighter
            tx, tx_hash, err = await self.signer_client.create_order(
                market_index=market_id,
                client_order_index=abs(hash(order.id)) % (10**8),
                base_amount=base_amount,
                price=price_int,
                is_ask=order.dir == OrderDir.SELL,
                order_type=SignerClient.ORDER_TYPE_LIMIT,
                time_in_force=SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                reduce_only=0,
                trigger_price=0
            )

            if err is not None:
                logger.error(f"Failed to place order: {err}")
                self.reject_order(
                    order.id,
                    reject_reason=OrderRejectReason.ExchangeReject,
                    reject_message=str(err)
                )
                return
            
            # Track order
            tx_hash_str = str(tx_hash.tx_hash) if hasattr(tx_hash, 'tx_hash') else str(tx_hash)
            client_order_index = abs(hash(order.id)) % (10**8)
            
            # Store mappings for both tx_hash and order index
            self.orders[order.id] = order
            self.client_to_exchange_id[order.id] = tx_hash_str
            self.exchange_to_client_id[tx_hash_str] = order.id
            
            # Also store mapping by order index for WebSocket matching
            order_index_key = f"order_index_{client_order_index}"
            self.exchange_to_client_id[order_index_key] = order.id
            
            # Acknowledge order
            logger.info(f"About to acknowledge order: {order.id}")
            self.ack_order(order.id, exchange_order_id=tx_hash_str)
            logger.info(f"Order acknowledged: {order.id} -> {tx_hash_str}")
            logger.info(f"Order placed: {order.id} -> {tx_hash_str}, client_order_index: {client_order_index}")
            
            # Debug: Check orderflow subscriptions
            logger.info(f"Active orderflow subscriptions: {len(self.orderflow_subscriptions)}")
            
            # Order is now on the exchange - fills will come through WebSocket
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            self.reject_order(
                order.id,
                reject_reason=OrderRejectReason.InvalidOrder,
                reject_message=str(e)
            )
    
    async def on_cancel_order(self, cancel: Cancel, original_order: Optional[Order] = None):
        """Handle cancel order request."""
        logger.info(f"Cancel order: {cancel.xid}")  # xid is the cancel_id field
        
        # Get the order to cancel
        if original_order is None:
            self.reject_cancel(
                cancel.xid,
                reject_reason="Order not found",
                reject_message="Cannot find order to cancel"
            )
            return
        
        # Check if order is cancelable
        if original_order.status not in [OrderStatus.Pending, OrderStatus.Open]:
            self.reject_cancel(
                cancel.xid,
                reject_reason="Order not cancelable",
                reject_message=f"Order status {original_order.status.name} cannot be cancelled"
            )
            return
        
        try:
            # Get exchange order ID
            exchange_order_id = self.client_to_exchange_id.get(original_order.id)
            if not exchange_order_id:
                self.reject_cancel(
                    cancel.xid,
                    reject_reason="Exchange order ID not found",
                    reject_message="Cannot find exchange order ID"
                )
                return
            
            # Get market ID
            market_id = self.symbol_to_market_id.get(original_order.symbol)
            if market_id is None:
                self.reject_cancel(
                    cancel.xid,
                    reject_reason="Unknown symbol",
                    reject_message=f"Unknown symbol: {original_order.symbol}"
                )
                return
            
            # Get order index from hash/tx
            # For Lighter, we need the order index which is typically the client_order_index we used
            order_index = abs(hash(original_order.id)) % (10**8)
            
            # Cancel order on Lighter
            cancel_tx, cancel_hash, err = await self.signer_client.cancel_order(
                market_index=market_id,
                order_index=order_index
            )
            
            if err is not None:
                logger.error(f"Failed to cancel order: {err}")
                self.reject_cancel(
                    cancel.xid,
                    reject_reason="Exchange cancel failed",
                    reject_message=str(err)
                )
                return
            
            # Cancel accepted - no explicit ack_cancel method in AsyncCpty
            logger.info(f"Order cancel sent: {original_order.id} -> {cancel_hash}")
            
            # After some delay, mark as cancelled (in real implementation, wait for exchange confirmation)
            asyncio.create_task(self._finalize_cancel(original_order.id, cancel.xid))
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            self.reject_cancel(
                cancel.xid,
                reject_reason="Cancel error",
                reject_message=str(e)
            )
    
    async def on_cancel_all_orders(
        self,
        account: Optional[str] = None,
        execution_venue: Optional[str] = None,
        trader: Optional[str] = None,
    ):
        """Handle cancel all orders request."""
        logger.info("========== CANCEL ALL ORDERS REQUEST ==========")
        logger.info(f"Account: {account}, Venue: {execution_venue}, Trader: {trader}")
        
        if not self.logged_in or not self.signer_client:
            logger.error("Cannot cancel all - not logged in or client not initialized")
            return
        
        try:
            # Cancel all orders on Lighter
            # time_in_force=0 means cancel all orders regardless of TIF
            # time=0 means cancel all immediately
            response, err = await self.signer_client.cancel_all_orders(
                time_in_force=0,  # Cancel all orders regardless of time in force
                time=0  # 0 means cancel all immediately
            )
            
            if err is not None:
                logger.error(f"Failed to cancel all orders: {err}")
                return
            
            logger.info("Cancel all orders sent successfully")
            
            # Get list of our open orders to mark as cancelled
            orders_to_cancel = []
            for order_id, order in self.orders.items():
                # Check filters
                should_cancel = True
                
                # Filter by account if specified
                if account and str(order.account) != str(account):
                    should_cancel = False
                    
                # Filter by venue if specified (we only have LIGHTER)
                if execution_venue and execution_venue != self.execution_venue:
                    should_cancel = False
                    
                # Filter by trader if specified
                if trader and str(order.trader) != str(trader):
                    should_cancel = False
                
                # Only cancel open/pending orders
                if order.status not in [OrderStatus.Pending, OrderStatus.Open]:
                    should_cancel = False
                    
                if should_cancel:
                    orders_to_cancel.append(order_id)
            
            logger.info(f"Marking {len(orders_to_cancel)} orders as cancelled")
            
            # Mark all matching orders as cancelled
            for order_id in orders_to_cancel:
                # Create a unique cancel ID for tracking
                cancel_id = f"cancel_all_{int(time.time() * 1000)}_{order_id}"
                asyncio.create_task(self._finalize_cancel(order_id, cancel_id))
                
            logger.info("Cancel all orders completed")
            
        except Exception as e:
            logger.error(f"Error in cancel all orders: {e}")
            import traceback
            traceback.print_exc()
    
    async def get_open_orders(self) -> Sequence[Order]:
        """Get all open orders."""
        open_orders = []
        for order_id, order in self.orders.items():
            if order.status in [OrderStatus.Pending, OrderStatus.Open]:
                open_orders.append(order)
        return open_orders
    
    def _process_order_fills(self, account_data: Dict):
        """Process order fills from account WebSocket data."""
        try:
            # Debug: Log the structure of account data to understand the format
            logger.debug("_process_order_fills called")
            if "trades" in account_data or "recent_trades" in account_data or "orders" in account_data:
                logger.debug(f"Account data keys: {list(account_data.keys())}")
            
            # Check trade counts
            total_trades = account_data.get("total_trades_count", 0)
            daily_trades = account_data.get("daily_trades_count", 0)
            if total_trades > 0 or daily_trades > 0:
                logger.debug(f"Trade counts - total: {total_trades}, daily: {daily_trades}")
            
            # Check for trades/fills in the account data
            trades = account_data.get("trades", {})
            if trades and isinstance(trades, dict):
                logger.info(f"Found trades for {len(trades)} markets in account update")
                # Trades come as a dict with market IDs as keys, values are lists of trades
                for market_id, market_trades in trades.items():
                    logger.info(f"Processing {len(market_trades) if isinstance(market_trades, list) else 1} trades for market {market_id}")
                    if isinstance(market_trades, list):
                        for trade_data in market_trades:
                            if isinstance(trade_data, dict):
                                self._process_single_fill(trade_data)
                            else:
                                logger.warning(f"Unexpected trade data format: {type(trade_data)}")
                    elif isinstance(market_trades, dict):
                        self._process_single_fill(market_trades)
                    else:
                        logger.warning(f"Unexpected market trades format: {type(market_trades)}")
                    
            # Also check for "recent_trades" or "filled_orders"
            recent_trades = account_data.get("recent_trades", [])
            if recent_trades:
                for trade in recent_trades:
                    self._process_single_fill(trade)
                    
            # Check for orders with fills
            orders = account_data.get("orders", {})
            if isinstance(orders, dict):
                for order_id, order_data in orders.items():
                    if isinstance(order_data, dict):
                        filled_qty = order_data.get("filled_quantity", order_data.get("filled", "0"))
                        if filled_qty and Decimal(str(filled_qty)) > 0:
                            # This order has fills, process them
                            self._process_order_update(order_id, order_data)
            elif isinstance(orders, list):
                for order_data in orders:
                    if isinstance(order_data, dict):
                        filled_qty = order_data.get("filled_quantity", order_data.get("filled", "0"))
                        if filled_qty and Decimal(str(filled_qty)) > 0:
                            self._process_order_update(order_data.get("id", order_data.get("order_id")), order_data)
                    
        except Exception as e:
            logger.error(f"Error processing order fills: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_single_fill(self, trade_data: Dict):
        """Process a single fill/trade from WebSocket data."""
        try:
            # Extract trade information from Lighter format
            trade_id = str(trade_data.get("trade_id", ""))
            
            if not trade_id:
                logger.warning(f"No trade_id in trade data: {trade_data}")
                return
                
            # Check if we've already processed this fill
            if trade_id in self._processed_fills:
                return
            
            # Skip if we have no orders to match against
            if not self.orders:
                logger.debug(f"Skipping trade {trade_id} - no active orders to match")
                return
                
            logger.info(f"Processing new trade {trade_id}")
            
            # Determine which order was ours based on account ID
            is_our_ask = trade_data.get("ask_account_id") == self.account_index
            is_our_bid = trade_data.get("bid_account_id") == self.account_index
            
            if not (is_our_ask or is_our_bid):
                logger.warning(f"Trade {trade_id} doesn't involve our account")
                return
            
            # Get the order ID (it's the ask_id or bid_id depending on our side)
            lighter_order_id = trade_data.get("ask_id") if is_our_ask else trade_data.get("bid_id")
            
            # Find the client order ID using tx_hash or order index
            tx_hash = trade_data.get("tx_hash")
            client_order_id = None
            
            # Log the trade data for debugging
            logger.info(f"Trade data: ask_id={trade_data.get('ask_id')}, bid_id={trade_data.get('bid_id')}, tx_hash={tx_hash}")
            
            if tx_hash:
                client_order_id = self.exchange_to_client_id.get(tx_hash)
                if client_order_id:
                    logger.info(f"Matched trade {trade_id} to order {client_order_id} via tx_hash")
            
            # If not found by tx_hash, try matching by order index
            if not client_order_id and lighter_order_id:
                # Try to extract order index from the lighter_order_id
                for client_id, order in self.orders.items():
                    expected_index = abs(hash(client_id)) % (10**8)
                    order_index_key = f"order_index_{expected_index}"
                    
                    # Check if this order index matches
                    if (str(expected_index) in str(lighter_order_id) or 
                        self.exchange_to_client_id.get(order_index_key) == client_id):
                        client_order_id = client_id
                        logger.info(f"Matched trade {trade_id} to order {client_order_id} via order index {expected_index}")
                        break
            
            if not client_order_id:
                # This is likely a historical trade or a trade that happened before we started tracking
                logger.debug(f"Could not match trade {trade_id} to any known order (tx_hash={tx_hash}, lighter_order_id={lighter_order_id})")
                logger.debug(f"Known exchange_to_client_id mappings: {list(self.exchange_to_client_id.keys())[:5]}...")  # Show first 5
                return
                
            order = self.orders.get(client_order_id)
            if not order:
                logger.warning(f"Order {client_order_id} not found in orders dict")
                return
                
            logger.info(f"Matched trade {trade_id} to order {client_order_id}")
            
            # Extract fill details from Lighter trade format
            market_id = trade_data.get("market_id")
            price = Decimal(str(trade_data.get("price", "0")))
            quantity = Decimal(str(trade_data.get("size", "0")))  # Lighter uses "size" not "quantity"
            
            # Determine if we were taker or maker
            is_maker_ask = trade_data.get("is_maker_ask", False)
            is_taker = (is_our_ask and not is_maker_ask) or (is_our_bid and is_maker_ask)
            
            timestamp = trade_data.get("timestamp")
            
            # Note: Price and quantity are already in human-readable format from Lighter
                
            # Calculate fee (typically 0.1% for taker, 0.05% for maker)
            fee_rate = Decimal("0.001") if is_taker else Decimal("0.0005")
            fee = price * quantity * fee_rate
            
            # Determine trade time
            if isinstance(timestamp, (int, float)):
                trade_time = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
            else:
                trade_time = datetime.now()
                
            # Report the fill
            self.fill_order(
                dir=order.dir,
                exchange_fill_id=trade_id,
                fill_id=None,  # Let Architect generate it
                price=price,
                quantity=quantity,
                symbol=order.symbol,
                trade_time=trade_time,
                account=order.account,
                is_taker=is_taker,
                fee=fee,
                fee_currency="USDC",
                order_id=client_order_id,
                trader=order.trader,
            )
            
            # Update filled quantity tracking
            if client_order_id not in self._order_filled_quantities:
                self._order_filled_quantities[client_order_id] = Decimal("0")
            self._order_filled_quantities[client_order_id] += quantity
            
            # Mark fill as processed
            self._processed_fills.add(trade_id)
            logger.info(f"Processed fill: {trade_id} for order {client_order_id}, qty={quantity}, total_filled={self._order_filled_quantities[client_order_id]}")
            
            # Check if order is fully filled
            filled_qty = self._calculate_filled_quantity(client_order_id)
            if filled_qty >= order.quantity:
                self.out_order(client_order_id, canceled=False)
                logger.info(f"Order fully filled: {client_order_id}")
                
        except Exception as e:
            logger.error(f"Error processing single fill: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_filled_quantity(self, order_id: str) -> Decimal:
        """Calculate total filled quantity for an order."""
        return self._order_filled_quantities.get(order_id, Decimal("0"))
    
    async def _finalize_cancel(self, order_id: str, cancel_id: str):
        """Finalize order cancellation after exchange confirmation."""
        # Wait a bit for exchange to process
        await asyncio.sleep(2)
        
        try:
            # Out the order as cancelled
            self.out_order(order_id, canceled=True)
            
            # Clean up tracking
            if order_id in self.client_to_exchange_id:
                exchange_id = self.client_to_exchange_id[order_id]
                del self.client_to_exchange_id[order_id]
                if exchange_id in self.exchange_to_client_id:
                    del self.exchange_to_client_id[exchange_id]
            
            # Remove from orders dict and clean up tracking
            if order_id in self.orders:
                del self.orders[order_id]
            if order_id in self._order_filled_quantities:
                del self._order_filled_quantities[order_id]
            
            logger.info(f"Order cancelled: {order_id}")
            
        except Exception as e:
            logger.error(f"Error finalizing cancel: {e}")
    
    async def _fetch_and_process_recent_trades(self):
        """Fetch recent trades from API when trade count changes."""
        try:
            if not self.api_client or not self.signer_client:
                return
                
            logger.info("Fetching recent trades from API...")
            
            # For now, just log that we need to implement this
            # In a real implementation, we would:
            # 1. Call the Lighter API to get recent trades
            # 2. Match them to our orders
            # 3. Report fills via fill_order()
            
            logger.info("TODO: Implement trade fetching from Lighter API")
            
            # As a workaround, check if any orders are no longer open
            # This indicates they were filled
            for order_id, order in list(self.orders.items()):
                if order.status == OrderStatus.Pending:
                    # Check if this order still exists
                    # If not, it was likely filled
                    logger.info(f"Checking status of order {order_id}")
                    
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            import traceback
            traceback.print_exc()
    
    async def _periodic_account_updates(self):
        """Send periodic account updates.
        
        DISABLED: This function was causing 429 rate limit errors.
        WebSocket provides real-time account updates, making polling unnecessary.
        Only enable this as a fallback if WebSocket updates are unreliable.
        """
        while self.logged_in:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                if self.balance_fetcher and self.account_index is not None:
                    # Fetch latest balance
                    balance, _ = await self.balance_fetcher.get_account_balance(self.account_index)
                    if balance:
                        self.latest_balance = balance
                        await self._broadcast_account_update()
                
            except Exception as e:
                logger.error(f"Error in periodic updates: {e}")
    
    def _process_order_update(self, exchange_order_id: str, order_data: Dict):
        """Process order update that may contain fill information."""
        try:
            # Find client order ID
            client_order_id = self.exchange_to_client_id.get(str(exchange_order_id))
            if not client_order_id:
                return
                
            order = self.orders.get(client_order_id)
            if not order:
                return
                
            # Check if order is filled or partially filled
            status = order_data.get("status", "").lower()
            filled_qty = Decimal(str(order_data.get("filled_quantity", order_data.get("filled", "0"))))
            
            if filled_qty > self._order_filled_quantities.get(client_order_id, Decimal("0")):
                # New fill detected, create a synthetic fill event
                fill_price = order_data.get("avg_fill_price", order_data.get("price", order.limit_price))
                
                # Generate a unique fill ID
                fill_id = f"{exchange_order_id}-{int(time.time() * 1000)}"
                
                # Calculate the new fill quantity
                prev_filled = self._order_filled_quantities.get(client_order_id, Decimal("0"))
                new_fill_qty = filled_qty - prev_filled
                
                if new_fill_qty > 0:
                    self.fill_order(
                        dir=order.dir,
                        exchange_fill_id=fill_id,
                        fill_id=None,
                        price=Decimal(str(fill_price)),
                        quantity=new_fill_qty,
                        symbol=order.symbol,
                        trade_time=datetime.now(),
                        account=order.account,
                        is_taker=True,  # Assume taker for now
                        fee=Decimal("0.001") * Decimal(str(fill_price)) * new_fill_qty,
                        fee_currency="USDC",
                        order_id=client_order_id,
                        trader=order.trader,
                    )
                    
                    # Update tracking
                    self._order_filled_quantities[client_order_id] = filled_qty
                    self._processed_fills.add(fill_id)
                    
                    logger.info(f"Order update fill: {client_order_id} filled {new_fill_qty}, total {filled_qty}")
                    
            # Check if order is fully filled or cancelled
            if status in ["filled", "complete", "done"]:
                if filled_qty >= order.quantity:
                    self.out_order(client_order_id, canceled=False)
                    logger.info(f"Order complete: {client_order_id}")
            elif status in ["cancelled", "canceled", "rejected"]:
                self.out_order(client_order_id, canceled=True)
                logger.info(f"Order cancelled: {client_order_id}")
                
        except Exception as e:
            logger.error(f"Error processing order update: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run the Lighter CPTY server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Lighter CPTY Server")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="Port to listen on (default: 50051)"
    )
    args = parser.parse_args()
    
    # Configure logging
    numeric_level = getattr(logging, args.log_level.upper())
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Force reconfiguration
    )
    
    # Disable propagation for specific noisy loggers
    logging.getLogger('architect_py').setLevel(numeric_level)
    logging.getLogger('websockets').setLevel(numeric_level)
    logging.getLogger('asyncio').setLevel(numeric_level)
    logging.getLogger('grpc').setLevel(numeric_level)
    
    # Set level for all existing loggers
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.setLevel(numeric_level)
    
    # Run the server
    cpty = LighterCpty()
    await cpty.serve(f"[::]:{args.port}")


if __name__ == "__main__":
    asyncio.run(main())