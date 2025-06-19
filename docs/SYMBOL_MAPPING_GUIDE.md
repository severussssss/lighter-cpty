# Symbol Mapping: Architect ↔ Lighter

## Overview

The Lighter CPTY integration translates between Architect's standardized symbol format and Lighter's internal market IDs.

## Symbol Format

### Architect Symbol Format
```
BASE-QUOTE LIGHTER Perpetual/QUOTE Crypto
```

**Structure:**
- `BASE`: The base asset (e.g., ETH, BTC, HYPE, BERA)
- `QUOTE`: The quote asset (always USDC for Lighter)
- `LIGHTER`: Exchange identifier
- `Perpetual`: Product type
- `Crypto`: Asset class

**Examples:**
- `ETH-USDC LIGHTER Perpetual/USDC Crypto`
- `HYPE-USDC LIGHTER Perpetual/USDC Crypto`
- `BERA-USDC LIGHTER Perpetual/USDC Crypto`

### Lighter Internal Format
Lighter uses numeric market IDs (0-42 currently).

## Mapping System

### 1. Symbol Construction
```python
def _build_architect_symbol(self, base_asset: str, quote_asset: str) -> str:
    """Build Architect-style symbol."""
    return f"{base_asset}-{quote_asset} LIGHTER Perpetual/{quote_asset} Crypto"
```

### 2. Symbol Parsing
```python
def _parse_architect_symbol(self, symbol: str) -> tuple[str, str]:
    """Parse Architect symbol to extract base and quote assets."""
    parts = symbol.split(' ')
    if parts and '-' in parts[0]:
        base, quote = parts[0].split('-')
        return base, quote
    return None, None
```

### 3. Bidirectional Mappings
The system maintains two dictionaries:
- `symbol_to_market_id`: Architect symbol → Lighter market ID
- `market_id_to_symbol`: Lighter market ID → Architect symbol

## Complete Symbol Mapping Table

| Architect Symbol | Lighter Market ID | Base Asset | Quote Asset |
|-----------------|-------------------|------------|-------------|
| `ETH-USDC LIGHTER Perpetual/USDC Crypto` | 0 | ETH | USDC |
| `BTC-USDC LIGHTER Perpetual/USDC Crypto` | 1 | BTC | USDC |
| `SOL-USDC LIGHTER Perpetual/USDC Crypto` | 2 | SOL | USDC |
| `DOGE-USDC LIGHTER Perpetual/USDC Crypto` | 3 | DOGE | USDC |
| `1000PEPE-USDC LIGHTER Perpetual/USDC Crypto` | 4 | 1000PEPE | USDC |
| `WIF-USDC LIGHTER Perpetual/USDC Crypto` | 5 | WIF | USDC |
| `WLD-USDC LIGHTER Perpetual/USDC Crypto` | 6 | WLD | USDC |
| `XRP-USDC LIGHTER Perpetual/USDC Crypto` | 7 | XRP | USDC |
| `LINK-USDC LIGHTER Perpetual/USDC Crypto` | 8 | LINK | USDC |
| `AVAX-USDC LIGHTER Perpetual/USDC Crypto` | 9 | AVAX | USDC |
| `NEAR-USDC LIGHTER Perpetual/USDC Crypto` | 10 | NEAR | USDC |
| `DOT-USDC LIGHTER Perpetual/USDC Crypto` | 11 | DOT | USDC |
| `TON-USDC LIGHTER Perpetual/USDC Crypto` | 12 | TON | USDC |
| `TAO-USDC LIGHTER Perpetual/USDC Crypto` | 13 | TAO | USDC |
| `POL-USDC LIGHTER Perpetual/USDC Crypto` | 14 | POL | USDC |
| `TRUMP-USDC LIGHTER Perpetual/USDC Crypto` | 15 | TRUMP | USDC |
| `SUI-USDC LIGHTER Perpetual/USDC Crypto` | 16 | SUI | USDC |
| `1000SHIB-USDC LIGHTER Perpetual/USDC Crypto` | 17 | 1000SHIB | USDC |
| `1000BONK-USDC LIGHTER Perpetual/USDC Crypto` | 18 | 1000BONK | USDC |
| `1000FLOKI-USDC LIGHTER Perpetual/USDC Crypto` | 19 | 1000FLOKI | USDC |
| `BERA-USDC LIGHTER Perpetual/USDC Crypto` | 20 | BERA | USDC |
| `FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto` | 21 | FARTCOIN | USDC |
| `AI16Z-USDC LIGHTER Perpetual/USDC Crypto` | 22 | AI16Z | USDC |
| `POPCAT-USDC LIGHTER Perpetual/USDC Crypto` | 23 | POPCAT | USDC |
| `HYPE-USDC LIGHTER Perpetual/USDC Crypto` | 24 | HYPE | USDC |
| `BNB-USDC LIGHTER Perpetual/USDC Crypto` | 25 | BNB | USDC |
| `JUP-USDC LIGHTER Perpetual/USDC Crypto` | 26 | JUP | USDC |
| `AAVE-USDC LIGHTER Perpetual/USDC Crypto` | 27 | AAVE | USDC |
| `MKR-USDC LIGHTER Perpetual/USDC Crypto` | 28 | MKR | USDC |
| `ENA-USDC LIGHTER Perpetual/USDC Crypto` | 29 | ENA | USDC |
| `UNI-USDC LIGHTER Perpetual/USDC Crypto` | 30 | UNI | USDC |
| `APT-USDC LIGHTER Perpetual/USDC Crypto` | 31 | APT | USDC |
| `SEI-USDC LIGHTER Perpetual/USDC Crypto` | 32 | SEI | USDC |
| `KAITO-USDC LIGHTER Perpetual/USDC Crypto` | 33 | KAITO | USDC |
| `IP-USDC LIGHTER Perpetual/USDC Crypto` | 34 | IP | USDC |
| `LTC-USDC LIGHTER Perpetual/USDC Crypto` | 35 | LTC | USDC |
| `CRV-USDC LIGHTER Perpetual/USDC Crypto` | 36 | CRV | USDC |
| `PENDLE-USDC LIGHTER Perpetual/USDC Crypto` | 37 | PENDLE | USDC |
| `ONDO-USDC LIGHTER Perpetual/USDC Crypto` | 38 | ONDO | USDC |
| `ADA-USDC LIGHTER Perpetual/USDC Crypto` | 39 | ADA | USDC |
| `S-USDC LIGHTER Perpetual/USDC Crypto` | 40 | S | USDC |
| `VIRTUAL-USDC LIGHTER Perpetual/USDC Crypto` | 41 | VIRTUAL | USDC |
| `SPX-USDC LIGHTER Perpetual/USDC Crypto` | 42 | SPX | USDC |

