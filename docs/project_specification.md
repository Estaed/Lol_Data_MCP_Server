# LoL Data MCP Server - Project Specification

**Version:** 1.0  
**Date:** December 2024  
**Project Goal:** To develop a comprehensive Model Context Protocol (MCP) server that provides real-time, structured access to League of Legends game data for development environments, AI agents, and other applications.

---

## I. Vision & Scope

### Problem Statement
- **Data Fragmentation**: LoL data is scattered across wiki, APIs, and community sources
- **Development Friction**: Manual data gathering slows development of LoL-related projects
- **Data Staleness**: Game patches constantly change champion/item stats
- **Format Inconsistency**: Different data sources use different formats and structures

### Solution
Create a unified, intelligent MCP server that:
- **Aggregates** data from multiple sources (Wiki, Riot API, Community APIs)
- **Normalizes** data into consistent, structured formats
- **Caches** intelligently for performance while staying current
- **Serves** data through MCP protocol for direct IDE integration

### Success Criteria
- **Performance**: Sub-100ms response times for cached data
- **Accuracy**: 99.9% data accuracy compared to official sources
- **Coverage**: 160+ champions, 200+ items, all major game mechanics
- **Integration**: Seamless MCP integration with popular IDEs
- **Reliability**: 99.5% uptime with automatic failover

---

## II. Requirements & Features

### R1: MCP Protocol Implementation
- **R1.1**: Full MCP server compliance with protocol specification
- **R1.2**: WebSocket and HTTP transport support
- **R1.3**: Standard MCP tool definitions for all data endpoints
- **R1.4**: Error handling and status reporting via MCP
- **R1.5**: Client authentication and rate limiting

### R2: Data Sources Integration
- **R2.1**: League of Legends Wiki scraping and parsing
- **R2.2**: Riot Games API integration (Data Dragon, Live API)
- **R2.3**: Community API integration (op.gg, lolalytics, etc.)
- **R2.4**: Patch detection and automatic data refresh
- **R2.5**: Data validation and conflict resolution

### R3: Champion Data Management
- **R3.1**: Complete champion roster (160+ champions)
- **R3.2**: Base stats and growth per level
- **R3.3**: Ability details (damage, cooldowns, scaling, mechanics)
- **R3.4**: Recommended builds and skill orders
- **R3.5**: Historical patch changes and meta evolution

### R4: Item Data Management
- **R4.1**: All items with stats and costs
- **R4.2**: Item components and build paths
- **R4.3**: Active and passive effects
- **R4.4**: Item interactions and synergies
- **R4.5**: Cost efficiency calculations

### R5: Game Mechanics Data
- **R5.1**: Minion stats and wave patterns
- **R5.2**: Turret behavior and stats
- **R5.3**: Jungle monsters and objectives
- **R5.4**: Experience and gold curves
- **R5.5**: Game rules and formulas

### R6: Query Engine & Search
- **R6.1**: Complex queries across data relationships
- **R6.2**: Full-text search capabilities
- **R6.3**: Filtering and sorting options
- **R6.4**: Aggregation and statistics
- **R6.5**: Query optimization and caching

### R7: Performance & Reliability
- **R7.1**: Intelligent caching with TTL management
- **R7.2**: Database optimization for fast queries
- **R7.3**: Horizontal scaling capabilities
- **R7.4**: Health monitoring and alerting
- **R7.5**: Graceful degradation under load

---

## III. MCP Tools Specification

### Tool: `get_champion_data`
```json
{
  "name": "get_champion_data",
  "description": "Get comprehensive champion information",
  "inputSchema": {
    "type": "object",
    "properties": {
      "champion": {"type": "string", "description": "Champion name"},
      "patch": {"type": "string", "default": "current"},
      "include": {
        "type": "array",
        "items": {"enum": ["stats", "abilities", "builds", "history"]},
        "default": ["stats", "abilities"]
      }
    },
    "required": ["champion"]
  }
}
```

### Tool: `get_ability_details`
```json
{
  "name": "get_ability_details", 
  "description": "Get detailed ability information",
  "inputSchema": {
    "type": "object",
    "properties": {
      "champion": {"type": "string"},
      "ability": {"enum": ["passive", "Q", "W", "E", "R"]},
      "level": {"type": "integer", "minimum": 1, "maximum": 18},
      "include_scaling": {"type": "boolean", "default": true}
    },
    "required": ["champion", "ability"]
  }
}
```

