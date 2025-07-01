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
            self.ws_client.on_connected = self._on_ws_connected
            self.ws_client.on_disconnected = self._on_ws_disconnected
            self.ws_client.on_error = self._on_ws_error
            
            # Run WebSocket in background
            asyncio.create_task(self._run_websocket())
            print("[INFO] WebSocket client initialized")
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize WebSocket: {e}")
    
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
        if self.account_index is not None and self.ws_client:
            asyncio.create_task(self.ws_client.subscribe_account(self.account_index))
    
    def _on_ws_disconnected(self):
        """Handle WebSocket disconnection."""
        print("[WARNING] WebSocket disconnected")
        self.ws_connected = False
    
    def _on_ws_error(self, error: Exception):
        """Handle WebSocket errors."""
        print(f"[ERROR] WebSocket error: {error}")
    
    def _on_account_update(self, account_id: int, account: Dict):
        """Handle account updates from WebSocket."""
        try:
            print(f"[INFO] Account update for {account_id}")
            self.latest_account_data = account
            
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
            self.ack_order(order.id, exchange_order_id=tx_hash_str)
            print(f"[INFO] Order placed: {order.id} -> {tx_hash_str}")
            
            # Order is now on the exchange - status will be managed by Architect
            # based on exchange confirmations
            
            # Disabled simulated lifecycle - real orders will be managed by exchange
            # asyncio.create_task(self._simulate_order_lifecycle(order))
            
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
    
    async def get_open_orders(self) -> Sequence[Order]:
        """Get all open orders."""
        open_orders = []
        for order_id, order in self.orders.items():
            if order.status in [OrderStatus.Pending, OrderStatus.Open]:
                open_orders.append(order)
        return open_orders
    
    async def _simulate_order_lifecycle(self, order: Order):
        """Simulate order lifecycle for demo purposes."""
        # Wait a bit then fill the order
        await asyncio.sleep(2)
        
        # Fill the order
        now = datetime.now()
        fill_id = str(uuid.uuid4())
        exchange_fill_id = f"LIGHTER-{fill_id[:8]}"
        
        self.fill_order(
            dir=order.dir,
            exchange_fill_id=exchange_fill_id,
            fill_id=fill_id,
            price=order.limit_price,
            quantity=order.quantity,
            symbol=order.symbol,
            trade_time=now,
            account=order.account,
            is_taker=True,
            fee=Decimal("0.001") * order.limit_price * order.quantity,
            fee_currency="USDC",
            order_id=order.id,
            trader=order.trader,
        )
        
        # Out the order
        self.out_order(order.id, canceled=False)
        print(f"[INFO] Order filled and outed: {order.id}")
    
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
            
            # Remove from orders dict
            if order_id in self.orders:
                del self.orders[order_id]
            
            print(f"[INFO] Order cancelled: {order_id}")
            
        except Exception as e:
            print(f"[ERROR] Error finalizing cancel: {e}")
    
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


async def main():
    """Run the Lighter CPTY server."""
    logging.basicConfig(level=logging.INFO)
    
    cpty = LighterCpty()
    await cpty.serve("[::]:50051")


if __name__ == "__main__":
    asyncio.run(main())