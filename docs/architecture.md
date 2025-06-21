# LoL Data MCP Server - Architecture Guide

## System Overview

The LoL Data MCP Server is designed as a high-performance, scalable service that aggregates League of Legends game data from multiple sources and serves it through the Model Context Protocol (MCP) for direct integration with development environments.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           Client Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  IDEs (Cursor, VSCode)  │  AI Agents  │  Custom Applications    │
└─────────────────┬───────────────────────────────────────────────┘
                  │ MCP Protocol (WebSocket/HTTP)
┌─────────────────▼───────────────────────────────────────────────┐
│                        MCP Server Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Server │ MCP Protocol Handler │ Authentication & Rate  │
│                 │                      │ Limiting               │
└─────────────────┬───────────────────────────────────────────────┘
                  │ Internal API
┌─────────────────▼───────────────────────────────────────────────┐
│                     Application Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  Query Engine   │  Data Processor     │  Cache Manager         │
│                 │                     │                        │
│  Search         │  Validator          │  Update Scheduler      │
└─────────────────┬───────────────────────────────────────────────┘
                  │ Data Access
┌─────────────────▼───────────────────────────────────────────────┐
│                      Storage Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL     │  Redis Cache        │  File Storage          │
│  (Primary DB)   │  (L2 Cache)         │  (Static Assets)       │
└─────────────────┬───────────────────────────────────────────────┘
                  │ Data Ingestion
┌─────────────────▼───────────────────────────────────────────────┐
│                    Data Sources Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  LoL Wiki       │  Riot Games API     │  Community APIs        │
│  Scraper        │  (Data Dragon)      │  (op.gg, lolalytics)   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. MCP Server Layer

**FastAPI Application** ✅ **IMPLEMENTED (Task 1.2)**
- ✅ Handles HTTP/WebSocket connections with lifespan management
- ✅ Implements MCP protocol specification over WebSocket at `/mcp`
- ✅ Provides health checks endpoint at `/health`
- ✅ Graceful startup and shutdown with proper resource cleanup
- ✅ Structured logging with contextual information

**MCP Protocol Handler** ✅ **IMPLEMENTED (Task 1.2)**
- ✅ Translates MCP requests to internal API calls
- ✅ Manages MCP tool registry with basic tools (ping, server_info)
- ✅ Handles request/response serialization with proper JSON-RPC 2.0 format
- ✅ Implements MCP protocol methods: initialize, list_tools, call_tool
- ✅ Error handling with standardized error codes

**Authentication & Rate Limiting**
- API key validation
- Request rate limiting per client
- Usage tracking and quotas

### 2. Application Layer

**Query Engine**
- SQL query optimization
- Complex data relationship handling
- Aggregation and statistics calculation

**Data Processor**
- Data normalization and validation
- Conflict resolution between sources
- Schema transformation

**Cache Manager**
- Multi-level caching strategy
- TTL management
- Cache invalidation on data updates

**Update Scheduler**
- Periodic data refresh from sources
- Patch detection and automatic updates
- Failure handling and retry logic

### 3. Storage Layer