### Tool: `get_item_data`
```json
{
  "name": "get_item_data",
  "description": "Get item information and stats",
  "inputSchema": {
    "type": "object", 
    "properties": {
      "item": {"type": "string"},
      "include": {
        "type": "array",
        "items": {"enum": ["stats", "components", "passive", "cost"]},
        "default": ["stats", "cost"]
      }
    },
    "required": ["item"]
  }
}
```

### Tool: `search_champions`
```json
{
  "name": "search_champions",
  "description": "Search champions by criteria",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "role": {"enum": ["top", "jungle", "mid", "adc", "support"]},
      "tags": {"type": "array", "items": {"type": "string"}},
      "limit": {"type": "integer", "default": 10}
    }
  }
}
```

### Tool: `get_meta_builds`
```json
{
  "name": "get_meta_builds",
  "description": "Get current meta builds and statistics",
  "inputSchema": {
    "type": "object",
    "properties": {
      "champion": {"type": "string"},
      "role": {"type": "string"},
      "rank": {"enum": ["all", "diamond+", "master+"]},
      "patch": {"type": "string", "default": "current"}
    },
    "required": ["champion"]
  }
}
```

---

## IV. Data Architecture

### Data Flow
```
External Sources → Ingestion → Processing → Storage → Cache → MCP Server → Client
```

### Storage Strategy
- **PostgreSQL**: Primary database for structured data
- **Redis**: High-performance caching layer
- **File Storage**: Static assets (images, videos)
- **Time Series DB**: Historical patch data and statistics

### Caching Strategy
- **L1 Cache**: In-memory application cache (5 min TTL)
- **L2 Cache**: Redis distributed cache (1 hour TTL)
- **L3 Cache**: Database query cache (24 hour TTL)
- **CDN**: Static content delivery

---

## V. Implementation Plan

### Phase 1: MCP Foundation
**Objective**: Basic MCP server with champion data
- MCP protocol implementation and basic server setup
- Wiki scraping for champion data and basic tools
- Working MCP server with `get_champion_data` tool
- Champion stats for popular champions and basic caching

### Phase 2: Data Expansion
**Objective**: Full data coverage and Riot API integration
- Complete champion roster and item data
- Riot API integration and ability details
- All MCP tools functional with 160+ champions
- 200+ items with complete information

### Phase 3: Intelligence Layer
**Objective**: Advanced features and optimization
- Query engine and search capabilities
- Meta builds, statistics, and historical data
- Advanced search and filtering with meta analysis
- Performance optimization (sub-100ms responses)

### Phase 4: Production Ready
**Objective**: Production deployment and reliability
- Monitoring, logging, and error handling
- Documentation, testing, and deployment
- Production-ready deployment with comprehensive docs
- Integration examples for LoL development projects

---

## VI. Integration with Other Projects

### LoL Simulation Environment Projects
- **Champion Configs**: Auto-generate YAML configs from MCP data
- **Balance Updates**: Automatic config updates when patches release
- **Item Stats**: Real-time item data for accurate simulation

### AI Agent Projects
- **State Mapping**: Enhanced mapping with real-time wiki correlation
- **Meta Analysis**: Current meta builds for realistic opponent modeling
- **Patch Adaptation**: Automatic adaptation to balance changes

### Development Tools & Analytics
- **Champion Coverage**: Easy expansion to other champions/roles
- **Game Mode Support**: ARAM, Ranked, Tournament data
- **Statistical Analysis**: Win rates, pick/ban rates, meta trends

---

## VII. Success Metrics

### Performance Metrics
- **Response Time**: < 100ms for 95% of cached requests
- **Throughput**: > 1000 requests/second sustained
- **Availability**: 99.5% uptime
- **Data Freshness**: < 1 hour lag from patch releases

### Quality Metrics
- **Data Accuracy**: 99.9% match with official sources
- **Coverage**: 100% champion/item coverage
- **Completeness**: 95% of data fields populated
- **Consistency**: 100% schema compliance

### Usage Metrics
- **Integration Success**: Seamless compatibility with LoL development projects
- **Development Speed**: 50% reduction in data gathering time
- **Error Rate**: < 0.1% failed requests
- **Client Satisfaction**: 95% developer satisfaction rating 