#!/usr/bin/env python3
"""Fetch all market information from Lighter API."""
import requests
import json
from typing import Dict, Any

def fetch_all_markets() -> Dict[int, Dict[str, Any]]:
    """Fetch all market information from Lighter API.
    
    Returns:
        Dict mapping market_id to market info
    """
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        # Create market mapping
        market_mapping = {}
        
        # Extract order_books array from response
        order_books = data.get('order_books', [])
        
        for market in order_books:
            market_id = market.get('market_id')
            if market_id is not None:
                # Symbol is the base asset, quote is always USDC
                symbol = market.get('symbol', '')
                base_asset = symbol
                quote_asset = 'USDC'
                
                market_mapping[market_id] = {
                    'base_asset': base_asset,
                    'quote_asset': quote_asset,
                    'symbol': symbol,
                    'min_base_amount': market.get('min_base_amount'),
                    'min_quote_amount': market.get('min_quote_amount'),
                    'supported_size_decimals': market.get('supported_size_decimals'),
                    'supported_price_decimals': market.get('supported_price_decimals'),
                    'supported_quote_decimals': market.get('supported_quote_decimals'),
                    'maker_fee': market.get('maker_fee'),
                    'taker_fee': market.get('taker_fee'),
                }
        
        return market_mapping
        
    except Exception as e:
        print(f"Error fetching market info: {e}")
        return {}


def main():
    """Fetch and display market information."""
    print("Fetching market information from Lighter API...")
    markets = fetch_all_markets()
    
    if not markets:
        print("Failed to fetch market information")
        return
    
    print(f"\nFound {len(markets)} markets:\n")
    
    # Sort by market ID
    for market_id in sorted(markets.keys()):
        info = markets[market_id]
        print(f"Market ID {market_id:>3}: {info['symbol']:>15} "
              f"(decimals: size={info['supported_size_decimals']}, "
              f"price={info['supported_price_decimals']})")
    
    # Save to file for reference
    output_file = "market_info.json"
    with open(output_file, 'w') as f:
        json.dump(markets, f, indent=2)
    print(f"\nSaved market information to {output_file}")
    
    # Generate Python dict for code
    print("\nPython dict for code:")
    print("MARKET_INFO = {")
    for market_id in sorted(markets.keys()):
        info = markets[market_id]
        print(f"    {market_id}: {{'base_asset': '{info['base_asset']}', 'quote_asset': '{info['quote_asset']}'}},")
    print("}")


if __name__ == "__main__":
    main()