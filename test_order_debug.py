#!/usr/bin/env python3
"""Debug order placement issue."""
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
    print("=== Order Debug Test ===\n")
    
    # Connect to Architect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Try different order formats
    order_id = str(uuid.uuid4())
    
    # Test 1: Using Decimal values
    try:
        print("\nTest 1: Using Decimal values...")
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
    except Exception as e:
        print(f"✗ Failed with Decimal: {e}")
        
        # Test 2: Try without execution_venue
        try:
            print("\nTest 2: Without execution_venue...")
            order_id2 = str(uuid.uuid4())
            order = await client.place_order(
                id=order_id2,
                symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
                dir=OrderDir.BUY,
                order_type=OrderType.LIMIT,
                limit_price=Decimal("1.20"),
                quantity=Decimal("10.0"),
                time_in_force=TimeInForce.GTC,
                post_only=False,
            )
            print(f"✓ Order placed successfully: {order}")
        except Exception as e2:
            print(f"✗ Failed without venue: {e2}")
            
            # Test 3: Try minimal order
            try:
                print("\nTest 3: Minimal order...")
                order_id3 = str(uuid.uuid4())
                order = await client.place_order(
                    symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
                    dir=OrderDir.BUY,
                    quantity="10.0",
                    limit_price="1.20",
                )
                print(f"✓ Order placed successfully: {order}")
            except Exception as e3:
                print(f"✗ Failed minimal: {e3}")
    
    await client.close()
    print("\n✓ Test completed")


if __name__ == "__main__":
    asyncio.run(main())