"""
Configuration utility functions.

This module contains utility functions for creating configuration templates
and providing default settings for the LoL Data MCP Server.
"""

import yaml
from enum import Enum
from pathlib import Path
from typing import Dict, Any


class Environment(str, Enum):
    """Environment types for configuration."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


def create_config_template(config_path: Path, environment: Environment = Environment.DEVELOPMENT) -> None:
    """
    Create a configuration template file.
    
    Args:
        config_path: Path where to create the config template
        environment: Environment type for the template
    """
    template_config = {
        'environment': environment.value,
        'server': {
            'host': '0.0.0.0',
            'port': 8000,
            'debug': environment == Environment.DEVELOPMENT,
            'workers': 1 if environment == Environment.DEVELOPMENT else 4
        },
        'database': {
            'url': f'postgresql://lol_user:lol_pass@localhost:5432/lol_data_{environment.value}',
            'pool_size': 5 if environment == Environment.DEVELOPMENT else 20,
            'max_overflow': 10 if environment == Environment.DEVELOPMENT else 40,
            'echo': environment == Environment.DEVELOPMENT
        },
        'redis': {
            'url': f'redis://localhost:6379/{environment.value}',
            'max_connections': 5 if environment == Environment.DEVELOPMENT else 20
        },
        'data_sources': {
            'wiki_base_url': 'https://wiki.leagueoflegends.com',
            'wiki_rate_limit': 1.0
        },
        'logging': {
            'level': 'DEBUG' if environment == Environment.DEVELOPMENT else 'INFO',
            'format': 'text' if environment == Environment.DEVELOPMENT else 'json'
        },
        'cache': {
            'ttl_champion_data': 3600,
            'max_memory_cache_size': 1000
        }
    }
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(template_config, f, default_flow_style=False, sort_keys=False)


def default_settings() -> Dict[str, Any]:
    """
    Default settings for demonstration and testing.
    """
    return {
        'server': {
            'host': '127.0.0.1',
            'port': 8000
        },
        'database': {
            'url': 'sqlite:///./test.db'
        },
        'data_sources': {
            'wiki_base_url': 'https://wiki.leagueoflegends.com',
            'wiki_rate_limit': 1.0
        },
        'logging': {
            'level': 'DEBUG'
        },
        'cache': {
            'ttl_champion_data': 3600,
            'max_memory_cache_size': 1000
        }
    } 