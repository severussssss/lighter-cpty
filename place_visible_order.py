#!/usr/bin/env python3
"""Place a single order with current market price."""
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
    print("=== Place Visible Order Test ===\n")
    
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
    
    try:
        # Use a reasonable price for FARTCOIN
        buy_price = Decimal("1.20")  # Safe price for FARTCOIN
        order_id = f"visible-{uuid.uuid4().hex[:8]}"
        
        print(f"\nPlacing BUY order...")
        print(f"Order ID: {order_id}")
        print(f"Price: ${buy_price}")
        print(f"Quantity: 100 FARTCOIN")
        
        order = await client.place_order(
            order_id=order_id,
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            execution_venue="LIGHTER",
            dir=OrderDir.BUY,
            limit_price=buy_price,
            quantity=Decimal("100.0"),
            account=account_address,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=True,  # Make sure it goes to the book
        )
        
        print(f"\n✅ Order placed successfully!")
        print(f"Architect Order ID: {order.id}")
        print(f"Status: {order.status}")
        
        print("\n⚠️  Check the frontend to see if this order appears")
        print(f"Account: {account_address}")
        print(f"Look for: BUY 100 FARTCOIN @ ${buy_price}")
        
        # Don't cancel - leave it open
        print("\n📌 Order left open - check frontend now!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())