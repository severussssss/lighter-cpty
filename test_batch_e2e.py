#!/usr/bin/env python3
"""End-to-end test for batch order placement."""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from decimal import Decimal
import time

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce
from architect_py.batch_place_order import BatchPlaceOrder

dotenv.load_dotenv()


async def main():
    print("=== End-to-End Batch Order Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    account_address = os.getenv("LIGHTER_ACCOUNT_ADDRESS", "2f018d76-5cf9-658a-b08e-a04f36782817")
    
    # Create a batch of orders with reasonable prices
    batch = BatchPlaceOrder()
    order_ids = []
    placed_orders = {}
    
    # Order 1: Buy FARTCOIN below market
    order1_id = f"e2e1-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order1_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.BUY,
        order_type="LIMIT",
        limit_price=Decimal("1.19"),  # Below market
        quantity=Decimal("50.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=True,  # Ensure it goes to book
    )
    order_ids.append(order1_id)
    placed_orders[order1_id] = {"symbol": "FARTCOIN", "side": "BUY", "price": "1.19", "qty": "50.0"}
    print(f"Order 1: BUY 50 FARTCOIN @ $1.19 (ID: {order1_id})")
    
    # Order 2: Sell FARTCOIN above market
    order2_id = f"e2e2-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order2_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.SELL,
        order_type="LIMIT",
        limit_price=Decimal("1.22"),  # Above market
        quantity=Decimal("50.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=True,
    )
    order_ids.append(order2_id)
    placed_orders[order2_id] = {"symbol": "FARTCOIN", "side": "SELL", "price": "1.22", "qty": "50.0"}
    print(f"Order 2: SELL 50 FARTCOIN @ $1.22 (ID: {order2_id})")
    
    # Order 3: Buy HYPE (instead of BERA which was getting rejected)
    order3_id = f"e2e3-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order3_id,
        symbol="HYPE-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.BUY,
        order_type="LIMIT",
        limit_price=Decimal("42.50"),  # Reasonable price for HYPE
        quantity=Decimal("2.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=True,
    )
    order_ids.append(order3_id)
    placed_orders[order3_id] = {"symbol": "HYPE", "side": "BUY", "price": "42.50", "qty": "2.0"}
    print(f"Order 3: BUY 2 HYPE @ $42.50 (ID: {order3_id})")
    
    print(f"\n📦 Sending batch of {len(batch.place_orders)} orders...")
    
    # Track order events
    successful_orders = []
    rejected_orders = []
    order_events = {order_id: [] for order_id in order_ids}
    
    # Start event tracking
    async def track_events():
        try:
            async for event in client.stream_orderflow():
                # Check if this event is for one of our orders
                order_id = None
                
                if hasattr(event, 'order_id'):
                    order_id = event.order_id
                elif hasattr(event, 'order') and hasattr(event.order, 'id'):
                    order_id = event.order.id
                
                # Check if it's one of our orders
                for our_id in order_ids:
                    if our_id in str(order_id):
                        event_type = type(event).__name__
                        order_events[our_id].append(event_type)
                        print(f"  📍 Order {our_id} - {event_type}")
                        
                        if event_type == "OrderAck":
                            successful_orders.append(our_id)
                        elif event_type == "OrderReject":
                            rejected_orders.append(our_id)
                            if hasattr(event, 'reason'):
                                print(f"     ❌ Reject reason: {event.reason}")
                        
                        break
        except Exception as e:
            print(f"Event tracking error: {e}")
    
    event_task = asyncio.create_task(track_events())
    
    # Place the batch order
    try:
        start_time = time.time()
        response = await client.place_batch_order(batch)
        elapsed = time.time() - start_time
        
        print(f"\n✅ Batch order response received in {elapsed:.2f}s")
        
        # Check response
        if hasattr(response, 'order_rejects') and response.order_rejects:
            print(f"\n❌ {len(response.order_rejects)} orders rejected:")
            for reject in response.order_rejects:
                print(f"   - Order {reject.order_id}: {reject.reason}")
                rejected_orders.append(reject.order_id)
                
        if hasattr(response, 'pending_orders') and response.pending_orders:
            print(f"\n✅ {len(response.pending_orders)} orders pending:")
            for order in response.pending_orders[:5]:  # Show first 5
                print(f"   - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
        
        # Wait for events
        print("\n⏳ Waiting for order acknowledgments...")
        await asyncio.sleep(3)
        
        # Cancel event tracking
        event_task.cancel()
        try:
            await event_task
        except asyncio.CancelledError:
            pass
        
        # Summary
        print("\n=== Batch Order Summary ===")
        print(f"Total orders sent: {len(order_ids)}")
        print(f"Successful: {len(successful_orders)}")
        print(f"Rejected: {len(rejected_orders)}")
        
        # Check CPTY logs
        print("\n=== CPTY Processing ===")
        print("Check CPTY logs with: tmux capture-pane -t l_cpty -p | tail -50")
        
        # Final status
        print("\n=== Order Status ===")
        for order_id in order_ids:
            info = placed_orders[order_id]
            status = "✅ Placed" if order_id in successful_orders else "❌ Rejected" if order_id in rejected_orders else "⏳ Unknown"
            events = order_events[order_id]
            print(f"\n{order_id}: {status}")
            print(f"  {info['side']} {info['qty']} {info['symbol']} @ ${info['price']}")
            print(f"  Events: {', '.join(events) if events else 'None'}")
        
        # Leave orders open for checking
        print("\n📌 Orders left open - check frontend to verify they appear!")
        print(f"Account: {account_address}")
        print("\nTo cancel all orders later, run:")
        print("source venv/bin/activate && python -c \"import asyncio; from architect_py.async_client import AsyncClient; import os; from dotenv import load_dotenv; load_dotenv(); asyncio.run((lambda: AsyncClient.connect(endpoint=os.getenv('ARCHITECT_HOST'), api_key=os.getenv('ARCHITECT_API_KEY'), api_secret=os.getenv('ARCHITECT_API_SECRET'), paper_trading=False, use_tls=True).then(lambda c: c.cancel_all_orders(venue='LIGHTER')))())\"")
        
    except Exception as e:
        print(f"\n❌ Error placing batch order: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✅ Test completed")


if __name__ == "__main__":
    asyncio.run(main())