#!/usr/bin/env python3
"""Test placing orders on HYPE, BTC, and 1000BONK markets using batch orders."""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce
from architect_py.batch_place_order import BatchPlaceOrder

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
    print("=== Multiple Market Batch Order Test ===")
    
    # Initialize client
    architect_client = await get_default_architect_client()
    print("✓ Connected to Architect Core")
    
    # LIGHTER account from core config
    account_address = "2f018d76-5cf9-658a-b08e-a04f36782817"
    
    # Test configurations based on market data:
    # HYPE: price_decimals=4, size_decimals=2, min_base_amount=0.50
    # BTC: price_decimals=1, size_decimals=5, min_base_amount=0.00020
    # 1000BONK: price_decimals=6, size_decimals=0, min_base_amount=500
    
    test_configs = [
        # (symbol, base_symbol, price, quantity, side)
        ("HYPE", "HYPE", "54.1234", "0.5", OrderDir.SELL),  # 4 price decimals, 2 size decimals
        ("BTC", "BTC", "125432.1", "0.0002", OrderDir.SELL),  # 1 price decimal, 5 size decimals
        ("1000BONK", "1000BONK", "0.035678", "500", OrderDir.SELL),  # 6 price decimals, 0 size decimals
    ]
    
    # Create batch
    batch = BatchPlaceOrder()
    
    print("\n📦 Preparing batch orders:")
    for i, (symbol, base_symbol, price, quantity, side) in enumerate(test_configs, 1):
        order_id = f"{symbol.lower()}-{uuid.uuid4().hex[:8]}"
        architect_symbol = f"{base_symbol}-USDC LIGHTER Perpetual/USDC Crypto"
        
        print(f"\nOrder {i}: {symbol}")
        print(f"  Symbol: {architect_symbol}")
        print(f"  ID: {order_id}")
        print(f"  Side: {side.name}")
        print(f"  Quantity: {quantity}")
        print(f"  Price: {price}")
        
        await batch.place_order(
            order_id=order_id,
            symbol=architect_symbol,
            dir=side,
            order_type="LIMIT",
            limit_price=Decimal(price),
            quantity=Decimal(quantity),
            time_in_force=TimeInForce.GTC,
            execution_venue="LIGHTER",
            account=account_address,
            post_only=False,
        )
    
    print(f"\n📨 Sending batch of {len(batch.place_orders)} orders...")
    
    # Place the batch order
    try:
        response = await architect_client.place_batch_order(batch)
        print(f"\n✓ Batch order response received")
        
        # The response contains rejected orders and pending orders
        if hasattr(response, 'order_rejects') and response.order_rejects:
            print(f"\n❌ {len(response.order_rejects)} orders rejected:")
            for reject in response.order_rejects:
                print(f"   - Order {reject.order_id}: {reject.reason}")
                
        if hasattr(response, 'pending_orders') and response.pending_orders:
            print(f"\n✅ {len(response.pending_orders)} orders pending")
            
    except Exception as e:
        print(f"\n✗ Error placing batch order: {e}")
        import traceback
        traceback.print_exc()
    
    await asyncio.sleep(1)  # Wait for orders to process
    
    # Get open orders from Architect
    print("\n📋 Checking open orders...")
    try:
        open_orders = await architect_client.get_open_orders(venue="LIGHTER")
        import pdb;pdb.set_trace()
        # Filter for only Open status, exclude Pending
        truly_open_orders = [o for o in open_orders if o.status.name == "Open"]
        print(f"Found {len(truly_open_orders)} open LIGHTER orders (status=Open)")
        
        for order in truly_open_orders:
            print(f"  - {order.symbol}: {order.dir.name} {order.quantity} @ ${order.limit_price}")
    except Exception as e:
        print(f"Error getting open orders: {e}")
    
    print("\n=== All Tests Completed ===")
    print("Check CPTY logs for details:")
    print("tmux capture-pane -t l_cpty -p | tail -100")
    
    await architect_client.close()


if __name__ == "__main__":
    asyncio.run(main())