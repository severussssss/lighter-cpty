#!/usr/bin/env python3
"""Test HYPE and BERA by trying different market IDs directly."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_market(market_name: str, market_id: int, price: str):
    """Test a specific market ID."""
    cpty = LighterCptyServicer()
    
    # Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print(f"\nTesting {market_name} at market ID {market_id}...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("Login failed")
        return False
    
    # Manually add the market mapping
    symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
    cpty.symbol_to_market_id[symbol] = market_id
    cpty.market_id_to_symbol[market_id] = symbol
    
    # Also add to markets dict to handle decimal precision
    cpty.markets[market_id] = {
        'base_asset': market_name,
        'quote_asset': 'USDC'
    }
    
    # Try placing an order
    order_id = f"{market_name.lower()}_{market_id}_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = price
        qty = "1"  # Small quantity
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    try:
        print(f"Placing order: Buy 1 {market_name} at ${price}")
        response = await cpty._handle_request(MockPlaceRequest())
        
        if response and hasattr(response, 'reconcile_order'):
            exchange_id = response.reconcile_order.ord_id
            print(f"✓ SUCCESS! {market_name} = Market ID {market_id}")
            print(f"  Exchange Order ID: {exchange_id}")
            
            # Cancel the order
            class MockCancel:
                cl_ord_id = order_id
                orig_cl_ord_id = order_id
            
            class MockCancelOrder:
                cancel = MockCancel()
            
            class MockCancelRequest:
                cancel_order = MockCancelOrder()
            
            await cpty._handle_request(MockCancelRequest())
            print("  Order cancelled")
            
            # Logout
            class MockLogoutRequest:
                logout = True
            
            await cpty._handle_request(MockLogoutRequest())
            return True
        else:
            print("✗ No response")
            
    except Exception as e:
        error_str = str(e)
        if "order price flagged" in error_str:
            print(f"✗ Price rejected - market might exist but price ${price} is wrong")
            print("  (Try a different price)")
        elif "market is not found" in error_str:
            print(f"✗ Market ID {market_id} not found")
        else:
            print(f"✗ Error: {error_str[:100]}")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    await cpty._handle_request(MockLogoutRequest())
    return False


async def main():
    """Test HYPE and BERA with various market IDs."""
    print("=== Testing HYPE and BERA Market IDs ===")
    print("\nSince FARTCOIN was at ID 21 (not in sequence),")
    print("HYPE and BERA might also be at unexpected IDs.\n")
    
    # Test configurations with different prices
    test_configs = [
        # HYPE - try different IDs and prices
        ("HYPE", 11, "10.00"),
        ("HYPE", 12, "10.00"),
        ("HYPE", 13, "10.00"),
        ("HYPE", 14, "10.00"),
        ("HYPE", 15, "10.00"),
        ("HYPE", 22, "10.00"),  # After FARTCOIN
        ("HYPE", 23, "10.00"),
        ("HYPE", 24, "10.00"),
        ("HYPE", 25, "10.00"),
        
        # BERA - try different IDs and prices
        ("BERA", 11, "0.10"),
        ("BERA", 12, "0.10"),
        ("BERA", 13, "0.10"),
        ("BERA", 14, "0.10"),
        ("BERA", 15, "0.10"),
        ("BERA", 16, "0.10"),
        ("BERA", 17, "0.10"),
        ("BERA", 18, "0.10"),
        ("BERA", 19, "0.10"),
        ("BERA", 20, "0.10"),
        ("BERA", 26, "0.10"),  # Try higher IDs
        ("BERA", 27, "0.10"),
    ]
    
    found = {}
    
    for market_name, market_id, price in test_configs:
        # Skip if we already found this market
        if market_name in found:
            continue
            
        success = await test_market(market_name, market_id, price)
        if success:
            found[market_name] = market_id
        
        await asyncio.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n=== Results ===")
    if found:
        print("Found markets:")
        for name, market_id in found.items():
            print(f"  ✓ {name}: Market ID {market_id}")
            
        # Show how to add to defaults
        print("\nTo add these to the defaults, update lighter_cpty.py:")
        print("```python")
        print("default_markets = [")
        print("    # ... existing markets ...")
        for name, market_id in found.items():
            print(f'    ({market_id}, "{name}", "USDC"),')
        print("]")
        print("```")
    else:
        print("Could not find HYPE or BERA")
        print("\nThey might:")
        print("- Use market IDs > 27")
        print("- Require different decimal precision")
        print("- Need exact price ranges to avoid 'accidental price' errors")


if __name__ == "__main__":
    asyncio.run(main())