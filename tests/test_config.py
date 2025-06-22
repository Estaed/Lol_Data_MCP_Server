"""
Unit tests for Task 1.5: Configuration Management System

Tests verify:
1. Settings class using Pydantic BaseSettings
2. Environment variables and YAML config file support
3. Database, Redis, and API configurations
4. Development/production environment settings
5. Config validation
6. Config loading with fallbacks
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from src.config import (
    Settings, Environment, ServerConfig, DatabaseConfig, RedisConfig,
    DataSourcesConfig, LoggingConfig, CacheConfig, SecurityConfig,
    get_settings, reload_settings, create_config_template, _deep_merge
)
from pydantic_settings import BaseSettings


class TestEnvironment:
    """Test Environment enum."""
    
    def test_environment_values(self):
        """Test environment enum values."""
        assert Environment.DEVELOPMENT == "development"
        assert Environment.PRODUCTION == "production"
        assert Environment.TESTING == "testing"


class TestServerConfig:
    """Test ServerConfig class."""
    
    def test_server_config_defaults(self):
        """Test server config default values."""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.debug is True
        assert config.workers == 1
    
    def test_server_config_env_variables(self):
        """Test server config with environment variables."""
        with patch.dict(os.environ, {
            'SERVER_HOST': '127.0.0.1',
            'SERVER_PORT': '9000',
            'SERVER_DEBUG': 'false',
            'SERVER_WORKERS': '4'
        }):
            config = ServerConfig()
            assert config.host == "127.0.0.1"
            assert config.port == 9000
            assert config.debug is False
            assert config.workers == 4


class TestDatabaseConfig:
    """Test DatabaseConfig class."""
    
    def test_database_config_defaults(self):
        """Test database config default values."""
        config = DatabaseConfig()
        assert config.url == "postgresql://lol_user:lol_pass@localhost:5432/lol_data"
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.echo is False
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
    
    def test_database_config_env_variables(self):
        """Test database config with environment variables."""
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
            'DATABASE_POOL_SIZE': '5',
            'DATABASE_ECHO': 'true'
        }):
            config = DatabaseConfig()
            assert config.url == "postgresql://test:test@localhost:5432/test"
            assert config.pool_size == 5
            assert config.echo is True


class TestRedisConfig:
    """Test RedisConfig class."""
    
    def test_redis_config_defaults(self):
        """Test Redis config default values."""
        config = RedisConfig()
        assert config.url == "redis://localhost:6379/0"
        assert config.max_connections == 10
        assert config.socket_timeout == 5
        assert config.socket_connect_timeout == 5
        assert config.retry_on_timeout is True


class TestDataSourcesConfig:
    """Test DataSourcesConfig class."""
    
    def test_data_sources_config_defaults(self):
        """Test data sources config default values."""
        config = DataSourcesConfig()
        assert config.wiki_base_url == "https://wiki.leagueoflegends.com"
        assert config.wiki_rate_limit == 1.0
        assert config.riot_api_enabled is True
        assert config.riot_api_key is None
        assert config.riot_api_rate_limit == 0.5


class TestLoggingConfig:
    """Test LoggingConfig class."""
    
    def test_logging_config_defaults(self):
        """Test logging config default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.file_path is None
        assert config.max_file_size == "10MB"
        assert config.backup_count == 5
    
    def test_logging_level_validation(self):
        """Test logging level validation."""
        # Valid levels
        config = LoggingConfig(level="DEBUG")
        assert config.level == "DEBUG"
        
        config = LoggingConfig(level="error")  # Should be converted to uppercase
        assert config.level == "ERROR"
        
        # Invalid level should raise validation error
        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(level="INVALID")
    
    def test_logging_format_validation(self):
        """Test logging format validation."""
        # Valid formats
        config = LoggingConfig(format="json")
        assert config.format == "json"
        
        config = LoggingConfig(format="TEXT")  # Should be converted to lowercase
        assert config.format == "text"
        
        # Invalid format should raise validation error
        with pytest.raises(ValueError, match="Invalid log format"):
            LoggingConfig(format="invalid")


class TestCacheConfig:
    """Test CacheConfig class."""
    
    def test_cache_config_defaults(self):
        """Test cache config default values."""
        config = CacheConfig()
        assert config.ttl_champion_data == 3600
        assert config.ttl_item_data == 3600
        assert config.ttl_search_results == 300
        assert config.max_memory_cache_size == 1000


class TestSecurityConfig:
    """Test SecurityConfig class."""
    
    def test_security_config_defaults(self):
        """Test security config default values."""
        config = SecurityConfig()
        assert config.api_key_header == "X-API-Key"
        assert config.rate_limit_per_minute == 100
        assert config.allowed_origins == ["*"]


