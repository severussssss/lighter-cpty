#!/usr/bin/env python3
"""Test order placement with correct parameters."""
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
from architect_py import OrderDir, TimeInForce

dotenv.load_dotenv()


async def main():
    print("=== Fixed Order Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Use the correct parameters
    order_id = f"test-{uuid.uuid4().hex[:8]}"
    account_address = os.getenv("LIGHTER_ACCOUNT_ADDRESS", "2f018d76-5cf9-658a-b08e-a04f36782817")
    
    try:
        print(f"\nPlacing order {order_id}...")
        print(f"Symbol: FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto")
        print(f"Side: BUY")
        print(f"Quantity: 10.0")
        print(f"Price: $1.20")
        
        order = await client.place_order(
            order_id=order_id,  # Use order_id, not id
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            execution_venue="LIGHTER",
            dir=OrderDir.BUY,
            limit_price=Decimal("1.20"),
            quantity=Decimal("10.0"),
            account=account_address,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",  # String, not enum
            post_only=False,
        )
        
        print(f"\n✓ Order placed successfully!")
        print(f"Order ID: {order.id}")
        print(f"Status: {order.status}")
        
        # Wait and check status
        await asyncio.sleep(2)
        
        # Get open orders
        print("\n📋 Checking open orders...")
        open_orders = await client.open_orders(venue="LIGHTER")
        print(f"Found {len(open_orders)} open orders")
        
        our_order = None
        for o in open_orders:
            if str(o.id) == order_id or order_id in str(o.id):
                our_order = o
                print(f"\n✓ Found our order:")
                print(f"  Symbol: {o.symbol}")
                print(f"  Side: {o.dir.name}")
                print(f"  Quantity: {o.quantity}")
                print(f"  Price: ${o.limit_price}")
                print(f"  Status: {o.status.name}")
                break
        
        # Cancel the order
        if our_order:
            print(f"\n🧹 Cancelling order...")
            await client.cancel_order(order.id, venue="LIGHTER")
            print("✓ Cancel sent")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())