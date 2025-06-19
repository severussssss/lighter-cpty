#!/usr/bin/env python3
"""Simple test of FARTCOIN order lifecycle."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_order():
    """Test FARTCOIN order lifecycle."""
    cpty = LighterCptyServicer()
    
    print("=== FARTCOIN Order Test ===\n")
    
    # 1. Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("1. Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)
    
    print(f"   Logged in: {cpty.logged_in}")
    print(f"   WebSocket: {cpty.ws_connected}")
    
    # 2. Place FARTCOIN order
    order_id = f"fartcoin_{int(datetime.now().timestamp())}"
    
    class MockOrder:
        cl_ord_id = order_id
        symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
        dir = OrderDir.BUY
        price = "1.09"
        qty = "20"
        type = OrderType.LIMIT
        tif = TimeInForce.GTC
        reduce_only = False
        post_only = True
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\n2. Placing order {order_id}...")
    response = await cpty._handle_request(MockPlaceRequest())
    if response and hasattr(response, 'reconcile_order'):
        print(f"   ✓ Order placed: {response.reconcile_order.ord_id}")
    
    # 3. Check open orders
    print("\n3. Checking open orders...")
    print(f"   Tracked orders: {len(cpty.orders)}")
    for cl_ord_id, order in cpty.orders.items():
        print(f"   - {cl_ord_id}: ${order.price} x {order.qty}")
    
    # 4. Cancel order
    class MockCancel:
        cl_ord_id = order_id
        orig_cl_ord_id = order_id
    
    class MockCancelOrder:
        cancel = MockCancel()
    
    class MockCancelRequest:
        cancel_order = MockCancelOrder()
    
    print(f"\n4. Cancelling order...")
    response = await cpty._handle_request(MockCancelRequest())
    if response and hasattr(response, 'reconcile_order'):
        print(f"   ✓ Order cancelled")
    
    # 5. Check WebSocket updates
    print("\n5. WebSocket updates:")
    count = 0
    while not cpty.response_queue.empty() and count < 5:
        update = await cpty.response_queue.get()
        count += 1
        print(f"   - Update {count}: {type(update).__name__}")
    
    # 6. Logout
    class MockLogoutRequest:
        logout = True
    
    print("\n6. Logging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Complete ===")


if __name__ == "__main__":
    asyncio.run(test_order())