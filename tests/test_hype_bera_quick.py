#!/usr/bin/env python3
"""Quick test for HYPE and BERA with specific market IDs."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_orders():
    """Test HYPE and BERA orders."""
    cpty = LighterCptyServicer()
    
    print("=== Testing HYPE and BERA Orders ===\n")
    
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
        return
    
    print("   ✓ Logged in")
    
    # Test configurations
    # Based on the gap between NEAR (10) and FARTCOIN (21), let's try:
    test_markets = [
        ("HYPE", 12, "0.50"),   # Try $0.50 for HYPE
        ("HYPE", 13, "0.50"),
        ("HYPE", 14, "0.50"),
        ("BERA", 15, "0.10"),   # Try $0.10 for BERA
        ("BERA", 16, "0.10"),
        ("BERA", 17, "0.10"),
    ]
    
    successful = []
    
    for market_name, market_id, price in test_markets:
        print(f"\n2. Testing {market_name} with market ID {market_id}...")
        
        # Add to symbol mapping
        symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
        cpty.symbol_to_market_id[symbol] = market_id
        cpty.market_id_to_symbol[market_id] = symbol
        
        # Create order
        order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
        
        class MockOrder:
            cl_ord_id = order_id
            symbol = symbol
            dir = OrderDir.BUY
            price = price
            qty = "10"
            type = OrderType.LIMIT
            tif = TimeInForce.GTC
            reduce_only = False
            post_only = True
        
        class MockPlaceRequest:
            place_order = MockOrder()
        
        print(f"   Placing order: Buy 10 {market_name} at ${price}")
        
        try:
            response = await cpty._handle_request(MockPlaceRequest())
            if response and hasattr(response, 'reconcile_order'):
                exchange_id = response.reconcile_order.ord_id
                print(f"   ✓ SUCCESS! Order placed with exchange ID: {exchange_id}")
                successful.append((market_name, market_id, exchange_id))
                
                # Cancel the order
                class MockCancel:
                    cl_ord_id = order_id
                    orig_cl_ord_id = order_id
                
                class MockCancelOrder:
                    cancel = MockCancel()
                
                class MockCancelRequest:
                    cancel_order = MockCancelOrder()
                
                print(f"   Cancelling order...")
                await cpty._handle_request(MockCancelRequest())
                print(f"   ✓ Order cancelled")
                
                # Found the right market ID, skip other attempts for this token
                break
            else:
                print(f"   ✗ No response received")
                
        except Exception as e:
            error_msg = str(e)
            if "order price flagged" in error_msg:
                print(f"   ✗ Price rejected (might be correct market but wrong price)")
            else:
                print(f"   ✗ Error: {type(e).__name__}")
    
    # 3. Summary
    print("\n=== Summary ===")
    if successful:
        print("Successfully traded:")
        for name, market_id, exchange_id in successful:
            print(f"  ✓ {name}: Market ID {market_id}")
            print(f"    Exchange ID: {exchange_id}")
    else:
        print("Could not trade HYPE or BERA")
        print("Possible reasons:")
        print("  - They use different market IDs")
        print("  - They're not on Lighter mainnet")
        print("  - They require different price ranges")
    
    # 4. Logout
    class MockLogoutRequest:
        logout = True
    
    print("\nLogging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_orders())