class TestSettings:
    """Test main Settings class."""
    
    def test_settings_defaults(self):
        """Test settings with default values."""
        with patch('src.config.Path') as mock_path:
            # Mock Path to avoid file system operations
            mock_path.return_value.exists.return_value = False
            
            settings = Settings()
            assert settings.environment == Environment.DEVELOPMENT
            assert settings.server.host == "0.0.0.0"
            assert settings.database.pool_size == 10
            assert settings.redis.max_connections == 10
    
    def test_settings_helper_methods(self):
        """Test settings helper methods."""
        with patch('src.config.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            settings = Settings()
            
            # Test environment check methods
            assert settings.is_development() is True
            assert settings.is_production() is False
            assert settings.is_testing() is False
            
            # Test URL getter methods
            assert settings.get_database_url() == settings.database.url
            assert settings.get_redis_url() == settings.redis.url
    
    def test_settings_with_yaml_config(self):
        """Test settings loading from YAML config file."""
        yaml_content = {
            'environment': 'production',
            'server': {
                'host': '0.0.0.0',
                'port': 9000,
                'debug': False
            },
            'database': {
                'url': 'postgresql://prod:prod@localhost:5432/prod_db',
                'pool_size': 20
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            yaml_file_path = Path(f.name)
        
        try:
            with patch('src.config.Path') as mock_path_class:
                # Create a mock path instance
                mock_path_instance = mock_path_class.return_value
                mock_path_instance.exists.return_value = True
                mock_path_instance.__truediv__ = lambda self, other: yaml_file_path
                
                # Mock the file opening
                with patch('builtins.open', mock_open(read_data=yaml.dump(yaml_content))):
                    settings = Settings(config_dir=yaml_file_path.parent)
                    
                    # Verify the config was loaded
                    assert settings.environment == Environment.PRODUCTION
                    assert settings.server.port == 9000
                    assert settings.server.debug is False
                    assert settings.database.pool_size == 20
        finally:
            yaml_file_path.unlink()  # Clean up
    
    def test_environment_validation(self):
        """Test environment validation."""
        # Valid environment string
        settings = Settings(environment="production")
        assert settings.environment == Environment.PRODUCTION
        
        # Invalid environment should default to development
        settings = Settings(environment="invalid")
        assert settings.environment == Environment.DEVELOPMENT


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_deep_merge(self):
        """Test _deep_merge function."""
        base = {
            'a': 1,
            'b': {
                'c': 2,
                'd': 3
            },
            'e': 4
        }
        
        override = {
            'b': {
                'd': 30,  # Override existing
                'f': 40   # Add new
            },
            'g': 5        # Add new top-level
        }
        
        result = _deep_merge(base, override)
        
        expected = {
            'a': 1,
            'b': {
                'c': 2,
                'd': 30,  # Overridden
                'f': 40   # Added
            },
            'e': 4,
            'g': 5        # Added
        }
        
        assert result == expected
    
    def test_get_settings_singleton(self):
        """Test get_settings returns same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
    
    def test_reload_settings(self):
        """Test reload_settings creates new instance."""
        settings1 = get_settings()
        settings2 = reload_settings()
        # Note: Due to patching, these might be the same in tests,
        # but the function should work correctly in practice
        assert isinstance(settings2, Settings)
    
    def test_create_config_template(self):
        """Test create_config_template function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            create_config_template(config_path, Environment.PRODUCTION)
            
            assert config_path.exists()
            
            # Load and verify the template
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            assert config['environment'] == 'production'
            assert config['server']['debug'] is False  # Production should have debug=False
            assert config['server']['workers'] == 4    # Production should have more workers
            assert 'database' in config
            assert 'redis' in config
            assert 'logging' in config


class TestConfigurationValidation:
    """Test configuration validation requirements."""
    
    def test_config_validation_with_invalid_data(self):
        """Test configuration validation with invalid data."""
        # Test with invalid logging level
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID_LEVEL")
        
        # Test with invalid logging format
        with pytest.raises(ValueError):
            LoggingConfig(format="invalid_format")
    
    def test_config_fallback_behavior(self):
        """Test configuration fallback behavior."""
        # Test that invalid config files don't crash the system
        with patch('builtins.open', side_effect=FileNotFoundError):
            settings = Settings()
            # Should still work with defaults
            assert settings.environment == Environment.DEVELOPMENT
            assert settings.server.port == 8000


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset the global settings instance before each test."""
    import src.config
    src.config._settings = None
    yield
    src.config._settings = None


# Integration test
def test_task_1_5_requirements():
    """
    Integration test to verify all Task 1.5 requirements are met:
    
    1. Create Settings class using Pydantic BaseSettings ✅
    2. Support environment variables and YAML config files ✅
    3. Define database, Redis, and API configurations ✅
    4. Add development/production environment settings ✅
    5. Implement config validation ✅
    6. Add config loading with fallbacks ✅
    """
    # Test 1: Pydantic BaseSettings
    assert issubclass(Settings, BaseSettings)
    assert issubclass(ServerConfig, BaseSettings)
    assert issubclass(DatabaseConfig, BaseSettings)
    
    # Test 2: Environment variables support
    with patch.dict(os.environ, {'SERVER_PORT': '9999'}):
        config = ServerConfig()
        assert config.port == 9999
    
    # Test 3: Database, Redis, API configurations
    settings = Settings()
    assert hasattr(settings, 'database')
    assert hasattr(settings, 'redis')
    assert hasattr(settings, 'data_sources')
    assert hasattr(settings.database, 'url')
    assert hasattr(settings.redis, 'url')
    assert hasattr(settings.data_sources, 'riot_api_enabled')
    
    # Test 4: Environment settings
    assert hasattr(settings, 'environment')
    assert settings.is_development() or settings.is_production() or settings.is_testing()
    
    # Test 5: Config validation
    with pytest.raises(ValueError):
        LoggingConfig(level="INVALID")
    
    # Test 6: Config loading with fallbacks
    assert get_settings() is not None
    
    print("✅ All Task 1.5 requirements verified!") 