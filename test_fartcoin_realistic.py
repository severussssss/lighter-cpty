#!/usr/bin/env python3
"""Test placing a FARTCOIN order with realistic price."""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent))
# sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

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
    print("=== FARTCOIN Order Test (Realistic Price) ===")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # LIGHTER account from core config
    account_address = "2f018d76-5cf9-658a-b08e-a04f36782817"
    architect_symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
    
    # Order parameters - using a more realistic price
    order_id = f"fart-{uuid.uuid4().hex[:8]}"
    limit_price = Decimal("1.255")  # More realistic price for FARTCOIN
    amount = Decimal("20")
    
    print(f"\n=== Placing Order ===")
    print(f"Order ID: {order_id}")
    print(f"Symbol: {architect_symbol}")
    print(f"Account: {account_address}")
    print(f"Side: SELL")
    print(f"Quantity: {amount}")
    print(f"Price: {limit_price}")
    
    # Place order
    try:
        place_order_result = await architect_client.place_order(
            symbol=architect_symbol,
            execution_venue="LIGHTER",
            order_id=order_id,
            dir=OrderDir.SELL, #OrderDir.BUY,
            limit_price=limit_price,
            quantity=amount,
            account=account_address,
            time_in_force=TimeInForce.GTC,
            order_type="LIMIT",
            post_only=False,
        )
        
        print(f"Architect Order ID: {place_order_result.id}")
        await asyncio.sleep(1)
        status = await architect_client.get_order(place_order_result.id)
        print(f"Status: {status}")
        import pdb; pdb.set_trace()
        
        # Wait for order to process
        await asyncio.sleep(5)
        
        # Check order status
        try:
            orders = await architect_client.get_orders()
            our_order = next((o for o in orders if order_id in str(o.id)), None)
            if our_order:
                print(f"\n=== Order Status ===")
                print(f"Status: {our_order.status}")
                print(f"Filled quantity: {getattr(our_order, 'filled_quantity', 0)}")
        except:
            pass
            
    except Exception as e:
        print(f"\n✗ Order failed: {e}")
    
    print("\n=== Check CPTY Logs ===")
    print("Run: tmux capture-pane -t lighter-cpty -p | tail -50")
    

if __name__ == "__main__":
    asyncio.run(main())