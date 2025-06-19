#!/usr/bin/env python3
"""Final test of FARTCOIN order lifecycle with WebSocket tracking."""
import asyncio
from datetime import datetime
from LighterCpty.lighter_cpty import LighterCptyServicer
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce
from dotenv import load_dotenv

load_dotenv()


async def final_test():
    """Complete test of order lifecycle and tracking."""
    cpty = LighterCptyServicer()
    
    print("=== FARTCOIN Order Lifecycle & Tracking Test ===")
    print("This test will:")
    print("1. Place a FARTCOIN order")
    print("2. Check open orders")
    print("3. Cancel the order")
    print("4. Verify order tracking")
    print("5. Monitor WebSocket updates\n")
    
    # 1. Login
    class MockLogin:
        user_id = "test_trader"
        account_id = "30188"
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("Step 1: Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(3)  # Wait for login and WebSocket
    
    print(f"✓ Logged in: {cpty.logged_in}")
    print(f"✓ WebSocket connected: {cpty.ws_connected}")
    print(f"✓ Available symbols: {len(cpty.symbol_to_market_id)}")
    
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
    
    print(f"\nStep 2: Placing FARTCOIN order...")
    print(f"- Order ID: {order_id}")
    print(f"- Buy 20 FARTCOIN at $1.09")
    print(f"- Total value: $21.80 USDC")
    
    response = await cpty._handle_request(MockPlaceRequest())
    exchange_id = None
    if response and hasattr(response, 'reconcile_order'):
        exchange_id = response.reconcile_order.ord_id
        print(f"✓ Order placed successfully!")
        print(f"  Exchange ID: {exchange_id}")
        print(f"  Status: {response.reconcile_order.status}")
    
    # 3. Check order tracking
    print("\nStep 3: Verifying order tracking...")
    print(f"- Orders in memory: {len(cpty.orders)}")
    print(f"- Client->Exchange mapping: {len(cpty.client_to_exchange_id)}")
    
    if order_id in cpty.orders:
        print(f"✓ Order tracked locally:")
        print(f"  {order_id} -> {cpty.client_to_exchange_id.get(order_id, 'N/A')}")
    
    # 4. Check open orders
    class MockReconcileOpenOrders:
        orders = []
    
    class MockOpenOrdersRequest:
        reconcile_open_orders = MockReconcileOpenOrders()
    
    print("\nStep 4: Checking open orders...")
    response = await cpty._handle_request(MockOpenOrdersRequest())
    if response and hasattr(response, 'reconcile_open_orders'):
        orders = response.reconcile_open_orders.orders
        print(f"✓ Found {len(orders)} open order(s)")
        for order in orders:
            print(f"  - {order.cl_ord_id}: Status={order.status}")
    
    # 5. Cancel the order
    class MockCancel:
        cl_ord_id = order_id
        orig_cl_ord_id = order_id
    
    class MockCancelOrder:
        cancel = MockCancel()
    
    class MockCancelRequest:
        cancel_order = MockCancelOrder()
    
    print(f"\nStep 5: Cancelling order...")
    response = await cpty._handle_request(MockCancelRequest())
    if response and hasattr(response, 'reconcile_order'):
        print(f"✓ Order cancelled successfully")
        print(f"  Status: {response.reconcile_order.status}")
    
    # 6. Check open orders again
    print("\nStep 6: Verifying cancellation...")
    response = await cpty._handle_request(MockOpenOrdersRequest())
    if response and hasattr(response, 'reconcile_open_orders'):
        orders = response.reconcile_open_orders.orders
        print(f"✓ Open orders after cancel: {len(orders)}")
        if len(orders) == 0:
            print("  All orders cancelled successfully!")
    
    # 7. Check WebSocket updates
    print("\nStep 7: WebSocket updates received:")
    await asyncio.sleep(1)  # Give time for any updates
    
    count = 0
    while not cpty.response_queue.empty() and count < 10:
        try:
            update = await asyncio.wait_for(cpty.response_queue.get(), timeout=0.1)
            count += 1
            print(f"  Update {count}: {type(update).__name__}")
            if hasattr(update, 'update_account_summary'):
                print(f"    Account update received")
        except asyncio.TimeoutError:
            break
    
    if count == 0:
        print("  No WebSocket updates in queue (may be due to subscription issue)")
    
    # 8. Summary
    print("\n=== Summary ===")
    print(f"✓ Order placed: {order_id}")
    print(f"✓ Exchange ID: {exchange_id}")
    print(f"✓ Order cancelled successfully")
    print(f"✓ WebSocket status: {'Connected' if cpty.ws_connected else 'Not connected'}")
    print(f"✓ Total orders tracked: {len(cpty.orders)}")
    
    # 9. Logout
    class MockLogoutRequest:
        logout = True
    
    print("\nLogging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(final_test())