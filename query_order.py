#!/usr/bin/env python3
"""Query order status via Architect client."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

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
    # Get order ID from command line or use default
    order_id = sys.argv[1] if len(sys.argv) > 1 else "a5e06eb6-69a5-48cb-95b8-5ef1e744bd17:0"
    
    print(f"=== Querying Order Status ===")
    print(f"Order ID: {order_id}")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # Query specific order
    print(f"\n--- Querying order {order_id} ---")
    try:
        order = await architect_client.get_order(order_id)
        if order:
            print(f"Order found!")
            print(f"  ID: {order.id}")
            print(f"  Status: {order.status}")
            print(f"  Symbol: {order.symbol}")
            print(f"  Side: {order.dir}")
            print(f"  Quantity: {order.quantity}")
            print(f"  Limit Price: {order.limit_price}")
            print(f"  Filled Quantity: {getattr(order, 'filled_quantity', 'N/A')}")
            print(f"  Account: {order.account}")
            print(f"  Reject Reason: {getattr(order, 'reject_reason', 'N/A')}")
            print(f"  Reject Message: {getattr(order, 'reject_message', 'N/A')}")
        else:
            print("Order not found (returned None/empty)")
    except Exception as e:
        print(f"Error querying order: {e}")
    
    # Try to get multiple orders by providing a list of IDs
    print("\n--- Checking Multiple Order IDs ---")
    try:
        # Try with a list of order IDs including the one we're looking for
        order_ids = [order_id]
        orders = await architect_client.get_orders(order_ids)
        if orders:
            print(f"Found {len(orders)} orders:")
            print(f"Type of orders: {type(orders)}")
            print(f"Orders content: {orders}")
            # Handle different possible return types
            if isinstance(orders, list):
                for i, order in enumerate(orders):
                    print(f"  Order {i}: type={type(order)}")
                    if order is not None:
                        # Try different ways to access order info
                        if hasattr(order, 'id'):
                            print(f"    ID: {order.id}")
                        if hasattr(order, 'status'):
                            print(f"    Status: {order.status}")
                        print(f"    Full order: {order}")
                    else:
                        print(f"    Order {i} is None")
        else:
            print("No orders found with get_orders()")
    except Exception as e:
        print(f"Error with get_orders: {e}")
        import traceback
        traceback.print_exc()
    
    # Try different order ID formats
    print("\n--- Trying Different ID Formats ---")
    # Try without the :0 suffix
    base_id = order_id.split(':')[0]
    try:
        order = await architect_client.get_order(base_id)
        if order:
            print(f"Found with base ID {base_id}: {order.status}")
        else:
            print(f"Not found with base ID: {base_id}")
    except Exception as e:
        print(f"Error with base ID: {e}")


if __name__ == "__main__":
    asyncio.run(main())