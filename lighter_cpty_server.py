#!/usr/bin/env python3
"""Standalone Lighter CPTY server for Architect using mainnet."""
import asyncio
import logging
import signal
import sys
import grpc
import os
from concurrent import futures
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent / '.env')

# Import from installed architect-py package
from architect_py.grpc.server import add_CptyServicer_to_server, add_OrderflowServicer_to_server

# Import local LighterCpty implementation
from LighterCpty.lighter_cpty import LighterCptyServicer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the Lighter CPTY server."""
    port = 50051
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    logger.info("=== Lighter CPTY Server (Mainnet) ===")
    
    # Configuration from environment variables or defaults
    config = {
        'url': os.getenv('LIGHTER_URL', 'https://mainnet.zklighter.elliot.ai'),
        'private_key': os.getenv('LIGHTER_API_KEY_PRIVATE_KEY'),
        'account_index': int(os.getenv('LIGHTER_ACCOUNT_INDEX', '30188')),
        'api_key_index': int(os.getenv('LIGHTER_API_KEY_INDEX', '1'))
    }
    
    # Show configuration
    logger.info("Configuration:")
    logger.info(f"  Port: {port}")
    logger.info(f"  Lighter URL: {config['url']}")
    logger.info(f"  Account Index: {config['account_index']}")
    logger.info(f"  API Key Index: {config['api_key_index']}")
    logger.info(f"  API Key: {'*' * 20 + config['private_key'][-10:] if config['private_key'] else 'Not set'}")
    
    if not config['private_key']:
        logger.error("LIGHTER_API_KEY_PRIVATE_KEY environment variable not set!")
        logger.error("Please set: export LIGHTER_API_KEY_PRIVATE_KEY='your_private_key'")
        sys.exit(1)
    
    # Create servicer with config
    servicer = LighterCptyServicer(config)
    
    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ]
    )
    
    # Add servicers
    add_CptyServicer_to_server(servicer, server)
    add_OrderflowServicer_to_server(servicer, server)
    
    # Start server
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"\nServer listening on port {port}")
    logger.info("Ready to accept connections from Architect core")
    logger.info("\nTo connect from Architect core:")
    logger.info(f"  1. Configure Architect to route 'lighter' orders to this server")
    logger.info(f"  2. Use your machine's IP address and port {port}")
    logger.info("\nPress Ctrl+C to stop")
    
    # Handle shutdown
    def signal_handler(sig, frame):
        logger.info("\nShutting down...")
        server.stop(grace=5)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait for termination
    server.wait_for_termination()


if __name__ == "__main__":
    main()