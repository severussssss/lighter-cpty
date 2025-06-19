#!/usr/bin/env python3
"""Simple FARTCOIN order example."""

# FARTCOIN order parameters
order = {
    "cl_ord_id": "fartcoin_12345",                           # Your unique order ID
    "symbol": "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto", # Architect-style symbol
    "dir": "BUY",                                            # BUY or SELL
    "price": "1.09",                                         # Price per FARTCOIN
    "qty": "20",                                             # Quantity (min 20)
    "type": "LIMIT",                                         # Order type
    "tif": "GTC",                                           # Good Till Cancelled
    "reduce_only": False,                                    # Not reduce-only
    "post_only": True                                        # Post-only (maker)
}

# That's it! Send this order to the CPTY server at localhost:50051
# The server will:
# - Translate "FARTCOIN-USDC LIGHTER Perpetual/USDC Crypto" to market ID 21
# - Convert price $1.09 to Lighter format (109000 with 5 decimals)
# - Convert quantity 20 to Lighter format (200 with 1 decimal)
# - Place the order on Lighter mainnet

print(f"""
FARTCOIN Order:
- Buy {order['qty']} FARTCOIN at ${order['price']} each
- Total: ${float(order['price']) * float(order['qty']):.2f} USDC
- Symbol: {order['symbol']}
- Order type: {order['type']}, Post-only: {order['post_only']}
""")