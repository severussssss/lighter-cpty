#!/usr/bin/env python3
"""Find all active markets by testing market IDs."""
import asyncio
import os
from dotenv import load_dotenv
from lighter import SignerClient, ApiClient, Configuration
import lighter

load_dotenv()


async def test_market_id(signer_client, market_id):
    """Test if a market ID exists by trying to place a tiny order."""
    try:
        # Try to place a very small order at a very low price
        tx, tx_hash, err = await signer_client.create_order(
            market_index=market_id,
            client_order_index=12345,
            base_amount=1,  # Smallest possible amount
            price=1,        # Lowest possible price
            is_ask=False,   # Buy order
            order_type=SignerClient.ORDER_TYPE_LIMIT,
            time_in_force=SignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
            reduce_only=0,
            trigger_price=0
        )
        
        if err is None:
            # Order was accepted, market exists
            # Cancel it immediately
            await signer_client.cancel_order(
                market_index=market_id,
                order_index=12345
            )
            return True, None
        else:
            # Check error message
            error_str = str(err)
            if "market is not found" in error_str:
                return False, "not found"
            elif "order price flagged" in error_str:
                # Market exists but price was rejected
                return True, "exists"
            else:
                return False, error_str
                
    except Exception as e:
        return False, str(e)


async def main():
    """Scan market IDs to find all active markets."""
    print("=== Lighter Market Scanner ===\n")
    
    # Initialize signer client
    signer_client = SignerClient(
        url=os.getenv("LIGHTER_URL", "https://mainnet.zklighter.elliot.ai"),
        private_key=os.getenv("LIGHTER_API_KEY_PRIVATE_KEY"),
        account_index=int(os.getenv("LIGHTER_ACCOUNT_INDEX", "30188")),
        api_key_index=int(os.getenv("LIGHTER_API_KEY_INDEX", "1"))
    )
    
    # Check client
    err = signer_client.check_client()
    if err:
        print(f"Client check failed: {err}")
        return
    
    print("Testing market IDs 0-50...\n")
    
    found_markets = []
    
    for market_id in range(51):  # Test 0-50
        exists, info = await test_market_id(signer_client, market_id)
        
        if exists:
            found_markets.append(market_id)
            print(f"Market ID {market_id:2d}: ✓ EXISTS")
        else:
            if info == "not found":
                print(f"Market ID {market_id:2d}: ✗ Not found")
            else:
                print(f"Market ID {market_id:2d}: ✗ Error: {info[:50]}")
        
        # Small delay to avoid rate limits
        if market_id % 5 == 0 and market_id > 0:
            await asyncio.sleep(1)
    
    # Summary
    print(f"\n{'='*50}")
    print("FOUND MARKETS:")
    print('='*50)
    
    known_names = {
        0: "ETH",
        1: "BTC", 
        2: "SOL",
        3: "DOGE",
        4: "1000PEPE",
        5: "WIF",
        6: "WLD",
        7: "XRP",
        8: "LINK",
        9: "AVAX",
        10: "NEAR",
        21: "FARTCOIN"
    }
    
    for market_id in found_markets:
        name = known_names.get(market_id, "Unknown")
        print(f"Market ID {market_id:2d}: {name}")
    
    print(f"\nTotal markets found: {len(found_markets)}")
    
    # Clean up
    await signer_client.close()


if __name__ == "__main__":
    asyncio.run(main())