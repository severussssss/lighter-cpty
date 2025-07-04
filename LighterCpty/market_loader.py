"""Load market information from Lighter API."""
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache for market info
_market_info_cache: Optional[Dict[int, Dict[str, Any]]] = None


def load_market_info() -> Dict[int, Dict[str, Any]]:
    """Load market information from Lighter API.
    
    Returns:
        Dict mapping market_id to market info
    """
    global _market_info_cache
    
    # Return cached info if available
    if _market_info_cache is not None:
        return _market_info_cache
    
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        order_books = data.get('order_books', [])
        
        # Create market mapping
        market_mapping = {}
        
        for market in order_books:
            market_id = market.get('market_id')
            if market_id is not None:
                # Symbol is the base asset, quote is always USDC
                symbol = market.get('symbol', '')
                base_asset = symbol
                quote_asset = 'USDC'
                
                market_mapping[market_id] = {
                    'base_asset': base_asset,
                    'quote_asset': quote_asset,
                    'symbol': symbol,
                    'min_base_amount': market.get('min_base_amount'),
                    'min_quote_amount': market.get('min_quote_amount'),
                    'supported_size_decimals': market.get('supported_size_decimals'),
                    'supported_price_decimals': market.get('supported_price_decimals'),
                    'supported_quote_decimals': market.get('supported_quote_decimals'),
                    'maker_fee': market.get('maker_fee'),
                    'taker_fee': market.get('taker_fee'),
                    'status': market.get('status'),
                }
        
        # Cache the result
        _market_info_cache = market_mapping
        
        logger.info(f"Loaded {len(market_mapping)} markets from Lighter API")
        return market_mapping
        
    except Exception as e:
        logger.error(f"Failed to load market info from API: {e}")
        # Return fallback mapping
        return get_fallback_market_info()


def get_fallback_market_info() -> Dict[int, Dict[str, Any]]:
    """Get fallback market info if API fails."""
    return {
        0: {'base_asset': 'ETH', 'quote_asset': 'USDC'},
        1: {'base_asset': 'BTC', 'quote_asset': 'USDC'},
        2: {'base_asset': 'SOL', 'quote_asset': 'USDC'},
        3: {'base_asset': 'DOGE', 'quote_asset': 'USDC'},
        4: {'base_asset': '1000PEPE', 'quote_asset': 'USDC'},
        5: {'base_asset': 'WIF', 'quote_asset': 'USDC'},
        6: {'base_asset': 'WLD', 'quote_asset': 'USDC'},
        7: {'base_asset': 'XRP', 'quote_asset': 'USDC'},
        8: {'base_asset': 'LINK', 'quote_asset': 'USDC'},
        9: {'base_asset': 'AVAX', 'quote_asset': 'USDC'},
        10: {'base_asset': 'NEAR', 'quote_asset': 'USDC'},
        11: {'base_asset': 'DOT', 'quote_asset': 'USDC'},
        12: {'base_asset': 'TON', 'quote_asset': 'USDC'},
        13: {'base_asset': 'TAO', 'quote_asset': 'USDC'},
        14: {'base_asset': 'POL', 'quote_asset': 'USDC'},
        15: {'base_asset': 'TRUMP', 'quote_asset': 'USDC'},
        16: {'base_asset': 'SUI', 'quote_asset': 'USDC'},
        17: {'base_asset': '1000SHIB', 'quote_asset': 'USDC'},
        18: {'base_asset': '1000BONK', 'quote_asset': 'USDC'},
        19: {'base_asset': '1000FLOKI', 'quote_asset': 'USDC'},
        20: {'base_asset': 'BERA', 'quote_asset': 'USDC'},
        21: {'base_asset': 'FARTCOIN', 'quote_asset': 'USDC'},
        22: {'base_asset': 'AI16Z', 'quote_asset': 'USDC'},
        23: {'base_asset': 'POPCAT', 'quote_asset': 'USDC'},
        24: {'base_asset': 'HYPE', 'quote_asset': 'USDC'},
        25: {'base_asset': 'BNB', 'quote_asset': 'USDC'},
        26: {'base_asset': 'JUP', 'quote_asset': 'USDC'},
        27: {'base_asset': 'AAVE', 'quote_asset': 'USDC'},
        28: {'base_asset': 'MKR', 'quote_asset': 'USDC'},
        29: {'base_asset': 'ENA', 'quote_asset': 'USDC'},
        30: {'base_asset': 'UNI', 'quote_asset': 'USDC'},
        31: {'base_asset': 'APT', 'quote_asset': 'USDC'},
        32: {'base_asset': 'SEI', 'quote_asset': 'USDC'},
        33: {'base_asset': 'KAITO', 'quote_asset': 'USDC'},
        34: {'base_asset': 'IP', 'quote_asset': 'USDC'},
        35: {'base_asset': 'LTC', 'quote_asset': 'USDC'},
        36: {'base_asset': 'CRV', 'quote_asset': 'USDC'},
        37: {'base_asset': 'PENDLE', 'quote_asset': 'USDC'},
        38: {'base_asset': 'ONDO', 'quote_asset': 'USDC'},
        39: {'base_asset': 'ADA', 'quote_asset': 'USDC'},
        40: {'base_asset': 'S', 'quote_asset': 'USDC'},
        41: {'base_asset': 'VIRTUAL', 'quote_asset': 'USDC'},
        42: {'base_asset': 'SPX', 'quote_asset': 'USDC'},
        43: {'base_asset': 'TRX', 'quote_asset': 'USDC'},
        44: {'base_asset': 'SYRUP', 'quote_asset': 'USDC'},
    }