#!/usr/bin/env python3
"""Simple script to check Lighter account status."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

import lighter
from lighter import ApiClient, Configuration
from lighter.api import AccountApi

# Load environment variables
load_dotenv()


async def main():
    print("=== Lighter Account Status ===\n")
    
    # Initialize API client
    configuration = Configuration(
        host=os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    )
    api_client = ApiClient(configuration=configuration)
    
    # Account index from env
    account_index = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "30188"))
    
    try:
        # Get account details
        account_api = AccountApi(api_client)
        response = await account_api.account(by="index", value=str(account_index))
        
        if not response.accounts:
            print("❌ No account found")
            return
            
        account = response.accounts[0]
        
        # Display account info
        print(f"Account Index: {account.index}")
        print(f"Collateral: ${account.collateral} USDC")
        print(f"Total Asset Value: ${account.total_asset_value}")
        print(f"\n📊 Order Summary:")
        print(f"  • Total Orders Ever Placed: {account.total_order_count}")
        
        # Count open orders from positions
        total_open_orders = 0
        if hasattr(account, 'positions') and account.positions:
            for pos in account.positions:
                if hasattr(pos, 'open_order_count'):
                    total_open_orders += pos.open_order_count
        
        print(f"  • Open Orders on Lighter: {total_open_orders}")
        
        if total_open_orders == 0:
            print("\n✅ No open orders on Lighter Exchange")
            print("\n💡 If Architect shows pending orders, they are stuck")
            print("   in the CPTY layer and never reached Lighter.")
        else:
            print(f"\n⚠️  {total_open_orders} orders are active on Lighter")
            
        # Show positions and orders by market
        if hasattr(account, 'positions') and account.positions:
            has_positions = False
            has_orders = False
            
            # Show positions
            for pos in account.positions:
                if hasattr(pos, 'position') and float(pos.position) != 0:
                    if not has_positions:
                        print(f"\n📈 Active Positions:")
                        has_positions = True
                    print(f"  • Market {pos.market_index}: {pos.position} contracts")
            
            # Show open orders by market
            for pos in account.positions:
                if hasattr(pos, 'open_order_count') and pos.open_order_count > 0:
                    if not has_orders:
                        print(f"\n📋 Open Orders by Market:")
                        has_orders = True
                    symbol = getattr(pos, 'symbol', f'Market {pos.market_id}')
                    print(f"  • {symbol}: {pos.open_order_count} open order(s)")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await api_client.close()
        
    print("\n" + "="*40)
    print("To check Architect's view of orders:")
    print("  python fetch_lighter_orders.py")
    print("\nTo monitor real-time updates:")
    print("  python monitor_lighter_orders.py")


if __name__ == "__main__":
    asyncio.run(main())