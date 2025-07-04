#!/usr/bin/env python3
"""Simple test to place LIGHTER order and check if it reaches CPTY."""
import asyncio
import os
import sys
from pathlib import Path
from decimal import Decimal
import uuid

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce


async def main():
    print("=== LIGHTER Order Flow Test ===")
    print(f"CPTY configured at: http://13.114.195.99:50051")
    print(f"Account: 2f018d76-5cf9-658a-b08e-a04f36782817")
    
    # Connect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Place order
    order_id = f"test-{uuid.uuid4().hex[:8]}"
    print(f"\nPlacing order: {order_id}")
    
    result = await client.place_order(
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        execution_venue="LIGHTER",
        order_id=order_id,
        dir=OrderDir.BUY,
        limit_price=Decimal("0.00001"),
        quantity=Decimal("100"),
        account="2f018d76-5cf9-658a-b08e-a04f36782817",
        time_in_force=TimeInForce.GTC,
        order_type="LIMIT",
        post_only=False,
    )
    
    print(f"✓ Order placed: {result.id}")
    print(f"  Status: {result.status}")
    
    print("\nNow check CPTY logs:")
    print("  tmux capture-pane -t lighter-cpty -p | tail -20")


if __name__ == "__main__":
    asyncio.run(main())