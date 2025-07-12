#!/usr/bin/env python3
"""Simple test to verify L1 book subscription works."""
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
    print("=== Simple L1 Book Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Workaround: Initialize l1_books if it doesn't exist
    if not hasattr(client, 'l1_books'):
        client.l1_books = {}
        print("  (Initialized l1_books attribute)")
    
    # Subscribe to just BTC
    symbol = "BTC-USDC LIGHTER Perpetual/USDC Crypto"
    print(f"\nSubscribing to L1 book for: {symbol}")
    print("Waiting for data...\n")
    
    # Subscribe to L1 book - returns a snapshot that updates in background
    snapshot = await client.subscribe_l1_book(
        venue="LIGHTER",
        symbol=symbol,
    )
    
    print("✓ Subscription created, polling for updates...\n")
    
    count = 0
    last_bid = None
    last_ask = None
    
    # Poll the snapshot object for updates
    for _ in range(100):
        # Check if bid/ask changed
        current_bid = snapshot.best_bid
        current_ask = snapshot.best_ask
        
        if current_bid != last_bid or current_ask != last_ask:
            count += 1
            
            print(f"[Update #{count}] ", end="")
            
            if current_bid:
                print(f"Bid: ${current_bid.price} x {current_bid.quantity} | ", end="")
            else:
                print("Bid: None | ", end="")
                
            if current_ask:
                print(f"Ask: ${current_ask.price} x {current_ask.quantity} | ", end="")
            else:
                print("Ask: None | ", end="")
                
            if current_bid and current_ask:
                spread = float(current_ask.price) - float(current_bid.price)
                print(f"Spread: ${spread:.5f}")
            else:
                print("Spread: N/A")
            
            last_bid = current_bid
            last_ask = current_ask
        
        # Small delay between polls
        await asyncio.sleep(0.1)
    
    print(f"\n✓ Test completed! Saw {count} updates")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())