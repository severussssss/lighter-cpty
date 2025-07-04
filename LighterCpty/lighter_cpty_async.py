"""Lighter CPTY implementation using architect-py's AsyncCpty base class."""
import asyncio
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

# Add architect-py to path
sys.path.insert(0, str(Path(__file__).parent.parent / "architect-py"))

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

# Lighter SDK imports
import lighter
from lighter import SignerClient, ApiClient, Configuration
from lighter.exceptions import ApiException

# Local imports
from .lighter_ws import LighterWebSocketClient
from .balance_fetcher import LighterBalanceFetcher

# logger = logging.getLogger(__name__)


class LighterCpty(AsyncCpty):
    """Lighter CPTY implementation using AsyncCpty base class."""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize Lighter CPTY."""
        super().__init__("LIGHTER")
        print("[INFO] LighterCpty initialized")
        
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
    
    def _load_config_from_env(self) -> Dict:
        """Load configuration from environment variables."""
        env_path = Path(__file__).parent.parent.parent.parent.parent.parent / "lighter-python" / "examples" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Loaded .env from {env_path}")
        
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
            
            # Initialize the venue dict if needed
            if self.execution_venue not in self.execution_info:
                self.execution_info[self.execution_venue] = {}
            
            self.execution_info[self.execution_venue][architect_symbol] = exec_info
    
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
                print(f"[ERROR] Signer client check failed: {err}")
                return False
            
            print("[INFO] Lighter SDK clients initialized successfully")
            
            # Initialize WebSocket
            await self._init_websocket()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize clients: {e}")
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
            self.ws_client.on_trade = self._on_trade_update
            self.ws_client.on_connected = self._on_ws_connected
            self.ws_client.on_disconnected = self._on_ws_disconnected
            self.ws_client.on_error = self._on_ws_error
            
            # Run WebSocket in background
            asyncio.create_task(self._run_websocket())
            
            # Subscribe to account updates after a short delay
            asyncio.create_task(self._initial_subscriptions())
            
            print("[INFO] WebSocket client initialized")
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize WebSocket: {e}")
    
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
                print(f"[INFO] Subscribed to account_all/{self.account_index}")
                
        except Exception as e:
            print(f"[ERROR] Failed to set up subscriptions: {e}")
    
    async def _run_websocket(self):
        """Run WebSocket client."""
        try:
            await self.ws_client.run()
        except Exception as e:
            print(f"[ERROR] WebSocket error: {e}")
            self.ws_connected = False
    
    def _on_ws_connected(self):
        """Handle WebSocket connection."""
        print("[INFO] WebSocket connected")
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
            print(f"[INFO] Subscribed to account_market for market {market_id}")
    
    def _on_ws_disconnected(self):
        """Handle WebSocket disconnection."""
        print("[WARNING] WebSocket disconnected")
        self.ws_connected = False
    
    def _on_ws_error(self, error: Exception):
        """Handle WebSocket errors."""
        print(f"[ERROR] WebSocket error: {error}")
    
    def _on_trade_update(self, market_id: int, trade: Dict):
        """Handle trade updates from WebSocket."""
        try:
            print(f"[INFO] Trade update for market {market_id}: {trade}")
            
            # Process the trade as a fill
            self._process_single_fill(trade)
            
        except Exception as e:
            print(f"[ERROR] Error processing trade update: {e}")
    
    def _on_account_update(self, account_id: int, account: Dict):
        """Handle account updates from WebSocket."""
        try:
            print(f"[INFO] Account update for {account_id}")
            self.latest_account_data = account
            
            # Log trades field for debugging
            trades = account.get("trades", {})
            if trades:
                print(f"[INFO] Trades in account update: {trades}")
            else:
                print(f"[DEBUG] Empty trades field in account update")
            
            # Check if trade counts changed
            new_total_trades = account.get("total_trades_count", 0)
            new_daily_trades = account.get("daily_trades_count", 0)
            
            # Store previous counts to detect changes
            if not hasattr(self, '_last_trade_counts'):
                self._last_trade_counts = {'total': 0, 'daily': 0}
            
            if new_total_trades > self._last_trade_counts['total']:
                print(f"[INFO] New trades detected! Total: {self._last_trade_counts['total']} -> {new_total_trades}")
                # Fetch recent trades via API
                asyncio.create_task(self._fetch_and_process_recent_trades())
            
            self._last_trade_counts['total'] = new_total_trades
            self._last_trade_counts['daily'] = new_daily_trades
            
            # Log any trade-related fields
            for key in account:
                if "trade" in key.lower() or "fill" in key.lower():
                    print(f"[DEBUG] {key}: {account[key]}")
            
            # Extract balance
            balance = LighterBalanceFetcher.parse_ws_account_update(account)
            if balance is not None:
                self.latest_balance = balance
                print(f"[INFO] Updated balance: {balance}")
            else:
                # Try to calculate equity
                equity = LighterBalanceFetcher.calculate_account_equity(account)
                if equity is not None:
                    self.latest_balance = equity
                    print(f"[INFO] Calculated equity: {equity}")
            
            # Process any order fills in the account data
            self._process_order_fills(account)
            
            # Broadcast update using AsyncCpty method
            asyncio.create_task(self._broadcast_account_update())
            
        except Exception as e:
            print(f"[ERROR] Error processing account update: {e}")
    
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
    
    async def on_login(self, request: CptyLoginRequest):
        """Handle login request."""
        print(f"[INFO] ========== LOGIN REQUEST RECEIVED ==========")
        print(f"[INFO] Login request from trader={request.trader}, account={request.account}")
        
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
        print(f"[INFO] Login successful for user {self.user_id}")
        
        # Start periodic updates
        asyncio.create_task(self._periodic_account_updates())
    
    async def on_logout(self, request: CptyLogoutRequest):
        """Handle logout request."""
        print("[INFO] Logout request received")
        self.logged_in = False
        self.user_id = None
        self.account_id = None
    
    async def on_place_order(self, order: Order):
        """Handle place order request."""
        print(f"[INFO] Place order: {order}")
        
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
                print(f"[ERROR] Failed to place order: {err}")
                self.reject_order(
                    order.id,
                    reject_reason=OrderRejectReason.ExchangeReject,
                    reject_message=str(err)
                )
                return
            
            # Track order
            tx_hash_str = str(tx_hash.tx_hash) if hasattr(tx_hash, 'tx_hash') else str(tx_hash)
            self.orders[order.id] = order
            self.client_to_exchange_id[order.id] = tx_hash_str
            self.exchange_to_client_id[tx_hash_str] = order.id
            
            # Acknowledge order
            print(f"[INFO] About to acknowledge order: {order.id}")
            self.ack_order(order.id, exchange_order_id=tx_hash_str)
            print(f"[INFO] Order acknowledged: {order.id} -> {tx_hash_str}")
            print(f"[INFO] Order placed: {order.id} -> {tx_hash_str}")
            
            # Order is now on the exchange - fills will come through WebSocket
            
        except Exception as e:
            print(f"[ERROR] Error placing order: {e}")
            self.reject_order(
                order.id,
                reject_reason=OrderRejectReason.InvalidOrder,
                reject_message=str(e)
            )
    
    async def on_cancel_order(self, cancel: Cancel, original_order: Optional[Order] = None):
        """Handle cancel order request."""
        print(f"[INFO] Cancel order: {cancel.xid}")  # xid is the cancel_id field
        
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
                print(f"[ERROR] Failed to cancel order: {err}")
                self.reject_cancel(
                    cancel.xid,
                    reject_reason="Exchange cancel failed",
                    reject_message=str(err)
                )
                return
            
            # Cancel accepted - no explicit ack_cancel method in AsyncCpty
            print(f"[INFO] Order cancel sent: {original_order.id} -> {cancel_hash}")
            
            # After some delay, mark as cancelled (in real implementation, wait for exchange confirmation)
            asyncio.create_task(self._finalize_cancel(original_order.id, cancel.xid))
            
        except Exception as e:
            print(f"[ERROR] Error cancelling order: {e}")
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
        print(f"[INFO] ========== CANCEL ALL ORDERS REQUEST ==========")
        print(f"[INFO] Account: {account}, Venue: {execution_venue}, Trader: {trader}")
        
        if not self.logged_in or not self.signer_client:
            print(f"[ERROR] Cannot cancel all - not logged in or client not initialized")
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
                print(f"[ERROR] Failed to cancel all orders: {err}")
                return
            
            print(f"[INFO] Cancel all orders sent successfully")
            
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
            
            print(f"[INFO] Marking {len(orders_to_cancel)} orders as cancelled")
            
            # Mark all matching orders as cancelled
            for order_id in orders_to_cancel:
                # Create a unique cancel ID for tracking
                cancel_id = f"cancel_all_{int(time.time() * 1000)}_{order_id}"
                asyncio.create_task(self._finalize_cancel(order_id, cancel_id))
                
            print(f"[INFO] Cancel all orders completed")
            
        except Exception as e:
            print(f"[ERROR] Error in cancel all orders: {e}")
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
            print(f"[DEBUG] _process_order_fills called")
            if "trades" in account_data or "recent_trades" in account_data or "orders" in account_data:
                print(f"[DEBUG] Account data keys: {list(account_data.keys())}")
            
            # Check trade counts
            total_trades = account_data.get("total_trades_count", 0)
            daily_trades = account_data.get("daily_trades_count", 0)
            if total_trades > 0 or daily_trades > 0:
                print(f"[DEBUG] Trade counts - total: {total_trades}, daily: {daily_trades}")
            
            # Check for trades/fills in the account data
            trades = account_data.get("trades", {})
            if trades and isinstance(trades, dict):
                print(f"[INFO] Found trades for {len(trades)} markets in account update")
                # Trades come as a dict with market IDs as keys, values are lists of trades
                for market_id, market_trades in trades.items():
                    print(f"[INFO] Processing {len(market_trades) if isinstance(market_trades, list) else 1} trades for market {market_id}")
                    if isinstance(market_trades, list):
                        for trade_data in market_trades:
                            if isinstance(trade_data, dict):
                                self._process_single_fill(trade_data)
                            else:
                                print(f"[WARNING] Unexpected trade data format: {type(trade_data)}")
                    elif isinstance(market_trades, dict):
                        self._process_single_fill(market_trades)
                    else:
                        print(f"[WARNING] Unexpected market trades format: {type(market_trades)}")
                    
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
            print(f"[ERROR] Error processing order fills: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_single_fill(self, trade_data: Dict):
        """Process a single fill/trade from WebSocket data."""
        try:
            # Extract trade information from Lighter format
            trade_id = str(trade_data.get("trade_id", ""))
            
            if not trade_id:
                print(f"[WARNING] No trade_id in trade data: {trade_data}")
                return
                
            # Check if we've already processed this fill
            if trade_id in self._processed_fills:
                return
                
            print(f"[INFO] Processing new trade {trade_id}")
            
            # Determine which order was ours based on account ID
            is_our_ask = trade_data.get("ask_account_id") == self.account_index
            is_our_bid = trade_data.get("bid_account_id") == self.account_index
            
            if not (is_our_ask or is_our_bid):
                print(f"[WARNING] Trade {trade_id} doesn't involve our account")
                return
            
            # Get the order ID (it's the ask_id or bid_id depending on our side)
            lighter_order_id = trade_data.get("ask_id") if is_our_ask else trade_data.get("bid_id")
            
            # Find the client order ID using tx_hash
            tx_hash = trade_data.get("tx_hash")
            client_order_id = None
            
            if tx_hash:
                client_order_id = self.exchange_to_client_id.get(tx_hash)
                if client_order_id:
                    print(f"[INFO] Matched trade {trade_id} to order {client_order_id} via tx_hash")
                else:
                    print(f"[WARNING] tx_hash {tx_hash} not found in exchange_to_client_id mapping")
                    # Fall back to old matching logic
                    for client_id, order in self.orders.items():
                        expected_index = abs(hash(client_id)) % (10**8)
                        if str(expected_index) in str(lighter_order_id):
                            client_order_id = client_id
                            print(f"[INFO] Matched trade {trade_id} to order {client_order_id} via index matching")
                            break
            else:
                print(f"[WARNING] No tx_hash in trade data")
                
            if not client_order_id:
                print(f"[WARNING] Could not match trade {trade_id} to any known order")
                return
                
            order = self.orders.get(client_order_id)
            if not order:
                print(f"[WARNING] Order {client_order_id} not found in orders dict")
                return
                
            print(f"[INFO] Matched trade {trade_id} to order {client_order_id}")
            
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
            print(f"[INFO] Processed fill: {trade_id} for order {client_order_id}, qty={quantity}, total_filled={self._order_filled_quantities[client_order_id]}")
            
            # Check if order is fully filled
            filled_qty = self._calculate_filled_quantity(client_order_id)
            if filled_qty >= order.quantity:
                self.out_order(client_order_id, canceled=False)
                print(f"[INFO] Order fully filled: {client_order_id}")
                
        except Exception as e:
            print(f"[ERROR] Error processing single fill: {e}")
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
            
            print(f"[INFO] Order cancelled: {order_id}")
            
        except Exception as e:
            print(f"[ERROR] Error finalizing cancel: {e}")
    
    async def _fetch_and_process_recent_trades(self):
        """Fetch recent trades from API when trade count changes."""
        try:
            if not self.api_client or not self.signer_client:
                return
                
            print("[INFO] Fetching recent trades from API...")
            
            # For now, just log that we need to implement this
            # In a real implementation, we would:
            # 1. Call the Lighter API to get recent trades
            # 2. Match them to our orders
            # 3. Report fills via fill_order()
            
            print("[INFO] TODO: Implement trade fetching from Lighter API")
            
            # As a workaround, check if any orders are no longer open
            # This indicates they were filled
            for order_id, order in list(self.orders.items()):
                if order.status == OrderStatus.Pending:
                    # Check if this order still exists
                    # If not, it was likely filled
                    print(f"[INFO] Checking status of order {order_id}")
                    
        except Exception as e:
            print(f"[ERROR] Error fetching recent trades: {e}")
            import traceback
            traceback.print_exc()
    
    async def _periodic_account_updates(self):
        """Send periodic account updates."""
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
                print(f"[ERROR] Error in periodic updates: {e}")
    
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
                    
                    print(f"[INFO] Order update fill: {client_order_id} filled {new_fill_qty}, total {filled_qty}")
                    
            # Check if order is fully filled or cancelled
            if status in ["filled", "complete", "done"]:
                if filled_qty >= order.quantity:
                    self.out_order(client_order_id, canceled=False)
                    print(f"[INFO] Order complete: {client_order_id}")
            elif status in ["cancelled", "canceled", "rejected"]:
                self.out_order(client_order_id, canceled=True)
                print(f"[INFO] Order cancelled: {client_order_id}")
                
        except Exception as e:
            print(f"[ERROR] Error processing order update: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run the Lighter CPTY server."""
    logging.basicConfig(level=logging.INFO)
    
    cpty = LighterCpty()
    await cpty.serve("[::]:50051")


if __name__ == "__main__":
    asyncio.run(main())