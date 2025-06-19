#!/usr/bin/env python3
"""Test FARTCOIN order lifecycle with WebSocket tracking."""
import asyncio
import time
from datetime import datetime
from architect_py.grpc.client import GrpcClient
from architect_py.grpc.models.Cpty import CptyRequest, CptyResponse
from architect_py.grpc.models.Oms import Order, Cancel
from architect_py.grpc.models.definitions import OrderDir, OrderType, TimeInForce, OrderStatus


async def test_order_lifecycle():
    """Test FARTCOIN order lifecycle."""
    print("=== FARTCOIN Order Lifecycle Test ===")
    print("Testing: Place Order → Check Open → Cancel → Check Open")
    print("Also monitoring WebSocket for real-time updates\n")
    
    # Create gRPC client
    client = GrpcClient(host="localhost", port=50051)
    
    # Track responses
    order_updates = {}
    
    async def handle_responses():
        """Handle responses from server."""
        async for response in client.subscribe_cpty():
            print(f"\n📨 Response: {type(response).__name__}")
            
            if hasattr(response, 'reconcile_order') and response.reconcile_order:
                order = response.reconcile_order
                order_updates[order.cl_ord_id] = order
                print(f"   Order Update: {order.cl_ord_id}")
                print(f"   - Status: {order.status}")
                print(f"   - Exchange ID: {order.ord_id}")
                print(f"   - Price: ${order.price}")
                print(f"   - Qty: {order.qty}")
                
            elif hasattr(response, 'reconcile_open_orders') and response.reconcile_open_orders:
                open_orders = response.reconcile_open_orders
                print(f"   Open Orders: {len(open_orders.orders)} total")
                for order in open_orders.orders:
                    print(f"   - {order.cl_ord_id}: {order.status.name if hasattr(order.status, 'name') else order.status}")
                    
            elif hasattr(response, 'update_account_summary') and response.update_account_summary:
                summary = response.update_account_summary
                print(f"   Account Update")
                if summary.b:
                    print(f"   - Balances: {summary.b}")
    
    # Start response handler
    response_task = asyncio.create_task(handle_responses())
    
    try:
        # 1. Login
        print("1️⃣ Logging in...")
        login_req = CptyRequest.Login(
            user_id="test_trader",
            account_id="30188"
        )
        await client.send_cpty(CptyRequest(login=login_req))
        await asyncio.sleep(3)
        
        # 2. Place FARTCOIN order
        print("\n2️⃣ Placing FARTCOIN order...")
        order_id = f"fartcoin_test_{int(datetime.now().timestamp())}"
        
        place_order = CptyRequest.PlaceOrder(
            cl_ord_id=order_id,
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            price="1.09",
            qty="20",
            type=OrderType.LIMIT,
            tif=TimeInForce.GTC,
            reduce_only=False,
            post_only=True
        )
        
        print(f"   Order ID: {order_id}")
        print(f"   Buy 20 FARTCOIN at $1.09")
        print(f"   Total: $21.80 USDC")
        
        await client.send_cpty(CptyRequest(place_order=place_order))
        await asyncio.sleep(2)
        
        # 3. Check open orders
        print("\n3️⃣ Checking open orders...")
        open_orders_req = CptyRequest.ReconcileOpenOrders()
        await client.send_cpty(CptyRequest(reconcile_open_orders=open_orders_req))
        await asyncio.sleep(2)
        
        # 4. Cancel the order
        print(f"\n4️⃣ Cancelling order {order_id}...")
        cancel = Cancel(
            cl_ord_id=order_id,
            orig_cl_ord_id=order_id
        )
        cancel_req = CptyRequest.CancelOrder(cancel=cancel)
        await client.send_cpty(CptyRequest(cancel_order=cancel_req))
        await asyncio.sleep(2)
        
        # 5. Check open orders again
        print("\n5️⃣ Checking open orders after cancellation...")
        await client.send_cpty(CptyRequest(reconcile_open_orders=open_orders_req))
        await asyncio.sleep(2)
        
        # 6. Wait for WebSocket updates
        print("\n⏳ Waiting for any WebSocket updates...")
        await asyncio.sleep(5)
        
        # 7. Logout
        print("\n6️⃣ Logging out...")
        logout_req = CptyRequest.Logout()
        await client.send_cpty(CptyRequest(logout=logout_req))
        await asyncio.sleep(1)
        
    finally:
        # Cancel response handler
        response_task.cancel()
        try:
            await response_task
        except asyncio.CancelledError:
            pass
        
        # Close client
        await client.close()
        
        print("\n=== Test Complete ===")
        print(f"Total order updates received: {len(order_updates)}")


if __name__ == "__main__":
    asyncio.run(test_order_lifecycle())