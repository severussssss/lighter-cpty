"""Type compatibility layer for handling version differences."""
import logging
from typing import Any, Dict, Union
from architect_py.grpc.models.definitions import OrderStatus, OrderType, OrderDir
from architect_py.grpc.models.Oms import Order
from decimal import Decimal

logger = logging.getLogger(__name__)


def convert_order_status(value: Union[str, int]) -> OrderStatus:
    """Convert string or int to OrderStatus enum."""
    if isinstance(value, int):
        return OrderStatus(value)
    elif isinstance(value, str):
        # Map string values to enum
        status_map = {
            "Pending": OrderStatus.Pending,
            "Open": OrderStatus.Open,
            "Rejected": OrderStatus.Rejected,
            "Out": OrderStatus.Out,
            "Canceling": OrderStatus.Canceling,
            "Canceled": OrderStatus.Canceled,
            "ReconciledOut": OrderStatus.ReconciledOut,
            "Stale": OrderStatus.Stale,
            "Unknown": OrderStatus.Unknown,
        }
        return status_map.get(value, OrderStatus.Unknown)
    return OrderStatus.Unknown


def convert_order_type(value: Union[str, int]) -> OrderType:
    """Convert string or int to OrderType enum."""
    if isinstance(value, int):
        return OrderType(value)
    elif isinstance(value, str):
        type_map = {
            "MARKET": OrderType.MARKET,
            "LIMIT": OrderType.LIMIT,
            "STOP_LOSS_LIMIT": OrderType.STOP_LOSS_LIMIT,
            "TAKE_PROFIT_LIMIT": OrderType.TAKE_PROFIT_LIMIT,
            "BRACKET": OrderType.BRACKET,
        }
        return type_map.get(value.upper(), OrderType.LIMIT)
    return OrderType.LIMIT


def convert_order_dir(value: Union[str, int]) -> OrderDir:
    """Convert string or int to OrderDir enum."""
    if isinstance(value, str):
        if value.upper() == "BUY":
            return OrderDir.BUY
        elif value.upper() == "SELL":
            return OrderDir.SELL
    elif isinstance(value, int):
        return OrderDir(value)
    return OrderDir.BUY


def normalize_incoming_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize incoming order data to handle type differences."""
    normalized = data.copy()
    
    # Convert enums from strings to proper types
    if "o" in normalized and isinstance(normalized["o"], str):
        normalized["o"] = convert_order_status(normalized["o"]).value
    
    if "k" in normalized and isinstance(normalized["k"], str):
        normalized["k"] = convert_order_type(normalized["k"]).value
    
    if "d" in normalized and isinstance(normalized["d"], str):
        normalized["d"] = convert_order_dir(normalized["d"]).value
    
    # Ensure numeric fields are properly typed
    numeric_fields = ["q", "xq", "p", "tp", "tpp"]
    for field in numeric_fields:
        if field in normalized and normalized[field] is not None:
            normalized[field] = str(normalized[field])
    
    # Ensure time fields are integers
    time_fields = ["tn", "ts"]
    for field in time_fields:
        if field in normalized and normalized[field] is not None:
            try:
                normalized[field] = int(normalized[field])
            except (ValueError, TypeError):
                normalized[field] = 0
    
    logger.debug(f"Normalized order data: {normalized}")
    return normalized


def create_compatible_order(place_order_data: Dict[str, Any]) -> Order:
    """Create an Order object from potentially incompatible data."""
    # Extract fields with defaults
    return Order(
        a=str(place_order_data.get("a", place_order_data.get("account", ""))),
        d=convert_order_dir(place_order_data.get("d", place_order_data.get("dir", "BUY"))),
        id=str(place_order_data.get("id", place_order_data.get("cl_ord_id", ""))),
        o=convert_order_status(place_order_data.get("o", place_order_data.get("status", "Pending"))),
        q=str(place_order_data.get("q", place_order_data.get("qty", "0"))),
        s=str(place_order_data.get("s", place_order_data.get("symbol", ""))),
        src=str(place_order_data.get("src", place_order_data.get("source", "API"))),
        tif=str(place_order_data.get("tif", place_order_data.get("time_in_force", "GTC"))),
        tn=int(place_order_data.get("tn", place_order_data.get("recv_time_ns", 0))),
        ts=int(place_order_data.get("ts", place_order_data.get("recv_time", 0))),
        u=str(place_order_data.get("u", place_order_data.get("trader", ""))),
        ve=str(place_order_data.get("ve", place_order_data.get("execution_venue", "LIGHTER"))),
        xq=str(place_order_data.get("xq", place_order_data.get("filled_quantity", "0"))),
        k=convert_order_type(place_order_data.get("k", place_order_data.get("type", "LIMIT"))),
        p=str(place_order_data.get("p", place_order_data.get("price", place_order_data.get("limit_price", "0")))),
        po=bool(place_order_data.get("po", place_order_data.get("post_only", False))),
    )