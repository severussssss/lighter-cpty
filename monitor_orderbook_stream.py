#!/usr/bin/env python3
"""Monitor orderbook streaming without starting a new connection."""
import redis
import json
import time
from datetime import datetime

def monitor_orderbooks():
    """Monitor existing orderbook data in Redis."""
    r = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    
    print("Monitoring orderbook data in Redis...")
    print("=" * 80)
    
    # Check both key formats
    key_patterns = ["l2_book:*", "orderbook:*"]
    
    while True:
        all_keys = []
        for pattern in key_patterns:
            keys = r.keys(pattern)
            all_keys.extend(keys)
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(all_keys)} orderbook keys")
        
        # Sample a few markets
        sample_markets = {
            "BTC": ["l2_book:BTC-USDC LIGHTER Perpetual/USDC Crypto", 
                    "orderbook:BTC-USDC LIGHTER Perpetual/USDC Crypto"],
            "ETH": ["l2_book:ETH-USDC LIGHTER Perpetual/USDC Crypto",
                    "orderbook:ETH-USDC LIGHTER Perpetual/USDC Crypto"],
            "FARTCOIN": ["l2_book:FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto",
                         "orderbook:FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto"]
        }
        
        for market, keys in sample_markets.items():
            for key in keys:
                try:
                    data = r.get(key)
                    if data:
                        ob = json.loads(data)
                        # Get best bid/ask
                        if 'bids' in ob and ob['bids']:
                            bid = ob['bids'][0]
                            bid_price = float(bid[0] if isinstance(bid, list) else bid.get('price', 0))
                        else:
                            bid_price = 0
                            
                        if 'asks' in ob and ob['asks']:
                            ask = ob['asks'][0]
                            ask_price = float(ask[0] if isinstance(ask, list) else ask.get('price', 0))
                        else:
                            ask_price = 0
                        
                        if bid_price > 0 and ask_price > 0:
                            spread = ask_price - bid_price
                            ttl = r.ttl(key)
                            key_type = "L2" if key.startswith("l2_book") else "L1"
                            
                            print(f"  {market:>10} ({key_type}): Bid=${bid_price:>10,.2f} Ask=${ask_price:>10,.2f} "
                                  f"Spread=${spread:>8,.4f} TTL={ttl:>4}s")
                            break  # Found data for this market
                except:
                    pass
        
        # Check write activity
        redis_info = r.info('commandstats')
        setex_stats = redis_info.get('cmdstat_setex', {})
        if setex_stats:
            print(f"\n  Redis SETEX calls: {setex_stats.get('calls', 0):,}")
        
        time.sleep(5)


if __name__ == "__main__":
    try:
        monitor_orderbooks()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")