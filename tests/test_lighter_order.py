#!/usr/bin/env python3
"""Test placing an order to LIGHTER using the configured account."""
import asyncio
import logging
import sys
import os
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from dotenv import load_dotenv
load_dotenv()

from architect_py.async_client import AsyncClient
from architect_py import OrderDir, TimeInForce


async def main():
    """Test LIGHTER order placement."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("=== LIGHTER Order Test ===")
    
    # The LIGHTER account from the core config
    LIGHTER_ACCOUNT_ID = "2f018d76-5cf9-658a-b08e-a04f36782817"
    LIGHTER_TRADER_ID = "23d913e4-2bb1-5e63-b94e-6a9f2ef761de"
    
    logger.info(f"Using LIGHTER account: {LIGHTER_ACCOUNT_ID}")
    logger.info(f"CPTY URL in core: http://13.114.195.99:50051")
    logger.info(f"Our CPTY server: localhost:50051")
    
    try:
        # Connect to Architect Core
        client = await AsyncClient.connect(
            endpoint=os.getenv("ARCHITECT_HOST"),
            api_key=os.getenv("ARCHITECT_API_KEY"),
            api_secret=os.getenv("ARCHITECT_API_SECRET"),
            paper_trading=False,
            use_tls=True,
        )
        logger.info("✓ Connected to Architect Core")
        
        # Create test order
        order_id = f"lighter-{uuid.uuid4().hex[:8]}-{int(datetime.now().timestamp())}"
        symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
        limit_price = Decimal("0.00001")
        quantity = Decimal("100")
        
        logger.info(f"\n=== Placing LIGHTER Order ===")
        logger.info(f"Order ID: {order_id}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Side: BUY")
        logger.info(f"Quantity: {quantity}")
        logger.info(f"Price: {limit_price}")
        logger.info(f"Account: {LIGHTER_ACCOUNT_ID}")
        
        # Monitor CPTY logs in another terminal
        logger.info("\nMonitor CPTY logs in another terminal:")
        logger.info("  tmux attach -t lighter-cpty")
        
        # Place order
        try:
            result = await client.place_order(
                symbol=symbol,
                execution_venue="LIGHTER",
                order_id=order_id,
                dir=OrderDir.BUY,
                limit_price=limit_price,
                quantity=quantity,
                account=LIGHTER_ACCOUNT_ID,  # Use the account ID directly
                time_in_force=TimeInForce.GTC,
                order_type="LIMIT",
                post_only=False,
            )
            logger.info("✓ Order sent to Architect Core!")
            logger.info(f"Result: {result}")
            
            # The order should now flow:
            # Architect Core -> http://13.114.195.99:50051 (our CPTY) -> Lighter
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            logger.info("\nTroubleshooting:")
            logger.info("1. Check if Architect Core can reach our CPTY at the configured URL")
            logger.info("2. The core config shows: http://13.114.195.99:50051")
            logger.info("3. Make sure that IP/port is accessible from Architect Core")
            return
        
        # Wait for order processing
        await asyncio.sleep(5)
        
        # Check if order was processed
        logger.info("\n=== Checking Order Status ===")
        try:
            # Try to get order status
            open_orders = await client.list_open_orders()
            our_order = next((o for o in open_orders if o.order_id == order_id), None)
            
            if our_order:
                logger.info(f"✓ Order found: {our_order.status}")
                
                # Cancel it
                await client.cancel_order(order_id)
                logger.info("✓ Order cancelled")
            else:
                logger.info("Order not in open orders (check CPTY logs)")
        except Exception as e:
            logger.warning(f"Could not check order status: {e}")
        
        logger.info("\n✅ Test completed!")
        logger.info("\nCheck CPTY logs to see if the order was received:")
        logger.info("  tmux capture-pane -t lighter-cpty -p | grep -i 'place\\|order'")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())