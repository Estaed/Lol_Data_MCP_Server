"""
Task 1.5: Configuration Management System

This module provides comprehensive configuration management for the LoL Data MCP Server.
It supports loading configuration from environment variables, YAML files, and provides
validation and fallbacks for different environments.
"""

import os
import yaml
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings
from .environment_loader import EnvironmentLoader


class Environment(str, Enum):
    """Environment types for configuration."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class ServerConfig(BaseSettings):
    """Server configuration settings."""
    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=True, description="Debug mode")
    workers: int = Field(default=1, description="Number of worker processes")
    
    class Config:
        env_prefix = "SERVER_"


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""
    url: str = Field(
        default="postgresql://lol_user:lol_pass@localhost:5432/lol_data",
        description="Database connection URL"
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max pool overflow")
    echo: bool = Field(default=False, description="Echo SQL queries")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Pool recycle time in seconds")
    
    class Config:
        env_prefix = "DATABASE_"


class RedisConfig(BaseSettings):
    """Redis configuration settings."""
    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(default=10, description="Max connections")
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, description="Socket connect timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    
    class Config:
        env_prefix = "REDIS_"


class DataSourcesConfig(BaseSettings):
    """Data sources configuration settings."""
    wiki_base_url: str = Field(
        default="https://wiki.leagueoflegends.com",
        description="LoL Wiki base URL"
    )
    wiki_rate_limit: float = Field(default=1.0, description="Wiki rate limit in seconds")
    
    riot_api_enabled: bool = Field(default=True, description="Enable Riot API")
    riot_api_key: Optional[str] = Field(default=None, description="Riot API key")
    riot_api_rate_limit: float = Field(default=0.5, description="Riot API rate limit")
    
    # Additional data sources configuration
    data_sources_config: Optional[Dict[str, Any]] = Field(default=None, description="Data sources config from YAML")
    mcp_tools_config: Optional[Dict[str, Any]] = Field(default=None, description="MCP tools config from YAML")
    
    class Config:
        env_prefix = "DATA_SOURCES_"


class LoggingConfig(BaseSettings):
    """Logging configuration settings."""
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Log format (json|text)")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_file_size: str = Field(default="10MB", description="Max log file size")
    backup_count: int = Field(default=5, description="Number of backup files")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Invalid log level. Must be one of: {valid_levels}')
        return v.upper()
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        valid_formats = ['json', 'text']
        if v.lower() not in valid_formats:
            raise ValueError(f'Invalid log format. Must be one of: {valid_formats}')
        return v.lower()
    
    class Config:
        env_prefix = "LOGGING_"


class CacheConfig(BaseSettings):
    """Cache configuration settings."""
    ttl_champion_data: int = Field(default=3600, description="Champion data TTL in seconds")
    ttl_item_data: int = Field(default=3600, description="Item data TTL in seconds")
    ttl_search_results: int = Field(default=300, description="Search results TTL in seconds")
    max_memory_cache_size: int = Field(default=1000, description="Max in-memory cache entries")
    
    class Config:
        env_prefix = "CACHE_"


class SecurityConfig(BaseSettings):
    """Security configuration settings."""
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    rate_limit_per_minute: int = Field(default=100, description="Rate limit per minute")
    allowed_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    
    class Config:
        env_prefix = "SECURITY_"


class Settings(BaseSettings):
    """Main settings class that aggregates all configuration sections."""
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Application environment")
    
    # Configuration sections
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    config_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "config")
    
    @model_validator(mode='before')
    @classmethod
    def load_config_files(cls, values):
        """Load configuration from YAML files with environment-specific overrides."""
        config_dir = values.get('config_dir')
        if not config_dir:
            config_dir = Path(__file__).parent.parent / "config"
        
        environment = values.get('environment', Environment.DEVELOPMENT)
        if isinstance(environment, str):
            try:
                environment = Environment(environment.lower())
            except ValueError:
                environment = Environment.DEVELOPMENT
        
        # Load base configuration with environment variable substitution
        base_config_path = config_dir / "server_config.yaml"
        config_data = {}
        loader = EnvironmentLoader()
        
        if base_config_path.exists():
            try:
                config_data = loader.load_yaml_with_env(base_config_path)
            except Exception as e:
                # Fallback to defaults if config file can't be loaded
                print(f"Warning: Could not load base config file {base_config_path}: {e}")
        
        # Load data sources configuration with environment variables
        data_sources_path = config_dir / "data_sources.yaml"
        if data_sources_path.exists():
            try:
                data_sources_config = loader.load_yaml_with_env(data_sources_path)
                # Merge data sources config into main config
                if 'data_sources' not in config_data:
                    config_data['data_sources'] = {}
                
                # Extract useful values from data_sources.yaml
                if 'sources' in data_sources_config:
                    lol_wiki = data_sources_config['sources'].get('lol_wiki', {})
                    if 'base_url' in lol_wiki:
                        config_data['data_sources']['wiki_base_url'] = lol_wiki['base_url']
                    if 'rate_limit_seconds' in lol_wiki:
                        config_data['data_sources']['wiki_rate_limit'] = lol_wiki['rate_limit_seconds']
                        
                config_data['data_sources']['data_sources_config'] = data_sources_config
            except Exception as e:
                print(f"Warning: Could not load data sources config file {data_sources_path}: {e}")
        
        # Load MCP tools configuration with environment variables
        mcp_tools_path = config_dir / "mcp_tools.yaml"
        if mcp_tools_path.exists():
            try:
                mcp_tools_config = loader.load_yaml_with_env(mcp_tools_path)
                if 'data_sources' not in config_data:
                    config_data['data_sources'] = {}
                config_data['data_sources']['mcp_tools_config'] = mcp_tools_config
            except Exception as e:
                print(f"Warning: Could not load MCP tools config file {mcp_tools_path}: {e}")
        
        # Load environment-specific configuration with environment variables
        env_config_path = config_dir / f"{environment.value}_config.yaml"
        if env_config_path.exists():
            try:
                env_config = loader.load_yaml_with_env(env_config_path)
                # Merge environment-specific config
                config_data = _deep_merge(config_data, env_config)
            except Exception as e:
                print(f"Warning: Could not load environment config file {env_config_path}: {e}")
        
        # Merge with provided values (environment variables take precedence)
        merged_values = _deep_merge(config_data, values)
        
        return merged_values
    
    @field_validator('environment', mode='before')
    @classmethod
    def validate_environment(cls, v):
        """Validate and convert environment value."""
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                return Environment.DEVELOPMENT
        return v
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == Environment.TESTING
    
    def get_database_url(self) -> str:
        """Get the database URL for the current environment."""
        return self.database.url
    
    def get_redis_url(self) -> str:
        """Get the Redis URL for the current environment."""
        return self.redis.url
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "LOL_MCP_"
        extra = "allow"  # Allow extra fields for dynamic config loading


def _deep_merge(base_dict: Dict[str, Any], override_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override_dict taking precedence."""
    result = base_dict.copy()
    
    for key, value in override_dict.items():
        if (
            key in result 
            and isinstance(result[key], dict) 
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.
    
    This function implements the singleton pattern to ensure that configuration
    is loaded only once and reused throughout the application.
    
    Returns:
        Settings: The global settings instance
    """
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            # Create settings with defaults as fallback
            _settings = Settings.parse_obj({})
    
    return _settings


def reload_settings() -> Settings:
    """
    Reload the global settings instance.
    
    This function forces a reload of the configuration, useful for testing
    or when configuration files have been updated.
    
    Returns:
        Settings: The reloaded settings instance
    """
    global _settings
    _settings = None
    return get_settings()


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
            'wiki_rate_limit': 1.0,
            'riot_api_enabled': True,
            'riot_api_rate_limit': 0.5
        },
        'logging': {
            'level': 'DEBUG' if environment == Environment.DEVELOPMENT else 'INFO',
            'format': 'text' if environment == Environment.DEVELOPMENT else 'json'
        },
        'cache': {
            'ttl_champion_data': 3600,
            'ttl_item_data': 3600,
            'ttl_search_results': 300
        }
    }
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(template_config, f, default_flow_style=False, sort_keys=False)
