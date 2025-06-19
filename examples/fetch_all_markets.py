#!/usr/bin/env python3
"""Fetch all available markets from Lighter API."""
import asyncio
import aiohttp
import json
from dotenv import load_dotenv
import os

load_dotenv()


async def fetch_markets_direct():
    """Fetch markets directly from Lighter API."""
    url = os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    
    print(f"Fetching markets from {url}...\n")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Try the info endpoint
            async with session.get(f"{url}/info") as response:
                if response.status == 200:
                    data = await response.json()
                    print("Raw response from /info:")
                    print(json.dumps(data, indent=2)[:1000])  # First 1000 chars
                    
                    if 'markets' in data:
                        print(f"\nFound {len(data['markets'])} markets:")
                        print("-" * 50)
                        
                        # Convert and sort markets
                        markets = []
                        for market_id, market_info in data['markets'].items():
                            markets.append((int(market_id), market_info))
                        
                        markets.sort(key=lambda x: x[0])
                        
                        print(f"{'ID':>4} | {'Base':>10} | {'Quote':>6} | {'Active':>6}")
                        print("-" * 50)
                        
                        for market_id, info in markets:
                            base = info.get('base_asset', 'Unknown')
                            quote = info.get('quote_asset', 'USDC')
                            active = info.get('is_active', False)
                            
                            print(f"{market_id:>4} | {base:>10} | {quote:>6} | {'Yes' if active else 'No':>6}")
                            
                            # Highlight HYPE and BERA
                            if base.upper() in ['HYPE', 'BERA']:
                                print(f"     ^^^ Found {base}! Market ID: {market_id}")
                    else:
                        print("No 'markets' field in response")
                else:
                    print(f"Error: Status {response.status}")
                    text = await response.text()
                    print(f"Response: {text[:200]}")
                    
        except Exception as e:
            print(f"Error fetching markets: {e}")
            
        # Try alternative endpoints
        print("\n\nTrying alternative endpoints...")
        
        endpoints = [
            "/api/v1/markets",
            "/api/markets", 
            "/markets",
            "/exchange/info",
            "/api/v1/exchange/info"
        ]
        
        for endpoint in endpoints:
            try:
                async with session.get(f"{url}{endpoint}") as response:
                    print(f"\n{endpoint}: Status {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"Response preview: {json.dumps(data, indent=2)[:200]}...")
            except Exception as e:
                print(f"{endpoint}: Error - {type(e).__name__}")


async def fetch_using_sdk():
    """Try using the SDK to fetch markets."""
    print("\n\nTrying with Lighter SDK...")
    
    try:
        from lighter import ApiClient, Configuration, RootApi
        
        config = Configuration(host=os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai"))
        api_client = ApiClient(configuration=config)
        root_api = RootApi(api_client)
        
        # Get info
        info = await root_api.info()
        
        print(f"SDK Response type: {type(info)}")
        print(f"Has markets attr: {hasattr(info, 'markets')}")
        
        if hasattr(info, '__dict__'):
            print(f"Attributes: {list(info.__dict__.keys())}")
            
        # Try to access data different ways
        if hasattr(info, 'markets'):
            print(f"Markets type: {type(info.markets)}")
            if info.markets:
                print(f"Number of markets: {len(info.markets)}")
                
                # Try to iterate
                if hasattr(info.markets, 'items'):
                    for i, (k, v) in enumerate(info.markets.items()):
                        if i < 5:  # First 5 markets
                            print(f"Market {k}: {v}")
                            
        await api_client.close()
        
    except Exception as e:
        print(f"SDK Error: {e}")
        import traceback
        traceback.print_exc()


async def check_specific_markets():
    """Check if specific market IDs work."""
    print("\n\nChecking specific market IDs...")
    
    # Based on community info, HYPE and BERA might be at these IDs
    potential_markets = {
        11: "HYPE",
        12: "HYPE", 
        13: "HYPE",
        14: "BERA",
        15: "BERA",
        16: "BERA",
        17: "TRUMP",
        18: "MELANIA",
        19: "SONIC",
        20: "AI16Z",
        22: "PENGU",
        23: "SPX",
        24: "MOG",
        25: "POPCAT"
    }
    
    print("\nPotential market mappings to test:")
    for market_id, name in potential_markets.items():
        print(f"  Market ID {market_id}: {name}")


async def main():
    """Run all market discovery methods."""
    print("=== Lighter Market Discovery ===\n")
    
    # Try direct API
    await fetch_markets_direct()
    
    # Try SDK
    await fetch_using_sdk()
    
    # Show potential mappings
    await check_specific_markets()
    
    print("\n\nNote: If markets aren't showing in the API response, they might still")
    print("be tradeable using the correct market ID. You can test specific IDs")
    print("by placing small test orders.")


if __name__ == "__main__":
    asyncio.run(main())