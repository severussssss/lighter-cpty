# Lighter CPTY Integration for Architect

A gRPC-based counterparty (CPTY) integration that enables Architect to trade on the Lighter exchange.

## Features

- ✅ Full order lifecycle support (place, cancel, track)
- ✅ 43 supported markets including ETH, BTC, HYPE, BERA, FARTCOIN, and more
- ✅ Real-time WebSocket updates for order status and fills
- ✅ Automatic symbol mapping between Architect and Lighter formats
- ✅ Market-specific decimal precision handling

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Lighter API credentials

### 2. Installation

```bash
# Create virtual environment
python3.12 -m venv lighter_env
source lighter_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file with your Lighter credentials:

```env
LIGHTER_API_KEY_PRIVATE_KEY=your_private_key_here
LIGHTER_ACCOUNT_INDEX=30188
LIGHTER_API_KEY_INDEX=1
LIGHTER_URL=https://mainnet.zklighter.elliot.ai
```

### 4. Run the Server

```bash
python lighter_cpty_server.py
```

The server will start on port 50051 and accept connections from Architect core.

## Supported Markets

The integration supports all 43 markets on Lighter mainnet:

| Symbol | Market ID | Symbol | Market ID |
|--------|-----------|--------|-----------|
| ETH | 0 | FARTCOIN | 21 |
| BTC | 1 | AI16Z | 22 |
| SOL | 2 | POPCAT | 23 |
| DOGE | 3 | HYPE | 24 |
| 1000PEPE | 4 | BNB | 25 |
| WIF | 5 | JUP | 26 |
| WLD | 6 | AAVE | 27 |
| XRP | 7 | MKR | 28 |
| LINK | 8 | ENA | 29 |
| AVAX | 9 | UNI | 30 |
| NEAR | 10 | APT | 31 |
| DOT | 11 | SEI | 32 |
| TON | 12 | KAITO | 33 |
| TAO | 13 | IP | 34 |
| POL | 14 | LTC | 35 |
| TRUMP | 15 | CRV | 36 |
| SUI | 16 | PENDLE | 37 |
| 1000SHIB | 17 | ONDO | 38 |
| 1000BONK | 18 | ADA | 39 |
| 1000FLOKI | 19 | S | 40 |
| BERA | 20 | VIRTUAL | 41 |
| | | SPX | 42 |

## Symbol Format

Architect uses a standardized symbol format:
```
BASE-QUOTE LIGHTER Perpetual/QUOTE Crypto
```

Examples:
- `ETH-USDC LIGHTER Perpetual/USDC Crypto`
- `HYPE-USDC LIGHTER Perpetual/USDC Crypto`
- `BERA-USDC LIGHTER Perpetual/USDC Crypto`

## Project Structure

```
lighter_cpty/
├── LighterCpty/
│   ├── __init__.py
│   ├── lighter_cpty.py      # Main CPTY implementation
│   └── lighter_ws.py        # WebSocket client
├── lighter_cpty_server.py   # gRPC server
├── requirements.txt         # Python dependencies
├── .env                     # Configuration (not in git)
├── docs/                    # Documentation
├── examples/                # Example scripts
└── tests/                   # Test files
```

## Testing

See the `examples/` directory for sample order placement scripts:

```bash
# Place a HYPE order
python examples/fartcoin_order_simple.py
```

## Documentation

- [Production Usage Guide](docs/PRODUCTION_USAGE.md)
- [Symbol Mapping Guide](docs/SYMBOL_MAPPING_GUIDE.md)
- [End-to-End Test Results](docs/END_TO_END_TEST_RESULTS.md)

## License

MIT License