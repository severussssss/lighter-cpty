#!/usr/bin/env python3
"""Test a single order rejection case."""
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
    print("\n=== Single Order Rejection Test ===")
    
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
    
    # Place order with price that triggers rejection
    order_id = f"reject-test-{int(time.time())}"
    price = "1.055"
    
    print(f"\nPlacing order:")
    print(f"  Order ID: {order_id}")
    print(f"  Price: ${price}")
    print(f"  Quantity: 20")
    
    result = await client.place_order(
        symbol=symbol,
        execution_venue="LIGHTER",
        order_id=order_id,
        dir=OrderDir.BUY,
        limit_price=Decimal(price),
        quantity=Decimal("20"),
        account=account,
        time_in_force=TimeInForce.GTC,
        order_type="LIMIT",
        post_only=False,
    )
    
    architect_order_id = result.id
    print(f"\n✓ Order placed:")
    print(f"  Architect ID: {architect_order_id}")
    print(f"  Initial status: {result.status}")
    
    # Monitor status changes
    print("\nMonitoring status...")
    prev_status = result.status
    
    for i in range(30):  # Check for 30 seconds
        await asyncio.sleep(1)
        
        orders = await client.get_open_orders(order_ids=[architect_order_id])
        
        if orders:
            order = orders[0]
            if order.status != prev_status:
                print(f"  Status changed: {prev_status} → {order.status}")
                prev_status = order.status
                
            # Check for rejection details
            if hasattr(order, 'reject_reason'):
                print(f"  Reject reason: {order.reject_reason}")
            if hasattr(order, 'reject_message'):
                print(f"  Reject message: {order.reject_message}")
                
            if order.status not in [OrderStatus.Pending, OrderStatus.Open]:
                break
        else:
            print(f"  Order no longer in open orders (after {i+1}s)")
            break
            
        if i % 5 == 4:
            print(f"  Still {prev_status} after {i+1}s")
    
    print("\n=== Check CPTY Logs ===")
    print("tmux capture-pane -t l_cpty -p | grep -A10 -B10 'reject-test'")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())