#!/usr/bin/env python3
"""Test placing orders on HYPE, BTC, and 1000BONK markets using batch orders."""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, OrderType, TimeInForce
from architect_py.batch_place_order import BatchPlaceOrder

dotenv.load_dotenv()


async def get_default_architect_client() -> AsyncClient:
    return await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )


async def main():
    print("=== Multiple Market Batch Order Test ===")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # LIGHTER account from core config
    account_address = "2f018d76-5cf9-658a-b08e-a04f36782817"
    
    # Test configurations based on market data:
    # HYPE: price_decimals=4, size_decimals=2, min_base_amount=0.50
    # BTC: price_decimals=1, size_decimals=5, min_base_amount=0.00020
    # 1000BONK: price_decimals=6, size_decimals=0, min_base_amount=500
    
    test_configs = [
        # (symbol, base_symbol, price, quantity, side)
        ("HYPE", "HYPE", "54.1234", "0.5", OrderDir.SELL),  # 4 price decimals, 2 size decimals
        ("BTC", "BTC", "125432.1", "0.0002", OrderDir.SELL),  # 1 price decimal, 5 size decimals
        ("1000BONK", "1000BONK", "0.035678", "500", OrderDir.SELL),  # 6 price decimals, 0 size decimals
    ]
    
    # Create batch
    batch = BatchPlaceOrder()
    order_ids = []
    
    print("\n📦 Preparing batch orders:")
    for i, (symbol, base_symbol, price, quantity, side) in enumerate(test_configs, 1):
        order_id = f"{symbol.lower()}-{uuid.uuid4().hex[:8]}"
        architect_symbol = f"{base_symbol}-USDC LIGHTER Perpetual/USDC Crypto"
        
        print(f"\nOrder {i}: {symbol}")
        print(f"  Symbol: {architect_symbol}")
        print(f"  ID: {order_id}")
        print(f"  Side: {side.name}")
        print(f"  Quantity: {quantity}")
        print(f"  Price: {price}")
        
        await batch.place_order(
            id=order_id,
            symbol=architect_symbol,
            dir=side,
            order_type=OrderType.LIMIT,
            limit_price=Decimal(price),
            quantity=Decimal(quantity),
            time_in_force=TimeInForce.GTC,
            execution_venue="LIGHTER",
            account=account_address,
            post_only=False,
        )
        order_ids.append(order_id)
    
    print(f"\n📨 Sending batch of {len(batch.place_orders)} orders...")
    
    # Track orderflow events
    order_events = {order_id: [] for order_id in order_ids}
    successful_orders = set()
    rejected_orders = set()
    
    async def track_events():
        """Track orderflow events for our orders."""
        async for event in architect_client.stream_orderflow(venue="LIGHTER"):
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
                    if hasattr(event, 'message'):
                        print(f"     ❌ Message: {event.message}")
                
                # Stop after we've heard about all orders
                if len(successful_orders) + len(rejected_orders) >= len(order_ids):
                    return
    
    # Start tracking events
    event_task = asyncio.create_task(track_events())
    
    # Wait a bit to ensure subscription is active
    await asyncio.sleep(0.5)
    
    # Place the batch order
    try:
        response = await architect_client.place_batch_order(batch)
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
    print("\n⏳ Waiting for order events...")
    try:
        await asyncio.wait_for(event_task, timeout=10.0)
    except asyncio.TimeoutError:
        print("Timeout waiting for all events")
        event_task.cancel()
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Total orders sent: {len(order_ids)}")
    print(f"Successful orders: {len(successful_orders)}")
    print(f"Rejected orders: {len(rejected_orders)}")
    
    for i, (order_id, (symbol, _, _, _, _)) in enumerate(zip(order_ids, test_configs), 1):
        events = order_events[order_id]
        status = "✅ Success" if order_id in successful_orders else "❌ Rejected" if order_id in rejected_orders else "⏳ Unknown"
        print(f"\nOrder {i} ({symbol}): {status}")
        print(f"  Events: {', '.join(events) if events else 'None'}")
    
    # Get open orders
    print("\n📋 Checking open orders...")
    try:
        open_orders = await architect_client.open_orders(venue="LIGHTER")
        print(f"Found {len(open_orders)} open orders")
        
        for order in open_orders[:5]:  # Show first 5
            print(f"  - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
    except Exception as e:
        print(f"Error getting open orders: {e}")
    
    print("\n=== All Tests Completed ===")
    print("Check CPTY logs for details:")
    print("tmux capture-pane -t l_cpty -p | tail -100")
    
    await architect_client.close()


if __name__ == "__main__":
    asyncio.run(main())