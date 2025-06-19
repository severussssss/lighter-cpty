#!/usr/bin/env python3
"""Fetch all markets using the orderBooks endpoint."""
import asyncio
import aiohttp
import json
from dotenv import load_dotenv
import os

load_dotenv()


async def main():
    """Try to fetch orderbooks from various endpoints."""
    base_url = os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai")
    
    # Try different endpoint patterns
    endpoints = [
        f"{base_url}/orderBooks",
        f"{base_url}/api/orderBooks",
        f"{base_url}/api/v1/orderBooks",
        f"{base_url}/v1/orderBooks",
        f"{base_url}/orderbooks",
        f"{base_url}/api/orderbooks",
        f"{base_url}/api/v1/orderbooks",
        f"{base_url}/api/v1/order-books",
        f"{base_url}/v1/order-books",
        # Try with trailing slash
        f"{base_url}/orderBooks/",
        f"{base_url}/api/v1/orderBooks/",
    ]
    
    print("=== Searching for Lighter Markets ===\n")
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            print(f"Trying {endpoint}...")
            
            try:
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print(f"✓ SUCCESS! Found endpoint\n")
                        
                        data = await response.json()
                        
                        # Check if it's a dict of orderbooks
                        if isinstance(data, dict) and len(data) > 0:
                            print(f"Found {len(data)} markets:\n")
                            
                            # Process markets
                            markets = []
                            for market_id, orderbook in data.items():
                                try:
                                    market_id_int = int(market_id)
                                    markets.append({
                                        'id': market_id_int,
                                        'data': orderbook
                                    })
                                except:
                                    pass
                            
                            # Sort by ID
                            markets.sort(key=lambda x: x['id'])
                            
                            print(f"{'ID':>4} | {'Info'}")
                            print("-" * 40)
                            
                            hype_id = None
                            bera_id = None
                            
                            for market in markets:
                                market_id = market['id']
                                info = str(market['data'])[:50] + "..." if len(str(market['data'])) > 50 else str(market['data'])
                                print(f"{market_id:>4} | {info}")
                                
                                # Check data for HYPE/BERA references
                                data_str = json.dumps(market['data']).upper()
                                if 'HYPE' in data_str:
                                    hype_id = market_id
                                    print(f"     ^^^ Contains HYPE reference!")
                                if 'BERA' in data_str:
                                    bera_id = market_id
                                    print(f"     ^^^ Contains BERA reference!")
                            
                            # Save full data
                            with open('lighter_orderbooks.json', 'w') as f:
                                json.dump(data, f, indent=2)
                            
                            print(f"\n{'='*40}")
                            print(f"Total markets: {len(markets)}")
                            if hype_id:
                                print(f"HYPE found at market ID: {hype_id}")
                            if bera_id:
                                print(f"BERA found at market ID: {bera_id}")
                            print("\nFull data saved to lighter_orderbooks.json")
                            
                            return
                        else:
                            print(f"✗ Response is not market data")
                    else:
                        print(f"✗ Status {response.status}")
                        
            except asyncio.TimeoutError:
                print(f"✗ Timeout")
            except Exception as e:
                print(f"✗ Error: {type(e).__name__}")
    
    print("\n✗ Could not find orderbooks endpoint")
    print("\nTrying WebSocket approach...")
    
    # Try WebSocket
    ws_url = base_url.replace("https://", "wss://") + "/stream"
    print(f"\nWebSocket URL: {ws_url}")
    print("You can connect to the WebSocket and subscribe to orderbook channels")
    print("to discover available markets.")


if __name__ == "__main__":
    asyncio.run(main())