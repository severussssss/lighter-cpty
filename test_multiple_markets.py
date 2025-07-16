#!/usr/bin/env python3
"""Test placing orders on HYPE, BTC, and 1000BONK markets using batch orders."""
import asyncio
import os
import uuid
from decimal import Decimal

import dotenv
from architect_py.async_client import AsyncClient
from architect_py import OrderDir, OrderType, TimeInForce, OrderStatus
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
    # AI16Z: price_decimals=5, size_decimals=1, min_base_amount=20.0
    # DOGE: price_decimals=6, size_decimals=0, min_base_amount=10
    # APT: price_decimals=4, size_decimals=2, min_base_amount=2.00
    # SEI: price_decimals=5, size_decimals=1, min_base_amount=50.0
    # CRV: price_decimals=5, size_decimals=1, min_base_amount=20.0
    # ENA: price_decimals=5, size_decimals=1, min_base_amount=20.0
    # S: price_decimals=5, size_decimals=1, min_base_amount=20.0
    
    test_configs = [
        # (symbol, base_symbol, price, quantity, side)
        ("HYPE", "HYPE", "54.1234", "0.5", OrderDir.SELL),  # 4 price decimals, 2 size decimals
        ("BTC", "BTC", "125432.1", "0.0002", OrderDir.SELL),  # 1 price decimal, 5 size decimals
        ("1000BONK", "1000BONK", "0.035678", "500", OrderDir.SELL),  # 6 price decimals, 0 size decimals
        #("AI16Z", "AI16Z", "1.23456", "20.0", OrderDir.SELL),  # 5 price decimals, 1 size decimal
        #("DOGE", "DOGE", "0.245678", "10", OrderDir.SELL),  # 6 price decimals, 0 size decimals
        #("APT", "APT", "14.5678", "2.00", OrderDir.SELL),  # 4 price decimals, 2 size decimals
        #("SEI", "SEI", "0.45432", "100.0", OrderDir.SELL),  # 5 price decimals, 1 size decimal
        #("CRV", "CRV", "0.84321", "40.0", OrderDir.SELL),  # 5 price decimals, 1 size decimal
        #("ENA", "ENA", "0.37654", "50.0", OrderDir.SELL),  # 5 price decimals, 1 size decimal
        ("S", "S", "0.52345", "20.0", OrderDir.SELL),  # 5 price decimals, 1 size decimal
    ]
    
    # Create batch
    batch = BatchPlaceOrder()
    order_ids = []
    
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
            order_id=order_id,  # Use order_id instead of id
            symbol=architect_symbol,
            dir=side,
            order_type=OrderType.LIMIT,
            limit_price=Decimal(price),
            quantity=Decimal(quantity),
            time_in_force=TimeInForce.GTC,
            execution_venue="LIGHTER",
            account=account_address,
            post_only=False,
        )
        order_ids.append(order_id)
    
    print(f"\n📨 Sending batch of {len(batch.place_orders)} orders...")
    
    # Place the batch order
    placed_order_ids = []
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
            # Store the actual order IDs
            for pending in response.pending_orders:
                placed_order_ids.append(pending.id)
                print(f"   - {pending.id}")
            
    except Exception as e:
        print(f"\n✗ Error placing batch order: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait for orders to be acknowledged
    print("\n⏳ Waiting 0.5s for order acknowledgment...")
    await asyncio.sleep(0.5)
    
    # Check order status before cancel
    print("\n=== Order Status Before Cancel ===")
    our_orders = []
    try:
        open_orders = await architect_client.get_open_orders(venue="LIGHTER")
        for order in open_orders:
            if order.id in placed_order_ids:
                our_orders.append(order)
                print(f"  {order.symbol}: {order.status} - {order.dir.name} {order.quantity} @ ${order.limit_price}")
        
        print(f"\nFound {len(our_orders)}/{len(placed_order_ids)} of our orders")
    except Exception as e:
        print(f"Error checking orders: {e}")
    
    # Cancel all orders
    print("\n=== Executing Cancel All ===")
    print("Calling cancel_all_orders() for LIGHTER venue with synthetic=False...")
    try:
        await architect_client.cancel_all_orders(execution_venue="LIGHTER", synthetic=False)
        print("✓ Cancel all request sent")
    except Exception as e:
        print(f"✗ Error sending cancel all: {e}")
    
    # Wait and check status after cancel
    print("\n⏳ Waiting 0.5s for cancellation to process...")
    await asyncio.sleep(0.5)
    
    # Check final order status
    print("\n=== Order Status After Cancel ===")
    still_open = []
    try:
        open_orders = await architect_client.get_open_orders(venue="LIGHTER")
        for order in open_orders:
            if order.id in placed_order_ids:
                still_open.append(order)
                print(f"  STILL OPEN: {order.symbol}: {order.status}")
        
        if len(still_open) == 0:
            print(f"✅ All {len(placed_order_ids)} orders successfully cancelled!")
        else:
            print(f"❌ {len(still_open)}/{len(placed_order_ids)} orders still open")
            
    except Exception as e:
        print(f"Error checking final status: {e}")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"• Orders placed: {len(placed_order_ids)}")
    print(f"• Orders found before cancel: {len(our_orders)}")
    print(f"• Orders remaining after cancel: {len(still_open)}")
    print(f"• Cancel success: {'YES' if len(still_open) == 0 else 'NO'}")
    
    print("\n=== Test Completed ===")
    print("Check CPTY logs for details:")
    print("tmux capture-pane -t l_c -p | tail -100")
    
    await architect_client.close()


if __name__ == "__main__":
    asyncio.run(main())