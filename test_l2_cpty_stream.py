#!/usr/bin/env python3
"""Test L2 book streaming from LighterCpty gRPC server."""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import grpc
from architect_py.protos.architect.cpty.v1 import cpty_pb2, cpty_pb2_grpc
from architect_py.protos.architect.cpty.v1.cpty_pb2 import StreamL2BookSnapshotsRequest

async def main():
    print("=== L2 Book Streaming from LighterCpty ===\n")
    
    # Connect to the CPTY gRPC server
    channel = grpc.aio.insecure_channel('localhost:50051')
    stub = cpty_pb2_grpc.CptyServiceStub(channel)
    
    print("✓ Connected to LighterCpty gRPC server")
    
    # Request L2 book snapshots for the first 5 markets
    symbols = [
        "BTC-USDC LIGHTER Perpetual/USDC Crypto",
        "ETH-USDC LIGHTER Perpetual/USDC Crypto", 
        "SOL-USDC LIGHTER Perpetual/USDC Crypto",
        "ARB-USDC LIGHTER Perpetual/USDC Crypto",
        "OP-USDC LIGHTER Perpetual/USDC Crypto",
    ]
    
    request = StreamL2BookSnapshotsRequest(
        venue="LIGHTER",
        symbols=symbols
    )
    
    print(f"Subscribing to {len(symbols)} symbols:")
    for symbol in symbols:
        print(f"  - {symbol}")
    print("\nWaiting for L2 book snapshots...\n")
    
    # Stream snapshots
    count = 0
    market_counts = {}
    start_time = datetime.now()
    
    try:
        async for snapshot in stub.StreamL2BookSnapshots(request):
            count += 1
            
            # Track per-market counts
            symbol = snapshot.symbol
            if symbol not in market_counts:
                market_counts[symbol] = 0
            market_counts[symbol] += 1
            
            # Print first few snapshots
            if count <= 10:
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Snapshot #{count}")
                print(f"  Symbol: {symbol}")
                print(f"  Sequence: {snapshot.sequence}")
                
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
                    
                print()
            else:
                # Just show progress
                if count % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = count / elapsed if elapsed > 0 else 0
                    print(f"[{count} snapshots, {rate:.1f}/sec]")
            
            # Stop after 200 snapshots
            if count >= 200:
                break
                
    except grpc.RpcError as e:
        print(f"\n✗ gRPC Error: {e.code()} - {e.details()}")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    # Print statistics
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n=== Statistics ===")
    print(f"Total snapshots: {count}")
    print(f"Duration: {elapsed:.1f} seconds")
    print(f"Average rate: {count/elapsed if elapsed > 0 else 0:.1f} snapshots/sec")
    print(f"\nPer-symbol counts:")
    for symbol, cnt in sorted(market_counts.items()):
        rate = cnt / elapsed if elapsed > 0 else 0
        print(f"  {symbol}: {cnt} ({rate:.1f}/sec)")
    
    await channel.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())