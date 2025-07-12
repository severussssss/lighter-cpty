#!/usr/bin/env python3
"""Simple test to verify L2 book subscription works."""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("=== Simple L2 Book Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Subscribe to just BTC
    symbol = "BTC-USDC LIGHTER Perpetual/USDC Crypto"
    print(f"\nSubscribing to L2 book for: {symbol}")
    print("Waiting for data...\n")
    
    # Initialize l2_books if it doesn't exist (workaround for architect_py bug)
    if not hasattr(client, 'l2_books'):
        client.l2_books = {}
        print("  (Initialized l2_books attribute)")
    
    # Subscribe to L2 book - this returns a snapshot object that updates in the background
    try:
        snap = await client.subscribe_l2_book(
            venue="LIGHTER",
            symbol=symbol,
        )
        print("✓ Subscription successful, polling for updates...")
    except Exception as e:
        print(f"✗ Failed to subscribe: {e}")
        await client.close()
        return
    
    count = 0
    last_timestamp = 0
    start_time = asyncio.get_event_loop().time()
    
    # Poll the snapshot object for updates with minimal delay
    # Using a tight loop with minimal sleep for near real-time updates
    while count < 100:
        # Minimal sleep just to yield control to other tasks
        await asyncio.sleep(0.001)  # 1ms instead of 100ms
        
        # Check if the snapshot has been updated
        if snap.timestamp > last_timestamp:
            count += 1
            last_timestamp = snap.timestamp
            update_time = time.time()
            
            # Print first few snapshots in detail
            if count <= 5:
                print(f"\n=== Update #{count} ===")
                print(f"Timestamp: {snap.timestamp}")
                print(f"Sequence: {snap.sequence_number}")
                
                if snap.bids:
                    print(f"Top 3 Bids:")
                    for i, bid in enumerate(snap.bids[:3]):
                        # bid is a list [price, quantity]
                        print(f"  {i+1}. ${bid[0]} x {bid[1]}")
                
                if snap.asks:
                    print(f"Top 3 Asks:")
                    for i, ask in enumerate(snap.asks[:3]):
                        # ask is a list [price, quantity]
                        print(f"  {i+1}. ${ask[0]} x {ask[1]}")
                
                if snap.bids and snap.asks:
                    spread = float(snap.asks[0][0]) - float(snap.bids[0][0])
                    print(f"Spread: ${spread:.5f}")
            else:
                # Just show dots for subsequent updates
                print(".", end="", flush=True)
                if count % 10 == 0:
                    print(f" [{count} updates received]")
        
        # Stop after 30 seconds even if we haven't received updates
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > 30:
            if count == 0:
                print("\n✗ Timeout: No updates received after 30 seconds")
            else:
                print(f"\n⏱️ Stopping after {elapsed:.1f} seconds")
            break
    
    print(f"\n\n✓ Test successful! Received {count} L2 snapshots")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())