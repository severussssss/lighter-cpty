#!/usr/bin/env python3
"""Simple test for HYPE and BERA orders with guessed market IDs."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_order(market_name: str, market_id: int, test_price: str):
    """Test placing an order for a specific market."""
    cpty = LighterCptyServicer()
    
    print(f"\n=== Testing {market_name} (Market ID: {market_id}) ===")
    
    # 1. Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("1. Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("   ✗ Login failed")
        return False
    
    # Add market to mappings
    symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
    cpty.symbol_to_market_id[symbol] = market_id
    cpty.market_id_to_symbol[market_id] = symbol
    
    # 2. Place order
    order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = test_price
        qty = "10"  # Small quantity
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\n2. Placing {market_name} order...")
    print(f"   Order: Buy 10 {market_name} at ${test_price}")
    
    try:
        response = await cpty._handle_request(MockPlaceRequest())
        if response and hasattr(response, 'reconcile_order'):
            print(f"   ✓ Order placed! Exchange ID: {response.reconcile_order.ord_id}")
            
            # Cancel the order
            class MockCancel:
                cl_ord_id = order_id
                orig_cl_ord_id = order_id
            
            class MockCancelOrder:
                cancel = MockCancel()
            
            class MockCancelRequest:
                cancel_order = MockCancelOrder()
            
            print(f"\n3. Cancelling order...")
            await cpty._handle_request(MockCancelRequest())
            print(f"   ✓ Order cancelled")
            
            # Logout
            class MockLogoutRequest:
                logout = True
            
            await cpty._handle_request(MockLogoutRequest())
            return True
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
        
    # Logout on failure
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())
    return False


async def main():
    """Test HYPE and BERA with various market IDs."""
    print("=== HYPE and BERA Order Testing ===")
    print("Testing potential market IDs 11-20...")
    
    # Test configurations
    # Using very low prices to avoid "accidental price" errors
    test_configs = [
        # HYPE tests
        ("HYPE", 11, "0.01"),
        ("HYPE", 12, "0.01"),
        ("HYPE", 13, "0.01"),
        ("HYPE", 14, "0.01"),
        ("HYPE", 15, "0.01"),
        # BERA tests
        ("BERA", 16, "0.01"),
        ("BERA", 17, "0.01"),
        ("BERA", 18, "0.01"),
        ("BERA", 19, "0.01"),
        ("BERA", 20, "0.01"),
    ]
    
    # Track successful markets
    successful = []
    
    for market_name, market_id, test_price in test_configs:
        success = await test_order(market_name, market_id, test_price)
        if success:
            successful.append((market_name, market_id))
            print(f"\n✓ {market_name} works with market ID {market_id}!")
            break  # Stop testing other IDs for this market
        await asyncio.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n=== Summary ===")
    if successful:
        print("Successfully traded:")
        for name, id in successful:
            print(f"  - {name}: Market ID {id}")
    else:
        print("Neither HYPE nor BERA could be traded with market IDs 11-20")
        print("They might:")
        print("  - Use different market IDs")
        print("  - Not be listed on Lighter mainnet")
        print("  - Require different decimal precision")


if __name__ == "__main__":
    asyncio.run(main())