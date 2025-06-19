#!/usr/bin/env python3
"""Example client snippet for using Lighter CPTY."""
import asyncio
import grpc
import logging
from typing import AsyncIterator
import architect_py.grpc.models.Cpty_pb2 as cpty_pb2
import architect_py.grpc.models.Cpty_pb2_grpc as cpty_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LighterCptyClient:
    def __init__(self, address="localhost:50051"):
        self.address = address
        self.channel = None
        self.stub = None
        self.request_queue = None
        self.stream = None
        
    async def connect(self):
        """Establish connection to the server."""
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = cpty_pb2_grpc.CptyStub(self.channel)
        self.request_queue = asyncio.Queue()
        logger.info(f"Connected to {self.address}")
        
    async def disconnect(self):
        """Close the connection."""
        if self.stream:
            self.stream.cancel()
        if self.channel:
            await self.channel.close()
        logger.info("Disconnected")
        
    async def login(self, user_id: str, account_id: str):
        """Send login request."""
        req = cpty_pb2.CptyRequest()
        req.login.user_id = user_id
        req.login.account_id = account_id
        await self.request_queue.put(req)
        logger.info(f"Login sent for user {user_id}")
        
    async def place_order(self, cl_ord_id: str, symbol: str, side: str, 
                         price: str, qty: str):
        """Place an order."""
        req = cpty_pb2.CptyRequest()
        req.place_order.cl_ord_id = cl_ord_id
        req.place_order.symbol = symbol
        req.place_order.dir = cpty_pb2.BUY if side.upper() == "BUY" else cpty_pb2.SELL
        req.place_order.price = price
        req.place_order.qty = qty
        req.place_order.type = cpty_pb2.LIMIT
        req.place_order.tif = cpty_pb2.GTC
        await self.request_queue.put(req)
        logger.info(f"Order placed: {cl_ord_id}")
        
    async def handle_responses(self):
        """Process server responses."""
        async def request_generator():
            while True:
                req = await self.request_queue.get()
                if req is None:
                    break
                yield req
                
        # Start the bidirectional stream
        self.stream = self.stub.Cpty(request_generator())
        
        # Process responses
        async for response in self.stream:
            if response.HasField('symbology'):
                logger.info("Received symbology update")
            elif response.HasField('reconcile_order'):
                order = response.reconcile_order
                logger.info(f"Order update: {order.cl_ord_id} - Status: {order.status}")
            elif response.HasField('update_account_summary'):
                logger.info("Account summary updated")
            else:
                logger.info(f"Received response: {response}")


# Your original snippet works with this implementation
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
    asyncio.run(main())