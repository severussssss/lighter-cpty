#!/usr/bin/env python3
"""Test orderflow streaming from CPTY."""
import asyncio
import os
import sys
import time
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce

dotenv.load_dotenv()


async def main():
    print("\n=== Orderflow Stream Test ===")
    
    # Connect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    account = "2f018d76-5cf9-658a-b08e-a04f36782817"
    symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
    
    # Start streaming orderflow
    print("\nStarting orderflow stream...")
    
    event_count = 0
    
    async def handle_orderflow(event):
        nonlocal event_count
        event_count += 1
        print(f"\n[ORDERFLOW EVENT {event_count}]")
        print(f"Type: {type(event).__name__}")
        print(f"Event: {event}")
        
        # Check specific event types
        if hasattr(event, 'order_id'):
            print(f"Order ID: {event.order_id}")
        if hasattr(event, 'status'):
            print(f"Status: {event.status}")
        if hasattr(event, 'reject_reason'):
            print(f"Reject Reason: {event.reject_reason}")
        if hasattr(event, 'reject_message'):
            print(f"Reject Message: {event.reject_message}")
    
    # Subscribe to orderflow
    print("Subscribing to orderflow...")
    orderflow_stream = client.stream_orderflow(
        execution_venue="LIGHTER",
        account=account
    )
    
    # Start consuming events in background
    async def consume_events():
        try:
            async for event in orderflow_stream:
                await handle_orderflow(event)
        except Exception as e:
            print(f"Stream error: {e}")
    
    # Start the consumer task
    consumer_task = asyncio.create_task(consume_events())
    
    # Give it a moment to connect
    await asyncio.sleep(2)
    
    # Place a test order
    print("\n=== Placing Test Order ===")
    order_id = f"flow-test-{int(time.time())}"
    
    try:
        result = await client.place_order(
            symbol=symbol,
            execution_venue="LIGHTER",
            order_id=order_id,
            dir=OrderDir.BUY,
            limit_price=Decimal("1.10"),  # Reasonable price
            quantity=Decimal("10"),
            account=account,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=True,
        )
        print(f"✓ Order placed: {result.id}")
    except Exception as e:
        print(f"✗ Failed to place order: {e}")
    
    # Wait for events
    print("\nWaiting for orderflow events...")
    await asyncio.sleep(5)
    
    # Place an order that might get rejected
    print("\n=== Placing Rejection Test Order ===")
    reject_id = f"reject-flow-{int(time.time())}"
    
    try:
        result = await client.place_order(
            symbol=symbol,
            execution_venue="LIGHTER",
            order_id=reject_id,
            dir=OrderDir.BUY,
            limit_price=Decimal("1.055"),  # Price that might get rejected
            quantity=Decimal("20"),
            account=account,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=False,
        )
        print(f"✓ Order placed: {result.id}")
    except Exception as e:
        print(f"✗ Failed to place order: {e}")
    
    # Wait more for events
    await asyncio.sleep(10)
    
    print(f"\n=== Summary ===")
    print(f"Total orderflow events received: {event_count}")
    
    # Clean up
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())