"""Test Lighter CPTY with proper gRPC client."""
import asyncio
import logging
import sys
import grpc
import msgspec
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import uuid

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

# Import gRPC generated code
from architect_py.grpc.client import dec_hook
from architect_py.grpc.utils import encoder
from architect_py import (
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
)
from architect_py.grpc.models.Cpty.CptyRequest import Login, PlaceOrder, UnannotatedCptyRequest


async def test_cpty_server():
    """Test the CPTY server with proper gRPC communication."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Start server first
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    logger.info("Starting Lighter CPTY server...")
    cpty = LighterCpty()
    server_task = asyncio.create_task(cpty.serve("[::]:50051"))
    
    # Give server time to start
    await asyncio.sleep(2)
    logger.info("Server started")
    
    # Connect to server
    channel = grpc.aio.insecure_channel('localhost:50051')
    
    # Create request/response queues
    request_queue = asyncio.Queue()
    response_queue = asyncio.Queue()
    
    # Decoder for responses
    decoder = msgspec.json.Decoder(dec_hook=dec_hook)
    
    async def request_iterator():
        """Generate requests from queue."""
        while True:
            request = await request_queue.get()
            if request is None:
                break
            yield request
    
    # Create bidirectional stream
    stub = channel.stream_stream(
        '/json.architect.Cpty/Cpty',
        request_serializer=lambda x: x,
        response_deserializer=decoder.decode
    )
    
    # Start the stream
    call = stub(request_iterator())
    
    # Response handler
    async def handle_responses():
        try:
            async for response in call:
                logger.info(f"Response: {type(response).__name__}")
                await response_queue.put(response)
        except Exception as e:
            logger.error(f"Response handler error: {e}")
    
    response_task = asyncio.create_task(handle_responses())
    
    # Send login request
    login = Login(
        trader="test_trader",
        account="30188"
    )
    logger.info("Sending login...")
    await request_queue.put(encoder.encode(login))
    
    # Wait for responses
    symbology_received = False
    orders_received = False
    
    for _ in range(5):  # Wait for up to 5 responses
        try:
            response = await asyncio.wait_for(response_queue.get(), timeout=5.0)
            
            if hasattr(response, 'execution_info'):
                logger.info("✓ Received symbology")
                symbology_received = True
                logger.info(f"  Markets: {len(response.execution_info.get('LIGHTER', {}))}")
                
            elif hasattr(response, 'orders'):
                logger.info("✓ Received open orders")
                orders_received = True
                logger.info(f"  Open orders: {len(response.orders)}")
                
            elif hasattr(response, 'balances'):
                logger.info("✓ Received account update")
                if response.balances:
                    for currency, balance in response.balances.items():
                        logger.info(f"  {currency}: {balance}")
                        
        except asyncio.TimeoutError:
            logger.info("No more responses")
            break
    
    # Place a test order
    if symbology_received:
        order_id = f"test-{uuid.uuid4().hex[:8]}"
        place_order = PlaceOrder(
            cl_ord_id=order_id,
            account="30188",
            trader="test_trader",
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            qty=Decimal("100"),
            type=OrderType.Limit,
            price=Decimal("0.001"),
            tif=TimeInForce.GoodTillCancel
        )
        
        logger.info(f"Placing order {order_id}...")
        await request_queue.put(encoder.encode(place_order))
        
        # Wait for order response
        try:
            response = await asyncio.wait_for(response_queue.get(), timeout=5.0)
            logger.info(f"✓ Order response: {type(response).__name__}")
            
            if hasattr(response, 'id'):
                logger.info(f"  Order ID: {response.id}")
                logger.info(f"  Status: {getattr(response, 'o', 'unknown')}")
                
        except asyncio.TimeoutError:
            logger.warning("No order response received")
    
    # Cleanup
    await request_queue.put(None)  # Signal end of stream
    await channel.close()
    
    # Cancel tasks
    response_task.cancel()
    server_task.cancel()
    
    try:
        await response_task
    except asyncio.CancelledError:
        pass
        
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    
    logger.info("\n✅ Test completed!")
    logger.info(f"Symbology received: {symbology_received}")
    logger.info(f"Orders snapshot received: {orders_received}")


if __name__ == "__main__":
    try:
        asyncio.run(test_cpty_server())
    except KeyboardInterrupt:
        print("\nTest interrupted")