**PostgreSQL Database Schema**
```sql
-- Champions table
CREATE TABLE champions (
    id SERIAL PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    title VARCHAR(200),
    roles TEXT[],
    tags TEXT[],
    patch_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Champion stats table
CREATE TABLE champion_stats (
    id SERIAL PRIMARY KEY,
    champion_id INTEGER REFERENCES champions(id),
    level INTEGER NOT NULL CHECK (level >= 1 AND level <= 18),
    hp DECIMAL(8,2),
    mp DECIMAL(8,2),
    move_speed DECIMAL(6,2),
    armor DECIMAL(6,2),
    spell_block DECIMAL(6,2),
    attack_range DECIMAL(6,2),
    hp_regen DECIMAL(6,4),
    mp_regen DECIMAL(6,4),
    crit DECIMAL(6,4),
    attack_damage DECIMAL(6,2),
    attack_speed_offset DECIMAL(6,4),
    attack_speed_per_level DECIMAL(6,4)
);

-- Abilities table
CREATE TABLE abilities (
    id SERIAL PRIMARY KEY,
    champion_id INTEGER REFERENCES champions(id),
    slot VARCHAR(10) NOT NULL, -- 'passive', 'Q', 'W', 'E', 'R'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    cooldown DECIMAL[],
    cost DECIMAL[],
    range DECIMAL[],
    damage JSONB, -- Complex damage scaling data
    effect_amounts JSONB -- Other effect values
);

-- Items table
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    item_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    plaintext TEXT,
    gold JSONB, -- {base, purchasable, total, sell}
    stats JSONB, -- Flat stat bonuses
    tags TEXT[],
    builds_from INTEGER[], -- Array of item IDs
    builds_into INTEGER[], -- Array of item IDs
    patch_version VARCHAR(20)
);
```

**Redis Cache Structure**
```
champion:{name}:stats -> JSON object
champion:{name}:abilities -> JSON object
item:{name}:details -> JSON object
patch:current -> Version string
meta:builds:{champion}:{role} -> JSON array
search:champions:{query_hash} -> JSON array
```

### 4. Data Sources Layer

**LoL Wiki Scraper**
- BeautifulSoup-based HTML parsing
- Handles dynamic content loading
- Respects robots.txt and rate limits

**Riot Games API Client**
- Data Dragon for static data
- Live API for real-time information
- Automatic API key rotation

**Community API Integrations**
- op.gg for meta builds and statistics
- lolalytics for win rates and pick rates
- u.gg for skill order recommendations

## Data Flow Architecture

### 1. Data Ingestion Flow
```
External Source → Rate Limiter → Parser → Validator → Transformer → Database
                                   ↓
                              Conflict Resolver
                                   ↓
                              Cache Invalidator
```

### 2. Query Processing Flow
```
MCP Request → Auth Check → Request Parser → Cache Check → Query Engine → Response Builder → MCP Response
                                             ↓ (miss)
                                          Database Query → Cache Store
```

### 3. Update Flow
```
Scheduler → Source Check → Change Detection → Data Fetch → Validation → Database Update → Cache Invalidation
                                                                              ↓
                                                                        Notification System
```

## Scalability Design

### Horizontal Scaling
- Stateless application servers
- Load balancer with session affinity
- Database connection pooling
- Redis cluster for distributed caching

### Performance Optimization
- Database indexing strategy
- Query result pagination
- Async/await throughout the stack
- Connection pooling and reuse

### Monitoring & Observability
- Prometheus metrics collection
- Structured logging with correlation IDs
- Health check endpoints
- Performance dashboards

## Security Architecture

### Authentication
- API key-based authentication
- JWT tokens for session management
- Role-based access control

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- Rate limiting and DDoS protection
- Audit logging

## Deployment Architecture

### Development Environment
```
Docker Compose:
- FastAPI app container
- PostgreSQL container
- Redis container
- nginx reverse proxy
```

### Production Environment
```
Kubernetes Cluster:
- App pods (3+ replicas)
- PostgreSQL StatefulSet
- Redis deployment
- Ingress controller
- Monitoring stack (Prometheus, Grafana)
```

## Configuration Management

**Environment Variables**
- Database connection strings
- API keys and secrets
- Cache configuration
- Feature flags

**Configuration Files**
- MCP tool definitions (YAML)
- Data source configurations
- Logging configuration
- Deployment manifests

## Error Handling & Resilience

### Circuit Breaker Pattern
- Prevent cascade failures
- Automatic recovery
- Fallback responses

### Retry Strategy
- Exponential backoff
- Maximum retry limits
- Dead letter queues

### Graceful Degradation
- Serve cached data when sources unavailable
- Reduced functionality modes
- User-friendly error messages 