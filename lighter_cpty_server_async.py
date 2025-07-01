"""Lighter CPTY server using AsyncCpty implementation."""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
# Add architect-py to path
sys.path.insert(0, str(Path(__file__).parent / "architect-py"))

from LighterCpty.lighter_cpty_async import LighterCpty


async def main():
    """Run the Lighter CPTY server."""
    print("[INFO] Starting Lighter CPTY server using AsyncCpty...")
    
    # Create and run the CPTY server
    cpty = LighterCpty()
    
    # The AsyncCpty base class provides the serve method
    await cpty.serve("[::]:50051")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"[ERROR] Server error: {e}")
        sys.exit(1)