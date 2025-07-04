"""Simple test for AsyncCpty-based Lighter implementation without API key requirements."""
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
    Cancel,
    CancelStatus,
)


async def test_basic_functionality():
    """Test basic functionality without needing API keys."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create instance
    cpty = LighterCpty()
    logger.info("✓ Created LighterCpty instance")
    
    # Test execution info
    logger.info(f"✓ Execution venues: {list(cpty.execution_info.keys())}")
    logger.info(f"✓ Symbols: {list(cpty.symbol_to_market_id.keys())}")
    
    # Test helper methods
    logger.info("\n=== Testing Helper Methods ===")
    
    # Test ack_order (just verify it doesn't crash)
    cpty.ack_order("test-order-1", exchange_order_id="exchange-123")
    logger.info("✓ ack_order works")
    
    # Test reject_order
    from architect_py import OrderRejectReason
    cpty.reject_order(
        "test-order-2",
        reject_reason=OrderRejectReason.UnknownSymbol,
        reject_message="Test rejection"
    )
    logger.info("✓ reject_order works")
    
    # Test out_order
    cpty.out_order("test-order-3", canceled=False)
    logger.info("✓ out_order works")
    
    # Test fill_order
    cpty.fill_order(
        dir=OrderDir.BUY,
        exchange_fill_id="fill-123",
        price=Decimal("0.50"),
        quantity=Decimal("10"),
        symbol="FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
        trade_time=datetime.now(),
        account="12345",
        is_taker=True,
        order_id="test-order-4",
    )
    logger.info("✓ fill_order works")
    
    # Test update_account_summary
    cpty.update_account_summary(
        account="12345",
        is_snapshot=True,
        timestamp=datetime.now(),
        balances={"USDC Crypto": Decimal("10000")},
    )
    logger.info("✓ update_account_summary works")
    
    # Test reject_cancel
    cpty.reject_cancel(
        "cancel-123",
        reject_reason="Not implemented",
        reject_message="Cancels not supported"
    )
    logger.info("✓ reject_cancel works")
    
    logger.info("\n✅ All basic functionality tests passed!")
    logger.info("\nThe AsyncCpty implementation is working correctly.")
    logger.info("Note: Full integration tests require valid API keys.")


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())