#!/usr/bin/env python3
"""Test L2 book streaming via Architect Core from LighterCpty."""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("=== L2 Book Streaming via Architect Core ===\n")
    
    # Connect to Architect Core
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Test symbols
    symbols = [
        "BTC-USDC LIGHTER Perpetual/USDC Crypto",
        "ETH-USDC LIGHTER Perpetual/USDC Crypto",
        "SOL-USDC LIGHTER Perpetual/USDC Crypto",
    ]
    
    print(f"\nRequesting L2 snapshots for {len(symbols)} symbols:")
    for symbol in symbols:
        print(f"  - {symbol}")
    
    # Track statistics
    count = 0
    market_counts = {}
    start_time = datetime.now()
    
    try:
        # Try to get L2 snapshots via execution client
        # First, let's check what's available
        print("\nChecking execution client capabilities...")
        
        # Get current L2 book snapshots (polling approach)
        print("\nPolling L2 book snapshots...")
        
        for _ in range(20):  # Poll 20 times
            for symbol in symbols:
                try:
                    # Try to get a snapshot
                    snapshot = await client.get_l2_book_snapshot(
                        venue="LIGHTER",
                        symbol=symbol
                    )
                    
                    count += 1
                    if symbol not in market_counts:
                        market_counts[symbol] = 0
                    market_counts[symbol] += 1
                    
                    # Print first few snapshots
                    if count <= 5:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Snapshot #{count}")
                        print(f"  Symbol: {symbol}")
                        
                        if snapshot.bids:
                            print(f"  Top 3 Bids:")
                            for i, level in enumerate(snapshot.bids[:3]):
                                print(f"    {i+1}. ${level.price} x {level.quantity}")
                        
                        if snapshot.asks:
                            print(f"  Top 3 Asks:")
                            for i, level in enumerate(snapshot.asks[:3]):
                                print(f"    {i+1}. ${level.price} x {level.quantity}")
                        
                        if snapshot.bids and snapshot.asks:
                            spread = float(snapshot.asks[0].price) - float(snapshot.bids[0].price)
                            print(f"  Spread: ${spread:.5f}")
                    
                except Exception as e:
                    if count == 0:
                        print(f"  Error getting snapshot for {symbol}: {e}")
            
            # Small delay between polls
            await asyncio.sleep(0.5)
            
            # Show progress
            if count > 0 and count % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\n[Progress: {count} snapshots, {rate:.1f}/sec]")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Print statistics
    elapsed = (datetime.now() - start_time).total_seconds()
    if count > 0:
        print(f"\n=== Statistics ===")
        print(f"Total snapshots: {count}")
        print(f"Duration: {elapsed:.1f} seconds")
        print(f"Average rate: {count/elapsed:.1f} snapshots/sec")
        print(f"\nPer-symbol counts:")
        for symbol, cnt in sorted(market_counts.items()):
            rate = cnt / elapsed
            print(f"  {symbol}: {cnt} ({rate:.1f}/sec)")
        print("\n✓ Test successful!")
    else:
        print("\n✗ No snapshots received. Check that:")
        print("  1. LighterCpty is running and connected")
        print("  2. Markets are subscribed in LighterCpty")
        print("  3. Architect Core can reach the CPTY server")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())