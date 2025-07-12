#!/usr/bin/env python3
"""Test L2 book subscription via Architect client."""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def get_default_architect_client() -> AsyncClient:
    return await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )


async def main():
    print("=== L2 Book Subscription Test ===")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # Subscribe to first 5 markets
    symbols = [
        "BTC-USDC LIGHTER Perpetual/USDC Crypto",
        "ETH-USDC LIGHTER Perpetual/USDC Crypto",
        "SOL-USDC LIGHTER Perpetual/USDC Crypto",
        "ARB-USDC LIGHTER Perpetual/USDC Crypto",
        "OP-USDC LIGHTER Perpetual/USDC Crypto",
    ]
    
    print(f"\nSubscribing to L2 books for {len(symbols)} symbols:")
    for symbol in symbols:
        print(f"  - {symbol}")
    
    # Track statistics
    snapshot_count = 0
    market_snapshots = {}
    start_time = datetime.now()
    
    try:
        # Subscribe to L2 book snapshots
        async for snap in architect_client.stream_l2_book_snapshots(
            venue="LIGHTER",
            symbols=symbols,
        ):
            snapshot_count += 1
            
            # Track per-market counts
            symbol = snap.symbol
            if symbol not in market_snapshots:
                market_snapshots[symbol] = 0
            market_snapshots[symbol] += 1
            
            # Display snapshot info
            if snap.bids and snap.asks:
                best_bid = snap.bids[0]
                best_ask = snap.asks[0]
                spread = float(best_ask.price) - float(best_bid.price)
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "
                      f"Snapshot #{snapshot_count} | {symbol}")
                print(f"  Best Bid: ${best_bid.price} ({best_bid.quantity})")
                print(f"  Best Ask: ${best_ask.price} ({best_ask.quantity})")
                print(f"  Spread: ${spread:.5f}")
                print(f"  Depth: {len(snap.bids)} bids x {len(snap.asks)} asks")
            
            # Show statistics every 50 snapshots
            if snapshot_count % 50 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = snapshot_count / elapsed if elapsed > 0 else 0
                
                print(f"\n=== Statistics after {snapshot_count} snapshots ===")
                print(f"Total rate: {rate:.1f} snapshots/sec")
                print("Per-market snapshot counts:")
                for market, count in sorted(market_snapshots.items()):
                    market_rate = count / elapsed if elapsed > 0 else 0
                    print(f"  {market}: {count} ({market_rate:.1f}/sec)")
            
            # Run for 30 seconds
            if (datetime.now() - start_time).total_seconds() > 30:
                break
                
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during subscription: {e}")
        import traceback
        traceback.print_exc()
    
    # Final statistics
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n=== Final Statistics ===")
    print(f"Test duration: {elapsed:.1f} seconds")
    print(f"Total snapshots received: {snapshot_count}")
    print(f"Average rate: {snapshot_count/elapsed if elapsed > 0 else 0:.1f} snapshots/sec")
    print("\nPer-market totals:")
    for market, count in sorted(market_snapshots.items()):
        market_rate = count / elapsed if elapsed > 0 else 0
        print(f"  {market}: {count} snapshots ({market_rate:.1f}/sec)")
    
    await architect_client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())