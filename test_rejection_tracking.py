#!/usr/bin/env python3
"""Test order rejection tracking and status updates."""
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


async def test_rejection():
    print("\n=== Order Rejection Test ===")
    print("Testing multiple price points to see rejection handling\n")
    
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
    
    # Test different prices
    test_cases = [
        ("1.055", "Likely rejected as accidental price"),
        ("0.001", "Very low price - might be rejected"),
        ("1000.0", "Very high price - might be rejected"),
        ("1.19", "Near market price - should work"),
    ]
    
    results = []
    
    for price, description in test_cases:
        print(f"\n--- Testing Price: ${price} ---")
        print(f"Description: {description}")
        
        order_id = f"reject-{price}-{int(time.time())}"
        
        try:
            # Place order
            result = await client.place_order(
                symbol=symbol,
                execution_venue="LIGHTER",
                order_id=order_id,
                dir=OrderDir.BUY,
                limit_price=Decimal(price),
                quantity=Decimal("10"),
                account=account,
                time_in_force=TimeInForce.GTC,
                order_type="LIMIT",
                post_only=False,
            )
            
            architect_order_id = result.id
            print(f"✓ Order placed: {architect_order_id}")
            print(f"Initial status: {result.status}")
            
            # Wait a bit for processing
            await asyncio.sleep(2)
            
            # Check status
            orders = await client.get_open_orders(order_ids=[architect_order_id])
            
            if orders:
                order = orders[0]
                final_status = order.status
                print(f"Final status: {final_status}")
                
                # Try to cancel if still open
                if final_status == OrderStatus.Open:
                    try:
                        await client.cancel_order(order_id=architect_order_id)
                        print("✓ Order cancelled")
                    except:
                        pass
            else:
                final_status = "NOT_FOUND"
                print("Final status: NOT FOUND (possibly rejected)")
            
            results.append({
                "price": price,
                "order_id": order_id,
                "architect_id": architect_order_id,
                "status": final_status,
                "description": description
            })
            
        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({
                "price": price,
                "order_id": order_id,
                "architect_id": "N/A",
                "status": "ERROR",
                "description": str(e)
            })
    
    # Summary
    print("\n=== Summary ===")
    print(f"{'Price':<10} {'Status':<15} {'Description'}")
    print("-" * 60)
    for r in results:
        print(f"${r['price']:<9} {str(r['status']):<15} {r['description']}")
    
    print("\n=== CPTY Log Check ===")
    print("Run this to see CPTY rejection messages:")
    print("tmux capture-pane -t l_cpty -p -S -1000 | grep -E 'reject|ERROR|accidental' | tail -30")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_rejection())