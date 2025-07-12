#!/usr/bin/env python3
"""Check orders directly from Lighter."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

import lighter
from lighter import ApiClient, Configuration

load_dotenv()


async def main():
    print("=== Checking Orders Directly from Lighter ===\n")
    
    # Initialize Lighter API client
    config = Configuration(
        host="https://mainnet.zklighter.elliot.ai",
        api_key={"ApiKeyAuth": os.getenv("LIGHTER_API_KEY")}
    )
    
    async with ApiClient(config) as api_client:
        api_instance = lighter.MarketsApi(api_client)
        
        try:
            # Get open orders for account
            print(f"Checking orders for account index: 30188")
            
            # Get order nonces (this gives us active orders)
            orders_api = lighter.OrdersApi(api_client)
            account_orders = await orders_api.get_order_nonces(
                blockchain_id="245022926",
                account_id="30188"
            )
            
            print(f"\nOrder nonces response: {account_orders}")
            
            # Also check blockchains endpoint
            blockchains_api = lighter.BlockchainsApi(api_client)
            blockchain_info = await blockchains_api.get_blockchains()
            print(f"\nBlockchain info: {blockchain_info}")
            
        except Exception as e:
            print(f"Error: {e}")
            
            # Try a simpler approach - get market info
            try:
                print("\nTrying to get market info...")
                markets = await api_instance.get_markets(blockchain_id="245022926")
                print(f"Markets available: {len(markets)}")
                
                # Look for FARTCOIN market
                for market in markets:
                    if "FARTCOIN" in str(market.base_asset):
                        print(f"\nFARTCOIN Market: {market}")
                        break
                        
            except Exception as e2:
                print(f"Market error: {e2}")


if __name__ == "__main__":
    asyncio.run(main())