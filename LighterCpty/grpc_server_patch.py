"""Patched gRPC server setup to fix SubscribeOrderflow deserialization."""
import grpc
import msgspec
import json
import logging
from architect_py.grpc.models.Cpty.CptyRequest import UnannotatedCptyRequest, CptyRequest
from architect_py.grpc.models.Orderflow.SubscribeOrderflowRequest import SubscribeOrderflowRequest
from architect_py.grpc.utils import encoder
from architect_py import TimeInForce

logger = logging.getLogger(__name__)


def custom_cpty_deserializer(data):
    """Custom deserializer that handles TimeInForce string to enum conversion."""
    try:
        # First try standard decode
        decoder = msgspec.json.Decoder(type=UnannotatedCptyRequest)
        return decoder.decode(data)
    except msgspec.ValidationError as e:
        if "Expected `TimeInForce`" in str(e) and "got `str`" in str(e):
            # Parse as raw JSON first
            raw_obj = json.loads(data)
            logger.info(f"Raw request before TIF conversion: {raw_obj}")
            
            # Check if it's a place_order with tif field
            if isinstance(raw_obj, dict) and raw_obj.get('t') == 'place_order':
                if 'tif' in raw_obj and isinstance(raw_obj['tif'], str):
                    # Map string to index for TimeInForce enum
                    tif_map = {
                        "GTC": 0,  # Good Till Cancelled
                        "IOC": 1,  # Immediate or Cancel
                        "FOK": 2,  # Fill or Kill
                        "GTT": 3,  # Good Till Time
                    }
                    tif_str = raw_obj['tif']
                    if tif_str in tif_map:
                        raw_obj['tif'] = tif_map[tif_str]
                        logger.info(f"Converted TIF {tif_str} to {raw_obj['tif']}")
            
            # Re-encode and try again
            modified_data = json.dumps(raw_obj).encode()
            return decoder.decode(modified_data)
        else:
            # Re-raise if it's a different error
            raise


def add_CptyServicer_to_server_patched(servicer, server):
    """Add Cpty servicer with correct deserializer."""
    rpc_method_handlers = {
        "Cpty": grpc.stream_stream_rpc_method_handler(
            servicer.Cpty,
            request_deserializer=custom_cpty_deserializer,
            response_serializer=encoder.encode,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "json.architect.Cpty", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))


def add_OrderflowServicer_to_server_patched(servicer, server):
    """Add Orderflow servicer with FIXED deserializer for requests."""
    # FIX: Use SubscribeOrderflowRequest for deserializing the REQUEST, not the response type
    decoder = msgspec.json.Decoder(type=SubscribeOrderflowRequest)
    rpc_method_handlers = {
        "SubscribeOrderflow": grpc.unary_stream_rpc_method_handler(
            servicer.SubscribeOrderflow,
            request_deserializer=decoder.decode,
            response_serializer=encoder.encode,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "json.architect.Orderflow", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))