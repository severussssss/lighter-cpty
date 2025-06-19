#!/usr/bin/env python3
"""Test HYPE and BERA with the updated market IDs."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_market(market_name: str, price: str):
    """Test a market that's now in the defaults."""
    cpty = LighterCptyServicer()
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print(f"\n{'='*50}")
    print(f"Testing {market_name}")
    print('='*50)
    
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("✗ Login failed")
        return False
    
    print("✓ Logged in")
    
    # Check if market is in the mappings
    symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
    if symbol in cpty.symbol_to_market_id:
        market_id = cpty.symbol_to_market_id[symbol]
        print(f"✓ {market_name} found in mappings: Market ID {market_id}")
    else:
        print(f"✗ {market_name} not found in mappings")
        return False
    
    # Place order
    order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = price
        qty = "1"
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\nPlacing order: Buy 1 {market_name} at ${price}")
    
    try:
        response = await cpty._handle_request(MockPlaceRequest())
        
        if response and hasattr(response, 'reconcile_order'):
            exchange_id = response.reconcile_order.ord_id
            print(f"\n✓ SUCCESS! {market_name} order placed!")
            print(f"  Market ID: {market_id}")
            print(f"  Exchange Order ID: {exchange_id}")
            
            # Cancel the order
            class MockCancel:
                cl_ord_id = order_id
                orig_cl_ord_id = order_id
            
            class MockCancelOrder:
                cancel = MockCancel()
            
            class MockCancelRequest:
                cancel_order = MockCancelOrder()
            
            print(f"\nCancelling order...")
            cancel_response = await cpty._handle_request(MockCancelRequest())
            if cancel_response:
                print("✓ Order cancelled")
            
            # Logout
            class MockLogoutRequest:
                logout = True
            
            await cpty._handle_request(MockLogoutRequest())
            return True
            
    except Exception as e:
        error_str = str(e)
        print(f"\n✗ Error: {error_str}")
        
        if "order price flagged" in error_str:
            print(f"  → Price ${price} might be too far from market price")
            print(f"  → Try a different price for {market_name}")
        elif "market is not found" in error_str:
            print(f"  → Market ID {market_id} doesn't exist on Lighter")
            print(f"  → {market_name} might use a different market ID")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())
    return False


async def main():
    """Test HYPE and BERA."""
    print("=== Testing HYPE and BERA Orders ===")
    print("\nMarkets have been added to defaults:")
    print("- HYPE: Market ID 11")
    print("- BERA: Market ID 12")
    
    # Test with reasonable prices
    tests = [
        ("HYPE", "20.00"),   # HYPE around $20-30
        ("BERA", "0.50"),    # BERA around $0.50
    ]
    
    results = []
    
    for market_name, price in tests:
        success = await test_market(market_name, price)
        results.append((market_name, success))
        await asyncio.sleep(1)
    
    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print('='*50)
    
    for market_name, success in results:
        if success:
            print(f"✓ {market_name}: Successfully traded")
        else:
            print(f"✗ {market_name}: Failed to trade")
    
    print("\nNOTE: If these fail with 'market not found', the market IDs")
    print("(11 for HYPE, 12 for BERA) are incorrect. You'll need to")
    print("find the correct market IDs for these tokens.")


if __name__ == "__main__":
    asyncio.run(main())