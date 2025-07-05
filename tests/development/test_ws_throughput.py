#!/usr/bin/env python3
"""Simple WebSocket throughput test with known markets."""
import asyncio
import json
import time
import websockets
from collections import defaultdict
from datetime import datetime

# Known markets from LighterCpty
KNOWN_MARKETS = {
    0: "BTC/USDC",
    1: "ETH/USDC",
    20: "BERA/USDC",
    21: "FARTCOIN/USDC",
    24: "HYPE/USDC",
}


class ThroughputMonitor:
    def __init__(self):
        self.message_counts = defaultdict(int)
        self.total_messages = defaultdict(int)
        self.start_time = time.time()
        self.last_reset = time.time()
        
    def record_message(self, market_id: int):
        self.message_counts[market_id] += 1
        self.total_messages[market_id] += 1
        
    def get_stats(self):
        elapsed = time.time() - self.last_reset
        stats = []
        
        for market_id, count in self.message_counts.items():
            msg_per_sec = count / elapsed if elapsed > 0 else 0
            symbol = KNOWN_MARKETS.get(market_id, f"Market_{market_id}")
            
            stats.append({
                'market_id': market_id,
                'symbol': symbol,
                'count': count,
                'msg_per_sec': msg_per_sec,
                'total': self.total_messages[market_id]
            })
            
        return sorted(stats, key=lambda x: x['msg_per_sec'], reverse=True), elapsed
        
    def reset(self):
        self.message_counts.clear()
        self.last_reset = time.time()


async def monitor_throughput():
    """Monitor WebSocket throughput."""
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    monitor = ThroughputMonitor()
    
    print(f"Connecting to {ws_url}...")
    
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        print("Connected! Subscribing to markets...")
        
        # Subscribe to known markets and some test IDs
        test_market_ids = list(KNOWN_MARKETS.keys()) + list(range(2, 30))
        
        for market_id in test_market_ids:
            subscription = {
                "type": "subscribe",
                "channel": f"order_book/{market_id}"
            }
            await ws.send(json.dumps(subscription))
            await asyncio.sleep(0.05)
        
        print(f"Subscribed to {len(test_market_ids)} markets. Monitoring for 1 minute...")
        
        # Message handling
        async def receive_messages():
            msg_count = 0
            async for message in ws:
                try:
                    msg_count += 1
                    data = json.loads(message)
                    msg_type = data.get('type', '')
                    
                    # Debug: print first few messages
                    if msg_count <= 5:
                        print(f"Message {msg_count}: type={msg_type}, channel={data.get('channel', 'N/A')}")
                    
                    # Handle different message types
                    if msg_type == 'connected':
                        print("✓ WebSocket connected successfully")
                    elif msg_type == 'subscribed':
                        channel = data.get('channel', '')
                        print(f"✓ Subscribed to {channel}")
                    elif msg_type == 'error':
                        print(f"❌ Error: {data.get('message', 'Unknown error')}")
                    elif 'order_book' in msg_type:
                        channel = data.get('channel', '')
                        if ':' in channel:  # Actual format is order_book:0
                            market_id = int(channel.split(':')[-1])
                            monitor.record_message(market_id)
                            
                            # Check if it's a new market
                            if market_id not in KNOWN_MARKETS and 'subscribed' in msg_type:
                                print(f"✓ Found active market ID {market_id}")
                                
                except Exception as e:
                    print(f"Error processing message: {e}")
                    print(f"Raw message: {message[:200]}")
        
        # Start receiving
        receive_task = asyncio.create_task(receive_messages())
        
        # Report periodically
        report_interval = 10
        end_time = time.time() + 60  # 1 minute
        
        while time.time() < end_time:
            await asyncio.sleep(report_interval)
            
            stats, elapsed = monitor.get_stats()
            
            print(f"\n{'='*60}")
            print(f"Throughput Report - {datetime.now().strftime('%H:%M:%S')}")
            print(f"Period: {elapsed:.1f}s")
            print(f"{'='*60}")
            print(f"{'Symbol':>15} {'Msg/s':>10} {'Count':>10} {'Total':>10}")
            print(f"{'-'*15} {'-'*10} {'-'*10} {'-'*10}")
            
            total_rate = 0
            for stat in stats[:10]:  # Top 10
                if stat['count'] > 0:  # Only show active markets
                    print(f"{stat['symbol']:>15} {stat['msg_per_sec']:>10.2f} "
                          f"{stat['count']:>10} {stat['total']:>10}")
                    total_rate += stat['msg_per_sec']
            
            print(f"{'-'*15} {'-'*10} {'-'*10} {'-'*10}")
            print(f"{'TOTAL':>15} {total_rate:>10.2f}")
            
            monitor.reset()
        
        receive_task.cancel()
        
        # Final summary
        print(f"\n{'='*60}")
        print("Final Summary")
        print(f"{'='*60}")
        
        runtime = time.time() - monitor.start_time
        for market_id, total in sorted(monitor.total_messages.items(), 
                                     key=lambda x: x[1], reverse=True):
            if total > 0:
                symbol = KNOWN_MARKETS.get(market_id, f"Market_{market_id}")
                avg_rate = total / runtime
                print(f"{symbol:>15}: {total:>6} messages ({avg_rate:.2f} msg/s avg)")


if __name__ == "__main__":
    asyncio.run(monitor_throughput())