## How It Works

### 1. Order Placement Flow
```
Architect Order → CPTY Server → Symbol Mapping → Lighter API
```

1. **Architect sends order** with symbol: `"HYPE-USDC LIGHTER Perpetual/USDC Crypto"`
2. **CPTY looks up** in `symbol_to_market_id` dictionary → Gets market ID 24
3. **CPTY sends to Lighter** with `market_index=24`

### 2. Order Response Flow
```
Lighter Response → Market ID → Symbol Mapping → Architect Format
```

1. **Lighter returns** order with market ID 24
2. **CPTY looks up** in `market_id_to_symbol` dictionary → Gets Architect symbol
3. **CPTY returns to Architect** with symbol: `"HYPE-USDC LIGHTER Perpetual/USDC Crypto"`

## Implementation Code

### Symbol Mapping Creation
```python
# During initialization (_get_symbology method)
for market_id, base, quote in default_markets:
    architect_symbol = self._build_architect_symbol(base, quote)
    self.symbol_to_market_id[architect_symbol] = market_id
    self.market_id_to_symbol[market_id] = architect_symbol
```

### Order Placement Usage
```python
# In _place_order method
if order.symbol in self.symbol_to_market_id:
    market_index = self.symbol_to_market_id[order.symbol]
else:
    # Handle unknown symbol
    logger.error(f"Unknown symbol: {order.symbol}")
```

## Special Considerations

### 1. Tokens with Multipliers
Some tokens trade with multipliers (e.g., 1000PEPE, 1000SHIB):
- The base asset includes the multiplier
- Symbol: `1000PEPE-USDC LIGHTER Perpetual/USDC Crypto`
- This represents 1000 PEPE tokens as the base unit

### 2. Decimal Precision
Each market has specific decimal precision that must be handled:
- **Price decimals**: How many decimal places for price (2-6)
- **Size decimals**: How many decimal places for quantity (0-6)

Examples:
- HYPE: 4 price decimals, 2 size decimals
- BERA: 5 price decimals, 1 size decimal
- ETH: 2 price decimals, 6 size decimals

### 3. Adding New Markets
To add a new market:
1. Add to `default_markets` array in `lighter_cpty.py`
2. Include decimal precision handling if non-standard
3. The mapping will be created automatically

## Benefits

1. **Standardization**: All Architect integrations use the same symbol format
2. **Clarity**: Human-readable symbols instead of numeric IDs
3. **Flexibility**: Easy to add new markets without changing Architect core
4. **Consistency**: Same symbol format across different exchanges