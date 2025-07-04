#!/usr/bin/env python3
"""Inspect orderbook data stored in Redis."""
import asyncio
import json
import redis.asyncio as redis
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


async def inspect_redis_books():
    """Inspect all orderbook data in Redis."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        await r.ping()
        print("✓ Connected to Redis")
        
        # Get all orderbook keys
        all_keys = await r.keys("*book:*")
        l1_keys = [k for k in all_keys if k.startswith("l1_book:")]
        l2_keys = [k for k in all_keys if k.startswith("l2_book:")]
        
        print(f"\nFound {len(l1_keys)} L1 orderbooks and {len(l2_keys)} L2 orderbooks")
        print("=" * 80)
        
        # Inspect L1 orderbooks
        if l1_keys:
            print("\n📊 L1 ORDERBOOKS (Best Bid/Ask)")
            print("-" * 80)
            
            for key in sorted(l1_keys):
                data = await r.get(key)
                ttl = await r.ttl(key)
                
                if data:
                    try:
                        parsed = json.loads(data)
                        market_name = key.replace("l1_book:", "")
                        
                        print(f"\n🔹 {market_name}")
                        print(f"   Market ID: {parsed.get('market_id')}")
                        print(f"   TTL: {ttl} seconds")
                        
                        best_bid = parsed.get('best_bid')
                        best_ask = parsed.get('best_ask')
                        
                        if best_bid:
                            print(f"   Best Bid: ${float(best_bid[0]):.6f} x {best_bid[1]}")
                        else:
                            print("   Best Bid: None")
                            
                        if best_ask:
                            print(f"   Best Ask: ${float(best_ask[0]):.6f} x {best_ask[1]}")
                        else:
                            print("   Best Ask: None")
                            
                        if parsed.get('spread') is not None:
                            print(f"   Spread: ${parsed['spread']:.6f}")
                            
                        timestamp = parsed.get('timestamp')
                        if timestamp:
                            print(f"   Timestamp: {timestamp}")
                            
                    except json.JSONDecodeError:
                        print(f"   ❌ Invalid JSON data")
                    except Exception as e:
                        print(f"   ❌ Error parsing: {e}")
        
        # Inspect L2 orderbooks (show first few)
        if l2_keys:
            print("\n\n📊 L2 ORDERBOOKS (Market Depth)")
            print("-" * 80)
            
            for i, key in enumerate(sorted(l2_keys)):
                if i >= 3:  # Only show first 3 L2 books
                    print(f"\n... and {len(l2_keys) - 3} more L2 orderbooks")
                    break
                    
                data = await r.get(key)
                ttl = await r.ttl(key)
                
                if data:
                    try:
                        parsed = json.loads(data)
                        market_name = key.replace("l2_book:", "")
                        
                        print(f"\n🔹 {market_name}")
                        print(f"   Market ID: {parsed.get('market_id')}")
                        print(f"   TTL: {ttl} seconds")
                        print(f"   Bid Levels: {parsed.get('bid_depth', 0)}")
                        print(f"   Ask Levels: {parsed.get('ask_depth', 0)}")
                        
                        bids = parsed.get('bids', [])
                        asks = parsed.get('asks', [])
                        
                        # Show top 3 levels
                        if bids:
                            print("   Top Bids:")
                            for j, (price, size) in enumerate(bids[:3]):
                                print(f"     {j+1}. ${float(price):.6f} x {size}")
                                
                        if asks:
                            print("   Top Asks:")
                            for j, (price, size) in enumerate(asks[:3]):
                                print(f"     {j+1}. ${float(price):.6f} x {size}")
                                
                        # Calculate some stats
                        if bids and asks:
                            bid_prices = [float(b[0]) for b in bids]
                            ask_prices = [float(a[0]) for a in asks]
                            
                            spread = ask_prices[0] - bid_prices[0]
                            spread_pct = (spread / ask_prices[0]) * 100
                            
                            print(f"   Spread: ${spread:.6f} ({spread_pct:.3f}%)")
                            
                            # Check data validity
                            if bid_prices[0] >= ask_prices[0]:
                                print("   ⚠️  WARNING: Bid >= Ask (crossed book)")
                            
                            # Check if prices are sorted
                            bid_sorted = all(bid_prices[i] >= bid_prices[i+1] for i in range(len(bid_prices)-1))
                            ask_sorted = all(ask_prices[i] <= ask_prices[i+1] for i in range(len(ask_prices)-1))
                            
                            if not bid_sorted:
                                print("   ⚠️  WARNING: Bids not properly sorted")
                            if not ask_sorted:
                                print("   ⚠️  WARNING: Asks not properly sorted")
                                
                    except Exception as e:
                        print(f"   ❌ Error parsing: {e}")
        
        # Show raw data for one example
        if all_keys:
            print("\n\n📄 RAW DATA EXAMPLE")
            print("-" * 80)
            example_key = sorted(all_keys)[0]
            raw_data = await r.get(example_key)
            if raw_data:
                print(f"Key: {example_key}")
                print(f"Raw data (first 500 chars):")
                print(raw_data[:500])
                if len(raw_data) > 500:
                    print("...")
                    
                # Pretty print the JSON
                try:
                    parsed = json.loads(raw_data)
                    print("\nParsed JSON:")
                    print(json.dumps(parsed, indent=2)[:1000])
                except:
                    pass
                    
    except redis.ConnectionError:
        print("❌ Could not connect to Redis. Make sure Redis is running.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'r' in locals():
            await r.close()


if __name__ == "__main__":
    asyncio.run(inspect_redis_books())