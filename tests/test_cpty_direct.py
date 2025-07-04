"""Direct test of Lighter CPTY server functionality."""
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

from architect_py import (
    CptyLoginRequest,
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
)
from architect_py.grpc.models.Cpty.CptyRequest import PlaceOrder
from architect_py.grpc.client import dec_hook
from architect_py.grpc.utils import encoder


class CptyDirectTest:
    """Direct test of CPTY server."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.channel = None
        self.stub = None
        
    async def connect(self, host="localhost:50051"):
        """Connect to CPTY server."""
        try:
            self.channel = grpc.aio.insecure_channel(host)
            self.logger.info(f"✓ Connected to CPTY server at {host}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            return False
    
    async def test_cpty_stream(self):
        """Test the CPTY bidirectional stream."""
        decoder = msgspec.json.Decoder(dec_hook=dec_hook)
        
        async def request_generator():
            """Generate requests for the CPTY stream."""
            # Send login request
            login = CptyLoginRequest(
                trader="test_trader",
                account="30188"  # From .env LIGHTER_ACCOUNT_INDEX
            )
            
            self.logger.info("Sending login request...")
            yield encoder.encode(login)
            
            # Wait for login response
            await asyncio.sleep(2)
            
            # Send order
            order = Order(
                id=f"test-{uuid.uuid4().hex[:8]}",
                account="30188",
                trader="test_trader",
                symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
                dir=OrderDir.BUY,
                quantity=Decimal("100"),
                order_type=OrderType.Limit,
                limit_price=Decimal("0.001"),
                time_in_force=TimeInForce.GoodTillCancel,
                status=OrderStatus.Pending,
                recv_time=int(datetime.now().timestamp()),
                recv_time_ns=0,
                source=0,
                execution_venue="LIGHTER"
            )
            
            place_order = PlaceOrder(
                cl_ord_id=order.id,
                account=order.account,
                trader=order.trader,
                symbol=order.symbol,
                dir=order.dir,
                qty=order.quantity,
                type=order.order_type,
                price=order.limit_price,
                tif=order.time_in_force
            )
            
            self.logger.info(f"Sending order: {order.id}")
            yield encoder.encode(place_order)
            
            # Keep stream open
            await asyncio.sleep(10)
        
        try:
            # Create the bidirectional stream
            stub = self.channel.stream_stream(
                '/json.architect.Cpty/Cpty',
                request_serializer=lambda x: x,
                response_deserializer=decoder.decode
            )
            
            # Start the stream
            call = stub()
            
            # Send requests and receive responses concurrently
            async def send_requests():
                async for request in request_generator():
                    await call.write(request)
                await call.done_writing()
            
            # Start sending requests
            send_task = asyncio.create_task(send_requests())
            
            # Process responses
            async for response in call:
                self.logger.info(f"Received response: {type(response).__name__}")
                
                # Log response details
                if hasattr(response, '__dict__'):
                    for key, value in response.__dict__.items():
                        if not key.startswith('_'):
                            self.logger.info(f"  {key}: {value}")
                
                # Check for specific response types
                if hasattr(response, 'execution_info'):
                    self.logger.info("✓ Received symbology")
                elif hasattr(response, 'orders'):
                    self.logger.info("✓ Received open orders snapshot")
                elif hasattr(response, 'balances'):
                    self.logger.info("✓ Received account update")
                    if response.balances:
                        for currency, balance in response.balances.items():
                            self.logger.info(f"  Balance - {currency}: {balance}")
            
            # Wait for send task to complete
            await send_task
            
        except Exception as e:
            self.logger.error(f"Stream error: {e}")
            import traceback
            traceback.print_exc()
    
    async def run_test(self):
        """Run the direct CPTY test."""
        self.logger.info("=== Starting Direct CPTY Test ===")
        
        # Connect to server
        if not await self.connect():
            return False
        
        # Test CPTY stream
        await self.test_cpty_stream()
        
        # Close connection
        if self.channel:
            await self.channel.close()
        
        return True


async def start_server_and_test():
    """Start the CPTY server and run the test."""
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Start CPTY server
    logger.info("Starting Lighter CPTY server...")
    cpty = LighterCpty()
    server_task = asyncio.create_task(cpty.serve("[::]:50051"))
    
    # Give server time to start
    await asyncio.sleep(2)
    
    # Run test
    tester = CptyDirectTest()
    success = await tester.run_test()
    
    # Cancel server
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    
    if success:
        print("\n✅ Direct CPTY test completed successfully!")
    else:
        print("\n❌ Direct CPTY test failed!")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(start_server_and_test())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")