#!/usr/bin/env python3
"""Test writing Lighter orderbook data to Redis."""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from LighterCpty.redis_orderbook import RedisOrderbookClient


def test_write_orderbooks():
    """Test writing orderbook data in Lighter format."""
    
    # Initialize Redis client (uses db=2 by default now)
    redis_client = RedisOrderbookClient()
    redis_client.connect()
    
    # Set market info for FARTCOIN
    redis_client.set_market_info(21, {
        "base_asset": "FARTCOIN",
        "quote_asset": "USDC"
    })
    
    # Example orderbook data from Lighter WebSocket
    # Based on the WebSocket docs format
    orderbook_data = {
        "code": 0,
        "bids": [
            {"price": "0.0812", "size": "12500"},
            {"price": "0.0811", "size": "25000"},
            {"price": "0.0810", "size": "50000"},
            {"price": "0.0809", "size": "75000"},
            {"price": "0.0808", "size": "100000"}
        ],
        "asks": [
            {"price": "0.0813", "size": "13000"},
            {"price": "0.0814", "size": "26000"},
            {"price": "0.0815", "size": "52000"},
            {"price": "0.0816", "size": "78000"},
            {"price": "0.0817", "size": "104000"}
        ],
        "offset": 41692864
    }
    
    # Write both L1 and L2 orderbooks
    redis_client.write_orderbooks(21, orderbook_data)
    
    print("✅ Wrote FARTCOIN orderbook to Redis")
    
    # Also write a HYPE orderbook
    redis_client.set_market_info(15, {
        "base_asset": "HYPE",
        "quote_asset": "USDC"
    })
    
    hype_orderbook = {
        "code": 0,
        "bids": [
            {"price": "18.245", "size": "542.1"},
            {"price": "18.240", "size": "1084.2"},
            {"price": "18.235", "size": "2168.4"}
        ],
        "asks": [
            {"price": "18.250", "size": "540.5"},
            {"price": "18.255", "size": "1081.0"},
            {"price": "18.260", "size": "2162.0"}
        ],
        "offset": 41692865
    }
    
    redis_client.write_orderbooks(15, hype_orderbook)
    print("✅ Wrote HYPE orderbook to Redis")
    
    redis_client.disconnect()
    
    # Now check what was written
    print("\n📊 Checking Redis data...")
    check_redis_data()


def check_redis_data():
    """Verify the data was written correctly."""
    redis_client = RedisOrderbookClient()
    redis_client.connect()
    
    # Check L1 books
    fartcoin_l1 = redis_client.get_l1_orderbook("FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto")
    if fartcoin_l1:
        print(f"\n✅ FARTCOIN L1: Bid={fartcoin_l1['best_bid']}, Ask={fartcoin_l1['best_ask']}, Spread={fartcoin_l1['spread']}")
    
    hype_l1 = redis_client.get_l1_orderbook("HYPE-USDC LIGHTER Perpetual/USDC Crypto")
    if hype_l1:
        print(f"✅ HYPE L1: Bid={hype_l1['best_bid']}, Ask={hype_l1['best_ask']}, Spread={hype_l1['spread']}")
    
    # Check L2 books
    fartcoin_l2 = redis_client.get_l2_orderbook("FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto")
    if fartcoin_l2:
        print(f"\n✅ FARTCOIN L2: {fartcoin_l2['bid_depth']} bid levels, {fartcoin_l2['ask_depth']} ask levels")
        print("  Top 3 Bids:", fartcoin_l2['bids'][:3])
        print("  Top 3 Asks:", fartcoin_l2['asks'][:3])
    
    redis_client.disconnect()


if __name__ == "__main__":
    test_write_orderbooks()