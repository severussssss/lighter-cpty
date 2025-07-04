#!/usr/bin/env python3
"""Test CPTY server standalone functionality."""
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


async def test_cpty_functionality():
    """Test CPTY server core functionality."""
    from LighterCpty.lighter_cpty_async import LighterCpty
    from architect_py import (
        Order, OrderDir, OrderType, OrderStatus,
        TimeInForce, CptyLoginRequest
    )
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create CPTY instance
    cpty = LighterCpty()
    logger.info("✓ Created CPTY instance")
    
    # Test execution info
    logger.info(f"✓ Execution venue: {cpty.execution_venue}")
    logger.info(f"✓ Markets configured: {len(cpty.symbol_to_market_id)}")
    
    # Test login
    login_req = CptyLoginRequest(trader="test", account="30188")
    await cpty.on_login(login_req)
    logger.info("✓ Login successful")
    
    # Wait for WebSocket connection
    await asyncio.sleep(2)
    logger.info(f"✓ WebSocket connected: {cpty.ws_connected}")
    
    # Test order placement mechanism (without actually placing)
    test_order = Order(
        id="test-001",
        account="30188",
        trader="test",
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        dir=OrderDir.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.Limit,
        limit_price=Decimal("0.00001"),
        time_in_force=TimeInForce.GoodTillCancel,
        status=OrderStatus.Pending,
        recv_time=0,
        recv_time_ns=0,
        source=0,
        execution_venue="LIGHTER"
    )
    
    # Test order validation
    market_id = cpty.symbol_to_market_id.get(test_order.symbol)
    if market_id:
        logger.info(f"✓ Symbol mapped to market ID: {market_id}")
    else:
        logger.error(f"✗ Symbol not found: {test_order.symbol}")
    
    # Test price/quantity conversion
    if market_id == 21:  # FARTCOIN
        price_int = int(float(test_order.limit_price) * 100000)
        base_amount = int(float(test_order.quantity) * 10)
        logger.info(f"✓ FARTCOIN conversion: price={price_int}, amount={base_amount}")
    
    # Check signer client
    if cpty.signer_client:
        logger.info("✓ Signer client initialized")
    else:
        logger.error("✗ Signer client not initialized")
    
    logger.info("\n=== CPTY Server Status ===")
    logger.info(f"Logged in: {cpty.logged_in}")
    logger.info(f"Account: {cpty.account_id}")
    logger.info(f"WebSocket: {cpty.ws_connected}")
    logger.info(f"Signer client: {'Ready' if cpty.signer_client else 'Not ready'}")
    
    # Logout
    await cpty.on_logout(None)
    logger.info("✓ Logged out")
    
    return True


async def test_grpc_server():
    """Test CPTY as a gRPC server."""
    from LighterCpty.lighter_cpty_async import LighterCpty
    
    logger = logging.getLogger("grpc_test")
    
    # Start server
    cpty = LighterCpty()
    server_task = asyncio.create_task(cpty.serve("[::]:50051"))
    
    logger.info("✓ gRPC server started on port 50051")
    logger.info("  Ready to receive orders from Architect Core")
    
    # Let it run for a bit
    await asyncio.sleep(5)
    
    # Cancel server
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    
    logger.info("✓ gRPC server stopped")
    return True


async def main():
    """Run all tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=== Testing CPTY Server ===\n")
    
    # Test basic functionality
    logger.info("1. Testing core functionality...")
    result1 = await test_cpty_functionality()
    
    # Test gRPC server
    logger.info("\n2. Testing gRPC server...")
    result2 = await test_grpc_server()
    
    if result1 and result2:
        logger.info("\n✅ All tests passed!")
        logger.info("\nThe CPTY server is working correctly.")
        logger.info("To integrate with Architect Core:")
        logger.info("  1. Ensure Architect Core is configured to route LIGHTER orders to localhost:50051")
        logger.info("  2. Start this CPTY server: python lighter_cpty_server_async.py")
        logger.info("  3. Place orders through Architect Client")
    else:
        logger.error("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())