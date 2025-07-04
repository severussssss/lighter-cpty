"""Lighter balance fetching utilities."""
import logging
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import lighter
from lighter import ApiClient, Configuration, AccountApi
from lighter.exceptions import ApiException

logger = logging.getLogger(__name__)


class LighterBalanceFetcher:
    """Helper class to fetch balance information from Lighter."""
    
    def __init__(self, api_client: ApiClient):
        """Initialize balance fetcher.
        
        Args:
            api_client: Lighter API client instance
        """
        self.api_client = api_client
        self.account_api = AccountApi(api_client)
    
    async def get_account_balance(self, account_index: int) -> Tuple[Optional[Decimal], Optional[Dict[str, Any]]]:
        """Fetch account balance from Lighter API.
        
        Args:
            account_index: Account index to fetch balance for
            
        Returns:
            Tuple of (balance, full_account_data)
        """
        try:
            # Get account details using the account API
            logger.info(f"Fetching account details for index {account_index}")
            
            # Use the account endpoint with "index" parameter
            account_data = await self.account_api.account(
                by="index",
                value=str(account_index)
            )
            
            if account_data and hasattr(account_data, 'accounts') and account_data.accounts:
                account_info = account_data.accounts[0]
                
                # Extract balance from account info
                balance = None
                if hasattr(account_info, 'collateral'):
                    balance = Decimal(str(account_info.collateral))
                    logger.info(f"Account collateral balance: {balance}")
                elif hasattr(account_info, 'equity'):
                    balance = Decimal(str(account_info.equity))
                    logger.info(f"Account equity: {balance}")
                
                # Convert account info to dict for easier access
                account_dict = account_info.to_dict() if hasattr(account_info, 'to_dict') else vars(account_info)
                
                return balance, account_dict
            else:
                logger.warning("No account data found")
                return None, None
                
        except ApiException as e:
            logger.error(f"API error fetching account balance: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None, None
    
    @staticmethod
    def parse_ws_account_update(account_data: Dict[str, Any]) -> Optional[Decimal]:
        """Parse balance from WebSocket account update message.
        
        Args:
            account_data: Account data from WebSocket update
            
        Returns:
            Balance if found, None otherwise
        """
        # Check for direct balance fields
        if "balance" in account_data:
            return Decimal(str(account_data["balance"]))
        if "equity" in account_data:
            return Decimal(str(account_data["equity"]))
        if "collateral" in account_data:
            return Decimal(str(account_data["collateral"]))
        
        # Calculate from positions if available
        if "positions" in account_data:
            total_margin = Decimal("0")
            for market_id, position in account_data["positions"].items():
                if isinstance(position, dict) and "allocated_margin" in position:
                    margin = Decimal(str(position["allocated_margin"]))
                    total_margin += margin
            
            if total_margin > 0:
                logger.info(f"Calculated total margin from positions: {total_margin}")
                return total_margin
        
        return None
    
    @staticmethod
    def calculate_account_equity(account_data: Dict[str, Any]) -> Optional[Decimal]:
        """Calculate account equity from positions and PnL.
        
        Args:
            account_data: Account data containing positions
            
        Returns:
            Calculated equity if possible, None otherwise
        """
        try:
            equity = Decimal("0")
            
            # Add up position values and unrealized PnL
            if "positions" in account_data:
                for market_id, position in account_data["positions"].items():
                    if isinstance(position, dict):
                        # Add position value (negative because it represents obligation)
                        if "position_value" in position:
                            position_value = Decimal(str(position["position_value"]))
                            equity -= position_value  # Position value is negative for longs
                        
                        # Add unrealized PnL
                        if "unrealized_pnl" in position:
                            unrealized_pnl = Decimal(str(position["unrealized_pnl"]))
                            equity += unrealized_pnl
                        
                        # Add allocated margin
                        if "allocated_margin" in position:
                            margin = Decimal(str(position["allocated_margin"]))
                            equity += margin
            
            return equity if equity != 0 else None
            
        except Exception as e:
            logger.error(f"Error calculating equity: {e}")
            return None