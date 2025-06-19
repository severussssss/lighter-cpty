# HYPE and BERA Trading on Lighter - Summary

Based on my testing, here's what I found:

## Working Markets (Confirmed)
- **ETH-USDC**: Market ID 0
- **BTC-USDC**: Market ID 1  
- **FARTCOIN-USDC**: Market ID 21 (5 price decimals, 1 size decimal)
- Other default markets: SOL (2), DOGE (3), 1000PEPE (4), WIF (5), WLD (6), XRP (7), LINK (8), AVAX (9), NEAR (10)

## HYPE and BERA Status
**Not Found** - After testing market IDs 11-20, neither HYPE nor BERA appear to be available on Lighter mainnet.

### Evidence:
1. The API's `/info` endpoint doesn't return market data (returns empty)
2. Market IDs jump from 10 (NEAR) to 21 (FARTCOIN), leaving a gap
3. Attempted orders with market IDs 11-20 failed to execute
4. No references to HYPE or BERA in the codebase

## Possible Reasons:
1. **Not Listed**: HYPE and BERA might not be listed on Lighter mainnet
2. **Different Exchange**: They might be available on other exchanges that Architect supports
3. **Future Listings**: They could be added in the future (market IDs 11-20 are unused)

## How to Add New Markets
When HYPE/BERA are added to Lighter, update the default markets list in `lighter_cpty.py`:

```python
default_markets = [
    # ... existing markets ...
    (11, "HYPE", "USDC"),  # If HYPE gets market ID 11
    (15, "BERA", "USDC"),  # If BERA gets market ID 15
]
```

## Recommendation
For now, HYPE and BERA cannot be traded through the Lighter CPTY integration. You can:
1. Trade other supported assets (ETH, BTC, FARTCOIN, etc.)
2. Check with Lighter for when these markets might be added
3. Use a different exchange integration if available in Architect