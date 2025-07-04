"""Configuration loader for Lighter CPTY server."""
import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage configuration for Lighter CPTY."""
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from YAML file and environment variables.
        
        Args:
            config_path: Path to YAML config file. Defaults to config.yaml in project root.
            
        Returns:
            Merged configuration dictionary
        """
        config = {}
        
        # Try to load YAML config
        if config_path is None:
            # Look for config.yaml in project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config.yaml"
        
        if Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config = yaml_config
                        logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Failed to load config from {config_path}: {e}")
        
        # Override with environment variables
        config = ConfigLoader._merge_env_config(config)
        
        return config
    
    @staticmethod
    def _merge_env_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge environment variables into configuration.
        
        Environment variables override YAML config values.
        """
        # Lighter configuration
        if 'lighter' not in config:
            config['lighter'] = {}
        
        if os.getenv('LIGHTER_API_AUTH'):
            config['lighter']['api_auth'] = os.getenv('LIGHTER_API_AUTH')
        if os.getenv('LIGHTER_TRADER_INDEX'):
            config['lighter']['trader_index'] = os.getenv('LIGHTER_TRADER_INDEX')
        if os.getenv('LIGHTER_ACCOUNT_INDEX'):
            config['lighter']['account_index'] = os.getenv('LIGHTER_ACCOUNT_INDEX')
        if os.getenv('LIGHTER_URL'):
            config['lighter']['url'] = os.getenv('LIGHTER_URL')
        
        # Server configuration
        if 'server' not in config:
            config['server'] = {}
        
        if os.getenv('CPTY_SERVER_HOST'):
            config['server']['host'] = os.getenv('CPTY_SERVER_HOST')
        if os.getenv('CPTY_SERVER_PORT'):
            config['server']['port'] = int(os.getenv('CPTY_SERVER_PORT'))
        
        # External Architect Core configuration
        if 'external' not in config:
            config['external'] = {}
        
        if os.getenv('ARCHITECT_CORE_URL'):
            if 'lighter' not in config['external']:
                config['external']['lighter'] = {}
            config['external']['lighter']['url'] = os.getenv('ARCHITECT_CORE_URL')
        
        return config
    
    @staticmethod
    def get_lighter_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Lighter-specific configuration."""
        lighter_config = config.get('lighter', {})
        
        # Parse API auth to get components
        api_auth = lighter_config.get('api_auth', '')
        if api_auth:
            parts = api_auth.split(':')
            if len(parts) >= 4:
                return {
                    'url': lighter_config.get('url', 'https://mainnet.zklighter.elliot.ai'),
                    'private_key': parts[3],  # The private key part
                    'account_index': int(lighter_config.get('account_index', parts[1])),
                    'api_key_index': int(parts[2]),
                    'trader_index': int(lighter_config.get('trader_index', parts[0]))
                }
        
        # Fallback to individual env vars
        return {
            'url': os.getenv('LIGHTER_URL', 'https://mainnet.zklighter.elliot.ai'),
            'private_key': os.getenv('LIGHTER_API_KEY_PRIVATE_KEY', ''),
            'account_index': int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0')),
            'api_key_index': int(os.getenv('LIGHTER_API_KEY_INDEX', '1'))
        }
    
    @staticmethod
    def get_architect_core_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract Architect Core connection configuration."""
        external = config.get('external', {})
        lighter_external = external.get('lighter', {})
        
        if lighter_external.get('url'):
            return {
                'url': lighter_external['url'],
                'trader': lighter_external.get('trader', 'dummy-trader-id'),
                'account': lighter_external.get('account', 'dummy-account-id')
            }
        
        return None