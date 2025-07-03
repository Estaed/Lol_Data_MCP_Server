"""
Environment Variable Loader for Configuration Files

This module provides utilities to load configuration files with environment variable
substitution support, allowing secure configuration management.
"""

import os
import re
import yaml
from typing import Any, Dict, Union
from pathlib import Path


class EnvironmentLoader:
    """Handles loading YAML files with environment variable substitution."""
    
    # Pattern to match ${VAR_NAME} or ${VAR_NAME:-default_value}
    ENV_VAR_PATTERN = re.compile(r'\$\{([^}^{]+)\}')
    
    @classmethod
    def substitute_env_vars(cls, value: Any) -> Any:
        """
        Recursively substitute environment variables in configuration values.
        
        Supports:
        - ${VAR_NAME} - Required environment variable
        - ${VAR_NAME:-default} - Environment variable with default
        
        Args:
            value: Configuration value (can be string, dict, list, etc.)
            
        Returns:
            Value with environment variables substituted
        """
        if isinstance(value, str):
            return cls._substitute_string(value)
        elif isinstance(value, dict):
            return {k: cls.substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.substitute_env_vars(item) for item in value]
        else:
            return value
    
    @classmethod
    def _substitute_string(cls, text: str) -> Union[str, int, float, bool, list]:
        """
        Substitute environment variables in a string value.
        
        Args:
            text: String that may contain environment variable references
            
        Returns:
            String with variables substituted, or converted type if applicable
        """
        def replace_var(match):
            var_expr = match.group(1)
            
            if ':-' in var_expr:
                # Handle ${VAR:-default} syntax
                var_name, default_value = var_expr.split(':-', 1)
                value = os.getenv(var_name.strip(), default_value.strip())
            else:
                # Handle ${VAR} syntax
                var_name = var_expr.strip()
                value = os.getenv(var_name)
                if value is None:
                    raise ValueError(f"Required environment variable '{var_name}' is not set")
            
            return value
        
        # Substitute all environment variables
        result = cls.ENV_VAR_PATTERN.sub(replace_var, text)
        
        # Try to convert to appropriate type
        return cls._convert_type(result)
    
    @classmethod
    def _convert_type(cls, value: str) -> Union[str, int, float, bool, list]:
        """
        Convert string value to appropriate Python type.
        
        Args:
            value: String value to convert
            
        Returns:
            Converted value (maintains string if no conversion applies)
        """
        # Handle boolean values
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        elif value.lower() in ('false', 'no', 'off', '0'):
            return False
        
        # Handle numeric values
        try:
            # Try integer first
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            pass
        
        # Handle lists (basic JSON-like format)
        if value.startswith('[') and value.endswith(']'):
            try:
                import json
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Handle simple wildcard cases
        if value == '*':
            return ['*']
        
        # Return as string if no conversion applies
        return value
    
    @classmethod
    def load_yaml_with_env(cls, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a YAML file with environment variable substitution.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Dictionary with environment variables substituted
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            yaml.YAMLError: If the file has invalid YAML syntax
            ValueError: If required environment variables are missing
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            if content is None:
                return {}
            
            # Substitute environment variables recursively
            return cls.substitute_env_vars(content)
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML syntax in {file_path}: {e}")
    
    @classmethod
    def validate_required_env_vars(cls, config_files: list) -> Dict[str, list]:
        """
        Validate that all required environment variables are set.
        
        Args:
            config_files: List of config file paths to check
            
        Returns:
            Dictionary mapping file paths to missing required variables
        """
        missing_vars = {}
        
        for file_path in config_files:
            file_path = Path(file_path)
            if not file_path.exists():
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find all ${VAR} patterns (without defaults)
                required_vars = []
                for match in cls.ENV_VAR_PATTERN.finditer(content):
                    var_expr = match.group(1)
                    if ':-' not in var_expr:  # Required variable (no default)
                        var_name = var_expr.strip()
                        if var_name not in os.environ:
                            required_vars.append(var_name)
                
                if required_vars:
                    missing_vars[str(file_path)] = required_vars
                    
            except Exception as e:
                print(f"Warning: Could not validate environment variables in {file_path}: {e}")
        
        return missing_vars


