#!/usr/bin/env python3
"""Trace L2 streaming to find where it hangs."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py.grpc.models.Marketdata.SubscribeL2BookUpdatesRequest import SubscribeL2BookUpdatesRequest

dotenv.load_dotenv()


async def main():
    print("=== L2 Streaming Trace ===\n")
    
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
    venue = "LIGHTER"
    
    try:
        # Get the marketdata client
        print(f"\n1. Getting marketdata client for {venue}...")
        grpc_client = await client._marketdata(venue)
        print(f"   ✓ Got client: {grpc_client}")
        
        # Create request
        print(f"\n2. Creating SubscribeL2BookUpdatesRequest...")
        req = SubscribeL2BookUpdatesRequest(symbol=str(symbol), venue=venue)
        print(f"   ✓ Request: {req}")
        
        # Make the stream call
        print(f"\n3. Calling grpc_client.unary_stream...")
        stream = grpc_client.unary_stream(req)
        print(f"   ✓ Got stream: {stream}")
        
        # Try to get first update
        print(f"\n4. Waiting for first update...")
        count = 0
        async for res in stream:
            count += 1
            print(f"   ✓ Got update #{count}: {type(res)}")
            if count >= 3:
                break
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Trace completed")


if __name__ == "__main__":
    asyncio.run(main())