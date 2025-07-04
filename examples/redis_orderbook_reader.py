#!/usr/bin/env python3
"""Example of reading Lighter orderbooks from Redis."""
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def read_orderbooks():
    """Read and display orderbook data from Redis."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    r = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get all orderbook keys
        l1_keys = await r.keys("l1_book:*")
        l2_keys = await r.keys("l2_book:*")
        
        logger.info(f"Found {len(l1_keys)} L1 orderbooks and {len(l2_keys)} L2 orderbooks")
        
        # Display L1 orderbooks
        if l1_keys:
            print("\n=== L1 Orderbooks (Best Bid/Ask) ===")
            for key in sorted(l1_keys):
                data = await r.get(key)
                if data:
                    parsed = json.loads(data)
                    market_name = key.replace("l1_book:", "")
                    
                    best_bid = parsed.get('best_bid')
                    best_ask = parsed.get('best_ask')
                    spread = parsed.get('spread')
                    
                    if best_bid and best_ask:
                        print(f"\n{market_name}:")
                        print(f"  Best Bid: ${float(best_bid[0]):.4f} (Size: {best_bid[1]})")
                        print(f"  Best Ask: ${float(best_ask[0]):.4f} (Size: {best_ask[1]})")
                        print(f"  Spread: ${spread:.4f}")
        
        # Display L2 orderbooks (first few levels)
        if l2_keys:
            print("\n=== L2 Orderbooks (Market Depth) ===")
            for key in sorted(l2_keys)[:3]:  # Show first 3 markets
                data = await r.get(key)
                if data:
                    parsed = json.loads(data)
                    market_name = key.replace("l2_book:", "")
                    
                    bids = parsed.get('bids', [])
                    asks = parsed.get('asks', [])
                    
                    print(f"\n{market_name}:")
                    print(f"  Bid Depth: {parsed.get('bid_depth')}, Ask Depth: {parsed.get('ask_depth')}")
                    
                    # Show top 3 levels
                    print("  Top 3 Bids:")
                    for i, (price, size) in enumerate(bids[:3]):
                        print(f"    {i+1}. ${float(price):.4f} x {size}")
                    
                    print("  Top 3 Asks:")
                    for i, (price, size) in enumerate(asks[:3]):
                        print(f"    {i+1}. ${float(price):.4f} x {size}")
        
        # Get specific market example
        print("\n=== Specific Market Query Example ===")
        example_key = "l1_book:FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"
        data = await r.get(example_key)
        if data:
            print(f"Data for {example_key}:")
            print(json.dumps(json.loads(data), indent=2))
        else:
            print(f"No data found for {example_key}")
            print("Available markets:")
            for key in sorted(l1_keys)[:5]:
                print(f"  - {key}")
                
    finally:
        await r.close()


async def monitor_orderbooks(duration: int = 30):
    """Monitor orderbook updates in real-time."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    r = redis.from_url(redis_url, decode_responses=True)
    
    try:
        logger.info(f"Monitoring orderbooks for {duration} seconds...")
        
        start_time = asyncio.get_event_loop().time()
        last_values = {}
        
        while asyncio.get_event_loop().time() - start_time < duration:
            # Get all L1 orderbook keys
            keys = await r.keys("l1_book:*")
            
            for key in keys:
                data = await r.get(key)
                if data:
                    parsed = json.loads(data)
                    market_name = key.replace("l1_book:", "")
                    
                    if parsed.get('best_bid') and parsed.get('best_ask'):
                        bid_price = float(parsed['best_bid'][0])
                        ask_price = float(parsed['best_ask'][0])
                        
                        # Check if price changed
                        last_bid, last_ask = last_values.get(market_name, (None, None))
                        if last_bid != bid_price or last_ask != ask_price:
                            spread_pct = (ask_price - bid_price) / ask_price * 100
                            
                            # Show change indicators
                            bid_change = "↑" if last_bid and bid_price > last_bid else "↓" if last_bid and bid_price < last_bid else " "
                            ask_change = "↑" if last_ask and ask_price > last_ask else "↓" if last_ask and ask_price < last_ask else " "
                            
                            logger.info(
                                f"{market_name[:30]:30} | "
                                f"Bid: ${bid_price:.4f}{bid_change} | "
                                f"Ask: ${ask_price:.4f}{ask_change} | "
                                f"Spread: {spread_pct:.2f}%"
                            )
                            
                            last_values[market_name] = (bid_price, ask_price)
            
            await asyncio.sleep(0.5)
            
    finally:
        await r.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # Monitor mode
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        asyncio.run(monitor_orderbooks(duration))
    else:
        # Read mode
        asyncio.run(read_orderbooks())