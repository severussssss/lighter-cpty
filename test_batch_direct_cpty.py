#!/usr/bin/env python3
"""Test batch order directly through CPTY bidirectional stream."""
import asyncio
import uuid
from decimal import Decimal
import grpc
import msgspec

from architect_py.grpc.models.Cpty.CptyRequest import (
    Login,
    PlaceBatchOrder,
    CptyRequest,
    UnannotatedCptyRequest,
)
from architect_py import (
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
)


async def main():
    print("=== Direct CPTY Batch Order Test ===\n")
    
    # Connect directly to CPTY
    channel = grpc.aio.insecure_channel("127.0.0.1:50051")
    
    # Encoders/decoders
    encoder = msgspec.json.Encoder()
    decoder = msgspec.json.Decoder()
    
    # Request queue
    request_queue = asyncio.Queue()
    
    # Create the bidirectional stream
    async def request_iterator():
        while True:
            request = await request_queue.get()
            if request is None:
                break
            yield request
    
    stub = channel.stream_stream(
        "/json.architect.Cpty/Cpty",
        request_serializer=lambda x: x,
        response_deserializer=lambda x: x,
    )
    
    call = stub(request_iterator())
    
    # Response handler
    async def handle_responses():
        try:
            async for response_bytes in call:
                try:
                    response = decoder.decode(response_bytes)
                    print(f"\n📨 Response: {type(response).__name__ if hasattr(response, '__class__') else response}")
                    if isinstance(response, dict):
                        for key, value in response.items():
                            if value:
                                print(f"  {key}: {value}")
                except Exception as e:
                    print(f"Failed to decode response: {e}")
        except Exception as e:
            print(f"Response handler error: {e}")
    
    # Start response handler
    response_task = asyncio.create_task(handle_responses())
    
    try:
        # 1. Login
        print("1️⃣ Logging in...")
        login_req = Login(
            trader="test-trader",
            account="30188"
        )
        await request_queue.put(encoder.encode({"login": login_req}))
        await asyncio.sleep(1)
        
        # 2. Create batch order
        print("\n2️⃣ Creating batch order...")
        
        # Create orders for the batch
        orders = []
        
        # Order 1: Buy FARTCOIN
        order1 = Order(
            id=f"batch-{uuid.uuid4().hex[:8]}",
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            type=OrderType.LIMIT,
            limit_price=Decimal("1.20"),
            quantity=Decimal("10.0"),
            time_in_force=TimeInForce.GTC,
        )
        orders.append(order1)
        print(f"  Order 1: BUY 10 FARTCOIN @ $1.20")
        
        # Order 2: Sell FARTCOIN
        order2 = Order(
            id=f"batch-{uuid.uuid4().hex[:8]}",
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.SELL,
            type=OrderType.LIMIT,
            limit_price=Decimal("1.25"),
            quantity=Decimal("10.0"),
            time_in_force=TimeInForce.GTC,
        )
        orders.append(order2)
        print(f"  Order 2: SELL 10 FARTCOIN @ $1.25")
        
        # Order 3: Buy BERA
        order3 = Order(
            id=f"batch-{uuid.uuid4().hex[:8]}",
            symbol="BERA-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            type=OrderType.LIMIT,
            limit_price=Decimal("1.84"),
            quantity=Decimal("5.0"),
            time_in_force=TimeInForce.GTC,
        )
        orders.append(order3)
        print(f"  Order 3: BUY 5 BERA @ $1.84")
        
        # Order 4: Invalid symbol to test error handling
        order4 = Order(
            id=f"batch-{uuid.uuid4().hex[:8]}",
            symbol="INVALID-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            type=OrderType.LIMIT,
            limit_price=Decimal("100.0"),
            quantity=Decimal("1.0"),
            time_in_force=TimeInForce.GTC,
        )
        orders.append(order4)
        print(f"  Order 4: BUY 1 INVALID @ $100.0 (should fail)")
        
        # Send batch order
        print(f"\n3️⃣ Sending batch of {len(orders)} orders...")
        batch_req = PlaceBatchOrder(orders=orders)
        await request_queue.put(encoder.encode({"place_batch_order": batch_req}))
        
        # Wait for responses
        print("\n⏳ Waiting for order responses...")
        await asyncio.sleep(5)
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cancel response handler
        response_task.cancel()
        try:
            await response_task
        except asyncio.CancelledError:
            pass
        
        # Close channel
        await channel.close()


if __name__ == "__main__":
    asyncio.run(main())