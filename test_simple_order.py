#!/usr/bin/env python3
"""Simple test to place a single order to verify CPTY is working."""
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

dotenv.load_dotenv()


async def main():
    print("=== Simple Order Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Place a simple order
    try:
        order_id = str(uuid.uuid4())
        print(f"\nPlacing order {order_id[:8]}...")
        
        order = await client.place_order(
            id=order_id,
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.20"),
            quantity=Decimal("10.0"),
            time_in_force=TimeInForce.GTC,
            execution_venue="LIGHTER",
            post_only=False,
        )
        
        print(f"✓ Order placed successfully: {order}")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Check open orders
        print("\n📋 Checking open orders...")
        open_orders = await client.open_orders(venue="LIGHTER")
        print(f"Found {len(open_orders)} open orders")
        
        for o in open_orders:
            if o.id == order_id:
                print(f"✓ Found our order: {o.symbol} {o.dir.name} {o.quantity} @ ${o.limit_price}")
                
                # Cancel it
                print(f"\nCancelling order...")
                await client.cancel_order(order_id, venue="LIGHTER")
                print("✓ Cancel sent")
                break
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())