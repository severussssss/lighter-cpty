#!/usr/bin/env python3
"""Test specific market IDs for HYPE and BERA."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def main():
    """Test HYPE and BERA with specific configurations."""
    cpty = LighterCptyServicer()
    
    print("=== Testing HYPE and BERA ===\n")
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("Login failed")
        return
    
    print("✓ Logged in successfully")
    print(f"✓ Available symbols in mapping: {len(cpty.symbol_to_market_id)}")
    
    # Print all available symbols
    print("\nAvailable markets:")
    for symbol, market_id in sorted(cpty.symbol_to_market_id.items(), key=lambda x: x[1]):
        print(f"  Market ID {market_id:2d}: {symbol}")
    
    # Now test HYPE and BERA if they're in the mappings
    test_orders = [
        ("HYPE-USDC LIGHTER Perpetual/USDC Crypto", "15.00", "1"),
        ("BERA-USDC LIGHTER Perpetual/USDC Crypto", "0.30", "10"),
    ]
    
    for symbol, price, qty in test_orders:
        if symbol not in cpty.symbol_to_market_id:
            print(f"\n✗ {symbol} not in mappings")
            continue
            
        market_id = cpty.symbol_to_market_id[symbol]
        market_name = symbol.split('-')[0]
        
        print(f"\n{'='*50}")
        print(f"Testing {market_name} (Market ID: {market_id})")
        print('='*50)
        
        # Place order
        order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
        
        class MockOrder:
            cl_ord_id = order_id
            symbol = symbol
            dir = OrderDir.BUY
            price = price
            qty = qty
            type = OrderType.LIMIT
            tif = TimeInForce.GTC
            reduce_only = False
            post_only = True
        
        class MockPlaceRequest:
            place_order = MockOrder()
        
        print(f"Placing order: Buy {qty} {market_name} at ${price}")
        
        try:
            response = await cpty._handle_request(MockPlaceRequest())
            
            if response and hasattr(response, 'reconcile_order'):
                print(f"✓ SUCCESS! Order placed")
                print(f"  Exchange ID: {response.reconcile_order.ord_id}")
                
                # Cancel order
                class MockCancel:
                    cl_ord_id = order_id
                    orig_cl_ord_id = order_id
                
                class MockCancelOrder:
                    cancel = MockCancel()
                
                class MockCancelRequest:
                    cancel_order = MockCancelOrder()
                
                print("Cancelling order...")
                await cpty._handle_request(MockCancelRequest())
                print("✓ Order cancelled")
                
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    print("\nLogging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())