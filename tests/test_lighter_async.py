"""Comprehensive test suite for the AsyncCpty-based Lighter implementation."""
import asyncio
import logging
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from LighterCpty.lighter_cpty_async import LighterCpty
from architect_py import (
    Order,
    OrderDir,
    OrderType,
    OrderStatus,
    TimeInForce,
    CptyLoginRequest,
    CptyLogoutRequest,
    Cancel,
)


class TestLighterCpty:
    """Test suite for LighterCpty."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cpty = None
    
    async def setup(self):
        """Setup test environment."""
        self.cpty = LighterCpty()
        self.logger.info("Created LighterCpty instance")
        
    async def test_execution_info(self):
        """Test execution info setup."""
        self.logger.info("\n=== Testing Execution Info ===")
        
        # Check execution venues
        venues = list(self.cpty.execution_info.keys())
        assert "LIGHTER" in venues, f"LIGHTER not in venues: {venues}"
        self.logger.info(f"✓ Execution venues: {venues}")
        
        # Check symbols
        lighter_symbols = list(self.cpty.execution_info["LIGHTER"].keys())
        expected_symbols = [
            "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            "HYPE-USDC LIGHTER Perpetual/USDC Crypto",
            "BERA-USDC LIGHTER Perpetual/USDC Crypto",
        ]
        
        for symbol in expected_symbols:
            assert symbol in lighter_symbols, f"Symbol {symbol} not found"
            exec_info = self.cpty.execution_info["LIGHTER"][symbol]
            assert exec_info.execution_venue == "LIGHTER"
            assert exec_info.tick_size == {"simple": "0.00001"}
            self.logger.info(f"✓ Symbol {symbol} configured correctly")
    
    async def test_login(self):
        """Test login functionality."""
        self.logger.info("\n=== Testing Login ===")
        
        # Create login request
        login_req = CptyLoginRequest(
            trader="test_trader",
            account="12345"
        )
        
        # Test login
        try:
            await self.cpty.on_login(login_req)
            assert self.cpty.logged_in == True
            assert self.cpty.user_id == "test_trader"
            assert self.cpty.account_id == "12345"
            assert self.cpty.account_index == 12345
            self.logger.info("✓ Login successful")
        except Exception as e:
            self.logger.error(f"✗ Login failed: {e}")
            raise
    
    async def test_order_placement(self):
        """Test order placement."""
        self.logger.info("\n=== Testing Order Placement ===")
        
        # Create a test order
        test_order = Order(
            id="test-order-001",
            account="12345",
            trader="test_trader",
            symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
            dir=OrderDir.BUY,
            quantity=Decimal("10"),
            order_type=OrderType.Limit,
            limit_price=Decimal("0.50"),
            time_in_force=TimeInForce.GoodTillCancel,
            status=OrderStatus.Pending,
            recv_time=int(datetime.now().timestamp()),
            recv_time_ns=0,
            source=0,
            execution_venue="LIGHTER"
        )
        
        # Mock order acknowledgment
        order_acks = []
        original_ack_order = self.cpty.ack_order
        
        def mock_ack_order(order_id, exchange_order_id=None):
            order_acks.append((order_id, exchange_order_id))
            self.logger.info(f"Order acknowledged: {order_id} -> {exchange_order_id}")
        
        self.cpty.ack_order = mock_ack_order
        
        try:
            # Place order
            await self.cpty.on_place_order(test_order)
            
            # Wait a bit for async operations
            await asyncio.sleep(0.1)
            
            # Check that order was acknowledged
            assert len(order_acks) > 0, "No order acknowledgments received"
            assert order_acks[0][0] == "test-order-001"
            self.logger.info("✓ Order placement successful")
            
        finally:
            self.cpty.ack_order = original_ack_order
    
    async def test_cancel_order(self):
        """Test order cancellation."""
        self.logger.info("\n=== Testing Order Cancellation ===")
        
        # Create cancel request using the correct field names
        from architect_py import CancelStatus
        cancel_req = Cancel.new(
            order_id="test-order-001",
            status=CancelStatus.Pending,
            recv_time=int(datetime.now().timestamp()),
            recv_time_ns=0,
            cancel_id="cancel-001"
        )
        
        # Mock cancel rejection
        cancel_rejects = []
        original_reject_cancel = self.cpty.reject_cancel
        
        def mock_reject_cancel(cancel_id, reject_reason, reject_message=None):
            cancel_rejects.append((cancel_id, reject_reason, reject_message))
            self.logger.info(f"Cancel rejected: {cancel_id} - {reject_reason}")
        
        self.cpty.reject_cancel = mock_reject_cancel
        
        try:
            # Attempt to cancel
            await self.cpty.on_cancel_order(cancel_req)
            
            # Check that cancel was rejected (as expected in current implementation)
            assert len(cancel_rejects) > 0, "No cancel rejections received"
            assert cancel_rejects[0][0] == "cancel-001"
            self.logger.info("✓ Cancel rejection working as expected")
            
        finally:
            self.cpty.reject_cancel = original_reject_cancel
    
    async def test_account_updates(self):
        """Test account update broadcasting."""
        self.logger.info("\n=== Testing Account Updates ===")
        
        # Mock account data
        mock_account_data = {
            "equity": "10000.50",
            "positions": [
                {
                    "market_id": 21,
                    "quantity": "100",
                    "entryPrice": "0.45"
                }
            ]
        }
        
        # Set up test data
        self.cpty.latest_account_data = mock_account_data
        self.cpty.latest_balance = Decimal("10000.50")
        self.cpty.account_id = "12345"
        
        # Mock update_account_summary
        updates = []
        original_update = self.cpty.update_account_summary
        
        def mock_update(*args, **kwargs):
            updates.append(kwargs)
            self.logger.info(f"Account update: balances={kwargs.get('balances')}")
        
        self.cpty.update_account_summary = mock_update
        
        try:
            # Trigger account update
            await self.cpty._broadcast_account_update()
            
            # Check that update was sent
            assert len(updates) > 0, "No account updates sent"
            update = updates[0]
            assert "balances" in update
            assert "USDC Crypto" in update["balances"]
            assert update["balances"]["USDC Crypto"] == Decimal("10000.50")
            self.logger.info("✓ Account updates working correctly")
            
        finally:
            self.cpty.update_account_summary = original_update
    
    async def test_logout(self):
        """Test logout functionality."""
        self.logger.info("\n=== Testing Logout ===")
        
        # Ensure we're logged in first
        self.cpty.logged_in = True
        self.cpty.user_id = "test_trader"
        
        # Create logout request
        logout_req = CptyLogoutRequest()
        
        # Test logout
        await self.cpty.on_logout(logout_req)
        
        assert self.cpty.logged_in == False
        assert self.cpty.user_id == None
        self.logger.info("✓ Logout successful")
    
    async def run_all_tests(self):
        """Run all tests."""
        await self.setup()
        
        tests = [
            self.test_execution_info,
            self.test_login,
            self.test_order_placement,
            self.test_cancel_order,
            self.test_account_updates,
            self.test_logout,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                await test()
                passed += 1
            except Exception as e:
                failed += 1
                self.logger.error(f"Test {test.__name__} failed: {e}")
        
        self.logger.info(f"\n=== Test Results ===")
        self.logger.info(f"Passed: {passed}")
        self.logger.info(f"Failed: {failed}")
        self.logger.info(f"Total: {len(tests)}")
        
        return failed == 0


async def main():
    """Run the test suite."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    tester = TestLighterCpty()
    success = await tester.run_all_tests()
    
    if not success:
        sys.exit(1)
    
    print("\n✅ All tests passed! The AsyncCpty implementation is working correctly.")
    print("\nTo start the server, run:")
    print("  python lighter_cpty_server_async.py")


if __name__ == "__main__":
    asyncio.run(main())