#!/usr/bin/env python3
"""Measure WebSocket message throughput for Lighter markets."""
import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LighterCpty.lighter_ws import LighterWebSocketClient
from LighterCpty.market_info import fetch_market_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class ThroughputMonitor:
    """Monitor message throughput for each market."""
    
    def __init__(self):
        self.message_counts = defaultdict(int)
        self.last_reset = time.time()
        self.market_info = {}
        self.start_time = time.time()
        self.total_messages = defaultdict(int)
        self.last_message_time = defaultdict(float)
        
    def record_message(self, market_id: int):
        """Record a message for a market."""
        self.message_counts[market_id] += 1
        self.total_messages[market_id] += 1
        self.last_message_time[market_id] = time.time()
        
    def get_stats(self):
        """Get current throughput statistics."""
        current_time = time.time()
        elapsed = current_time - self.last_reset
        
        stats = []
        for market_id, count in sorted(self.message_counts.items()):
            info = self.market_info.get(market_id, {})
            base = info.get('base_asset', f'MARKET_{market_id}')
            quote = info.get('quote_asset', 'USDC')
            
            # Calculate messages per second
            msg_per_sec = count / elapsed if elapsed > 0 else 0
            
            # Time since last message
            time_since_last = current_time - self.last_message_time.get(market_id, 0)
            
            stats.append({
                'market_id': market_id,
                'symbol': f"{base}/{quote}",
                'msg_count': count,
                'msg_per_sec': msg_per_sec,
                'total_messages': self.total_messages[market_id],
                'time_since_last': time_since_last
            })
            
        return stats, elapsed
        
    def reset(self):
        """Reset counters for next interval."""
        self.message_counts.clear()
        self.last_reset = time.time()


async def monitor_throughput(duration_minutes: int = 5):
    """Monitor WebSocket throughput for specified duration."""
    # Configuration
    ws_url = os.getenv("LIGHTER_WS_URL", "wss://mainnet.zklighter.elliot.ai/stream")
    api_url = os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    
    logger.info(f"Starting throughput monitor for {duration_minutes} minutes...")
    logger.info(f"WebSocket URL: {ws_url}")
    
    # Fetch market info
    logger.info("Fetching market information...")
    market_info = await fetch_market_info(api_url)
    
    if not market_info:
        logger.error("Failed to fetch market information")
        return
    
    # Find active markets
    active_markets = [
        (market_id, info) 
        for market_id, info in market_info.items() 
        if info.get('is_active', False)
    ]
    
    logger.info(f"Found {len(active_markets)} active markets")
    
    # Target popular markets for testing
    target_symbols = ["BTC", "ETH", "SOL", "HYPE", "BERA", "SONIC", "FARTCOIN", "AI16Z", "GRIFFAIN"]
    subscribe_markets = []
    
    for market_id, info in active_markets:
        base = info.get('base_asset', '').upper()
        if base in target_symbols or len(subscribe_markets) < 10:  # Subscribe to up to 10 markets
            subscribe_markets.append((market_id, info))
            
    logger.info(f"Will monitor {len(subscribe_markets)} markets:")
    for market_id, info in subscribe_markets:
        logger.info(f"  - {info.get('base_asset')}/{info.get('quote_asset')} (ID: {market_id})")
    
    # Create WebSocket client
    monitor = ThroughputMonitor()
    monitor.market_info = market_info
    
    client = LighterWebSocketClient(ws_url)
    
    # Set up orderbook callback
    def on_order_book(market_id: int, order_book: dict):
        monitor.record_message(market_id)
    
    client.on_order_book = on_order_book
    client.on_connected = lambda: logger.info("Connected to Lighter WebSocket")
    client.on_disconnected = lambda: logger.info("Disconnected from Lighter WebSocket")
    client.on_error = lambda e: logger.error(f"WebSocket error: {e}")
    
    # Connect and subscribe
    try:
        # Start the client
        asyncio.create_task(client.run())
        
        # Wait for connection
        await asyncio.sleep(2)
        
        # Subscribe to markets
        for market_id, _ in subscribe_markets:
            await client.subscribe_order_book(market_id)
            await asyncio.sleep(0.1)  # Small delay between subscriptions
        
        logger.info("Subscribed to all markets. Monitoring...")
        
        # Monitor for specified duration
        end_time = time.time() + (duration_minutes * 60)
        report_interval = 10  # Report every 10 seconds
        last_report = time.time()
        
        while time.time() < end_time:
            current_time = time.time()
            
            # Report stats periodically
            if current_time - last_report >= report_interval:
                stats, elapsed = monitor.get_stats()
                
                print(f"\n{'='*80}")
                print(f"Throughput Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Measurement Period: {elapsed:.1f} seconds")
                print(f"{'='*80}")
                print(f"{'Symbol':>15} {'Msg/s':>10} {'Total':>10} {'Last Msg':>12}")
                print(f"{'-'*15} {'-'*10} {'-'*10} {'-'*12}")
                
                total_msg_per_sec = 0
                for stat in sorted(stats, key=lambda x: x['msg_per_sec'], reverse=True):
                    symbol = stat['symbol']
                    msg_per_sec = stat['msg_per_sec']
                    total_msg_per_sec += msg_per_sec
                    
                    time_since = stat['time_since_last']
                    if time_since < 60:
                        last_msg = f"{time_since:.1f}s ago"
                    else:
                        last_msg = ">1 min ago"
                    
                    print(f"{symbol:>15} {msg_per_sec:>10.2f} {stat['total_messages']:>10} {last_msg:>12}")
                
                print(f"{'-'*15} {'-'*10} {'-'*10} {'-'*12}")
                print(f"{'TOTAL':>15} {total_msg_per_sec:>10.2f}")
                
                # Reset counters for next interval
                monitor.reset()
                last_report = current_time
            
            await asyncio.sleep(1)
        
        # Final report
        runtime = time.time() - monitor.start_time
        print(f"\n{'='*80}")
        print(f"Final Summary - Total Runtime: {runtime/60:.1f} minutes")
        print(f"{'='*80}")
        
        for market_id, total in sorted(monitor.total_messages.items(), key=lambda x: x[1], reverse=True):
            info = market_info.get(market_id, {})
            symbol = f"{info.get('base_asset', f'MARKET_{market_id}')}/{info.get('quote_asset', 'USDC')}"
            avg_msg_per_sec = total / runtime
            print(f"{symbol:>15}: {total:>8} messages ({avg_msg_per_sec:.2f} msg/s average)")
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Parse command line arguments
    duration = 5  # Default 5 minutes
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [duration_in_minutes]")
            sys.exit(1)
    
    asyncio.run(monitor_throughput(duration))