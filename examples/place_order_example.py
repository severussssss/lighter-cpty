#!/usr/bin/env python3
"""Example: Place orders on Lighter through the CPTY server."""
import asyncio
from architect_py.grpc.client import GrpcClient
from architect_py.grpc.models.Cpty import CptyRequest
from architect_py.grpc.models.definitions import OrderDir, OrderType
from architect_py import TimeInForce


async def place_order_example():
    """Example of placing orders through the Lighter CPTY."""
    # Connect to CPTY server
    client = GrpcClient(host="localhost", port=50051)
    
    # Handle responses
    async def handle_responses():
        async for response in client.subscribe_cpty():
            print(f"Response: {type(response).__name__}")
            if hasattr(response, 'reconcile_order') and response.reconcile_order:
                order = response.reconcile_order
                print(f"  Order {order.cl_ord_id}: {order.status}")
                print(f"  Exchange ID: {order.ord_id}")
    
    # Start response handler
    response_task = asyncio.create_task(handle_responses())
    
    try:
        # 1. Login
        print("Logging in...")
        login = CptyRequest.Login(user_id="trader1", account_id="30188")
        await client.send_cpty(CptyRequest(login=login))
        await asyncio.sleep(2)
        
        # 2. Place ETH order
        print("\nPlacing ETH order...")
        eth_order = CptyRequest.PlaceOrder(
            cl_ord_id="eth_order_001",
            symbol="ETH-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            price="2000.00",
            qty="0.01",
            type=OrderType.LIMIT,
            tif=TimeInForce.GTC,
            reduce_only=False,
            post_only=True
        )
        await client.send_cpty(CptyRequest(place_order=eth_order))
        await asyncio.sleep(2)
        
        # 3. Place HYPE order
        print("\nPlacing HYPE order...")
        hype_order = CptyRequest.PlaceOrder(
            cl_ord_id="hype_order_001",
            symbol="HYPE-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            price="15.00",
            qty="0.50",  # Min 0.50 HYPE
            type=OrderType.LIMIT,
            tif=TimeInForce.GTC,
            reduce_only=False,
            post_only=True
        )
        await client.send_cpty(CptyRequest(place_order=hype_order))
        await asyncio.sleep(2)
        
        # 4. Check open orders
        print("\nChecking open orders...")
        await client.send_cpty(CptyRequest(
            reconcile_open_orders=CptyRequest.ReconcileOpenOrders()
        ))
        await asyncio.sleep(2)
        
        # 5. Logout
        print("\nLogging out...")
        await client.send_cpty(CptyRequest(logout=CptyRequest.Logout()))
        
    finally:
        response_task.cancel()
        await client.close()


if __name__ == "__main__":
    asyncio.run(place_order_example())