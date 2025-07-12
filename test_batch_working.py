#!/usr/bin/env python3
"""Test batch order placement with correct parameters."""
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
from architect_py.batch_place_order import BatchPlaceOrder

dotenv.load_dotenv()


async def main():
    print("=== Working Batch Order Test ===\n")
    
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
    
    # Create a batch of orders
    batch = BatchPlaceOrder()
    order_ids = []
    
    # Order 1: Buy FARTCOIN
    order1_id = f"batch1-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order1_id,  # Use order_id parameter
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.BUY,
        order_type="LIMIT",  # String, not enum
        limit_price=Decimal("1.20"),
        quantity=Decimal("10.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=False,
    )
    order_ids.append(order1_id)
    print(f"Order 1: BUY 10 FARTCOIN @ $1.20 (ID: {order1_id})")
    
    # Order 2: Sell FARTCOIN at higher price
    order2_id = f"batch2-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order2_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.SELL,
        order_type="LIMIT",
        limit_price=Decimal("1.25"),
        quantity=Decimal("10.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=False,
    )
    order_ids.append(order2_id)
    print(f"Order 2: SELL 10 FARTCOIN @ $1.25 (ID: {order2_id})")
    
    # Order 3: Buy BERA
    order3_id = f"batch3-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order3_id,
        symbol="BERA-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.BUY,
        order_type="LIMIT",
        limit_price=Decimal("1.84"),
        quantity=Decimal("5.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=False,
    )
    order_ids.append(order3_id)
    print(f"Order 3: BUY 5 BERA @ $1.84 (ID: {order3_id})")
    
    print(f"\n📦 Sending batch of {len(batch.place_orders)} orders...")
    
    # Place the batch order
    try:
        response = await client.place_batch_order(batch)
        print(f"\n✓ Batch order response received")
        
        # Check response
        if hasattr(response, 'order_rejects') and response.order_rejects:
            print(f"\n❌ {len(response.order_rejects)} orders rejected:")
            for reject in response.order_rejects:
                print(f"   - Order {reject.order_id}: {reject.reason}")
                
        if hasattr(response, 'pending_orders') and response.pending_orders:
            print(f"\n✅ {len(response.pending_orders)} orders pending:")
            for order in response.pending_orders:
                print(f"   - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
        
        # Wait a bit
        await asyncio.sleep(3)
        
        # Check orders
        print("\n📋 Checking orders...")
        try:
            orders = await client.get_orders(venue="LIGHTER")
            print(f"Found {len(orders)} total orders")
            
            # Find our orders
            our_orders = []
            for order in orders:
                for our_id in order_ids:
                    if our_id in str(order.id):
                        our_orders.append(order)
                        print(f"\n✓ Found order {our_id}:")
                        print(f"  Status: {order.status.name}")
                        print(f"  Symbol: {order.symbol}")
                        print(f"  Side: {order.dir.name}")
                        print(f"  Quantity: {order.quantity}")
                        print(f"  Price: ${order.limit_price}")
                        break
            
            # Cancel our orders
            if our_orders:
                print(f"\n🧹 Cancelling {len(our_orders)} orders...")
                for order in our_orders:
                    try:
                        await client.cancel_order(order.id, venue="LIGHTER")
                        print(f"  ✓ Cancelled {order.id}")
                    except Exception as e:
                        print(f"  ✗ Failed to cancel {order.id}: {e}")
                        
        except Exception as e:
            print(f"Error checking orders: {e}")
            
    except Exception as e:
        print(f"\n✗ Error placing batch order: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())