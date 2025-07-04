#!/usr/bin/env python3
"""Test order status query by order ID to check rejection status."""
import asyncio
import os
import sys
import time
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce, OrderStatus

dotenv.load_dotenv()


async def main():
    print("\n=== Order Status Query Test ===")
    print("Testing if order rejections are properly reflected\n")
    
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
    
    # Place an order with a price that will be rejected
    print("\n=== Placing Order with Rejectable Price ===")
    order_id = f"reject-test-{int(time.time())}"
    
    print(f"Order ID: {order_id}")
    print(f"Price: $1.055 (likely to be rejected)")
    
    try:
        result = await client.place_order(
            symbol=symbol,
            execution_venue="LIGHTER",
            order_id=order_id,
            dir=OrderDir.SELL,
            limit_price=Decimal("1.065"),  # Price that gets rejected
            quantity=Decimal("20"),
            account=account,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=False,
        )
        architect_order_id = result.id
        print(f"✓ Order placed: {architect_order_id}")
        print(f"Initial status: {result.status}")
    except Exception as e:
        print(f"✗ Failed to place order: {e}")
        await client.close()
        return

    
    # Also try to get historical orders to see if rejected orders appear there
    print("\n=== Checking Historical Orders ===")
    try:
        # Note: This method might not exist or might require different parameters
        if hasattr(client, 'get_historical_orders'):
            historical = await client.get_historical_orders(
                account="2f018d76-5cf9-658a-b08e-a04f36782817",
                # order_ids=[architect_order_id],
                #limit=10
            )
            import pdb;pdb.set_trace()
            if historical:
                print(f"Found in historical orders: {len(historical)} orders")
                for order in historical:
                    print(f"  ID: {order.id}, Status: {order.status}")
        else:
            print("Historical orders method not available")
    except Exception as e:
        print(f"Could not fetch historical orders: {e}")
    
    # Final check of all open orders
    print("\n=== Final Open Orders Check ===")
    all_orders = await client.get_open_orders(venue="LIGHTER")
    our_order = next((o for o in all_orders if o.id == architect_order_id), None)
    
    if our_order:
        print(f"Order still in open orders with status: {our_order.status}")
    else:
        print("Order no longer in open orders (likely rejected)")
    
    print("\n=== Test Complete ===")
    print("\nTo check CPTY logs for rejection details:")
    print("tmux capture-pane -t l_cpty -p | grep -E 'ERROR|reject|1\\.055' | tail -20")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())