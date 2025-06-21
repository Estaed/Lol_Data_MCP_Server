#!/usr/bin/env python3
"""
Project Setup Script for LoL Data MCP Server

This script initializes the project structure, creates necessary files,
and verifies that everything is set up correctly for development.
"""

import os
import sys
from pathlib import Path


def create_init_files():
    """Create __init__.py files in all Python packages."""
    init_locations = [
        "src/__init__.py",
        "src/mcp_server/__init__.py",
        "tests/__init__.py",
    ]

    for location in init_locations:
        init_file = Path(location)
        init_file.parent.mkdir(parents=True, exist_ok=True)
        if not init_file.exists():
            init_file.write_text("# Package initialization\n")
            print(f"✅ Created {location}")


def create_config_files():
    """Create default configuration files."""
    configs = {
        "config/server_config.yaml": """# MCP Server Configuration
server:
  host: "0.0.0.0"
  port: 8000
  debug: true
  
database:
  url: "postgresql://lol_user:lol_pass@localhost:5432/lol_data"
  pool_size: 10
  max_overflow: 20
  
redis:
  url: "redis://localhost:6379/0"
  max_connections: 10
  
data_sources:
  wiki:
    base_url: "https://wiki.leagueoflegends.com"
    rate_limit: 1.0  # seconds between requests
  
  riot_api:
    enabled: true
    rate_limit: 0.5
    
logging:
  level: "INFO"
  format: "json"
""",
        "config/data_sources.yaml": """# Data Sources Configuration
sources:
  lol_wiki:
    name: "League of Legends Wiki"
    type: "scraper"
    base_url: "https://wiki.leagueoflegends.com"
    endpoints:
      champion_page: "/wiki/{champion}"
      item_page: "/wiki/{item}"
    rate_limit: 1.0
    
  riot_data_dragon:
    name: "Riot Data Dragon"
    type: "api"
    base_url: "https://ddragon.leagueoflegends.com"
    endpoints:
      versions: "/api/versions.json"
      champions: "/cdn/{version}/data/en_US/champion.json"
      items: "/cdn/{version}/data/en_US/item.json"
    rate_limit: 0.5
""",
        "config/mcp_tools.yaml": """# MCP Tools Configuration
tools:
  get_champion_data:
    description: "Get comprehensive champion information"
    timeout: 30
    cache_ttl: 3600
    
  get_ability_details:
    description: "Get detailed ability information" 
    timeout: 15
    cache_ttl: 3600
    
  get_item_data:
    description: "Get item information and stats"
    timeout: 15
    cache_ttl: 3600
    
  search_champions:
    description: "Search champions by criteria"
    timeout: 10
    cache_ttl: 1800
    
  get_meta_builds:
    description: "Get current meta builds and statistics"
    timeout: 20
    cache_ttl: 900  # 15 minutes for meta data
""",
    }

    for file_path, content in configs.items():
        config_file = Path(file_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        if not config_file.exists():
            config_file.write_text(content)
            print(f"✅ Created {file_path}")


def create_example_files():
    """Create example files for testing and demonstration."""
    examples = {
        "examples/client_examples/basic_usage.py": '''"""
Basic MCP Client Usage Example

This example demonstrates how to connect to the LoL Data MCP Server
and make basic requests for champion and item data.
"""

import asyncio
import json
from mcp_client import MCPClient

async def main():
    # Connect to MCP server
    client = MCPClient("ws://localhost:8000/mcp")
    await client.connect()
    
    try:
        # Get Taric's champion data
        taric_data = await client.call_tool("get_champion_data", {
            "champion": "Taric",
            "include": ["stats", "abilities"]
        })
        print("Taric Data:", json.dumps(taric_data, indent=2))
        
        # Get Taric's Q ability details
        q_ability = await client.call_tool("get_ability_details", {
            "champion": "Taric",
            "ability": "Q",
            "level": 5
        })
        print("Taric Q at Level 5:", json.dumps(q_ability, indent=2))
        
        # Search for support champions
        supports = await client.call_tool("search_champions", {
            "role": "support",
            "limit": 5
        })
        print("Support Champions:", json.dumps(supports, indent=2))
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
''',
        "examples/integration_demos/project_integration.py": '''"""
Integration Demo for Projects 1 & 2

This example shows how the MCP server integrates with the LoL Simulation
Environment and Taric AI Agent projects.
"""

import asyncio
import yaml
from mcp_client import MCPClient

async def generate_taric_config_for_sim_env():
    """Generate Taric configuration for the simulation environment."""
    client = MCPClient("ws://localhost:8000/mcp")
    await client.connect()
    
    try:
        # Get comprehensive Taric data
        taric_data = await client.call_tool("get_champion_data", {
            "champion": "Taric",
            "include": ["stats", "abilities", "builds"]
        })
        
        # Transform to simulation environment format
        sim_config = {
            "name": "Taric",
            "base_stats": taric_data["stats"],
            "abilities": {
                ability["slot"]: {
                    "name": ability["name"],
                    "mana_cost": ability["cost"][0] if ability["cost"] else 0,
                    "cooldown": ability["cooldown"][0] if ability["cooldown"] else 0,
                    "range": ability["range"][0] if ability["range"] else 0
                }
                for ability in taric_data["abilities"]
            },
            "recommended_items": taric_data["builds"]["core_items"][:3]
        }
        
        # Save to YAML
        with open("taric_config_generated.yaml", "w") as f:
            yaml.dump(sim_config, f, default_flow_style=False)
        
        print("✅ Generated taric_config_generated.yaml for simulation environment")
        return sim_config
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_taric_config_for_sim_env())
''',
    }

    for file_path, content in examples.items():
        example_file = Path(file_path)
        example_file.parent.mkdir(parents=True, exist_ok=True)
        if not example_file.exists():
            example_file.write_text(content)
            print(f"✅ Created {file_path}")


def verify_structure():
    """Verify that the project structure is complete."""
    required_dirs = [
        "docs",
        "src",
        "config",
        "tests",
        "examples",
        "scripts",
        "src/mcp_server",
        "src/data_sources",
        "src/data_processing",
        "src/storage",
        "src/query_engine",
        "src/utils",
        "examples/client_examples",
        "examples/integration_demos",
    ]

    required_files = [
        "README.md",
        "requirements.txt",
        "docs/project_specification.md",
        "docs/architecture.md",
    ]

    print("\\n🔍 Verifying project structure...")

    # Check directories
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ Directory: {dir_path}")
        else:
            print(f"❌ Missing directory: {dir_path}")

    # Check files
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ File: {file_path}")
        else:
            print(f"❌ Missing file: {file_path}")


def main():
    """Main setup function."""
    print("🚀 Setting up LoL Data MCP Server project...")
    print("=" * 50)

    # Change to project directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Create all necessary files
    create_init_files()
    create_config_files()
    create_example_files()

    # Verify everything is set up
    verify_structure()

    print("\\n" + "=" * 50)
    print("✅ Project setup complete!")
    print("\\n🎯 Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Set up database: Create PostgreSQL database 'lol_data'")
    print("3. Start development: Begin with Phase 1 implementation")
    print("4. Test MCP connection: Run examples/client_examples/basic_usage.py")

    print("\\n📚 Documentation:")
    print("- Project Specification: docs/project_specification.md")
    print("- Architecture Guide: docs/architecture.md")


if __name__ == "__main__":
    main()
