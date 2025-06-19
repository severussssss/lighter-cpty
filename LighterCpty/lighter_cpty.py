"""Lighter CPTY implementation for Architect using lighter-python SDK."""
import asyncio
import logging
import time
import os
from typing import Iterator, Optional, Dict, Any, List
from decimal import Decimal
import grpc
from pathlib import Path
from dotenv import load_dotenv

# Lighter SDK imports
import lighter
from lighter import SignerClient, ApiClient, Configuration
from lighter.exceptions import ApiException

# Local imports
from .lighter_ws import LighterWebSocketClient

# Architect imports
from architect_py.grpc.server import CptyServicer, OrderflowServicer
from architect_py.grpc.models.Cpty import CptyRequest, CptyResponse
from architect_py.grpc.models.Oms import Order, Cancel
from architect_py.grpc.models.definitions import (
    OrderDir, OrderType, OrderStatus, CptyLoginRequest, CptyLogoutRequest
)
from architect_py.grpc.models.Orderflow import Orderflow, DropcopyRequest
from architect_py import TimeInForce

# Extract nested types from CptyRequest
Login = CptyRequest.Login if hasattr(CptyRequest, 'Login') else CptyLoginRequest
Logout = CptyRequest.Logout if hasattr(CptyRequest, 'Logout') else CptyLogoutRequest
PlaceOrder = CptyRequest.PlaceOrder
CancelOrder = CptyRequest.CancelOrder
Symbology = CptyRequest.Symbology
ReconcileOrder = CptyRequest.ReconcileOrder
ReconcileOpenOrders = CptyRequest.ReconcileOpenOrders
UpdateAccountSummary = CptyRequest.UpdateAccountSummary


logger = logging.getLogger(__name__)


