#!/usr/bin/env python3
"""Debug L2 streaming issue."""
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
    print("=== L2 Streaming Debug ===\n")
    
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
    print(f"\nTrying to stream L2 for: {symbol}")
    
    try:
        # Get the marketdata client
        print("\nGetting marketdata client for LIGHTER...")
        md_client = await client._marketdata("LIGHTER")
        print(f"✓ Got marketdata client: {md_client}")
        
        # Try the actual stream
        print("\nCalling stream_l2_book_updates...")
        count = 0
        async for snap in client.stream_l2_book_updates(
            symbol=symbol,
            venue="LIGHTER",
        ):
            count += 1
            print(f"Got snapshot #{count}")
            if count >= 3:
                break
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Debug completed")


if __name__ == "__main__":
    asyncio.run(main())