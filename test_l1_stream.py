#!/usr/bin/env python3
"""Test L1 book streaming via stream_l1_book_snapshots."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("=== L1 Book Streaming Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Subscribe to mainnet markets
    symbols = [
        "BERA-USDC LIGHTER Perpetual/USDC Crypto",
        "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        "HYPE-USDC LIGHTER Perpetual/USDC Crypto",
    ]
    
    print(f"\nStreaming L1 books for {len(symbols)} symbols:")
    for symbol in symbols:
        print(f"  - {symbol}")
    print("\nWaiting for data...\n")
    
    count = 0
    market_counts = {}
    
    try:
        async for snap in client.stream_l1_book_snapshots(
            venue="LIGHTER",
            symbols=symbols,
        ):
            count += 1
            
            # Track per-market counts
            if snap.symbol not in market_counts:
                market_counts[snap.symbol] = 0
            market_counts[snap.symbol] += 1
            
            # Print first few snapshots in detail
            if count <= 10:
                print(f"[Snapshot #{count}] {snap.symbol}")
                
                if snap.best_bid:
                    # best_bid is a list [price, quantity]
                    bid_price, bid_qty = snap.best_bid[0], snap.best_bid[1]
                    print(f"  Bid: ${bid_price} x {bid_qty}")
                else:
                    print(f"  Bid: None")
                    
                if snap.best_ask:
                    # best_ask is a list [price, quantity]
                    ask_price, ask_qty = snap.best_ask[0], snap.best_ask[1]
                    print(f"  Ask: ${ask_price} x {ask_qty}")
                else:
                    print(f"  Ask: None")
                    
                if snap.best_bid and snap.best_ask:
                    spread = float(snap.best_ask[0]) - float(snap.best_bid[0])
                    print(f"  Spread: ${spread:.5f}")
                print()
            else:
                # Just show dots for subsequent updates
                print(".", end="", flush=True)
                if count % 50 == 0:
                    print(f" [{count} snapshots, {len(market_counts)} markets]")
            
            # Stop after 100 snapshots
            if count >= 100:
                break
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n\n=== Summary ===")
    print(f"Total snapshots: {count}")
    print(f"Per-market snapshots:")
    for symbol, cnt in sorted(market_counts.items()):
        print(f"  {symbol}: {cnt}")
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())