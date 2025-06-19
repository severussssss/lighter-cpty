#!/usr/bin/env python3
"""
Example usage of the Lighter CPTY server.

This demonstrates how to connect to the CPTY server and perform operations.
"""
import grpc
from architect_py.grpc.cpty_pb2_grpc import CptyStub
from architect_py.grpc.cpty_pb2 import CptyRequest
from architect_py.grpc.oms_pb2 import Order, Cancel
from architect_py.grpc.definitions_pb2 import OrderDir, OrderType, TimeInForce
import time


def main():
    """Example CPTY client."""
    # Connect to the CPTY server
    channel = grpc.insecure_channel('localhost:50051')
    stub = CptyStub(channel)
    
    # Create a bidirectional stream
    request_queue = []
    
    # 1. Login
    login_req = CptyRequest()
    login_req.login.user_id = "example_trader"
    login_req.login.account_id = "30188"  # Your account index
    request_queue.append(login_req)
    
    # 2. Place an order
    order_req = CptyRequest()
    order = order_req.place_order
    order.cl_ord_id = f"example_{int(time.time())}"
    order.symbol = "ETH-USDC LIGHTER Perpetual/USDC Crypto"  # Architect-style symbol
    order.dir = OrderDir.BUY
    order.price = "2000.00"
    order.qty = "0.001"
    order.type = OrderType.LIMIT
    order.tif = TimeInForce.GTC
    order.reduce_only = False
    order.post_only = True
    request_queue.append(order_req)
    
    # 3. Cancel order (example)
    cancel_req = CptyRequest()
    cancel = cancel_req.cancel_order.cancel
    cancel.cl_ord_id = order.cl_ord_id
    cancel.symbol = order.symbol
    request_queue.append(cancel_req)
    
    # 4. Get open orders
    recon_req = CptyRequest()
    recon_req.reconcile_open_orders.SetInParent()
    request_queue.append(recon_req)
    
    # 5. Logout
    logout_req = CptyRequest()
    logout_req.logout.SetInParent()
    request_queue.append(logout_req)
    
    # Send requests and process responses
    def request_iterator():
        for req in request_queue:
            yield req
    
    responses = stub.Cpty(request_iterator())
    
    print("Processing responses:")
    for response in responses:
        if response.HasField('symbology'):
            print("Received symbology update")
        elif response.HasField('reconcile_order'):
            order = response.reconcile_order
            print(f"Order update: {order.cl_ord_id} - Status: {order.status}")
        elif response.HasField('reconcile_open_orders'):
            orders = response.reconcile_open_orders.orders
            print(f"Open orders: {len(orders)}")
        elif response.HasField('update_account_summary'):
            print("Account summary update received")


if __name__ == "__main__":
    main()