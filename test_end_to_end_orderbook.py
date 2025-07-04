#!/usr/bin/env python3
"""End-to-end test of orderbook streaming functionality."""
import asyncio
import json
import redis
import time
from datetime import datetime
from LighterCpty.lighter_ws import LighterWebSocketClient

# Test configuration
TEST_MARKETS = [0, 1, 2, 21, 24]  # ETH, BTC, SOL, FARTCOIN, HYPE
TEST_DURATION = 30  # seconds


async def test_orderbook_streaming():
    """Test orderbook streaming end-to-end."""
    print("=" * 60)
    print("End-to-End Orderbook Streaming Test")
    print("=" * 60)
    
    # Clear Redis
    r = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    r.flushdb()
    print("✓ Cleared Redis database")
    
    # Start optimized streamer
    print("\nStarting optimized orderbook streamer...")
    process = await asyncio.create_subprocess_exec(
        'python', 'run_orderbook_streamer_optimized.py',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    # Wait for startup
    await asyncio.sleep(5)
    print("✓ Streamer started")
    
    # Monitor orderbook updates
    print(f"\nMonitoring {len(TEST_MARKETS)} markets for {TEST_DURATION} seconds...")
    print("-" * 60)
    
    market_names = {
        0: "ETH",
        1: "BTC", 
        2: "SOL",
        21: "FARTCOIN",
        24: "HYPE"
    }
    
    update_counts = {m: 0 for m in TEST_MARKETS}
    last_values = {m: {} for m in TEST_MARKETS}
    
    start_time = time.time()
    
    while time.time() - start_time < TEST_DURATION:
        # Check each market
        for market_id in TEST_MARKETS:
            market_name = market_names[market_id]
            key = f"l2_book:{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
            
            try:
                data = r.get(key)
                if data:
                    orderbook = json.loads(data)
                    
                    # Check if data changed
                    current_value = {
                        'best_bid': orderbook['bids'][0] if orderbook['bids'] else None,
                        'best_ask': orderbook['asks'][0] if orderbook['asks'] else None,
                        'timestamp': orderbook.get('timestamp', 0)
                    }
                    
                    if current_value != last_values[market_id]:
                        update_counts[market_id] += 1
                        last_values[market_id] = current_value
                        
                        # Print update every 5 seconds
                        elapsed = int(time.time() - start_time)
                        if elapsed % 5 == 0 and update_counts[market_id] == 1:
                            if current_value['best_bid'] and current_value['best_ask']:
                                bid_price = float(current_value['best_bid'][0])
                                ask_price = float(current_value['best_ask'][0])
                                spread = ask_price - bid_price
                                print(f"[{elapsed:2d}s] {market_name:>10}: "
                                      f"Bid=${bid_price:>10,.2f} Ask=${ask_price:>10,.2f} "
                                      f"Spread=${spread:>8,.4f}")
            except Exception as e:
                pass
                
        await asyncio.sleep(0.1)
    
    # Stop the streamer
    process.terminate()
    await process.wait()
    
    # Final report
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    print(f"\nUpdate counts over {TEST_DURATION} seconds:")
    total_updates = 0
    for market_id in TEST_MARKETS:
        market_name = market_names[market_id]
        count = update_counts[market_id]
        rate = count / TEST_DURATION
        total_updates += count
        
        status = "✓" if count > 10 else "✗"
        print(f"  {status} {market_name:>10}: {count:>4} updates ({rate:>5.1f}/s)")
    
    print(f"\nTotal updates: {total_updates} ({total_updates/TEST_DURATION:.1f}/s)")
    
    # Verify data quality
    print("\nData Quality Check:")
    all_good = True
    
    for market_id in TEST_MARKETS:
        market_name = market_names[market_id]
        key = f"l2_book:{market_name}-USDC LIGHTER Perpetual/USDC Crypto"
        
        try:
            data = r.get(key)
            if data:
                orderbook = json.loads(data)
                
                # Check data structure
                has_bids = len(orderbook.get('bids', [])) > 0
                has_asks = len(orderbook.get('asks', [])) > 0
                has_timestamp = orderbook.get('timestamp', 0) > 0
                has_depth = orderbook.get('bid_depth', 0) > 0
                
                if all([has_bids, has_asks, has_timestamp, has_depth]):
                    best_bid = float(orderbook['bids'][0][0])
                    best_ask = float(orderbook['asks'][0][0])
                    spread_pct = (best_ask - best_bid) / best_bid * 100
                    
                    print(f"  ✓ {market_name:>10}: Valid orderbook, "
                          f"{orderbook['bid_depth']} bids, {orderbook['ask_depth']} asks, "
                          f"spread={spread_pct:.3f}%")
                else:
                    print(f"  ✗ {market_name:>10}: Invalid orderbook structure")
                    all_good = False
            else:
                print(f"  ✗ {market_name:>10}: No data in Redis")
                all_good = False
                
        except Exception as e:
            print(f"  ✗ {market_name:>10}: Error: {e}")
            all_good = False
    
    # Performance metrics from Redis
    print("\nRedis Performance:")
    redis_info = r.info('commandstats')
    
    setex_stats = redis_info.get('cmdstat_setex', {})
    if setex_stats:
        calls = setex_stats.get('calls', 0)
        usec_per_call = setex_stats.get('usec_per_call', 0)
        print(f"  SETEX calls: {calls}")
        print(f"  Average latency: {usec_per_call:.1f} μs")
    
    # Overall result
    print("\n" + "=" * 60)
    if all_good and total_updates > len(TEST_MARKETS) * 10:
        print("✓ END-TO-END TEST PASSED")
        print(f"  - All {len(TEST_MARKETS)} markets streaming correctly")
        print(f"  - {total_updates/TEST_DURATION:.1f} updates per second")
        print(f"  - Data structure validated")
    else:
        print("✗ END-TO-END TEST FAILED")
        if total_updates < len(TEST_MARKETS) * 10:
            print(f"  - Insufficient updates: {total_updates} (expected > {len(TEST_MARKETS) * 10})")
        if not all_good:
            print(f"  - Data quality issues detected")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_orderbook_streaming())