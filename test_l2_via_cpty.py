#!/usr/bin/env python3
"""Test L2 streaming directly via CPTY."""
import asyncio
import grpc
from architect_py.grpc.models.Marketdata.SubscribeL2BookUpdatesRequest import (
    SubscribeL2BookUpdatesRequest,
)
from architect_py.grpc.models.Marketdata.L2BookUpdate import L2BookUpdate
import msgspec


async def main():
    print("=== L2 Streaming via CPTY Test ===\n")
    
    # Connect directly to CPTY
    channel = grpc.aio.insecure_channel("127.0.0.1:50051")
    
    # Create request
    request = SubscribeL2BookUpdatesRequest(
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        venue="LIGHTER"
    )
    print(f"Request: {request}")
    
    # Encode request
    encoder = msgspec.json.Encoder()
    request_bytes = encoder.encode(request)
    
    # Make the streaming call
    print("\nSubscribing to L2 updates...")
    try:
        # Create the streaming call
        stream = channel.unary_stream(
            "/architect.api.v1.Cpty/SubscribeL2BookUpdates",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        
        count = 0
        decoder = msgspec.json.Decoder(type=L2BookUpdate)
        
        async for response_bytes in stream(request_bytes):
            count += 1
            try:
                # Decode the response
                update = decoder.decode(response_bytes)
                print(f"\n[Update #{count}]")
                print(f"  Type: {update.__class__.__name__}")
                if hasattr(update, 'b') and hasattr(update, 'a'):
                    print(f"  Bids: {len(update.b)} levels")
                    print(f"  Asks: {len(update.a)} levels")
                    if update.b:
                        print(f"  Best bid: {update.b[0]}")
                    if update.a:
                        print(f"  Best ask: {update.a[0]}")
            except Exception as e:
                print(f"  Failed to decode: {e}")
                print(f"  Raw: {response_bytes[:100]}...")
            
            if count >= 5:
                break
                
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await channel.close()
    
    print(f"\n✓ Received {count} L2 updates via CPTY")


if __name__ == "__main__":
    asyncio.run(main())