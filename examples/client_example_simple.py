#!/usr/bin/env python3
"""
Example client snippet for using Lighter CPTY.

This demonstrates the pattern you provided:

```python
import asyncio
from lighter_cpty_client import LighterCptyClient

async def main():
    client = LighterCptyClient("localhost:50051")
    await client.connect()
    
    # Login
    await client.login("my_user", "0")
    
    # Place order
    await client.place_order(
        cl_ord_id="order_001",
        symbol="0",
        side="BUY",
        price="2700.00",
        qty="0.1"
    )
    
    # Handle responses
    await client.handle_responses()
    
    await client.disconnect()

asyncio.run(main())
```

Since the protobuf files aren't in the installed architect-py package,
you would need to either:

1. Generate the protobuf files locally:
   - Install grpcio-tools: pip install grpcio-tools
   - Get the .proto files from architect-py source
   - Generate: python -m grpc_tools.protoc ...

2. Use the LighterCpty module directly (as we've set up)

3. Create a simple mock client for testing (shown below)
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LighterCptyClient:
    """Mock client for demonstration purposes."""
    
    def __init__(self, address: str):
        self.address = address
        self.connected = False
        
    async def connect(self):
        """Connect to the server."""
        logger.info(f"Connecting to {self.address}...")
        self.connected = True
        logger.info("Connected!")
        
    async def disconnect(self):
        """Disconnect from the server."""
        logger.info("Disconnecting...")
        self.connected = False
        logger.info("Disconnected!")
        
    async def login(self, user_id: str, account_id: str):
        """Login to the system."""
        logger.info(f"Logging in as {user_id} with account {account_id}")
        # In a real implementation, this would send a login request
        await asyncio.sleep(0.5)  # Simulate network delay
        logger.info("Login successful!")
        
    async def place_order(self, cl_ord_id: str, symbol: str, side: str, 
                         price: str, qty: str):
        """Place an order."""
        logger.info(f"Placing order {cl_ord_id}:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Side: {side}")
        logger.info(f"  Price: {price}")
        logger.info(f"  Quantity: {qty}")
        # In a real implementation, this would send the order
        await asyncio.sleep(0.5)  # Simulate network delay
        logger.info(f"Order {cl_ord_id} placed successfully!")
        
    async def handle_responses(self):
        """Handle responses from the server."""
        logger.info("Handling responses...")
        # In a real implementation, this would process streaming responses
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Response handling complete")


# Your exact snippet:
async def main():
    client = LighterCptyClient("localhost:50051")
    await client.connect()
    
    # Login
    await client.login("my_user", "0")
    
    # Place order
    await client.place_order(
        cl_ord_id="order_001",
        symbol="0",
        side="BUY",
        price="2700.00",
        qty="0.1"
    )
    
    # Handle responses
    await client.handle_responses()
    
    await client.disconnect()


if __name__ == "__main__":
    print("=== Lighter CPTY Client Example ===\n")
    asyncio.run(main())
    print("\n=== Example Complete ===")
    print("\nTo use with a real server:")
    print("1. Ensure the Lighter CPTY server is running on localhost:50051")
    print("2. Replace this mock client with the actual implementation")
    print("3. The actual client would use gRPC bidirectional streaming")