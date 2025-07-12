#!/usr/bin/env python3
"""Real-time L2 book subscription test using asyncio.Event."""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


class L2BookMonitor:
    """Monitor L2 book changes in real-time."""
    
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.last_timestamp = 0
        self.update_event = asyncio.Event()
        self.monitoring = True
        
    async def monitor_changes(self):
        """Background task that checks for changes and sets event."""
        while self.monitoring:
            if self.snapshot.timestamp > self.last_timestamp:
                self.last_timestamp = self.snapshot.timestamp
                self.update_event.set()
            # Very short sleep just to yield control
            await asyncio.sleep(0.001)  # 1ms
    
    async def wait_for_update(self, timeout=5.0):
        """Wait for next update with timeout."""
        self.update_event.clear()
        try:
            await asyncio.wait_for(self.update_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False


async def main():
    print("=== Real-time L2 Book Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Initialize l2_books if needed
    if not hasattr(client, 'l2_books'):
        client.l2_books = {}
    
    # Subscribe to BTC
    symbol = "BTC-USDC LIGHTER Perpetual/USDC Crypto"
    print(f"\nSubscribing to L2 book for: {symbol}")
    
    try:
        snap = await client.subscribe_l2_book(
            venue="LIGHTER",
            symbol=symbol,
        )
        print("✓ Subscription successful\n")
    except Exception as e:
        print(f"✗ Failed to subscribe: {e}")
        await client.close()
        return
    
    # Create monitor
    monitor = L2BookMonitor(snap)
    monitor_task = asyncio.create_task(monitor.monitor_changes())
    
    count = 0
    latencies = []
    start_time = time.time()
    
    try:
        while count < 100:
            # Wait for update
            update_start = time.time()
            has_update = await monitor.wait_for_update(timeout=5.0)
            
            if not has_update:
                print("\n✗ No updates for 5 seconds")
                break
            
            # Calculate latency
            latency = (time.time() - update_start) * 1000  # ms
            latencies.append(latency)
            count += 1
            
            # Print first few updates in detail
            if count <= 5:
                print(f"=== Update #{count} ===")
                print(f"Timestamp: {snap.timestamp}")
                print(f"Detection latency: {latency:.1f}ms")
                
                if snap.bids and snap.asks:
                    best_bid = snap.bids[0]
                    best_ask = snap.asks[0]
                    spread = float(best_ask[0]) - float(best_bid[0])
                    print(f"Best Bid: ${best_bid[0]} x {best_bid[1]}")
                    print(f"Best Ask: ${best_ask[0]} x {best_ask[1]}")
                    print(f"Spread: ${spread:.2f}")
                    print(f"Depth: {len(snap.bids)} bids x {len(snap.asks)} asks")
                print()
            else:
                # Progress indicator every 10 updates
                if count % 10 == 0:
                    avg_latency = sum(latencies[-10:]) / 10
                    print(f"[{count} updates, avg latency: {avg_latency:.1f}ms]")
                else:
                    print(".", end="", flush=True)
    
    finally:
        # Clean up
        monitor.monitoring = False
        await monitor_task
    
    # Statistics
    elapsed = time.time() - start_time
    if count > 0:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"\n\n=== Statistics ===")
        print(f"Total updates: {count}")
        print(f"Duration: {elapsed:.1f} seconds")
        print(f"Update rate: {count/elapsed:.1f} updates/sec")
        print(f"\nLatency stats:")
        print(f"  Average: {avg_latency:.1f}ms")
        print(f"  Min: {min_latency:.1f}ms")
        print(f"  Max: {max_latency:.1f}ms")
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())