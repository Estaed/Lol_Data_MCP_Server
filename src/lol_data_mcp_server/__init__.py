"""
LoL Data MCP Server

A comprehensive Model Context Protocol (MCP) server providing real-time, 
structured access to League of Legends game data for development environments, 
AI agents, and other applications.
"""

__version__ = "1.0.0"
__author__ = "Project Taric Team"
__email__ = "tarik.estaed@gmail.com"

from typing import Dict, Any

# Package metadata
__package_info__: Dict[str, Any] = {
    "name": "lol-data-mcp-server",
    "version": __version__,
    "description": "MCP server for League of Legends game data",
    "author": __author__,
    "email": __email__,
    "license": "MIT",
    "url": "https://github.com/project-taric/lol-data-mcp-server",
}

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__package_info__",
] 