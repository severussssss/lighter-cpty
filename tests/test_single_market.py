#!/usr/bin/env python3
"""Test a single market quickly."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv
import sys

load_dotenv()


async def test_market(market_name: str, market_id: int):
    """Test a single market."""
    cpty = LighterCptyServicer()
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print(f"Testing {market_name} with market ID {market_id}...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("Login failed")
        return
    
    # Add market
    symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
    cpty.symbol_to_market_id[symbol] = market_id
    cpty.market_id_to_symbol[market_id] = symbol
    
    # Place order
    order_id = f"test_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = "0.01"  # Very low price
        qty = "10"
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    try:
        response = await cpty._handle_request(MockPlaceRequest())
        if response and hasattr(response, 'reconcile_order'):
            print(f"✓ SUCCESS! {market_name} order placed with market ID {market_id}")
            print(f"  Exchange ID: {response.reconcile_order.ord_id}")
            
            # Cancel it
            class MockCancel:
                cl_ord_id = order_id
                orig_cl_ord_id = order_id
            
            class MockCancelOrder:
                cancel = MockCancel()
            
            class MockCancelRequest:
                cancel_order = MockCancelOrder()
            
            await cpty._handle_request(MockCancelRequest())
            print("  Order cancelled")
        else:
            print(f"✗ Failed to place order")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_single_market.py <MARKET_NAME> <MARKET_ID>")
        print("Example: python test_single_market.py HYPE 12")
        sys.exit(1)
    
    market_name = sys.argv[1].upper()
    market_id = int(sys.argv[2])
    
    asyncio.run(test_market(market_name, market_id))