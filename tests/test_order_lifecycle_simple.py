#!/usr/bin/env python3
"""Simple test of FARTCOIN order lifecycle."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.Cpty import CptyRequest
from architect_py.grpc.models.Oms import Order, Cancel
from architect_py.grpc.models.definitions import OrderDir, OrderType, OrderStatus
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def test_order_lifecycle():
    """Test FARTCOIN order lifecycle with WebSocket tracking."""
    # Create CPTY servicer instance
    cpty = LighterCptyServicer()
    
    print("=== FARTCOIN Order Lifecycle Test ===")
    print("Testing: Place Order → Check Open → Cancel → Check Open")
    print("Monitoring WebSocket for real-time updates\n")
    
    # 1. Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("1️⃣ Logging in...")
    response = await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(3)  # Wait for login and WebSocket connection
    
    if not cpty.logged_in:
        print("   ✗ Login failed")
        return
    
    print("   ✓ Logged in successfully")
    print(f"   WebSocket connected: {cpty.ws_connected}")
    
    # 2. Place FARTCOIN order
    order_id = f"fartcoin_test_{int(datetime.now().timestamp())}"
    
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
    
    print(f"\n2️⃣ Placing FARTCOIN order...")
    print(f"   Order ID: {order_id}")
    print(f"   Buy 20 FARTCOIN at $1.09 = $21.80 USDC")
    
    response = await cpty._handle_request(MockPlaceRequest())
    if response and hasattr(response, 'reconcile_order'):
        print(f"   ✓ Order placed: {response.reconcile_order.ord_id}")
    
    await asyncio.sleep(2)
    
    # 3. Check open orders
    class MockReconcileOpenOrders:
        orders = []  # Empty list for request
    
    class MockOpenOrdersRequest:
        reconcile_open_orders = MockReconcileOpenOrders()
    
    print("\n3️⃣ Checking open orders...")
    response = await cpty._handle_request(MockOpenOrdersRequest())
    if response and hasattr(response, 'reconcile_open_orders'):
        orders = response.reconcile_open_orders.orders
        print(f"   Found {len(orders)} open order(s)")
        for order in orders:
            print(f"   - {order.cl_ord_id}: {order.status} | ${order.price} x {order.qty}")
    
    await asyncio.sleep(2)
    
    # 4. Cancel the order
    class MockCancel:
        cl_ord_id = order_id
        orig_cl_ord_id = order_id
    
    class MockCancelOrder:
        cancel = MockCancel()
    
    class MockCancelRequest:
        cancel_order = MockCancelOrder()
    
    print(f"\n4️⃣ Cancelling order {order_id}...")
    response = await cpty._handle_request(MockCancelRequest())
    if response and hasattr(response, 'reconcile_order'):
        print(f"   ✓ Order cancelled: {response.reconcile_order.status}")
    
    await asyncio.sleep(2)
    
    # 5. Check open orders again
    print("\n5️⃣ Checking open orders after cancellation...")
    response = await cpty._handle_request(MockOpenOrdersRequest())
    if response and hasattr(response, 'reconcile_open_orders'):
        orders = response.reconcile_open_orders.orders
        print(f"   Found {len(orders)} open order(s)")
        if len(orders) == 0:
            print("   ✓ No open orders (order was successfully cancelled)")
    
    # 6. Check for WebSocket updates
    print("\n⏳ Checking WebSocket response queue...")
    updates_count = 0
    while not cpty.response_queue.empty():
        try:
            update = cpty.response_queue.get_nowait()
            updates_count += 1
            print(f"   📨 WebSocket update #{updates_count}: {type(update).__name__}")
        except asyncio.QueueEmpty:
            break
    
    if updates_count == 0:
        print("   No WebSocket updates received (connection might have failed)")
    
    # 7. Logout
    class MockLogoutRequest:
        logout = True
    
    print("\n6️⃣ Logging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Test Complete ===")
    print(f"Orders tracked: {len(cpty.orders)}")
    print(f"WebSocket was connected: {cpty.ws_connected}")


if __name__ == "__main__":
    asyncio.run(test_order_lifecycle())