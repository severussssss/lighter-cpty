#!/usr/bin/env python3
"""Check open orders on Lighter."""
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
    print("=== Checking Open Orders ===\n")
    
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
        # Get all orders
        print("\n📋 Fetching all orders...")
        orders = await client.get_orders()
        print(f"Total orders: {len(orders)}")
        
        # Filter for open/pending orders
        open_orders = [o for o in orders if o.status.name in ["OPEN", "PENDING", "Open", "Pending"]]
        print(f"Open/Pending orders: {len(open_orders)}")
        
        if open_orders:
            print("\n=== Open Orders ===")
            for i, order in enumerate(open_orders[:10], 1):  # Show first 10
                print(f"\n{i}. Order ID: {order.id}")
                print(f"   Symbol: {order.symbol}")
                print(f"   Side: {order.dir.name}")
                print(f"   Quantity: {order.quantity}")
                print(f"   Price: ${order.limit_price}")
                print(f"   Status: {order.status.name}")
                print(f"   Time: {order.recv_time}")
        else:
            print("\n❌ No open orders found")
            
        # Also check recent orders
        print("\n=== Recent Orders (last 5) ===")
        recent_orders = sorted(orders, key=lambda x: x.recv_time, reverse=True)[:5]
        for i, order in enumerate(recent_orders, 1):
            print(f"\n{i}. Order ID: {order.id}")
            print(f"   Symbol: {order.symbol}")
            print(f"   Side: {order.dir.name}")
            print(f"   Status: {order.status.name}")
            print(f"   Filled: {order.filled_quantity}/{order.quantity}")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Done")


if __name__ == "__main__":
    asyncio.run(main())