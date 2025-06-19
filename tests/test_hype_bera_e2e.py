#!/usr/bin/env python3
"""End-to-end test for HYPE and BERA trading."""
import grpc
import asyncio
import time
from datetime import datetime
from architect_py.grpc.client import GrpcClient
from architect_py.grpc.models.Cpty import CptyRequest
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce


async def test_market(client: GrpcClient, market_name: str, symbol: str, price: str, qty: str):
    """Test a specific market end-to-end."""
    print(f"\n{'='*60}")
    print(f"Testing {market_name}")
    print('='*60)
    
    # Place order
    order_id = f"{market_name.lower()}_{int(datetime.now().timestamp())}"
    
    place_order = CptyRequest.PlaceOrder(
        cl_ord_id=order_id,
        symbol=symbol,
        dir=OrderDir.BUY,
        price=price,
        qty=qty,
        type=OrderType.LIMIT,
        tif=TimeInForce.GTC,
        reduce_only=False,
        post_only=True
    )
    
    print(f"\n1. Placing {market_name} order:")
    print(f"   Order ID: {order_id}")
    print(f"   Symbol: {symbol}")
    print(f"   Buy {qty} {market_name} at ${price}")
    print(f"   Total: ${float(price) * float(qty):.2f} USDC")
    
    # Send order
    await client.send_cpty(CptyRequest(place_order=place_order))
    
    # Wait for response
    await asyncio.sleep(2)
    
    # Check open orders
    print(f"\n2. Checking open orders...")
    open_orders_req = CptyRequest.ReconcileOpenOrders()
    await client.send_cpty(CptyRequest(reconcile_open_orders=open_orders_req))
    
    await asyncio.sleep(2)
    
    # Cancel order
    print(f"\n3. Cancelling {market_name} order...")
    cancel = CptyRequest.CancelOrder(
        cancel=CptyRequest.CancelOrder.Cancel(
            cl_ord_id=order_id,
            orig_cl_ord_id=order_id
        )
    )
    await client.send_cpty(CptyRequest(cancel_order=cancel))
    
    await asyncio.sleep(2)
    
    # Check open orders again
    print(f"\n4. Verifying cancellation...")
    await client.send_cpty(CptyRequest(reconcile_open_orders=open_orders_req))
    
    await asyncio.sleep(2)
    
    print(f"\n✓ {market_name} test complete")


async def main():
    """Run end-to-end test for HYPE and BERA."""
    print("=== HYPE and BERA End-to-End Test ===")
    print("\nConnecting to CPTY server at localhost:50051...")
    
    # Create client
    client = GrpcClient(host="localhost", port=50051)
    
    # Track responses
    responses = []
    exchange_ids = {}
    
    async def handle_responses():
        """Handle responses in background."""
        async for response in client.subscribe_cpty():
            responses.append(response)
            
            # Extract response type
            response_type = None
            if hasattr(response, 'reconcile_order') and response.reconcile_order:
                response_type = "Order Update"
                order = response.reconcile_order
                print(f"\n📨 {response_type}: {order.cl_ord_id}")
                print(f"   Status: {order.status}")
                print(f"   Exchange ID: {order.ord_id}")
                exchange_ids[order.cl_ord_id] = order.ord_id
                
            elif hasattr(response, 'reconcile_open_orders') and response.reconcile_open_orders:
                response_type = "Open Orders"
                orders = response.reconcile_open_orders.orders
                print(f"\n📨 {response_type}: {len(orders)} order(s)")
                for order in orders:
                    print(f"   - {order.cl_ord_id}: {order.status}")
                    
            elif hasattr(response, 'update_account_summary') and response.update_account_summary:
                response_type = "Account Update"
                print(f"\n📨 {response_type}")
                
            elif hasattr(response, 'symbology') and response.symbology:
                response_type = "Symbology"
                print(f"\n📨 {response_type}: {len(response.symbology.x)} symbols")
    
    # Start response handler
    response_task = asyncio.create_task(handle_responses())
    
    try:
        # 1. Login
        print("\n1️⃣ Logging in...")
        login = CptyRequest.Login(
            user_id="test_trader",
            account_id="30188"
        )
        await client.send_cpty(CptyRequest(login=login))
        await asyncio.sleep(3)
        
        # 2. Test HYPE
        await test_market(
            client,
            "HYPE",
            "HYPE-USDC LIGHTER Perpetual/USDC Crypto",
            "15.00",  # $15 per HYPE
            "0.50"    # Min 0.50 HYPE
        )
        
        # 3. Test BERA
        await test_market(
            client,
            "BERA", 
            "BERA-USDC LIGHTER Perpetual/USDC Crypto",
            "0.40",   # $0.40 per BERA
            "3.0"     # Min 3.0 BERA
        )
        
        # 4. Logout
        print("\n5️⃣ Logging out...")
        logout = CptyRequest.Logout()
        await client.send_cpty(CptyRequest(logout=logout))
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
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total responses received: {len(responses)}")
    print(f"Exchange IDs generated: {len(exchange_ids)}")
    
    if exchange_ids:
        print("\nOrders placed:")
        for cl_ord_id, exchange_id in exchange_ids.items():
            market = "HYPE" if "hype" in cl_ord_id else "BERA"
            print(f"  {market}: {exchange_id}")
    
    print("\n✓ End-to-end test complete!")


if __name__ == "__main__":
    asyncio.run(main())