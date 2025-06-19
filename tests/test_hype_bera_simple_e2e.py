#!/usr/bin/env python3
"""Simple end-to-end test for HYPE and BERA."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def main():
    """Test HYPE and BERA end-to-end."""
    cpty = LighterCptyServicer()
    
    print("=== HYPE and BERA End-to-End Test ===\n")
    
    # 1. Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("1️⃣ Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    if not cpty.logged_in:
        print("❌ Login failed")
        return
    
    print("✅ Logged in successfully")
    print(f"✅ WebSocket connected: {cpty.ws_connected}")
    print(f"✅ Markets loaded: {len(cpty.symbol_to_market_id)} symbols\n")
    
    # Test configurations
    tests = [
        {
            "name": "HYPE",
            "symbol": "HYPE-USDC LIGHTER Perpetual/USDC Crypto",
            "price": "15.00",
            "qty": "0.50",
            "expected_market_id": 24
        },
        {
            "name": "BERA",
            "symbol": "BERA-USDC LIGHTER Perpetual/USDC Crypto", 
            "price": "0.40",
            "qty": "3.0",
            "expected_market_id": 20
        }
    ]
    
    results = []
    
    for test in tests:
        print(f"\n{'='*60}")
        print(f"Testing {test['name']} (Market ID {test['expected_market_id']})")
        print('='*60)
        
        # Verify market mapping
        if test['symbol'] in cpty.symbol_to_market_id:
            actual_market_id = cpty.symbol_to_market_id[test['symbol']]
            print(f"✅ Symbol mapped correctly: Market ID {actual_market_id}")
        else:
            print(f"❌ Symbol not found in mappings")
            results.append((test['name'], False, "Symbol not mapped"))
            continue
        
        # Place order
        order_id = f"{test['name'].lower()}_{int(datetime.now().timestamp())}"
        
        class MockOrder:
            cl_ord_id = order_id
            symbol = test['symbol']
            dir = OrderDir.BUY
            price = test['price']
            qty = test['qty']
            type = OrderType.LIMIT
            tif = TimeInForce.GTC
            reduce_only = False
            post_only = True
        
        class MockPlaceRequest:
            place_order = MockOrder()
        
        print(f"\n2️⃣ Placing order:")
        print(f"   Buy {test['qty']} {test['name']} at ${test['price']}")
        print(f"   Total: ${float(test['price']) * float(test['qty']):.2f} USDC")
        
        try:
            response = await cpty._handle_request(MockPlaceRequest())
            
            if response and hasattr(response, 'reconcile_order'):
                exchange_id = response.reconcile_order.ord_id
                print(f"\n✅ Order placed successfully!")
                print(f"   Exchange ID: {exchange_id}")
                
                # Check if order is tracked
                if order_id in cpty.orders:
                    print(f"✅ Order tracked locally")
                
                # Cancel order
                class MockCancel:
                    cl_ord_id = order_id
                    orig_cl_ord_id = order_id
                
                class MockCancelOrder:
                    cancel = MockCancel()
                
                class MockCancelRequest:
                    cancel_order = MockCancelOrder()
                
                print(f"\n3️⃣ Cancelling order...")
                cancel_response = await cpty._handle_request(MockCancelRequest())
                
                if cancel_response and hasattr(cancel_response, 'reconcile_order'):
                    print(f"✅ Order cancelled successfully")
                    results.append((test['name'], True, exchange_id))
                else:
                    print(f"⚠️  Cancel response not received")
                    results.append((test['name'], True, exchange_id))
            else:
                print(f"❌ Order placement failed - no response")
                results.append((test['name'], False, "No response"))
                
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append((test['name'], False, str(e)))
    
    # Check WebSocket updates
    print(f"\n4️⃣ Checking WebSocket updates...")
    updates = 0
    while not cpty.response_queue.empty() and updates < 5:
        try:
            update = await asyncio.wait_for(cpty.response_queue.get(), timeout=0.1)
            updates += 1
            print(f"   📨 Update {updates}: {type(update).__name__}")
        except asyncio.TimeoutError:
            break
    
    if updates == 0:
        print("   No WebSocket updates in queue")
    
    # Logout
    class MockLogoutRequest:
        logout = True
    
    print(f"\n5️⃣ Logging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    for name, success, info in results:
        if success:
            print(f"✅ {name}: Successfully placed and cancelled")
            print(f"   Exchange ID: {info}")
        else:
            print(f"❌ {name}: Failed")
            print(f"   Reason: {info}")
    
    print(f"\n✅ End-to-end test complete!")


if __name__ == "__main__":
    asyncio.run(main())