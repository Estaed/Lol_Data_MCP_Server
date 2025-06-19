# LoL Data MCP Server

**Project 3: League of Legends Data Model Context Protocol Server**

A comprehensive MCP (Model Context Protocol) server that provides real-time access to League of Legends game data including champions, items, abilities, game mechanics, and patch information. Designed to serve as the data backbone for LoL-related AI/ML projects.

## 🎯 Project Vision

Create a centralized, intelligent data service that can efficiently provide structured LoL game data to development environments, AI agents, and other applications through the MCP protocol.

## 🚀 Core Features

### Data Sources
- **LoL Wiki Integration**: Champion stats, abilities, items, game mechanics
- **Riot Games API**: Live game data, match history, current patch info
- **Community APIs**: Meta analysis, build recommendations, statistical insights
- **Patch Tracking**: Historical data, balance changes, meta evolution

### MCP Tools
- `get_champion_data` - Complete champion information
- `get_ability_details` - Detailed ability mechanics and scaling
- `get_item_data` - Item stats, components, build paths
- `get_game_mechanics` - Minion/turret stats, experience curves
- `search_champions` - Query champions by role, tags, abilities
- `get_patch_info` - Current and historical patch data
- `get_meta_builds` - Current meta builds and win rates

### Advanced Features
- **Intelligent Caching**: Performance-optimized data storage
- **Real-time Updates**: Automatic patch detection and data refresh
- **Query Engine**: Complex data relationships and searches
- **Multi-format Output**: JSON, YAML, XML support for different clients

## 📁 Project Structure

```
LoL_Data_MCP_Server/
├── README.md
├── docs/
│   ├── project_specification.md
│   ├── architecture.md
│   ├── api_reference.md
│   └── mcp_protocol_guide.md
├── src/
│   ├── mcp_server/           # Core MCP server implementation
│   ├── data_sources/         # Wiki, Riot API, community API integrations
│   ├── data_processing/      # Parsing, normalization, enrichment
│   ├── storage/              # Caching, database, file storage
│   ├── query_engine/         # Search and query capabilities
│   └── utils/                # Shared utilities
├── config/
│   ├── server_config.yaml
│   ├── data_sources.yaml
│   └── mcp_tools.yaml
├── tests/
├── examples/
│   ├── client_examples/
│   └── integration_demos/
├── scripts/
│   ├── setup_server.py
│   ├── data_refresh.py
│   └── health_check.py
├── requirements.txt
└── setup.py
```

## 🔗 Integration with Other Projects

This MCP server is designed to integrate with other LoL development projects:

- **LoL Simulation Environments**: Real-time champion/item data for simulation accuracy
- **AI Agent Projects**: Enhanced state mapping with live wiki correlation  
- **Game Analysis Tools**: Meta builds, statistics, and patch tracking
- **Development Workflows**: Direct IDE integration for instant data access

## 🏗️ Development Phases

### Phase 1: MCP Server Foundation
- Core MCP protocol implementation
- Basic wiki data extraction
- Champion and item data endpoints

### Phase 2: Enhanced Data Sources
- Riot API integration
- Community API connections
- Data normalization pipeline

### Phase 3: Intelligence Layer
- Query engine implementation
- Advanced caching strategies
- Patch tracking automation

### Phase 4: Production Ready
- Performance optimization
- Error handling and resilience
- Documentation and examples

## 🔧 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start MCP server
python scripts/setup_server.py

# Test connection
python examples/test_connection.py
```

## 📚 Documentation

- **[Project Specification](docs/project_specification.md)**: Detailed requirements and features
- **[Architecture Guide](docs/architecture.md)**: System design and components
- **[API Reference](docs/api_reference.md)**: Complete MCP tools documentation
- **[MCP Protocol Guide](docs/mcp_protocol_guide.md)**: Understanding MCP integration

## 🎮 Example Usage

```python
# In your IDE with MCP integration
champion_data = mcp_client.call_tool("get_champion_data", {
    "champion": "Taric",
    "include": ["stats", "abilities", "builds"]
})

ability_details = mcp_client.call_tool("get_ability_details", {
    "champion": "Taric", 
    "ability": "Q",
    "level": 5
})

current_meta = mcp_client.call_tool("get_meta_builds", {
    "champion": "Taric",
    "role": "support",
    "patch": "current"
})
```

---

**Version**: 1.0  
**Status**: 🚧 Under Development  
**Last Updated**: December 2024 