#!/usr/bin/env python3
"""Discover actual market IDs by analyzing price ranges."""
import asyncio
import json
import websockets

async def discover_markets():
    """Subscribe to many markets and guess what they are by price."""
    ws_url = 'wss://mainnet.zklighter.elliot.ai/stream'
    
    async with websockets.connect(ws_url) as ws:
        # Wait for connected
        await ws.recv()
        
        # Subscribe to first 30 markets
        for market_id in range(30):
            sub = {'type': 'subscribe', 'channel': f'order_book/{market_id}'}
            await ws.send(json.dumps(sub))
            await asyncio.sleep(0.05)
        
        print("Analyzing markets by price range...\n")
        print(f"{'Market':>6} | {'Best Bid':>12} | {'Best Ask':>12} | {'Likely Asset'}")
        print("-" * 60)
        
        # Collect some messages
        market_data = {}
        for _ in range(100):  # Process 100 messages
            msg = await ws.recv()
            data = json.loads(msg)
            
            if data.get('type') == 'update/order_book':
                channel = data.get('channel', '')
                if ':' in channel:
                    market_id = int(channel.split(':')[-1])
                    ob = data.get('order_book', {})
                    bids = ob.get('bids', [])
                    asks = ob.get('asks', [])
                    
                    if bids or asks:
                        bid_price = float(bids[0]['price']) if bids else 0
                        ask_price = float(asks[0]['price']) if asks else 0
                        
                        # Store the latest data
                        market_data[market_id] = {
                            'bid': bid_price,
                            'ask': ask_price,
                            'mid': (bid_price + ask_price) / 2 if bid_price and ask_price else max(bid_price, ask_price)
                        }
        
        # Analyze and guess assets
        for market_id in sorted(market_data.keys()):
            data = market_data[market_id]
            mid = data['mid']
            
            # Guess based on price ranges
            if mid > 50000:
                likely = "BTC"
            elif 2000 < mid < 4000:
                likely = "ETH"
            elif 100 < mid < 1000:
                likely = "SOL/BNB/AVAX"
            elif 10 < mid < 100:
                likely = "MATIC/LINK/UNI"
            elif 0.5 < mid < 10:
                likely = "DOGE/XRP/ADA/HYPE"
            elif 0.01 < mid < 0.5:
                likely = "SHIB/PEPE/FARTCOIN"
            else:
                likely = "Unknown/Stablecoin"
            
            print(f"{market_id:>6} | {data['bid']:>12.4f} | {data['ask']:>12.4f} | {likely}")

if __name__ == "__main__":
    asyncio.run(discover_markets())