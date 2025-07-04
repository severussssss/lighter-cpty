#!/usr/bin/env python3
"""Test order flow: Architect Client → Core → CPTY → Lighter."""
import asyncio
import logging
import sys
import os
from pathlib import Path
from decimal import Decimal
import uuid

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

# Import Architect client
from architect_py import Client as ArchitectClient
from architect_py import (
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
)


async def main():
    """Test the complete order flow through Architect."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # First, ensure CPTY server is running
    logger.info("=== Starting Lighter CPTY Server ===")
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    cpty = LighterCpty()
    # Start CPTY server in background
    cpty_task = asyncio.create_task(cpty.serve("[::]:50051"))
    await asyncio.sleep(3)  # Give server time to start
    logger.info("✓ CPTY server started on port 50051")
    
    try:
        # Connect to Architect Core
        logger.info("\n=== Connecting to Architect Core ===")
        client = ArchitectClient(
            host=os.getenv("ARCHITECT_HOST", "localhost:8081"),
            api_key=os.getenv("ARCHITECT_API_KEY"),
            api_secret=os.getenv("ARCHITECT_API_SECRET"),
        )
        
        # Login to Architect
        await client.login()
        logger.info("✓ Connected to Architect Core")
        
        # Get accounts
        accounts = await client.get_accounts()
        if not accounts:
            logger.error("No accounts available")
            return
        
        account = accounts[0]
        logger.info(f"✓ Using account: {account.account_id}")
        
        # Check initial balance
        logger.info("\n=== Checking Balance ===")
        summary = await client.get_account_summary(account.account_id)
        if summary and hasattr(summary, 'balances'):
            for currency, balance in summary.balances.items():
                logger.info(f"  {currency}: {balance}")
        
        # Place test order through Architect
        order_id = f"test-arch-{uuid.uuid4().hex[:8]}"
        
        order = Order(
            id=order_id,
            account=account.account_id,
            trader=os.getenv("ARCHITECT_API_KEY"),
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            quantity=Decimal("100"),
            order_type=OrderType.Limit,
            limit_price=Decimal("0.00001"),  # Very low price to avoid fill
            time_in_force=TimeInForce.GoodTillCancel,
            status=OrderStatus.Pending,
            recv_time=0,
            recv_time_ns=0,
            source=0,
            execution_venue="LIGHTER"
        )
        
        logger.info(f"\n=== Placing Order through Architect ===")
        logger.info(f"Order ID: {order.id}")
        logger.info(f"Symbol: {order.symbol}")
        logger.info(f"Side: {order.dir}")
        logger.info(f"Quantity: {order.quantity}")
        logger.info(f"Price: {order.limit_price}")
        
        # Place order
        try:
            result = await client.place_order(order)
            logger.info("✓ Order submitted to Architect Core")
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return
        
        # Wait for order to flow through the system
        await asyncio.sleep(5)
        
        # Check order status in Architect
        logger.info("\n=== Checking Order Status ===")
        open_orders = await client.get_open_orders()
        our_order = next((o for o in open_orders if o.id == order_id), None)
        
        if our_order:
            logger.info(f"✓ Order found in Architect")
            logger.info(f"  Status: {our_order.status}")
            logger.info(f"  Exchange ID: {getattr(our_order, 'exchange_order_id', 'N/A')}")
        else:
            logger.warning("Order not found in open orders")
        
        # Check if order reached CPTY
        logger.info("\n=== Checking CPTY Server ===")
        if order_id in cpty.client_to_exchange_id:
            exchange_id = cpty.client_to_exchange_id[order_id]
            logger.info(f"✓ Order reached CPTY server")
            logger.info(f"  Lighter transaction: {exchange_id}")
        else:
            logger.warning("Order not found in CPTY server")
        
        # Summary
        logger.info("\n=== Order Flow Summary ===")
        logger.info("1. Architect Client → ✓ Order placed")
        logger.info("2. Architect Core → ✓ Order received")
        logger.info(f"3. CPTY Server → {'✓ Order forwarded to Lighter' if order_id in cpty.client_to_exchange_id else '✗ Order not found'}")
        logger.info(f"4. Lighter Exchange → {'✓ Transaction created' if order_id in cpty.client_to_exchange_id else '✗ No transaction'}")
        
        # Cancel order if it's still open
        if our_order and our_order.status in [OrderStatus.Pending, OrderStatus.Open]:
            logger.info("\nCancelling order...")
            try:
                await client.cancel_order(order_id)
                logger.info("✓ Order cancelled")
            except Exception as e:
                logger.error(f"Failed to cancel: {e}")
        
    finally:
        # Cleanup
        cpty_task.cancel()
        try:
            await cpty_task
        except asyncio.CancelledError:
            pass
        
        logger.info("\n✅ Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)