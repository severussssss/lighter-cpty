#!/usr/bin/env python3
"""Standalone script to measure Lighter WebSocket throughput."""
import asyncio
import json
import logging
import time
import aiohttp
import websockets
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_markets(api_url: str) -> Dict[int, Dict[str, Any]]:
    """Fetch market information from Lighter API."""
    markets = {}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{api_url}/info") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'markets' in data:
                        for market_id_str, info in data['markets'].items():
                            try:
                                market_id = int(market_id_str)
                                markets[market_id] = info
                            except ValueError:
                                pass
                    
                    logger.info(f"Loaded {len(markets)} markets from API")
        except Exception as e:
            logger.error(f"Error fetching market info: {e}")
    
    return markets


class ThroughputMonitor:
    """Monitor message throughput for each market."""
    
    def __init__(self):
        self.message_counts = defaultdict(int)
        self.last_reset = time.time()
        self.market_info = {}
        self.start_time = time.time()
        self.total_messages = defaultdict(int)
        self.last_message_time = defaultdict(float)
        self.message_sizes = defaultdict(list)
        
    def record_message(self, market_id: int, message_size: int = 0):
        """Record a message for a market."""
        self.message_counts[market_id] += 1
        self.total_messages[market_id] += 1
        self.last_message_time[market_id] = time.time()
        if message_size > 0:
            self.message_sizes[market_id].append(message_size)
        
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
            
            # Average message size
            sizes = self.message_sizes.get(market_id, [])
            avg_size = sum(sizes) / len(sizes) if sizes else 0
            
            stats.append({
                'market_id': market_id,
                'symbol': f"{base}/{quote}",
                'msg_count': count,
                'msg_per_sec': msg_per_sec,
                'total_messages': self.total_messages[market_id],
                'time_since_last': time_since_last,
                'avg_msg_size': avg_size
            })
            
        return stats, elapsed
        
    def reset(self):
        """Reset counters for next interval."""
        self.message_counts.clear()
        self.message_sizes.clear()
        self.last_reset = time.time()


async def monitor_websocket(ws_url: str, markets: Dict[int, Any], duration_minutes: int):
    """Monitor WebSocket messages."""
    monitor = ThroughputMonitor()
    monitor.market_info = markets
    
    # Select markets to monitor
    active_markets = [(mid, info) for mid, info in markets.items() if info.get('is_active', False)]
    target_symbols = ["BTC", "ETH", "SOL", "HYPE", "BERA", "SONIC", "FARTCOIN", "AI16Z", "GRIFFAIN", "WDEGEN"]
    
    subscribe_markets = []
    for market_id, info in active_markets:
        base = info.get('base_asset', '').upper()
        if base in target_symbols or len(subscribe_markets) < 15:
            subscribe_markets.append(market_id)
    
    logger.info(f"Monitoring {len(subscribe_markets)} markets")
    
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        logger.info("Connected to WebSocket")
        
        # Subscribe to markets
        for market_id in subscribe_markets:
            subscription = {
                "type": "subscribe",
                "channel": f"order_book/{market_id}"
            }
            await ws.send(json.dumps(subscription))
            await asyncio.sleep(0.05)
        
        logger.info("Subscribed to all markets")
        
        # Monitor messages
        end_time = time.time() + (duration_minutes * 60)
        report_interval = 10
        last_report = time.time()
        
        async def receive_messages():
            async for message in ws:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type', '')
                    
                    if msg_type in ['update/order_book', 'subscribed/order_book']:
                        channel = data.get('channel', '')
                        if '/' in channel:
                            market_id = int(channel.split('/')[-1])
                            monitor.record_message(market_id, len(message))
                            
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        # Start receiving messages
        receive_task = asyncio.create_task(receive_messages())
        
        # Reporting loop
        while time.time() < end_time:
            current_time = time.time()
            
            if current_time - last_report >= report_interval:
                stats, elapsed = monitor.get_stats()
                
                print(f"\n{'='*90}")
                print(f"Throughput Report - {datetime.now().strftime('%H:%M:%S')} - Period: {elapsed:.1f}s")
                print(f"{'='*90}")
                print(f"{'Symbol':>15} {'Msg/s':>8} {'Total':>8} {'Avg Size':>10} {'Last Msg':>12}")
                print(f"{'-'*15} {'-'*8} {'-'*8} {'-'*10} {'-'*12}")
                
                total_msg_per_sec = 0
                for stat in sorted(stats, key=lambda x: x['msg_per_sec'], reverse=True):
                    symbol = stat['symbol'][:15]
                    msg_per_sec = stat['msg_per_sec']
                    total_msg_per_sec += msg_per_sec
                    
                    time_since = stat['time_since_last']
                    if time_since < 60:
                        last_msg = f"{time_since:.1f}s ago"
                    else:
                        last_msg = ">1 min ago"
                    
                    avg_size = stat['avg_msg_size']
                    size_str = f"{avg_size:.0f}B" if avg_size > 0 else "N/A"
                    
                    print(f"{symbol:>15} {msg_per_sec:>8.2f} {stat['total_messages']:>8} {size_str:>10} {last_msg:>12}")
                
                print(f"{'-'*15} {'-'*8} {'-'*8} {'-'*10} {'-'*12}")
                print(f"{'TOTAL':>15} {total_msg_per_sec:>8.2f}")
                
                monitor.reset()
                last_report = current_time
            
            await asyncio.sleep(1)
        
        # Cancel receive task
        receive_task.cancel()
        
        # Final summary
        runtime = time.time() - monitor.start_time
        print(f"\n{'='*90}")
        print(f"Final Summary - Total Runtime: {runtime/60:.1f} minutes")
        print(f"{'='*90}")
        
        for market_id, total in sorted(monitor.total_messages.items(), key=lambda x: x[1], reverse=True)[:10]:
            info = markets.get(market_id, {})
            symbol = f"{info.get('base_asset', f'MKT_{market_id}')}/{info.get('quote_asset', 'USDC')}"
            avg_msg_per_sec = total / runtime
            print(f"{symbol:>15}: {total:>6} messages ({avg_msg_per_sec:>6.2f} msg/s avg)")


async def main():
    """Main function."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    api_url = "https://mainnet.zklighter.elliot.ai"
    duration = 2  # minutes
    
    logger.info("Fetching market info...")
    markets = await fetch_markets(api_url)
    
    if not markets:
        logger.error("No markets found")
        return
    
    logger.info(f"Starting {duration} minute throughput test...")
    await monitor_websocket(ws_url, markets, duration)


if __name__ == "__main__":
    asyncio.run(main())