#!/usr/bin/env python3
"""Test CPTY connection and status."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dotenv
from architect_py.async_client import AsyncClient

dotenv.load_dotenv()


async def main():
    print("\n=== CPTY Connection Test ===")
    
    # Connect
    client = await AsyncClient.connect(
        endpoint=os.getenv("ARCHITECT_HOST"),
        api_key=os.getenv("ARCHITECT_API_KEY"),
        api_secret=os.getenv("ARCHITECT_API_SECRET"),
        paper_trading=False,
        use_tls=True,
    )
    print("✓ Connected to Architect Core")
    
    # Check CPTY status
    print("\n=== Checking CPTY Status ===")
    try:
        status = await client.cpty_status(kind="LIGHTER")
        print(f"CPTY Kind: {status.kind}")
        print(f"Connected: {status.connected}")
        print(f"Stale: {status.stale}")
        print(f"Logged In: {status.logged_in}")
        
        if status.connections:
            print(f"\nConnections ({len(status.connections)}):")
            for conn_id, conn_status in status.connections.items():
                print(f"  {conn_id}: {conn_status}")
    except Exception as e:
        print(f"Error getting CPTY status: {e}")
    
    # List all CPTYs
    print("\n=== All CPTYs ===")
    try:
        cptys = await client.cptys()
        for cpty in cptys.cptys:
            print(f"- {cpty.kind} (Connected: {cpty.connected}, Stale: {cpty.stale})")
    except Exception as e:
        print(f"Error listing CPTYs: {e}")
    
    # Check venue connections
    print("\n=== Venue Connections ===")
    try:
        venues = await client.list_venues()
        for venue in venues:
            print(f"- {venue}")
    except Exception as e:
        print(f"Error listing venues: {e}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())