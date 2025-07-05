#!/usr/bin/env python3
"""Simple WebSocket test for Lighter."""
import asyncio
import json
import websockets

async def test_websocket():
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    print(f"Connecting to {url}...")
    
    try:
        async with websockets.connect(url) as ws:
            print("Connected!")
            
            # Wait for initial message
            print("Waiting for messages...")
            message = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(message)
            print(f"First message: {json.dumps(data, indent=2)}")
            
            # Subscribe to BTC orderbook
            sub = {
                "type": "subscribe",
                "channel": "order_book/0"
            }
            print(f"\nSending subscription: {json.dumps(sub)}")
            await ws.send(json.dumps(sub))
            
            # Receive a few messages
            for i in range(5):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(message)
                    print(f"\nMessage {i+2}: type={data.get('type')}, channel={data.get('channel')}")
                    if data.get('type') == 'error':
                        print(f"Error details: {data}")
                except asyncio.TimeoutError:
                    print(f"Timeout waiting for message {i+2}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())