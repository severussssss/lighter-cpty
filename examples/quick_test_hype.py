#!/usr/bin/env python3
"""Quick test for HYPE."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()

async def main():
    cpty = LighterCptyServicer()
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    # Test HYPE with market ID 23 (common for new popular tokens)
    market_id = 23
    symbol = "HYPE-USDC LIGHTER Perpetual/USDC Crypto"
    cpty.symbol_to_market_id[symbol] = market_id
    cpty.market_id_to_symbol[market_id] = symbol
    
    # Place order
    order_id = f"hype_test_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = "15.00"  # HYPE is around $15-30
        qty = "1"
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\nTesting HYPE at market ID {market_id}...")
    print(f"Order: Buy 1 HYPE at $15.00")
    
    try:
        response = await cpty._handle_request(MockPlaceRequest())
        if response and hasattr(response, 'reconcile_order'):
            print(f"✓ SUCCESS! HYPE is market ID {market_id}")
            print(f"Exchange ID: {response.reconcile_order.ord_id}")
        else:
            print("✗ Failed")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())

asyncio.run(main())