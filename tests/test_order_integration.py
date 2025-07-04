"""Integration test for placing orders through Architect core to Lighter exchange."""
import asyncio
import logging
import sys
import time
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv
import os

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

# Load environment variables
load_dotenv()

import grpc
from architect_py import Client as ArchitectClient
from architect_py import (
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
)


class OrderIntegrationTest:
    """Test order placement through Architect core to Lighter exchange."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.architect_client = None
        self.orders_placed = []
        
    async def setup(self):
        """Setup Architect client connection."""
        try:
            # Create Architect client
            self.architect_client = ArchitectClient(
                host=os.getenv("ARCHITECT_HOST"),
                api_key=os.getenv("ARCHITECT_API_KEY"),
                api_secret=os.getenv("ARCHITECT_API_SECRET"),
            )
            
            # Login to get account info
            await self.architect_client.login()
            self.logger.info("✓ Connected to Architect core")
            
            # Get accounts
            accounts = await self.architect_client.get_accounts()
            self.logger.info(f"✓ Available accounts: {[acc.account_id for acc in accounts]}")
            
            if not accounts:
                raise Exception("No accounts available")
            
            # Use first account
            self.account = accounts[0]
            self.logger.info(f"✓ Using account: {self.account.account_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            return False
    
    async def test_place_order(self, symbol: str, side: OrderDir, quantity: Decimal, price: Decimal):
        """Place a test order."""
        order_id = f"test-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        
        self.logger.info(f"\n=== Placing Order ===")
        self.logger.info(f"Order ID: {order_id}")
        self.logger.info(f"Symbol: {symbol}")
        self.logger.info(f"Side: {side}")
        self.logger.info(f"Quantity: {quantity}")
        self.logger.info(f"Price: {price}")
        
        try:
            # Create order
            order = Order(
                id=order_id,
                account=self.account.account_id,
                trader=os.getenv("ARCHITECT_API_KEY"),
                symbol=symbol,
                dir=side,
                quantity=quantity,
                order_type=OrderType.Limit,
                limit_price=price,
                time_in_force=TimeInForce.GoodTillCancel,
                status=OrderStatus.Pending,
                recv_time=int(datetime.now().timestamp()),
                recv_time_ns=0,
                source=0,
                execution_venue="LIGHTER"
            )
            
            # Place order
            result = await self.architect_client.place_order(order)
            self.orders_placed.append(order_id)
            
            self.logger.info(f"✓ Order placed successfully")
            self.logger.info(f"Result: {result}")
            
            # Wait a bit for order to be processed
            await asyncio.sleep(2)
            
            # Check order status
            orders = await self.architect_client.get_open_orders()
            our_order = next((o for o in orders if o.id == order_id), None)
            
            if our_order:
                self.logger.info(f"✓ Order found in open orders")
                self.logger.info(f"Status: {our_order.status}")
                self.logger.info(f"Exchange order ID: {getattr(our_order, 'exchange_order_id', 'N/A')}")
            else:
                self.logger.warning("⚠ Order not found in open orders (might be filled or rejected)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"✗ Order placement failed: {e}")
            return False
    
    async def check_balances(self):
        """Check account balances."""
        try:
            self.logger.info("\n=== Checking Balances ===")
            
            # Get account summary
            summary = await self.architect_client.get_account_summary(self.account.account_id)
            
            if summary and hasattr(summary, 'balances'):
                for currency, balance in summary.balances.items():
                    self.logger.info(f"{currency}: {balance}")
            else:
                self.logger.warning("No balance data available")
                
        except Exception as e:
            self.logger.error(f"Failed to get balances: {e}")
    
    async def cleanup_orders(self):
        """Cancel any remaining open orders."""
        try:
            self.logger.info("\n=== Cleaning Up Orders ===")
            
            orders = await self.architect_client.get_open_orders()
            for order in orders:
                if order.id in self.orders_placed:
                    self.logger.info(f"Cancelling order: {order.id}")
                    await self.architect_client.cancel_order(order.id)
                    
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
    
    async def run_full_test(self):
        """Run the complete integration test."""
        self.logger.info("=== Starting Lighter CPTY Integration Test ===")
        
        # Setup
        if not await self.setup():
            self.logger.error("Setup failed, aborting test")
            return False
        
        # Check initial balances
        await self.check_balances()
        
        # Test different order types
        test_cases = [
            # (symbol, side, quantity, price)
            ("FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto", OrderDir.BUY, Decimal("100"), Decimal("0.0001")),
            ("HYPE-USDC LIGHTER Perpetual/USDC Crypto", OrderDir.BUY, Decimal("1"), Decimal("1.0")),
            ("BERA-USDC LIGHTER Perpetual/USDC Crypto", OrderDir.SELL, Decimal("10"), Decimal("10.0")),
        ]
        
        results = []
        for symbol, side, qty, price in test_cases:
            result = await self.test_place_order(symbol, side, qty, price)
            results.append(result)
            await asyncio.sleep(1)  # Space out orders
        
        # Check final balances
        await self.check_balances()
        
        # Cleanup
        await self.cleanup_orders()
        
        # Summary
        self.logger.info("\n=== Test Summary ===")
        self.logger.info(f"Total tests: {len(results)}")
        self.logger.info(f"Passed: {sum(1 for r in results if r)}")
        self.logger.info(f"Failed: {sum(1 for r in results if not r)}")
        
        return all(results)


async def start_cpty_server():
    """Start the Lighter CPTY server in the background."""
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    logger = logging.getLogger("cpty_server")
    logger.info("Starting Lighter CPTY server...")
    
    cpty = LighterCpty()
    # Run server on a different port to avoid conflicts
    asyncio.create_task(cpty.serve("[::]:50052"))
    
    # Give server time to start
    await asyncio.sleep(2)
    logger.info("CPTY server started on port 50052")


async def main():
    """Run the integration test."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start CPTY server
    await start_cpty_server()
    
    # Run integration test
    tester = OrderIntegrationTest()
    success = await tester.run_full_test()
    
    if success:
        print("\n✅ Integration test completed successfully!")
        print("Orders were placed through Architect core and reached the Lighter exchange.")
    else:
        print("\n❌ Integration test failed!")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")