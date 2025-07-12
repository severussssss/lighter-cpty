#!/usr/bin/env python3
"""Debug batch order placement."""
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
    print("=== Debug Batch Order Test ===\n")
    
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
    
    # Create a simple batch with just one order
    batch = BatchPlaceOrder()
    
    # Single FARTCOIN order
    order_id = f"debug-{uuid.uuid4().hex[:8]}"
    await batch.place_order(
        order_id=order_id,
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        dir=OrderDir.BUY,
        order_type="LIMIT",
        limit_price=Decimal("1.19000"),  # Explicit decimal places
        quantity=Decimal("50.0"),
        account=account_address,
        time_in_force=TimeInForce.GTC,
        post_only=True,
    )
    print(f"Created order: BUY 50 FARTCOIN @ $1.19000 (ID: {order_id})")
    
    print(f"\n📦 Sending batch of 1 order...")
    
    try:
        response = await client.place_batch_order(batch)
        print("✅ Batch order response received")
        
        # Check response
        if hasattr(response, 'order_rejects') and response.order_rejects:
            print(f"\n❌ Order rejected:")
            for reject in response.order_rejects:
                print(f"   - Order {reject.order_id}: {reject.reason}")
                
        if hasattr(response, 'pending_orders') and response.pending_orders:
            print(f"\n✅ Order pending:")
            for order in response.pending_orders:
                print(f"   - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✅ Test completed")


if __name__ == "__main__":
    asyncio.run(main())