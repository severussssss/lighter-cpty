#!/usr/bin/env python3
"""Test cancelling orders through Architect - minimal version without get_open_orders."""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce

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
    print("=== Testing Order Cancel Functionality (Minimal) ===\n")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # LIGHTER account from core config
    account_address = "2f018d76-5cf9-658a-b08e-a04f36782817"
    architect_symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
    
    # Place a test order
    order_id = f"cancel-test-{uuid.uuid4().hex[:8]}"
    limit_price = Decimal("0.81")  # Very low price so it won't fill
    amount = Decimal("100")  # Same as fartcoin test
    
    print(f"\n=== Step 1: Placing Test Order ===")
    print(f"Order ID: {order_id}")
    print(f"Symbol: {architect_symbol}")
    print(f"Side: BUY")
    print(f"Quantity: {amount}")
    print(f"Price: {limit_price} (very low price to avoid fill)")
    
    try:
        # Place order
        place_result = await architect_client.place_order(
            symbol=architect_symbol,
            execution_venue="LIGHTER",
            order_id=order_id,
            dir=OrderDir.BUY,
            limit_price=limit_price,
            quantity=amount,
            account=account_address,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=False,
        )
        
        print(f"\n✓ Order placed successfully!")
        print(f"Architect Order ID: {place_result.id}")
        print(f"Status: {place_result.status}")
        
        # Wait for order to be acknowledged
        print("\nWaiting for order to be processed...")
        await asyncio.sleep(2)
        
        # Cancel the order
        print(f"\n=== Step 2: Cancelling Order ===")
        print(f"Cancelling order: {place_result.id}")
        
        cancel_result = await architect_client.cancel_order(
            order_id=place_result.id
        )
        
        print(f"\n✓ Cancel request sent!")
        print(f"Cancel ID: {cancel_result.id}")
        print(f"Status: {cancel_result.status}")
        
        # Wait for cancellation to process
        print("\nWaiting for cancellation to process...")
        await asyncio.sleep(5)
        
        print("\n✓ Test completed. Check CPTY logs to verify cancellation.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Check CPTY Logs ===")
    print(f"Run: tail -n 100 cpty.log | grep -E '({order_id}|cancel)' | tail -20")
    
    await architect_client.close()


if __name__ == "__main__":
    asyncio.run(main())