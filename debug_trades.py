#!/usr/bin/env python3
"""Debug script to examine Lighter WebSocket trade format."""

import asyncio
import json
from LighterCpty.lighter_ws import LighterWebSocketClient

async def debug_trades():
    """Connect to Lighter WS and examine trade messages."""
    
    def on_trade(market_or_account_id, trade_data):
        print(f"\n=== TRADE DATA ===")
        print(f"Market/Account ID: {market_or_account_id}")
        print(f"Trade data type: {type(trade_data)}")
        print(json.dumps(trade_data, indent=2))
        
        # Check for various ID fields
        if isinstance(trade_data, dict):
            print(f"\nID fields found:")
            for key in ['trade_id', 'tx_hash', 'ask_id', 'bid_id', 'order_id', 'id']:
                if key in trade_data:
                    print(f"  {key}: {trade_data[key]}")
    
    # Create WS client
    ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
    client = LighterWebSocketClient(ws_url)
    client.on_trade = on_trade
    
    # Run the client
    await asyncio.gather(
        client.run(),
        client.subscribe_trades(0),  # ETH market
        client.subscribe_trades(1),  # BTC market
    )

if __name__ == "__main__":
    asyncio.run(debug_trades())