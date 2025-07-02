"""WebSocket client for Lighter API using websockets library."""
import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any, Callable, Set
import websockets
from websockets.client import WebSocketClientProtocol


logger = logging.getLogger(__name__)


class LighterWebSocketClient:
    """WebSocket client for Lighter real-time data using websockets library."""
    
    def __init__(self, url: str, auth_token: Optional[str] = None):
        """Initialize WebSocket client.
        
        Args:
            url: WebSocket URL (e.g., wss://testnet.zklighter.elliot.ai/stream)
            auth_token: Optional authentication token
        """
        self.url = url
        self.auth_token = auth_token
        self.ws: Optional[WebSocketClientProtocol] = None
        self.running = False
        
        # Callbacks
        self.on_order_book: Optional[Callable[[int, Dict[str, Any]], None]] = None
        self.on_account: Optional[Callable[[int, Dict[str, Any]], None]] = None
        self.on_trade: Optional[Callable[[int, Dict[str, Any]], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        
        # Subscription tracking
        self.subscriptions: Set[str] = set()
        self.pending_subscriptions: asyncio.Queue = asyncio.Queue()
        
        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
    
    async def connect(self) -> None:
        """Connect to Lighter WebSocket."""
        try:
            logger.info(f"Connecting to Lighter WebSocket: {self.url}")
            
            # Prepare headers with auth if available
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            
            # Connect with headers if available
            if headers:
                self.ws = await websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    additional_headers=headers  # Use additional_headers instead
                )
            else:
                self.ws = await websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
            self.running = True
            self.reconnect_attempts = 0
            
            if self.on_connected:
                self.on_connected()
            
            # Start message handler
            await self._message_handler()
            
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            if self.on_error:
                self.on_error(e)
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self.on_error:
                self.on_error(e)
            await self._handle_reconnect()
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        if self.on_disconnected:
            self.on_disconnected()
    
    async def _message_handler(self) -> None:
        """Handle incoming messages and send pending subscriptions."""
        if not self.ws:
            return
        
        try:
            # Send any pending subscriptions
            asyncio.create_task(self._subscription_sender())
            
            # Listen for messages
            async for message in self.ws:
                if not self.running:
                    break
                
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            if self.on_error:
                self.on_error(e)
        finally:
            await self._handle_reconnect()
    
    async def _subscription_sender(self) -> None:
        """Send pending subscriptions."""
        while self.running and self.ws:
            try:
                # Get pending subscription with timeout
                try:
                    subscription = await asyncio.wait_for(
                        self.pending_subscriptions.get(), 
                        timeout=1.0
                    )
                    
                    if self.ws and self.ws.state.name == "OPEN":
                        await self.ws.send(json.dumps(subscription))
                        logger.debug(f"Sent subscription: {subscription}")
                        
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error sending subscription: {e}")
    
    async def _send_pong(self) -> None:
        """Send pong response to server ping."""
        if self.ws and self.ws.state.name == "OPEN":
            pong_msg = {"type": "pong"}
            await self.ws.send(json.dumps(pong_msg))
            logger.debug("Sent pong response")
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        msg_type = data.get("type")
        
        if msg_type == "connected":
            logger.info("Connected to Lighter WebSocket")
            # Re-subscribe to all channels after connection
            await self._resubscribe_all()
            
        elif msg_type == "subscribed":
            channel = data.get("channel", "")
            logger.info(f"Successfully subscribed to {channel}")
            
        elif msg_type == "error":
            error_msg = data.get("message", "Unknown error")
            logger.error(f"Received error from server: {error_msg}")
            if self.on_error:
                self.on_error(Exception(error_msg))
                
        elif msg_type in ["subscribed/order_book", "update/order_book"]:
            await self._handle_order_book_message(data)
            
        elif msg_type in ["subscribed/account_all", "update/account_all", 
                          "subscribed/account_market", "update/account_market"]:
            await self._handle_account_message(data)
            
        elif msg_type in ["subscribed/trade", "update/trade", "subscribed/trades", "update/trades"]:
            await self._handle_trade_message(data)
            
        elif msg_type == "ping":
            # Respond to ping with pong
            await self._send_pong()
            
        else:
            logger.debug(f"Unhandled message type: {msg_type}")
    
    async def _handle_order_book_message(self, data: Dict[str, Any]) -> None:
        """Handle order book messages."""
        channel = data.get("channel", "")
        
        # Extract market ID from channel (e.g., "order_book:0" or "order_book/0")
        parts = channel.replace(":", "/").split("/")
        if len(parts) >= 2:
            try:
                market_id = int(parts[1])
                order_book = data.get("order_book", data.get("data", {}))
                
                if self.on_order_book:
                    self.on_order_book(market_id, order_book)
                    
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse market ID from channel {channel}: {e}")
    
    async def _handle_account_message(self, data: Dict[str, Any]) -> None:
        """Handle account messages."""
        channel = data.get("channel", "")
        
        # Log the full message for debugging
        logger.debug(f"Account message: {data}")
        
        # Extract account ID from channel
        parts = channel.replace(":", "/").split("/")
        if len(parts) >= 2:
            try:
                account_id = int(parts[1])
                
                # The account data is the entire message
                # Pass the full data to preserve all fields including positions, trades, etc.
                if self.on_account:
                    self.on_account(account_id, data)
                    
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse account ID from channel {channel}: {e}")
    
    async def _handle_trade_message(self, data: Dict[str, Any]) -> None:
        """Handle trade messages."""
        channel = data.get("channel", "")
        
        # Log the full trade message for debugging
        logger.debug(f"Trade message on channel {channel}: {data}")
        
        # Extract ID from channel - could be market ID or account ID
        parts = channel.replace(":", "/").split("/")
        if len(parts) >= 2:
            try:
                # For account-specific trades (trades:30188), the ID is the account index
                # For market trades (trade:21), the ID is the market ID
                id_value = int(parts[1])
                
                # Check for trades in different fields
                trades = data.get("trades", data.get("trade", data.get("data", {})))
                
                if trades and self.on_trade:
                    # If trades is a list, process each trade
                    if isinstance(trades, list):
                        for trade in trades:
                            # For account trades, pass the account ID as the first param
                            self.on_trade(id_value, trade)
                    # If trades is a dict, process it directly
                    elif isinstance(trades, dict):
                        # For dict format, iterate over the trades
                        for trade_id, trade_data in trades.items():
                            self.on_trade(id_value, trade_data)
                    
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse ID from channel {channel}: {e}")
    
    async def subscribe_order_book(self, market_id: int) -> None:
        """Subscribe to order book updates."""
        channel = f"order_book/{market_id}"
        if channel not in self.subscriptions:
            subscription = {
                "type": "subscribe",
                "channel": channel
            }
            await self.pending_subscriptions.put(subscription)
            self.subscriptions.add(channel)
    
    async def subscribe_account(self, account_id: int, market_id: Optional[int] = None) -> None:
        """Subscribe to account updates."""
        if market_id is not None:
            channel = f"account_market/{account_id}/{market_id}"
        else:
            channel = f"account_all/{account_id}"
        
        if channel not in self.subscriptions:
            subscription = {
                "type": "subscribe",
                "channel": channel
            }
            
            # Add auth if needed for account subscriptions
            if self.auth_token:
                subscription["auth"] = self.auth_token
            
            await self.pending_subscriptions.put(subscription)
            self.subscriptions.add(channel)
    
    async def subscribe_trades(self, market_id: int) -> None:
        """Subscribe to trade updates."""
        channel = f"trade/{market_id}"
        if channel not in self.subscriptions:
            subscription = {
                "type": "subscribe",
                "channel": channel
            }
            await self.pending_subscriptions.put(subscription)
            self.subscriptions.add(channel)
    
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        if channel in self.subscriptions:
            unsubscription = {
                "type": "unsubscribe",
                "channel": channel
            }
            await self.pending_subscriptions.put(unsubscription)
            self.subscriptions.remove(channel)
    
    async def _resubscribe_all(self) -> None:
        """Re-subscribe to all channels after reconnection."""
        for channel in list(self.subscriptions):
            subscription = {
                "type": "subscribe",
                "channel": channel
            }
            
            # Add auth for account channels
            if channel.startswith("account_"):
                if self.auth_token:
                    subscription["auth"] = self.auth_token
            
            await self.pending_subscriptions.put(subscription)
    
    async def _handle_reconnect(self) -> None:
        """Handle reconnection logic."""
        if not self.running:
            return
        
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            await self.disconnect()
            return
        
        delay = min(
            self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
            self.max_reconnect_delay
        )
        
        logger.info(f"Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
        
        await self.connect()
    
    async def run(self) -> None:
        """Run the WebSocket client."""
        await self.connect()
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to the WebSocket server."""
        if self.ws and self.ws.state.name == "OPEN":
            await self.ws.send(json.dumps(message))
        else:
            logger.error("Cannot send message: WebSocket not connected")