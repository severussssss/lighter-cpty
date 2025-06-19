#!/usr/bin/env python3
"""Test HYPE and BERA order placement on Lighter."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv
import lighter
from lighter import ApiClient, Configuration, RootApi

load_dotenv()


async def discover_markets():
    """Discover all available markets on Lighter."""
    print("=== Discovering Lighter Markets ===\n")
    
    # Create API client
    config = Configuration(host="https://mainnet.zklighter.elliot.ai")
    api_client = ApiClient(configuration=config)
    root_api = RootApi(api_client)
    
    try:
        # Get exchange info
        info = await root_api.info()
        
        if hasattr(info, 'markets') and info.markets:
            print(f"Found {len(info.markets)} markets:\n")
            
            # Sort by market ID
            sorted_markets = sorted(info.markets.items(), key=lambda x: int(x[0]))
            
            hype_found = False
            bera_found = False
            
            for market_id, market in sorted_markets:
                base = getattr(market, 'base_asset', 'Unknown')
                quote = getattr(market, 'quote_asset', 'USDC')
                
                # Print all markets
                print(f"Market ID {market_id}: {base}-{quote}")
                
                # Check for HYPE and BERA
                if base.upper() == 'HYPE':
                    hype_found = True
                    hype_market_id = int(market_id)
                    print(f"  ✓ Found HYPE market! ID: {hype_market_id}")
                elif base.upper() == 'BERA':
                    bera_found = True
                    bera_market_id = int(market_id)
                    print(f"  ✓ Found BERA market! ID: {bera_market_id}")
            
            print(f"\nHYPE market found: {hype_found}")
            print(f"BERA market found: {bera_found}")
            
            await api_client.close()
            return sorted_markets
            
    except Exception as e:
        print(f"Error discovering markets: {e}")
        await api_client.close()
        return []


async def test_market_orders(market_name: str, market_id: int):
    """Test order placement for a specific market."""
    cpty = LighterCptyServicer()
    
    print(f"\n=== Testing {market_name} Orders (Market ID: {market_id}) ===\n")
    
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
    
    print("   ✓ Logged in successfully")
    
    # Add the market to symbol mappings if not present
    symbol = f"{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
    if symbol not in cpty.symbol_to_market_id:
        cpty.symbol_to_market_id[symbol] = market_id
        cpty.market_id_to_symbol[market_id] = symbol
        print(f"   ✓ Added {symbol} to symbol mappings")
    
    # 2. Try to fetch current price
    print(f"\n2. Fetching {market_name} market info...")
    
    # We'll use a conservative price for testing
    test_price = "0.10"  # $0.10 per token
    test_qty = "100"     # 100 tokens
    
    print(f"   Using test price: ${test_price}")
    print(f"   Order size: {test_qty} {market_name}")
    
    # 3. Place order
    order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = symbol
        dir = OrderDir.BUY
        price = test_price
        qty = test_qty
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\n3. Placing {market_name} order...")
    print(f"   Order ID: {order_id}")
    print(f"   Buy {test_qty} {market_name} at ${test_price}")
    print(f"   Total value: ${float(test_price) * float(test_qty):.2f} USDC")
    
    response = await cpty._handle_request(MockPlaceRequest())
    exchange_id = None
    
    if response and hasattr(response, 'reconcile_order'):
        exchange_id = response.reconcile_order.ord_id
        print(f"   ✓ Order placed successfully!")
        print(f"   Exchange ID: {exchange_id}")
    else:
        print(f"   ✗ Failed to place order")
    
    # 4. Check open orders
    class MockReconcileOpenOrders:
        orders = []
    
    class MockOpenOrdersRequest:
        reconcile_open_orders = MockReconcileOpenOrders()
    
    print(f"\n4. Checking open orders...")
    response = await cpty._handle_request(MockOpenOrdersRequest())
    if response and hasattr(response, 'reconcile_open_orders'):
        orders = response.reconcile_open_orders.orders
        print(f"   Found {len(orders)} open order(s)")
        for order in orders:
            if market_name.lower() in order.cl_ord_id:
                print(f"   - {order.cl_ord_id}: {order.status}")
    
    # 5. Cancel order
    if exchange_id:
        class MockCancel:
            cl_ord_id = order_id
            orig_cl_ord_id = order_id
        
        class MockCancelOrder:
            cancel = MockCancel()
        
        class MockCancelRequest:
            cancel_order = MockCancelOrder()
        
        print(f"\n5. Cancelling {market_name} order...")
        response = await cpty._handle_request(MockCancelRequest())
        if response and hasattr(response, 'reconcile_order'):
            print(f"   ✓ Order cancelled successfully")
    
    # 6. Logout
    class MockLogoutRequest:
        logout = True
    
    print(f"\n6. Logging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print(f"\n=== {market_name} Test Complete ===")


async def test_manual_market_ids():
    """Test HYPE and BERA with guessed market IDs."""
    print("\n=== Testing with Guessed Market IDs ===")
    print("Trying market IDs 11-20 for HYPE and BERA...\n")
    
    # Common market IDs for new tokens
    potential_ids = {
        "HYPE": [11, 12, 13, 14, 15],
        "BERA": [16, 17, 18, 19, 20]
    }
    
    for market_name, ids in potential_ids.items():
        print(f"\nTrying {market_name} with market IDs: {ids}")
        
        for market_id in ids:
            try:
                await test_market_orders(market_name, market_id)
                break  # If successful, don't try other IDs
            except Exception as e:
                if "order price flagged" in str(e):
                    print(f"   Market ID {market_id} might be correct but price was wrong")
                else:
                    print(f"   Market ID {market_id} failed: {type(e).__name__}")
                continue


async def main():
    """Main test function."""
    print("=== HYPE and BERA Order Testing ===\n")
    
    # First, try to discover markets
    markets = await discover_markets()
    
    # Check if we found HYPE or BERA
    hype_id = None
    bera_id = None
    
    if markets:
        for market_id, market in markets:
            base = getattr(market, 'base_asset', 'Unknown')
            if base.upper() == 'HYPE':
                hype_id = int(market_id)
            elif base.upper() == 'BERA':
                bera_id = int(market_id)
    
    # Test the markets we found
    if hype_id:
        await test_market_orders("HYPE", hype_id)
    else:
        print("\n⚠️  HYPE market not found in API response")
    
    if bera_id:
        await test_market_orders("BERA", bera_id)
    else:
        print("\n⚠️  BERA market not found in API response")
    
    # If neither was found, try manual discovery
    if not hype_id and not bera_id:
        print("\n⚠️  Neither HYPE nor BERA found via API")
        print("Would you like to try manual market ID discovery? (This will attempt multiple orders)")
        # await test_manual_market_ids()  # Uncomment to try manual discovery


if __name__ == "__main__":
    asyncio.run(main())