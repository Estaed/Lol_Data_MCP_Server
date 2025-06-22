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
│   ├── services/             # Business logic and data services (NEW - Task 1.4)
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

## 🏗️ Current Development Status

### Phase 1: MCP Server Foundation ✅ **COMPLETED**
**Status**: All foundation tasks completed successfully

### 🚧 Phase 2: Data Sources Integration **IN PROGRESS**

### **🚧 CURRENT TASK**: Task 2.1 - Implement LoL Wiki Scraper
**Objective:** Create a web scraper for League of Legends Wiki  
**Files:** `src/data_sources/wiki_scraper.py`  
**Progress:** Not started
**Requirements:**
- Create `WikiScraper` class using httpx and BeautifulSoup
- Implement `scrape_champion_page()` for champion data
- Add rate limiting (1 request per second)
- Parse champion stats table (HP, AD, Armor, etc.)
- Extract ability information (Q, W, E, R, Passive)
- Handle HTTP errors and retries
- Add caching for scraped pages

### **📋 UPCOMING TASKS**:
- **Task 2.2**: Implement Riot Data Dragon Integration
- **Task 2.3**: Create Data Processor for Source Integration
- **Task 2.4**: Implement Basic Database Models
- **Task 2.5**: Create Data Storage Service

> **📋 Full Task Tracking**: See `docs/lol_data_mcp_server.md` for complete task list and detailed progress

## 🔧 Quick Start

```bash
# 1. Set up virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# or: source venv/bin/activate  # Unix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start MCP server (Task 1.2 - Basic Framework)
python -m src.mcp_server.server

# 4. Test server health
curl http://localhost:8000/health

# 5. Run tests
pytest tests/test_mcp_server.py -v
```

### Current Functionality (Task 1.2)
- ✅ MCP WebSocket server running on `ws://localhost:8000/mcp`
- ✅ Health check endpoint at `http://localhost:8000/health`
- ✅ Basic MCP tools: `ping` and `server_info`
- ✅ Full MCP protocol compliance for initialization and tool management

## 📚 Documentation

### Project Documentation
- **[Project Specification](docs/project_specification.md)**: Detailed requirements and features
- **[Architecture Guide](docs/architecture.md)**: System design and components
- **[API Reference](docs/api_reference.md)**: Complete MCP tools documentation
- **[MCP Protocol Guide](docs/mcp_protocol_guide.md)**: Understanding MCP integration

### External Data Sources
- **[League of Legends Wiki](https://wiki.leagueoflegends.com/en-us/)**: Primary data source for champions, items, abilities
- **[Riot Data Dragon](https://developer.riotgames.com/docs/lol#data-dragon)**: Official Riot API for game data
- **[Riot Games API](https://developer.riotgames.com/)**: Live game data and statistics

### IDE Integration - Cursor Settings
For enhanced development experience, add these documentation sources to your Cursor IDE settings:

1. **Open Cursor Settings** → `Cursor: Docs`
2. **Add Documentation Sources**:
   ```json
   {
     "sources": [
       {
         "name": "League of Legends Wiki",
         "url": "https://wiki.leagueoflegends.com/en-us/",
         "description": "Official LoL game data and mechanics"
       },
       {
         "name": "Riot Developer Portal", 
         "url": "https://developer.riotgames.com/",
         "description": "Riot APIs and Data Dragon documentation"
       },
       {
         "name": "MCP Protocol Spec",
         "url": "https://spec.modelcontextprotocol.io/",
         "description": "Model Context Protocol specification"
       }
     ]
   }
   ```
3. **Index for Auto-completion**: Enable indexing for LoL-specific terminology and data structures

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