"""
Test package structure and basic imports.

This test verifies that the package is properly structured and can be imported.
"""

import pytest
import sys
from pathlib import Path


def test_package_can_be_imported():
    """Test that the main package can be imported."""
    try:
        import lol_data_mcp_server
        assert lol_data_mcp_server.__version__ == "1.0.0"
        assert lol_data_mcp_server.__author__ == "Project Taric Team"
    except ImportError as e:
        pytest.fail(f"Failed to import main package: {e}")


def test_subpackages_can_be_imported():
    """Test that all subpackages can be imported."""
    subpackages = [
        "lol_data_mcp_server.data_processing",
        "lol_data_mcp_server.data_sources", 
        "lol_data_mcp_server.mcp_server",
        "lol_data_mcp_server.query_engine",
        "lol_data_mcp_server.storage",
        "lol_data_mcp_server.utils",
    ]
    
    for package in subpackages:
        try:
            __import__(package)
        except ImportError as e:
            pytest.fail(f"Failed to import subpackage {package}: {e}")


def test_package_metadata():
    """Test that package metadata is properly defined."""
    import lol_data_mcp_server
    
    assert hasattr(lol_data_mcp_server, "__package_info__")
    assert isinstance(lol_data_mcp_server.__package_info__, dict)
    
    required_keys = ["name", "version", "description", "author", "email", "license", "url"]
    for key in required_keys:
        assert key in lol_data_mcp_server.__package_info__
        assert lol_data_mcp_server.__package_info__[key] is not None


def test_package_structure_exists():
    """Test that the expected package structure exists on disk."""
    # Get the package root directory
    import lol_data_mcp_server
    package_path = Path(lol_data_mcp_server.__file__).parent
    
    expected_modules = [
        "data_processing",
        "data_sources", 
        "mcp_server",
        "query_engine",
        "storage",
        "utils",
    ]
    
    for module in expected_modules:
        module_path = package_path / module
        assert module_path.exists(), f"Module directory {module} does not exist"
        assert (module_path / "__init__.py").exists(), f"Module {module} missing __init__.py"


if __name__ == "__main__":
    pytest.main([__file__]) 