class LighterCptyServicer(CptyServicer, OrderflowServicer):
    """CPTY servicer for Lighter integration using official SDK."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Lighter CPTY servicer.
        
        Args:
            config: Configuration dict with:
                - url: Base URL (mainnet/testnet)
                - private_key: API key private key
                - account_index: Account index
                - api_key_index: API key index (default 1)
        """
        self.config = config or self._load_config_from_env()
        
        # Initialize SDK clients
        self.signer_client: Optional[SignerClient] = None
        self.ws_client: Optional[LighterWebSocketClient] = None
        self.api_client: Optional[ApiClient] = None
        
        # Session management
        self.logged_in = False
        self.user_id: Optional[str] = None
        self.account_id: Optional[str] = None
        self.account_index: Optional[int] = None
        
        # Market information cache
        self.markets: Dict[int, Dict[str, Any]] = {}
        self.symbology_sent = False
        
        # Symbol mapping: Architect symbol -> Lighter market ID
        self.symbol_to_market_id: Dict[str, int] = {}
        # Reverse mapping: Lighter market ID -> Architect symbol
        self.market_id_to_symbol: Dict[int, str] = {}
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.client_to_exchange_id: Dict[str, str] = {}
        self.exchange_to_client_id: Dict[str, str] = {}
        
        # Response queue for async updates
        self.response_queue: asyncio.Queue = asyncio.Queue()
        
        # Event loop for async operations
        self.loop = asyncio.new_event_loop()
        self.async_thread = None
        
        # WebSocket state
        self.ws_connected = False
        self.subscribed_markets: set = set()
        self.subscribed_accounts: set = set()
    
    def _build_architect_symbol(self, base_asset: str, quote_asset: str) -> str:
        """Build Architect-style symbol.
        
        Format: BASE-QUOTE LIGHTER Perpetual/QUOTE Crypto
        Example: ETH-USDC LIGHTER Perpetual/USDC Crypto
        """
        return f"{base_asset}-{quote_asset} LIGHTER Perpetual/{quote_asset} Crypto"
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available Architect-style symbols."""
        return list(self.symbol_to_market_id.keys())
    
    def _parse_architect_symbol(self, symbol: str) -> tuple[str, str]:
        """Parse Architect symbol to extract base and quote assets.
        
        Args:
            symbol: Architect-style symbol like "ETH-USDC LIGHTER Perpetual/USDC Crypto"
            
        Returns:
            Tuple of (base_asset, quote_asset)
        """
        # Extract the base-quote pair from the beginning
        parts = symbol.split(' ')
        if parts and '-' in parts[0]:
            base, quote = parts[0].split('-')
            return base, quote
        return None, None
    
    def _load_config_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        # Try to load .env file from lighter-python/examples
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
    
    async def _init_clients(self) -> bool:
        """Initialize Lighter SDK clients."""
        try:
            # Initialize API client
            configuration = Configuration(host=self.config["url"])
            self.api_client = ApiClient(configuration=configuration)
            
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
            
            # Create auth token
            auth, err = self.signer_client.create_auth_token_with_expiry(
                SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
            )
            if err is not None:
                logger.error(f"Failed to create auth token: {err}")
                return False
            
            logger.info("Lighter SDK clients initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return False
    
    async def _init_websocket(self) -> None:
        """Initialize WebSocket client with callbacks."""
        try:
            # Get WebSocket URL
            ws_url = self.config["url"].replace("https://", "wss://") + "/stream"
            
            # Get auth token if available
            auth_token = None
            if self.signer_client:
                auth_token, err = self.signer_client.create_auth_token_with_expiry(
                    SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
                )
                if err:
                    logger.warning(f"Failed to create auth token for WebSocket: {err}")
            
            # Initialize custom WebSocket client
            self.ws_client = LighterWebSocketClient(ws_url, auth_token)
            
            # Set up callbacks
            self.ws_client.on_order_book = self._on_order_book_update
            self.ws_client.on_account = self._on_account_update
            self.ws_client.on_trade = self._on_trade_update
            self.ws_client.on_error = self._on_ws_error
            self.ws_client.on_connected = self._on_ws_connected
            self.ws_client.on_disconnected = self._on_ws_disconnected
            
            # Run WebSocket in background
            asyncio.create_task(self._run_websocket())
            self.ws_connected = True
            logger.info("WebSocket client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket: {e}")
    
    def _on_order_book_update(self, market_id: int, order_book: Dict[str, Any]) -> None:
        """Handle order book updates."""
        try:
            # Convert to Architect format and queue response
            logger.debug(f"Order book update for market {market_id}")
            # Could convert to orderflow events here
        except Exception as e:
            logger.error(f"Error processing order book: {e}")
    
    def _on_account_update(self, account_id: int, account: Dict[str, Any]) -> None:
        """Handle account updates."""
        try:
            # Convert account update to UpdateAccountSummary
            balances = {}
            if "balances" in account:
                for asset, balance in account["balances"].items():
                    balances[asset] = {
                        "free": float(balance.get("free", 0)),
                        "locked": float(balance.get("locked", 0)),
                        "total": float(balance.get("total", 0))
                    }
            
            positions = []
            if "positions" in account:
                for pos in account["positions"]:
                    positions.append({
                        "market_id": pos.get("market_id"),
                        "side": pos.get("side"),
                        "quantity": float(pos.get("quantity", 0)),
                        "entry_price": float(pos.get("entry_price", 0)),
                        "mark_price": float(pos.get("mark_price", 0)),
                        "pnl": float(pos.get("pnl", 0))
                    })
            
            summary = UpdateAccountSummary(
                a=str(account_id),
                b=balances,
                p=positions,
                t=int(time.time() * 1000)
            )
            
            self.loop.call_soon_threadsafe(
                self.response_queue.put_nowait,
                CptyResponse(summary)
            )
            
        except Exception as e:
            logger.error(f"Error processing account update: {e}")
    
    def _on_trade_update(self, market_id: int, trade: Dict[str, Any]) -> None:
        """Handle trade updates."""
        logger.debug(f"Trade update for market {market_id}: {trade}")
    
    def _on_ws_error(self, error: Exception) -> None:
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
    
    def _on_ws_connected(self) -> None:
        """Handle WebSocket connection."""
        logger.info("WebSocket connected to Lighter")
        # Subscribe to account updates if we have an account index
        if self.account_index is not None and self.ws_client:
            asyncio.create_task(self.ws_client.subscribe_account(self.account_index))
    
    def _on_ws_disconnected(self) -> None:
        """Handle WebSocket disconnection."""
        logger.warning("WebSocket disconnected from Lighter")
        self.ws_connected = False
    
    async def _run_websocket(self) -> None:
        """Run WebSocket client asynchronously."""
        try:
            # Run the custom WebSocket client
            await self.ws_client.run()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.ws_connected = False
    
    async def _login(self, request: Login) -> bool:
        """Login to Lighter API."""
        try:
            self.user_id = request.user_id
            self.account_id = request.account_id or request.user_id
            
            # Parse account index from account_id if provided
            if request.account_id and request.account_id.isdigit():
                self.account_index = int(request.account_id)
            else:
                self.account_index = self.config["account_index"]
            
            # Initialize clients
            if not await self._init_clients():
                return False
            
            # Initialize WebSocket
            await self._init_websocket()
            
            self.logged_in = True
            logger.info(f"Successfully logged in for user {self.user_id}, account index {self.account_index}")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def _logout(self) -> bool:
        """Logout from Lighter."""
        try:
            self.logged_in = False
            
            # Close clients
            if self.signer_client:
                await self.signer_client.close()
                self.signer_client = None
            
            if self.api_client:
                await self.api_client.close()
                self.api_client = None
            
            # WebSocket client doesn't have async close in SDK
            self.ws_client = None
            self.ws_connected = False
            
            logger.info("Successfully logged out")
            return True
            
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    async def _place_order(self, order: PlaceOrder) -> Optional[Dict[str, Any]]:
        """Place order on Lighter."""
        try:
            if not self.signer_client:
                logger.error("Signer client not initialized")
                return None
            
            # Parse market_id from Architect symbol
            if order.symbol in self.symbol_to_market_id:
                market_index = self.symbol_to_market_id[order.symbol]
            else:
                # Try to parse as numeric for backward compatibility
                try:
                    market_index = int(order.symbol)
                    logger.warning(f"Using numeric market ID {market_index}, should use Architect symbol format")
                except ValueError:
                    logger.error(f"Unknown symbol: {order.symbol}")
                    return None
            
            # Convert price and quantity to integers (Lighter uses integer representation)
            # Different markets have different decimal precision
            # FARTCOIN has 5 price decimals, so price is in units of 0.00001 USDC
            # ETH has 2 price decimals, so price is in units of 0.01 USDC
            
            # Market-specific decimal handling based on API data
            # HYPE: 2 size decimals, 4 price decimals
            # BERA: 1 size decimal, 5 price decimals
            # FARTCOIN: 1 size decimal, 5 price decimals
            
            if market_index == 24:  # HYPE
                price_int = int(float(order.price) * 10000)  # 4 decimals
                base_amount = int(float(order.qty) * 100)  # 2 decimals for size
            elif market_index == 20:  # BERA
                price_int = int(float(order.price) * 100000)  # 5 decimals
                base_amount = int(float(order.qty) * 10)  # 1 decimal for size
            elif market_index == 21:  # FARTCOIN
                price_int = int(float(order.price) * 100000)  # 5 decimals
                base_amount = int(float(order.qty) * 10)  # 1 decimal for size
            else:
                # Default for most markets (ETH, BTC, etc.)
                price_int = int(float(order.price) * 100)  # 2 decimals
                base_amount = int(float(order.qty) * 1e6)  # 6 decimals
            
            # Determine order type
            order_type = SignerClient.ORDER_TYPE_LIMIT
            if hasattr(order, 'type') and order.type and str(order.type).upper() == "MARKET":
                order_type = SignerClient.ORDER_TYPE_MARKET
            
            # Determine time in force
            time_in_force = SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
            if hasattr(order, 'tif') and str(order.tif).upper() == "IOC":
                time_in_force = SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
            elif hasattr(order, 'post_only') and order.post_only:
                time_in_force = SignerClient.ORDER_TIME_IN_FORCE_POST_ONLY
            
            # Determine if ask (sell) or bid (buy)
            is_ask = str(order.dir).upper() == "SELL"
            
            # Use client order ID as integer (hash it if needed)
            client_order_index = abs(hash(order.cl_ord_id)) % (10**8)
            
            # Place order
            tx, tx_hash, err = await self.signer_client.create_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                price=price_int,
                is_ask=is_ask,
                order_type=order_type,
                time_in_force=time_in_force,
                reduce_only=1 if order.reduce_only else 0,
                trigger_price=0  # Not used for regular orders
            )
            
            if err is not None:
                logger.error(f"Failed to place order: {err}")
                return None
            
            # Track order
            self.orders[order.cl_ord_id] = order
            # Extract tx_hash string from object if needed
            if hasattr(tx_hash, 'tx_hash'):
                tx_hash_str = str(tx_hash.tx_hash)
            else:
                tx_hash_str = str(tx_hash)
            self.client_to_exchange_id[order.cl_ord_id] = tx_hash_str
            self.exchange_to_client_id[tx_hash_str] = order.cl_ord_id
            
            logger.info(f"Order placed successfully: {order.cl_ord_id} -> {tx_hash_str}")
            
            return {
                "order_id": tx_hash_str,
                "client_order_id": order.cl_ord_id,
                "status": "NEW",
                "filled_quantity": "0"
            }
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None
    
    async def _cancel_order(self, cancel: CancelOrder) -> bool:
        """Cancel order on Lighter."""
        try:
            if not self.signer_client:
                logger.error("Signer client not initialized")
                return False
            
            cl_ord_id = cancel.cancel.cl_ord_id
            
            # Get original order
            original_order = self.orders.get(cl_ord_id)
            if not original_order:
                logger.error(f"Original order not found: {cl_ord_id}")
                return False
            
            # Parse market_id from symbol
            if original_order.symbol in self.symbol_to_market_id:
                market_index = self.symbol_to_market_id[original_order.symbol]
            else:
                try:
                    market_index = int(original_order.symbol)
                except ValueError:
                    logger.error(f"Unknown symbol: {original_order.symbol}")
                    return False
            
            # Get order index (same as used in create_order)
            order_index = abs(hash(cl_ord_id)) % (10**8)
            
            # Cancel order
            tx, tx_hash, err = await self.signer_client.cancel_order(
                market_index=market_index,
                order_index=order_index
            )
            
            if err is not None:
                logger.error(f"Failed to cancel order: {err}")
                return False
            
            logger.info(f"Order cancelled successfully: {cl_ord_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def _get_symbology(self) -> Symbology:
        """Get market symbology from Lighter."""
        try:
            if not self.api_client:
                logger.error("API client not initialized")
                return Symbology()
            
            # Use the root API to get exchange info
            api_instance = lighter.RootApi(self.api_client)
            
            try:
                # Get exchange info which includes markets
                response = await api_instance.info()
                
                execution_info = {}
                
                # Extract market info from response
                if hasattr(response, 'markets'):
                    for market_id, market in response.markets.items():
                        base_asset = getattr(market, 'base_asset', 'Unknown')
                        quote_asset = getattr(market, 'quote_asset', 'USDC')
                        
                        # Build Architect-style symbol
                        architect_symbol = self._build_architect_symbol(base_asset, quote_asset)
                        
                        # Store mappings
                        market_id_int = int(market_id)
                        self.symbol_to_market_id[architect_symbol] = market_id_int
                        self.market_id_to_symbol[market_id_int] = architect_symbol
                        
                        # Store in execution_info using Architect symbol as key
                        execution_info[architect_symbol] = {
                            "base_asset": base_asset,
                            "quote_asset": quote_asset,
                            "tick_size": 0.01,  # Default values
                            "step_size": 0.01,
                            "min_order_size": 0.01,
                            "max_order_size": 1000000.0,
                            "is_active": True
                        }
                        
                        # Cache market info
                        self.markets[market_id_int] = market
                
                # If no markets found, provide some defaults for testing
                if not execution_info:
                    logger.warning("No markets found, using defaults")
                    
                    # Default markets (actual Lighter mainnet markets)
                    default_markets = [
                        (0, "ETH", "USDC"),
                        (1, "BTC", "USDC"),
                        (2, "SOL", "USDC"),
                        (3, "DOGE", "USDC"),
                        (4, "1000PEPE", "USDC"),
                        (5, "WIF", "USDC"),
                        (6, "WLD", "USDC"),
                        (7, "XRP", "USDC"),
                        (8, "LINK", "USDC"),
                        (9, "AVAX", "USDC"),
                        (10, "NEAR", "USDC"),
                        (11, "DOT", "USDC"),
                        (12, "TON", "USDC"),
                        (13, "TAO", "USDC"),
                        (14, "POL", "USDC"),
                        (15, "TRUMP", "USDC"),
                        (16, "SUI", "USDC"),
                        (17, "1000SHIB", "USDC"),
                        (18, "1000BONK", "USDC"),
                        (19, "1000FLOKI", "USDC"),
                        (20, "BERA", "USDC"),      # BERA is market ID 20!
                        (21, "FARTCOIN", "USDC"),
                        (22, "AI16Z", "USDC"),
                        (23, "POPCAT", "USDC"),
                        (24, "HYPE", "USDC"),       # HYPE is market ID 24!
                        (25, "BNB", "USDC"),
                        (26, "JUP", "USDC"),
                        (27, "AAVE", "USDC"),
                        (28, "MKR", "USDC"),
                        (29, "ENA", "USDC"),
                        (30, "UNI", "USDC"),
                        (31, "APT", "USDC"),
                        (32, "SEI", "USDC"),
                        (33, "KAITO", "USDC"),
                        (34, "IP", "USDC"),
                        (35, "LTC", "USDC"),
                        (36, "CRV", "USDC"),
                        (37, "PENDLE", "USDC"),
                        (38, "ONDO", "USDC"),
                        (39, "ADA", "USDC"),
                        (40, "S", "USDC"),
                        (41, "VIRTUAL", "USDC"),
                        (42, "SPX", "USDC"),
                    ]
                    
                    for market_id, base, quote in default_markets:
                        architect_symbol = self._build_architect_symbol(base, quote)
                        self.symbol_to_market_id[architect_symbol] = market_id
                        self.market_id_to_symbol[market_id] = architect_symbol
                        
                        execution_info[architect_symbol] = {
                            "base_asset": base,
                            "quote_asset": quote,
                            "tick_size": 0.01,
                            "step_size": 0.01,
                            "min_order_size": 0.01 if base != "BTC" else 0.001,
                            "max_order_size": 1000000.0,
                            "is_active": True
                        }
                
                # Create symbology response
                symbology = Symbology()
                for market_id, info in execution_info.items():
                    symbology.x[market_id] = info
                return symbology
                
            except ApiException as e:
                logger.error(f"API exception getting symbology: {e}")
                return Symbology()
                
        except Exception as e:
            logger.error(f"Failed to get symbology: {e}")
            return Symbology(x={})
    
    async def _handle_request(self, request: CptyRequest) -> Optional[CptyResponse]:
        """Handle incoming CPTY request."""
        try:
            # Check which field is set in the request
            if hasattr(request, 'login') and request.login:
                success = await self._login(request.login)
                if success and not self.symbology_sent:
                    # Send symbology after successful login
                    symbology = await self._get_symbology()
                    self.symbology_sent = True
                    
                    # Log available symbols
                    logger.info(f"Available symbols: {len(self.symbol_to_market_id)}")
                    for symbol in self.get_available_symbols():
                        market_id = self.symbol_to_market_id[symbol]
                        logger.info(f"  {symbol} -> Market ID {market_id}")
                    
                    # For now, skip symbology response due to format issues
                    # return CptyResponse(symbology=symbology)
                    return None
                    
            elif hasattr(request, 'logout') and request.logout:
                await self._logout()
                
            elif hasattr(request, 'place_order') and request.place_order:
                if not self.logged_in:
                    logger.error("Not logged in")
                    return None
                    
                order_resp = await self._place_order(request.place_order)
                if order_resp:
                    # Convert to ReconcileOrder
                    recon = ReconcileOrder(
                        cl_ord_id=request.place_order.cl_ord_id,
                        ord_id=order_resp["order_id"],
                        symbol=request.place_order.symbol,
                        dir=request.place_order.dir,
                        price=request.place_order.price,
                        qty=request.place_order.qty,
                        filled_qty=float(order_resp["filled_quantity"]),
                        status=OrderStatus.Open,
                        type=request.place_order.type,
                        tif=request.place_order.tif
                    )
                    return CptyResponse(reconcile_order=recon)
                    
            elif hasattr(request, 'cancel_order') and request.cancel_order:
                if not self.logged_in:
                    logger.error("Not logged in")
                    return None
                    
                success = await self._cancel_order(request.cancel_order)
                if success:
                    # Send order update showing cancelled status
                    cancel_req = request.cancel_order
                    if cancel_req.cancel.cl_ord_id in self.orders:
                        orig_order = self.orders[cancel_req.cancel.cl_ord_id]
                        recon = ReconcileOrder(
                            cl_ord_id=cancel_req.cancel.cl_ord_id,
                            ord_id=self.client_to_exchange_id.get(cancel_req.cancel.cl_ord_id, ""),
                            symbol=orig_order.symbol,
                            dir=orig_order.dir,
                            price=orig_order.price,
                            qty=orig_order.qty,
                            filled_qty=0.0,
                            status=OrderStatus.Canceled,
                            type=orig_order.type,
                            tif=orig_order.tif
                        )
                        return CptyResponse(reconcile_order=recon)
                        
            elif hasattr(request, 'reconcile_open_orders') and request.reconcile_open_orders:
                if not self.logged_in:
                    logger.error("Not logged in")
                    return None
                    
                # Return all tracked orders that are not cancelled/filled
                open_orders = ReconcileOpenOrders(orders=[])
                for cl_ord_id, order in self.orders.items():
                    # In a real implementation, we'd check actual status
                    # For now, return all tracked orders
                    recon = ReconcileOrder(
                        cl_ord_id=cl_ord_id,
                        ord_id=self.client_to_exchange_id.get(cl_ord_id, ""),
                        symbol=order.symbol,
                        dir=order.dir,
                        price=order.price,
                        qty=order.qty,
                        filled_qty=0.0,  # Would need to track this
                        status=OrderStatus.Open,  # Would need to track actual status
                        type=order.type,
                        tif=order.tif
                    )
                    open_orders.orders.append(recon)
                    
                return CptyResponse(reconcile_open_orders=open_orders)
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            
        return None
    
    def Cpty(self, request_iterator: Iterator[CptyRequest], context) -> Iterator[CptyResponse]:
        """Main CPTY bidirectional streaming method."""
        # Start async event loop in thread
        import threading
        
        def run_async_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.async_thread = threading.Thread(target=run_async_loop, daemon=True)
        self.async_thread.start()
        
        try:
            # Process requests
            for request in request_iterator:
                logger.info(f"Received request: {type(request).__name__}")
                
                # Handle request asynchronously
                future = asyncio.run_coroutine_threadsafe(
                    self._handle_request(request),
                    self.loop
                )
                
                # Get response (with timeout)
                try:
                    response = future.result(timeout=5.0)
                    if response:
                        yield response
                except asyncio.TimeoutError:
                    logger.error("Request handling timed out")
                
                # Check for async updates
                while not self.response_queue.empty():
                    try:
                        update = self.response_queue.get_nowait()
                        yield update
                    except asyncio.QueueEmpty:
                        break
                        
        except Exception as e:
            logger.error(f"CPTY error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
        finally:
            # Cleanup
            self.loop.call_soon_threadsafe(self.loop.stop)
            if self.async_thread:
                self.async_thread.join(timeout=5.0)
    
    def SubscribeOrderflow(self, request: DropcopyRequest, context) -> Iterator[Orderflow]:
        """Subscribe to orderflow updates."""
        # This would stream orderflow events
        # For now, just yield from response queue
        while True:
            try:
                if not self.response_queue.empty():
                    update = self.response_queue.get_nowait()
                    # Convert CptyResponse to Orderflow if needed
                    yield update
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Orderflow subscription error: {e}")
                break