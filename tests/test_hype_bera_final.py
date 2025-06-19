#!/usr/bin/env python3
"""Test HYPE and BERA orders with correct market IDs."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_order(market_name: str, symbol: str, price: str, qty: str):
    """Test placing an order for a specific market."""
    cpty = LighterCptyServicer()
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print(f"\n{'='*60}")
    print(f"Testing {market_name}")
    print('='*60)
    
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("✗ Login failed")
        return False
    
    print("✓ Logged in")
    
    # Check market mapping
    if symbol in cpty.symbol_to_market_id:
        market_id = cpty.symbol_to_market_id[symbol]
        print(f"✓ {market_name} mapped to market ID {market_id}")
    else:
        print(f"✗ {symbol} not found in mappings")
        return False
    
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
    
    print(f"\nPlacing order:")
    print(f"  Buy {qty} {market_name} at ${price}")
    print(f"  Total value: ${float(price) * float(qty):.2f} USDC")
    
    try:
        response = await cpty._handle_request(MockPlaceRequest())
        
        if response and hasattr(response, 'reconcile_order'):
            exchange_id = response.reconcile_order.ord_id
            print(f"\n✓ SUCCESS! Order placed")
            print(f"  Exchange Order ID: {exchange_id}")
            
            # Cancel the order
            class MockCancel:
                cl_ord_id = order_id
                orig_cl_ord_id = order_id
            
            class MockCancelOrder:
                cancel = MockCancel()
            
            class MockCancelRequest:
                cancel_order = MockCancelOrder()
            
            print("\nCancelling order...")
            cancel_resp = await cpty._handle_request(MockCancelRequest())
            if cancel_resp:
                print("✓ Order cancelled")
            
            # Logout
            class MockLogoutRequest:
                logout = True
            
            await cpty._handle_request(MockLogoutRequest())
            return True
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    # Logout on failure
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())
    return False


async def main():
    """Test HYPE and BERA with correct market IDs."""
    print("=== HYPE and BERA Order Testing ===")
    print("\nUsing discovered market IDs:")
    print("- HYPE: Market ID 24 (min 0.50, 2 size decimals, 4 price decimals)")
    print("- BERA: Market ID 20 (min 3.0, 1 size decimal, 5 price decimals)")
    
    # Test configurations based on orderbook data
    tests = [
        # HYPE: min 0.50, 2 size decimals, 4 price decimals
        ("HYPE", "HYPE-USDC LIGHTER Perpetual/USDC Crypto", "20.00", "0.50"),
        # BERA: min 3.0, 1 size decimal, 5 price decimals  
        ("BERA", "BERA-USDC LIGHTER Perpetual/USDC Crypto", "0.50", "3.0"),
    ]
    
    results = []
    
    for market_name, symbol, price, qty in tests:
        success = await test_order(market_name, symbol, price, qty)
        results.append((market_name, success))
        await asyncio.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    for market_name, success in results:
        if success:
            print(f"✓ {market_name}: Successfully placed and cancelled order")
        else:
            print(f"✗ {market_name}: Failed to trade")
    
    print("\nNote: If orders fail, check:")
    print("1. Price is within acceptable range")
    print("2. Quantity meets minimum requirements")
    print("3. Account has sufficient balance")


if __name__ == "__main__":
    asyncio.run(main())