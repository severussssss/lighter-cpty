#!/usr/bin/env python3
"""Simple test to verify order placement works."""
import asyncio
import logging
import sys
from pathlib import Path
from decimal import Decimal

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)


async def test_order_placement():
    """Test placing an order directly through the CPTY."""
    from LighterCpty.lighter_cpty_async import LighterCpty
    from architect_py import (
        Order, OrderDir, OrderType, OrderStatus, 
        TimeInForce, CptyLoginRequest
    )
    
    logger = logging.getLogger(__name__)
    
    # Create CPTY instance
    cpty = LighterCpty()
    logger.info("Created CPTY instance")
    
    # Simulate login
    login_req = CptyLoginRequest(
        trader="test_trader",
        account="30188"
    )
    
    try:
        await cpty.on_login(login_req)
        logger.info("✓ Login successful")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False
    
    # Wait for initialization
    await asyncio.sleep(2)
    
    # Create test order
    test_order = Order(
        id="test-simple-001",
        account="30188",
        trader="test_trader",
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.Limit,
        limit_price=Decimal("0.00001"),
        time_in_force=TimeInForce.GoodTillCancel,
        status=OrderStatus.Pending,
        recv_time=int(asyncio.get_event_loop().time()),
        recv_time_ns=0,
        source=0,
        execution_venue="LIGHTER"
    )
    
    logger.info(f"\n=== Placing Order ===")
    logger.info(f"Order ID: {test_order.id}")
    logger.info(f"Symbol: {test_order.symbol}")
    logger.info(f"Side: {test_order.dir}")
    logger.info(f"Quantity: {test_order.quantity}")
    logger.info(f"Price: {test_order.limit_price}")
    
    # Track order events
    order_events = []
    
    # Mock the event methods to capture what happens
    original_ack = cpty.ack_order
    original_reject = cpty.reject_order
    
    def track_ack(order_id, exchange_order_id=None):
        order_events.append(('ACK', order_id, exchange_order_id))
        logger.info(f"✓ Order acknowledged: {order_id} -> {exchange_order_id}")
        return original_ack(order_id, exchange_order_id=exchange_order_id)
    
    def track_reject(order_id, reject_reason, reject_message=None):
        order_events.append(('REJECT', order_id, reject_reason, reject_message))
        logger.error(f"✗ Order rejected: {order_id} - {reject_reason}: {reject_message}")
        return original_reject(order_id, reject_reason=reject_reason, reject_message=reject_message)
    
    cpty.ack_order = track_ack
    cpty.reject_order = track_reject
    
    try:
        # Place the order
        await cpty.on_place_order(test_order)
        
        # Wait for order processing
        await asyncio.sleep(3)
        
        # Check results
        logger.info(f"\n=== Results ===")
        logger.info(f"Order events: {len(order_events)}")
        
        if order_events:
            for event in order_events:
                logger.info(f"  {event}")
            
            # Check if order reached exchange
            if cpty.client_to_exchange_id.get(test_order.id):
                exchange_id = cpty.client_to_exchange_id[test_order.id]
                logger.info(f"\n✅ SUCCESS: Order reached Lighter exchange!")
                logger.info(f"   Client Order ID: {test_order.id}")
                logger.info(f"   Exchange Order ID: {exchange_id}")
                return True
            else:
                logger.warning("\n⚠️  Order acknowledged but no exchange ID recorded")
        else:
            logger.error("\n✗ FAILED: No order events received")
            
    except Exception as e:
        logger.error(f"Order placement error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original methods
        cpty.ack_order = original_ack
        cpty.reject_order = original_reject
        
        # Logout
        await cpty.on_logout(None)
    
    return False


async def main():
    """Run the test with timeout."""
    try:
        # Run test with timeout
        result = await asyncio.wait_for(test_order_placement(), timeout=15.0)
        
        if result:
            print("\n✅ Test passed! Orders are reaching the Lighter exchange through the CPTY.")
        else:
            print("\n❌ Test failed! Check the logs above for details.")
            sys.exit(1)
            
    except asyncio.TimeoutError:
        print("\n❌ Test timed out!")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())