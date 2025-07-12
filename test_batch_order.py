#!/usr/bin/env python3
"""Test batch order placement via Architect."""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, OrderType, TimeInForce
from architect_py.batch_place_order import BatchPlaceOrder

dotenv.load_dotenv()


async def main():
    print("=== Batch Order Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Create a batch of orders
    batch = BatchPlaceOrder()
    order_ids = []
    
    # Order 1: Buy FARTCOIN
    order1_id = str(uuid.uuid4())
    await batch.place_order(
        id=order1_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("1.20"),
        quantity=Decimal("10.0"),
        time_in_force=TimeInForce.GTC,
        execution_venue="LIGHTER",
        post_only=False,
    )
    order_ids.append(order1_id)
    print(f"\nOrder 1: BUY 10 FARTCOIN @ $1.20")
    
    # Order 2: Sell FARTCOIN at higher price
    order2_id = str(uuid.uuid4())
    await batch.place_order(
        id=order2_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.SELL,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("1.22"),
        quantity=Decimal("10.0"),
        time_in_force=TimeInForce.GTC,
        execution_venue="LIGHTER",
        post_only=False,
    )
    order_ids.append(order2_id)
    print(f"Order 2: SELL 10 FARTCOIN @ $1.22")
    
    # Order 3: Buy BERA
    order3_id = str(uuid.uuid4())
    await batch.place_order(
        id=order3_id,
        symbol="BERA-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("1.84"),
        quantity=Decimal("5.0"),
        time_in_force=TimeInForce.GTC,
        execution_venue="LIGHTER",
        post_only=False,
    )
    order_ids.append(order3_id)
    print(f"Order 3: BUY 5 BERA @ $1.84")
    
    # Order 4: Invalid symbol to test error handling
    order4_id = str(uuid.uuid4())
    await batch.place_order(
        id=order4_id,
        symbol="INVALID-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("100.0"),
        quantity=Decimal("1.0"),
        time_in_force=TimeInForce.GTC,
        execution_venue="LIGHTER",
        post_only=False,
    )
    order_ids.append(order4_id)
    print(f"Order 4: BUY 1 INVALID @ $100.0 (should fail)")
    
    print(f"\n📦 Sending batch of {len(batch.place_orders)} orders...")
    
    # Track orderflow events
    order_events = {order_id: [] for order_id in order_ids}
    successful_orders = set()
    rejected_orders = set()
    
    async def track_events():
        """Track orderflow events for our orders."""
        async for event in client.stream_orderflow(venue="LIGHTER"):
            # Check if this event is for one of our orders
            order_id = None
            
            if hasattr(event, 'order_id'):
                order_id = event.order_id
            elif hasattr(event, 'order') and hasattr(event.order, 'id'):
                order_id = event.order.id
                
            if order_id in order_events:
                event_type = type(event).__name__
                order_events[order_id].append(event_type)
                print(f"  📍 Order {order_id[:8]}... - {event_type}")
                
                if event_type == "OrderAck":
                    successful_orders.add(order_id)
                elif event_type == "OrderReject":
                    rejected_orders.add(order_id)
                    if hasattr(event, 'reject_reason'):
                        print(f"     ❌ Reject reason: {event.reject_reason}")
                
                # Stop after we've heard about all orders
                if len(successful_orders) + len(rejected_orders) >= len(order_ids):
                    return
    
    # Start tracking events
    event_task = asyncio.create_task(track_events())
    
    # Wait a bit to ensure subscription is active
    await asyncio.sleep(0.5)
    
    # Place the batch order
    try:
        response = await client.place_batch_order(batch)
        print(f"\n✓ Batch order response received")
        
        # The response contains rejected orders and pending orders
        if hasattr(response, 'order_rejects') and response.order_rejects:
            print(f"\n❌ {len(response.order_rejects)} orders rejected:")
            for reject in response.order_rejects:
                print(f"   - Order {reject.order_id}: {reject.reason}")
                
        if hasattr(response, 'pending_orders') and response.pending_orders:
            print(f"\n✅ {len(response.pending_orders)} orders pending")
            
    except Exception as e:
        print(f"\n✗ Error placing batch order: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait for events to complete
    print("\nWaiting for order events...")
    try:
        await asyncio.wait_for(event_task, timeout=5.0)
    except asyncio.TimeoutError:
        print("Timeout waiting for all events")
        event_task.cancel()
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Total orders sent: {len(order_ids)}")
    print(f"Successful orders: {len(successful_orders)}")
    print(f"Rejected orders: {len(rejected_orders)}")
    
    for i, order_id in enumerate(order_ids, 1):
        events = order_events[order_id]
        status = "✅ Success" if order_id in successful_orders else "❌ Rejected" if order_id in rejected_orders else "⏳ Unknown"
        print(f"\nOrder {i}: {status}")
        print(f"  Events: {', '.join(events) if events else 'None'}")
    
    # Get open orders
    print("\n📋 Checking open orders...")
    open_orders = await client.open_orders(venue="LIGHTER")
    print(f"Found {len(open_orders)} open orders")
    
    for order in open_orders[:5]:  # Show first 5
        print(f"  - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
    
    # Cancel all orders
    if len(open_orders) > 0:
        print("\n🧹 Cancelling all orders...")
        await client.cancel_all_orders(venue="LIGHTER")
        print("✓ Cancel all orders sent")
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())