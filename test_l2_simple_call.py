#!/usr/bin/env python3
"""Simple test to call CPTY's L2 streaming directly."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
import grpc
from architect_py.grpc.models.Marketdata.SubscribeL2BookUpdatesRequest import SubscribeL2BookUpdatesRequest

dotenv.load_dotenv()


async def main():
    print("=== Direct CPTY L2 Call Test ===\n")
    
    # Connect directly to CPTY
    host = "127.0.0.1:50051"
    print(f"Connecting to CPTY at {host}...")
    
    channel = grpc.aio.insecure_channel(host)
    stub = None  # We'll make raw call
    
    try:
        # Create request
        request = SubscribeL2BookUpdatesRequest(
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            venue="LIGHTER"
        )
        print(f"Request: {request}")
        
        # Make the call
        print("\nMaking SubscribeL2BookUpdates call...")
        call = channel.unary_stream(
            '/architect.api.v1.Cpty/SubscribeL2BookUpdates',
            request_serializer=lambda x: x.encode(),
            response_deserializer=lambda x: x
        )
        
        print("Waiting for responses...")
        async with asyncio.timeout(5):
            async for response in call(request.encode()):
                print(f"Got response: {response}")
                break
                
    except asyncio.TimeoutError:
        print("Timed out waiting for response")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await channel.close()
    
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())