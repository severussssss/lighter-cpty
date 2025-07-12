#!/usr/bin/env python3
"""Test basic connectivity to CPTY."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("=== Testing CPTY Connectivity ===\n")
    
    try:
        # Connect to Architect
        print("1. Connecting to Architect Core...")
        client = await AsyncClient.connect(
            endpoint=os.getenv("ARCHITECT_HOST"),
            api_key=os.getenv("ARCHITECT_API_KEY"),
            api_secret=os.getenv("ARCHITECT_API_SECRET"),
            paper_trading=False,
            use_tls=True,
        )
        print("✓ Connected to Architect Core")
        
        # Stream orderflow to test connectivity
        print("\n2. Testing orderflow stream...")
        event_count = 0
        
        async def test_stream():
            nonlocal event_count
            try:
                async for event in client.stream_orderflow():
                    event_count += 1
                    print(f"✓ Received event: {type(event).__name__}")
                    if event_count >= 3:
                        break
            except Exception as e:
                print(f"✗ Stream error: {e}")
        
        task = asyncio.create_task(test_stream())
        await asyncio.sleep(3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        if event_count > 0:
            print(f"✓ Received {event_count} events - connectivity confirmed")
        else:
            print("✗ No events received - possible connectivity issue")
        
        await client.close()
        print("\n✓ Connectivity test completed")
        
    except Exception as e:
        print(f"\n✗ Connection error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())