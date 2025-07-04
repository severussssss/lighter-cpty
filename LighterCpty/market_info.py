"""Utility for fetching and caching Lighter market information."""
import aiohttp
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def fetch_market_info(api_url: str) -> Dict[int, Dict[str, Any]]:
    """Fetch market information from Lighter API.
    
    Args:
        api_url: Base API URL (e.g., https://mainnet.zklighter.elliot.ai)
        
    Returns:
        Dictionary mapping market IDs to market info
    """
    market_info = {}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{api_url}/info") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'markets' in data:
                        # Convert string market IDs to integers
                        for market_id_str, info in data['markets'].items():
                            try:
                                market_id = int(market_id_str)
                                market_info[market_id] = info
                                logger.info(f"Loaded market {market_id}: {info.get('base_asset')}/{info.get('quote_asset')}")
                            except ValueError:
                                logger.warning(f"Invalid market ID: {market_id_str}")
                    
                    logger.info(f"Loaded {len(market_info)} markets from API")
                else:
                    logger.error(f"Failed to fetch market info: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error fetching market info: {e}")
    
    return market_info


def save_market_info_cache(market_info: Dict[int, Dict[str, Any]], cache_file: str = "market_info_cache.json"):
    """Save market info to local cache file.
    
    Args:
        market_info: Market information dictionary
        cache_file: Path to cache file
    """
    try:
        with open(cache_file, 'w') as f:
            json.dump(market_info, f, indent=2)
        logger.info(f"Saved market info cache to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to save market info cache: {e}")


def load_market_info_cache(cache_file: str = "market_info_cache.json") -> Dict[int, Dict[str, Any]]:
    """Load market info from local cache file.
    
    Args:
        cache_file: Path to cache file
        
    Returns:
        Market information dictionary
    """
    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
            # Convert string keys back to integers
            return {int(k): v for k, v in data.items()}
    except FileNotFoundError:
        logger.warning(f"Market info cache file not found: {cache_file}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load market info cache: {e}")
        return {}