#!/usr/bin/env python3
"""Example: Place a FARTCOIN order using the Lighter CPTY server."""
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from LighterCpty.lighter_cpty import LighterCptyServicer

load_dotenv()


async def place_fartcoin_order():
    """Place a FARTCOIN order through the CPTY server."""
    # Create CPTY servicer instance
    cpty = LighterCptyServicer()
    
    print("=== FARTCOIN Order Example ===\n")
    
    # 1. Create login request
    class MockLogin:
        user_id = "your_trader_id"  # Your trader ID
        account_id = "30188"        # Your Lighter account index
    
    class MockLoginRequest:
        login = MockLogin()
    
    print("1. Logging in...")
    await cpty._handle_request(MockLoginRequest())
    await asyncio.sleep(2)  # Wait for login to complete
    
    if not cpty.logged_in:
        print("   ✗ Login failed")
        return
    
    print("   ✓ Logged in successfully")
    
    # 2. Create FARTCOIN order
    class MockOrder:
        cl_ord_id = f"fartcoin_{int(datetime.now().timestamp())}"  # Unique order ID
        symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"    # Architect-style symbol
        dir = "BUY"                 # BUY or SELL
        price = "1.09"              # Price per FARTCOIN (market is ~$1.10)
        qty = "20"                  # Quantity (minimum 20 FARTCOIN)
        type = "LIMIT"              # Order type
        tif = "GTC"                 # Time in force: Good Till Cancelled
        reduce_only = False         # Not a reduce-only order
        post_only = True            # Post-only to ensure maker fees
    
    class MockPlaceRequest:
        place_order = MockOrder()
    
    print(f"\n2. Placing FARTCOIN order:")
    print(f"   Order ID: {MockOrder.cl_ord_id}")
    print(f"   Symbol: {MockOrder.symbol}")
    print(f"   Side: {MockOrder.dir}")
    print(f"   Price: ${MockOrder.price} per FARTCOIN")
    print(f"   Quantity: {MockOrder.qty} FARTCOIN")
    print(f"   Total Value: ${float(MockOrder.price) * float(MockOrder.qty):.2f} USDC")
    
    # Place the order
    await cpty._handle_request(MockPlaceRequest())
    
    # Check if order was placed successfully
    if MockOrder.cl_ord_id in cpty.orders:
        exchange_id = cpty.client_to_exchange_id.get(MockOrder.cl_ord_id, "Unknown")
        print(f"\n   ✓ Order placed successfully!")
        print(f"   Exchange Order ID: {exchange_id}")
    else:
        print(f"\n   ✗ Failed to place order")
    
    # 3. Logout
    class MockLogoutRequest:
        logout = True
    
    print("\n3. Logging out...")
    await cpty._handle_request(MockLogoutRequest())
    
    print("\n=== Done ===")


# Alternative: Using gRPC client (for production use)
def grpc_example():
    """Example using gRPC client to connect to the CPTY server."""
    print("""
To use with gRPC client:

```python
import grpc
from architect_py.grpc.cpty_pb2_grpc import CptyStub
from architect_py.grpc.cpty_pb2 import CptyRequest
from architect_py.grpc.oms_pb2 import Order
from architect_py.grpc.definitions_pb2 import OrderDir, OrderType, TimeInForce

# Connect to CPTY server
channel = grpc.insecure_channel('localhost:50051')
stub = CptyStub(channel)

# Create request stream
def request_iterator():
    # Login
    login_req = CptyRequest()
    login_req.login.user_id = "your_trader_id"
    login_req.login.account_id = "30188"
    yield login_req
    
    # Place FARTCOIN order
    order_req = CptyRequest()
    order = order_req.place_order
    order.cl_ord_id = f"fartcoin_{int(time.time())}"
    order.symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
    order.dir = OrderDir.BUY
    order.price = "1.09"
    order.qty = "20"
    order.type = OrderType.LIMIT
    order.tif = TimeInForce.GTC
    order.reduce_only = False
    order.post_only = True
    yield order_req

# Send requests and handle responses
responses = stub.Cpty(request_iterator())
for response in responses:
    print(f"Response: {response}")
```
""")


if __name__ == "__main__":
    print("This example shows how to place a FARTCOIN order\n")
    print("Note: FARTCOIN details on Lighter:")
    print("- Market ID: 21")
    print("- Current price: ~$1.10")
    print("- Minimum order size: 20 FARTCOIN")
    print("- Price decimals: 5")
    print("- Size decimals: 1")
    
    response = input("\nRun the example? (yes/no): ")
    
    if response.lower() == "yes":
        asyncio.run(place_fartcoin_order())
    else:
        print("\nShowing gRPC example instead:")
        grpc_example()