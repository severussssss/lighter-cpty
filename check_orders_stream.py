#!/usr/bin/env python3
"""Check orders via streaming."""
import asyncio
import os
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("=== Checking Orders via Stream ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    try:
        print("\n📊 Streaming order events...")
        print("Waiting for order events (10 seconds)...\n")
        
        orders_seen = defaultdict(lambda: {"events": [], "last_status": None})
        event_count = 0
        
        async def track_orders():
            nonlocal event_count
            try:
                async for event in client.stream_orderflow():
                    event_count += 1
                    event_type = type(event).__name__
                    
                    order_id = None
                    if hasattr(event, 'order_id'):
                        order_id = event.order_id
                    elif hasattr(event, 'order') and hasattr(event.order, 'id'):
                        order_id = event.order.id
                    
                    if order_id:
                        orders_seen[order_id]["events"].append(event_type)
                        
                        if hasattr(event, 'order'):
                            order = event.order
                            orders_seen[order_id]["order"] = order
                            if hasattr(order, 'status'):
                                orders_seen[order_id]["last_status"] = order.status.name
                        
                        # Print live event
                        print(f"📍 {event_type}: Order {order_id}")
                        if hasattr(event, 'order'):
                            order = event.order
                            print(f"   Symbol: {order.symbol}, Side: {order.dir.name}, Status: {getattr(order.status, 'name', 'Unknown')}")
                        if event_type == "OrderReject" and hasattr(event, 'reason'):
                            print(f"   ❌ Reject reason: {event.reason}")
                        print()
                    
            except Exception as e:
                print(f"Stream error: {e}")
        
        # Run for limited time
        task = asyncio.create_task(track_orders())
        await asyncio.sleep(10)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        print(f"\n=== Summary ===")
        print(f"Total events received: {event_count}")
        print(f"Unique orders seen: {len(orders_seen)}")
        
        if orders_seen:
            print("\n=== Orders by Status ===")
            by_status = defaultdict(list)
            for order_id, info in orders_seen.items():
                status = info.get("last_status", "Unknown")
                by_status[status].append((order_id, info))
            
            for status, orders in by_status.items():
                print(f"\n{status}: {len(orders)} orders")
                for order_id, info in orders[:3]:  # Show first 3
                    print(f"  - {order_id}")
                    if "order" in info:
                        order = info["order"]
                        print(f"    {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
                    print(f"    Events: {', '.join(info['events'][:5])}")
                    if len(orders) > 3:
                        print(f"  ... and {len(orders) - 3} more")
        else:
            print("\n❌ No order events received")
            print("Try placing some orders or check if CPTY is connected")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Done")


if __name__ == "__main__":
    asyncio.run(main())