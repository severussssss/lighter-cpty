#!/usr/bin/env python3
"""Test order placement through CPTY to Lighter exchange."""
import asyncio
import logging
import sys
import grpc
import msgspec
from pathlib import Path
from decimal import Decimal
import uuid
import time

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

from architect_py.grpc.client import dec_hook
from architect_py.grpc.utils import encoder
from architect_py import OrderDir, OrderType, TimeInForce
from architect_py.grpc.models.Cpty.CptyRequest import Login, PlaceOrder


async def main():
    """Test order placement."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Start CPTY server
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    logger.info("Starting Lighter CPTY server...")
    cpty = LighterCpty()
    server_task = asyncio.create_task(cpty.serve("[::]:50051"))
    await asyncio.sleep(3)  # Give server time to start
    
    # Connect to server
    channel = grpc.aio.insecure_channel('localhost:50051')
    decoder = msgspec.json.Decoder(dec_hook=dec_hook)
    
    # Setup bidirectional stream
    request_queue = asyncio.Queue()
    
    async def request_iterator():
        while True:
            request = await request_queue.get()
            if request is None:
                break
            yield request
    
    stub = channel.stream_stream(
        '/json.architect.Cpty/Cpty',
        request_serializer=lambda x: x,
        response_deserializer=decoder.decode
    )
    
    call = stub(request_iterator())
    
    # Response collector
    responses = []
    
    async def collect_responses():
        try:
            async for response in call:
                logger.info(f"Response: {type(response).__name__}")
                responses.append(response)
                
                # Log specific responses
                if hasattr(response, 'execution_info'):
                    logger.info("✓ Received symbology")
                elif hasattr(response, 'orders'):
                    logger.info(f"✓ Received open orders: {len(response.orders)} orders")
                elif hasattr(response, 'balances'):
                    logger.info("✓ Received account update")
                    for currency, balance in (response.balances or {}).items():
                        logger.info(f"  {currency}: {balance}")
                elif hasattr(response, 'id'):  # ReconcileOrder
                    logger.info(f"✓ Order update: {response.id}")
                    logger.info(f"  Status: {getattr(response, 'o', 'unknown')}")
                    logger.info(f"  Exchange order ID: {getattr(response, 've', 'N/A')}")
                    
        except Exception as e:
            logger.error(f"Response error: {e}")
    
    response_task = asyncio.create_task(collect_responses())
    
    # Login
    login = Login(trader="test_trader", account="30188")
    logger.info("Logging in...")
    await request_queue.put(encoder.encode(login))
    
    # Wait for login responses
    await asyncio.sleep(3)
    
    # Place test order
    order_id = f"test-{uuid.uuid4().hex[:8]}"
    place_order = PlaceOrder(
        cl_ord_id=order_id,
        account="30188",
        trader="test_trader",
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        qty=Decimal("100"),  # 100 FARTCOIN
        type=OrderType.Limit,
        price=Decimal("0.00001"),  # Very low price to avoid fill
        tif=TimeInForce.GoodTillCancel
    )
    
    logger.info(f"\n=== Placing Order ===")
    logger.info(f"Order ID: {order_id}")
    logger.info(f"Symbol: {place_order.symbol}")
    logger.info(f"Side: {place_order.dir}")
    logger.info(f"Quantity: {place_order.qty}")
    logger.info(f"Price: {place_order.price}")
    
    await request_queue.put(encoder.encode(place_order))
    
    # Wait for order response
    await asyncio.sleep(5)
    
    # Check if order was acknowledged
    order_responses = [r for r in responses if hasattr(r, 'id') and r.id == order_id]
    
    if order_responses:
        logger.info(f"\n✅ Order reached the exchange!")
        logger.info(f"Total responses for order: {len(order_responses)}")
        for resp in order_responses:
            logger.info(f"  Status: {getattr(resp, 'o', 'unknown')}")
            logger.info(f"  Venue: {getattr(resp, 've', 'unknown')}")
    else:
        logger.warning(f"\n⚠️  No order response received")
    
    # Check Lighter directly for the order
    logger.info("\n=== Checking Lighter SDK ===")
    if cpty.client_to_exchange_id.get(order_id):
        exchange_id = cpty.client_to_exchange_id[order_id]
        logger.info(f"✓ Order tracked in CPTY: {order_id} -> {exchange_id}")
        logger.info("✓ Order successfully submitted to Lighter exchange!")
    else:
        logger.warning("Order not found in CPTY tracking")
    
    # Summary
    logger.info(f"\n=== Summary ===")
    logger.info(f"Total responses received: {len(responses)}")
    logger.info(f"Order placed: {order_id}")
    logger.info(f"Order reached exchange: {'Yes' if order_responses or order_id in cpty.client_to_exchange_id else 'No'}")
    
    # Cleanup
    await request_queue.put(None)
    await channel.close()
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted")