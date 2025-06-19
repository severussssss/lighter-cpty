#!/usr/bin/env python3
"""Check available markets on Lighter."""
import asyncio
import os
from dotenv import load_dotenv
from lighter import ApiClient, Configuration, RootApi

load_dotenv()


async def check_markets():
    """Check all available markets."""
    # Create API client
    url = os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    config = Configuration(host=url)
    api_client = ApiClient(configuration=config)
    root_api = RootApi(api_client)
    
    print(f"Checking markets on {url}...\n")
    
    try:
        # Get exchange info
        info = await root_api.info()
        
        if hasattr(info, 'markets') and info.markets:
            print(f"Found {len(info.markets)} markets:\n")
            
            # Sort by market ID
            sorted_markets = sorted(info.markets.items(), key=lambda x: int(x[0]))
            
            # Track what we find
            found_hype = False
            found_bera = False
            
            print("ID  | Symbol      | Status")
            print("----|-------------|-------")
            
            for market_id, market in sorted_markets:
                base = getattr(market, 'base_asset', 'Unknown')
                quote = getattr(market, 'quote_asset', 'USDC')
                is_active = getattr(market, 'is_active', False)
                
                # Format output
                status = "Active" if is_active else "Inactive"
                print(f"{market_id:3} | {base:10}-{quote} | {status}")
                
                # Check for HYPE and BERA
                if base.upper() == 'HYPE':
                    found_hype = True
                elif base.upper() == 'BERA':
                    found_bera = True
            
            print(f"\nHYPE found: {'✓' if found_hype else '✗'}")
            print(f"BERA found: {'✓' if found_bera else '✗'}")
        else:
            print("No markets data in response")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(check_markets())