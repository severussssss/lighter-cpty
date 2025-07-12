#!/usr/bin/env python3
"""Test L2 book streaming using stream_l2_book_updates."""
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
    print("=== L2 Book Streaming Test (stream_l2_book_updates) ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Test with FARTCOIN
    symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
    print(f"\nStreaming L2 book updates for: {symbol}")
    print("Waiting for data...\n")
    
    count = 0
    try:
        # Use async for with stream_l2_book_updates
        async for snap in client.stream_l2_book_updates(
            symbol=symbol,
            venue="LIGHTER",
        ):
            count += 1
            
            # Print first few snapshots in detail
            if count <= 5:
                print(f"=== L2 Snapshot #{count} ===")
                print(f"Symbol: {snap.symbol}")
                print(f"Timestamp: {snap.timestamp}")
                print(f"Sequence: {snap.sequence}")
                
                if snap.bids:
                    print(f"Top 3 Bids:")
                    for i, level in enumerate(snap.bids[:3]):
                        print(f"  {i+1}. ${level.price} x {level.quantity}")
                else:
                    print("No bids")
                
                if snap.asks:
                    print(f"Top 3 Asks:")
                    for i, level in enumerate(snap.asks[:3]):
                        print(f"  {i+1}. ${level.price} x {level.quantity}")
                else:
                    print("No asks")
                
                if snap.bids and snap.asks:
                    spread = float(snap.asks[0].price) - float(snap.bids[0].price)
                    print(f"Spread: ${spread:.5f}")
                
                print(f"Total levels: {len(snap.bids)} bids, {len(snap.asks)} asks\n")
            else:
                # Just show dots for subsequent updates
                print(".", end="", flush=True)
                if count % 50 == 0:
                    print(f" [{count} snapshots received]")
            
            # Stop after 100 snapshots
            if count >= 100:
                break
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n\n✓ Test completed! Received {count} L2 snapshots")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())