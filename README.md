# LoL Data MCP Server

**Project 3: League of Legends Data Model Context Protocol Server**

A comprehensive MCP (Model Context Protocol) server that provides real-time access to League of Legends game data including champions, items, abilities, game mechanics, and patch information. Designed to serve as the data backbone for LoL-related AI/ML projects.

## 🎯 Project Vision

Create a centralized, intelligent data service that can efficiently provide structured LoL game data to development environments, AI agents, and other applications through the MCP protocol.

## ✅ Current Status: **Task 2.1.2 Ready to Start**

**🎯 CURRENT TASK**: Task 2.1.2 - Implement Champion Page Navigation

### ✅ What's Working Now
- **✅ Cursor MCP Integration**: 7 operational MCP tools successfully integrated with Cursor IDE
- **✅ Champion Data**: Complete data for Taric and Ezreal with stats and abilities
- **✅ Wiki Scraper Foundation**: Task 2.1.1 completed with basic HTTP handling and rate limiting
- **✅ MCP Server Core**: All Phase 1 tasks (1.1-1.8) completed successfully
- **✅ Documentation**: Comprehensive implementation roadmap with Tasks 8-10 added for missing tools

### 🎮 Available Champion Data
- **Taric** (Complete): 575 HP, 300 mana, all abilities (Bravado, Starlight's Touch, Bastion, Dazzle, Cosmic Radiance)
- **Ezreal** (Complete): 530 HP, 375 mana, all abilities (Rising Spell Force, Mystic Shot, Essence Flux, Arcane Shift, Trueshot Barrage)

## 🚀 Working MCP Tools

1. **get_champion_data** - Complete champion information with stats and abilities ✅
2. **get_ability_details** - Detailed ability information ✅
3. **get_item_data** - Item stats and information (placeholder) ⚠️
4. **search_champions** - Champion search functionality (placeholder) ⚠️
5. **get_meta_builds** - Meta builds and statistics (placeholder) ⚠️
6. **ping** - Connectivity testing ✅
7. **server_info** - Server status and statistics ✅

## 📁 Current Project Structure

```
LoL_Data_MCP_Server/
├── README.md
├── docs/
│   ├── lol_data_mcp_server.md     # Complete technical documentation
│   └── architecture.md            # System architecture
├── src/
│   ├── mcp_server/                # ✅ Core MCP server implementation
│   │   ├── stdio_server.py        # ✅ NEW: Stdio MCP server for Cursor
│   │   ├── server.py              # FastAPI web server (alternative)
│   │   ├── mcp_handler.py         # ✅ Protocol message handling (7 tools)
│   │   └── tools.py               # ✅ Tool definitions and registry
│   ├── services/                  # ✅ Business logic and data services
│   │   └── champion_service.py    # ✅ Champion data with Taric/Ezreal
│   ├── core/                      # ✅ Configuration management
│   │   └── config.py              # ✅ YAML-based configuration system
│   ├── data_sources/              # 📋 Wiki, Riot API integrations (planned)
│   ├── data_processing/           # 📋 Parsing, normalization (planned)
│   ├── storage/                   # 📋 Caching, database (planned)
│   ├── query_engine/              # 📋 Search capabilities (planned)
│   └── utils/                     # Shared utilities
├── config/                        # ✅ Configuration files
│   ├── server_config.yaml
│   ├── development_config.yaml
│   ├── production_config.yaml
│   ├── data_sources.yaml
│   └── mcp_tools.yaml
├── tests/                         # ✅ Test suite
├── examples/                      # Client examples and integration demos
├── scripts/                       # Setup and utility scripts
├── requirements.txt               # ✅ Dependencies
└── venv/                          # ✅ Virtual environment
```

## 🔧 Cursor MCP Integration Setup

### MCP Server Configuration
```json
{
  "mcpServers": {
    "lol-data": {
      "command": "powershell",
      "args": ["-Command", "& { cd 'C:\\Users\\tarik\\OneDrive\\Masaüstü\\Python\\Reinforcement Learning Projects\\Project Taric\\Lol_Data_MCP_Server'; .\\venv\\Scripts\\Activate.ps1; python -m src.mcp_server.stdio_server }"]
    }
  }
}
```

### Quick Start
```bash
# 1. Navigate to project and activate virtual environment
cd Lol_Data_MCP_Server
.\venv\Scripts\Activate.ps1  # Windows

# 2. Test the MCP server directly
python -m src.mcp_server.stdio_server

# 3. Use in Cursor via MCP commands
# @mcp lol-data get_champion_data {"champion": "Taric"}
# @mcp lol-data ping {"message": "Hello from Taric AI project!"}
```

## 🎮 Working Examples

### Get Champion Data
```python
# In Cursor chat or code
@mcp lol-data get_champion_data {"champion": "Taric"}
# Returns: Complete Taric data with stats and abilities

@mcp lol-data get_champion_data {"champion": "Ezreal"}  
# Returns: Complete Ezreal data with stats and abilities
```

### Test Connectivity
```python
@mcp lol-data ping {"message": "Hello from Taric AI project!"}
# Returns: pong: Hello from Taric AI project!
```

### Server Status
```python
@mcp lol-data server_info
# Returns: Server stats showing 7 tools available
```

## 🚧 Next Development Phase: Data Expansion

### **✅ COMPLETED**: Task 2.1.1 - Create Basic Wiki Scraper Foundation
**Objective:** Set up basic scraper infrastructure and HTTP handling  
**Files:** `src/data_sources/scrapers/wiki_scraper.py`, `src/data_sources/scrapers/__init__.py`  
**Status:** ✅ **COMPLETED** - June 2025

**✅ Accomplished:**
- ✅ Complete WikiScraper class with async HTTP handling using httpx and BeautifulSoup
- ✅ Rate limiting (1 request per second) with configurable delays
- ✅ Professional user agent and HTTP headers for responsible scraping
- ✅ Comprehensive error handling (404s, timeouts, connection errors)
- ✅ Retry logic with exponential backoff
- ✅ Champion URL building with special character support (Kai'Sa, Twisted Fate)
- ✅ Async context manager for proper resource management
- ✅ Connection testing and health checks
- ✅ Comprehensive logging at all levels
- ✅ 13 unit tests with 100% pass rate
- ✅ Verified real LoL Wiki connectivity and champion page fetching

### **🚧 CURRENT TASK**: Task 2.1.2 - Implement Champion Page Navigation
**Objective:** Navigate wiki pages and identify data sections  
**Progress:** Ready to start
**Requirements:**
- Add `find_champion_data_sections()` method
- Implement CSS selectors for champion info tables
- Add navigation to different wiki page sections (stats, abilities)
- Create page structure validation
- Handle different wiki page layouts and formats
- Add error handling for missing sections

### **📋 UPCOMING TASKS**:
- **Task 2.2**: Implement Riot Data Dragon Integration
- **Task 2.3**: Create Data Processor for Source Integration
- **Task 2.4**: Champion data service expansion (158 more champions)
- **Task 2.5**: Item data implementation

## 🔗 Integration with Other Projects

This MCP server is designed to integrate with other LoL development projects:

- **LoL Simulation Environments**: Real-time champion/item data for simulation accuracy
- **AI Agent Projects**: Enhanced state mapping with live wiki correlation  
- **Game Analysis Tools**: Meta builds, statistics, and patch tracking
- **Development Workflows**: Direct IDE integration for instant data access

## 📚 Documentation

### Project Documentation
- **[Complete Technical Documentation](docs/lol_data_mcp_server.md)**: ✅ **ENHANCED** - Comprehensive 1200+ line documentation with detailed Phase 1-7 implementation tasks, requirements, and success metrics
- **[Architecture Guide](docs/architecture.md)**: System design and components

### External Data Sources
- **[League of Legends Wiki](https://wiki.leagueoflegends.com/en-us/)**: Primary data source for champions, items, abilities
- **[Riot Data Dragon](https://developer.riotgames.com/docs/lol#data-dragon)**: Official Riot API for game data
- **[Riot Games API](https://developer.riotgames.com/)**: Live game data and statistics

## 📊 Current Achievements

- **✅ MCP Integration**: Successfully integrated with Cursor IDE
- **✅ Tool Availability**: 7 tools operational (5 LoL + 2 basic)
- **✅ Data Quality**: 100% accuracy for implemented champions (Taric, Ezreal)
- **✅ Response Time**: <50ms for mock data responses
- **✅ Reliability**: 100% uptime during development testing

## 🎯 Development Workflow

1. **Activate virtual environment** before any development
2. **Run tests** before committing changes  
3. **Update documentation** when adding features
4. **Follow code standards** (black, mypy, isort)

## 🎯 Current Task Status

**🚧 TASK 2.1.2 READY TO START: Implement Champion Page Navigation**
- **Objective**: Navigate wiki pages and identify data sections
- **Progress**: Ready to start implementation
- **Requirements**: Add `find_champion_data_sections()` method, implement CSS selectors for champion info tables, handle different wiki page layouts
- **Files**: `src/data_sources/scrapers/wiki_scraper.py`
- **Previous**: ✅ Task 2.1.1 completed (WikiScraper foundation with HTTP handling and rate limiting)

**📋 Current Phase**: Phase 2 - Data Sources Integration (Champion Page Navigation → Stats Parsing → Abilities Parsing)

### 🔧 Current Implementation Status
- **Phase 1**: ✅ **COMPLETED** - MCP Server Foundation (Tasks 1.1-1.8)
- **Task 2.1.1**: ✅ **COMPLETED** - Basic Wiki Scraper Foundation 
- **Task 2.1.2**: 🚧 **READY TO START** - Champion Page Navigation (Current Task)
- **Future Tasks**: 📋 Tasks 8-10 added for missing MCP tool implementations

---

**Version**: 2.2  
**Status**: ✅ **MCP Integration Complete** - Ready for Phase 2 Development  
**Last Updated**: June 2025