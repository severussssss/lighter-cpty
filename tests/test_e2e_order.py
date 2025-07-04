#!/usr/bin/env python3
"""End-to-end test: Architect Client → Core → CPTY → Lighter."""
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

# Import Architect client
from architect_py.async_client import AsyncClient
from architect_py import (
    Order,
    OrderDir,
    TimeInForce,
)


async def main():
    """Test complete order flow through Architect."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("=== E2E Order Test: Architect → CPTY → Lighter ===")
    logger.info(f"CPTY server should be running on localhost:50051")
    
    # Check CPTY server logs
    logger.info("\nChecking CPTY server status...")
    os.system("tmux capture-pane -t lighter-cpty -p | tail -5")
    
    try:
        # Connect to Architect Core
        logger.info("\n=== Connecting to Architect Core ===")
        logger.info(f"Host: {os.getenv('ARCHITECT_HOST')}")
        
        client = await AsyncClient.connect(
            endpoint=os.getenv("ARCHITECT_HOST"),
            api_key=os.getenv("ARCHITECT_API_KEY"),
            api_secret=os.getenv("ARCHITECT_API_SECRET"),
            paper_trading=False,
            use_tls=True,
        )
        logger.info("✓ Connected to Architect Core")
        
        # Get accounts
        accounts = await client.list_accounts()
        if not accounts:
            logger.error("No accounts available")
            return
        
        # Find LIGHTER account
        lighter_account = None
        for acc in accounts:
            # Log available attributes
            account_str = str(acc.account)
            logger.info(f"  Account: {account_str}")
            
            # Check various ways LIGHTER might be configured
            if any(x in account_str.upper() for x in ['LIGHTER', 'LIGHT', 'ZK']):
                lighter_account = acc
                logger.info(f"    ✓ Found LIGHTER account!")
                break
        
        if not lighter_account:
            logger.error("No LIGHTER account found!")
            logger.info("Make sure LIGHTER is configured in Architect Core")
            logger.info("The CPTY server is running on localhost:50051")
            return
        
        logger.info(f"✓ Using LIGHTER account: {lighter_account.account}")
        
        # Check balance
        logger.info("\n=== Checking Balance ===")
        try:
            balances = await client.get_balances(lighter_account.account)
            if balances:
                for balance in balances:
                    logger.info(f"  {balance.currency}: {balance.balance}")
        except Exception as e:
            logger.warning(f"Could not get balance: {e}")
        
        # Create test order
        order_id = f"e2e-{uuid.uuid4().hex[:8]}-{int(datetime.now().timestamp())}"
        symbol = "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
        limit_price = Decimal("0.00001")  # Very low price
        quantity = Decimal("100")  # 100 FARTCOIN
        
        logger.info(f"\n=== Placing Order ===")
        logger.info(f"Order ID: {order_id}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Side: BUY")
        logger.info(f"Quantity: {quantity}")
        logger.info(f"Price: {limit_price}")
        logger.info(f"Venue: LIGHTER")
        
        # Place order using the correct method
        try:
            # Use place_order instead of deprecated place_limit_order
            result = await client.place_order(
                symbol=symbol,
                execution_venue="LIGHTER",
                order_id=order_id,
                dir=OrderDir.BUY,
                limit_price=limit_price,
                quantity=quantity,
                account=lighter_account.account.id if hasattr(lighter_account.account, 'id') else str(lighter_account.account),
                time_in_force=TimeInForce.GTC,
                order_type="LIMIT",
                post_only=False,
            )
            logger.info("✓ Order sent to Architect Core")
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return
        
        # Wait for order to process
        logger.info("\nWaiting for order to flow through system...")
        await asyncio.sleep(5)
        
        # Check order status
        logger.info("\n=== Checking Order Status ===")
        try:
            open_orders = await client.list_open_orders()
            our_order = next((o for o in open_orders if o.order_id == order_id), None)
            
            if our_order:
                logger.info(f"✓ Order found in Architect")
                logger.info(f"  Status: {our_order.status}")
                logger.info(f"  Exchange ID: {getattr(our_order, 'exchange_order_id', 'N/A')}")
                
                # Cancel the order
                logger.info("\nCancelling order...")
                await client.cancel_order(order_id)
                logger.info("✓ Order cancelled")
            else:
                logger.warning("Order not found in open orders (might be rejected or filled)")
        except Exception as e:
            logger.error(f"Error checking order: {e}")
        
        # Check CPTY logs
        logger.info("\n=== CPTY Server Logs ===")
        os.system("tmux capture-pane -t lighter-cpty -p | grep -E '(PlaceOrder|place_order|Order placed|Failed)' | tail -10")
        
        logger.info("\n✅ Test completed!")
        logger.info("\nCheck the CPTY server logs for details:")
        logger.info("  tmux attach -t lighter-cpty")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())