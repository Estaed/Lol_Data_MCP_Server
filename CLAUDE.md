# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 PROJECT OVERVIEW

**LoL Data MCP Server** - A comprehensive Model Context Protocol server that provides real-time access to League of Legends game data including champions, items, abilities, game mechanics, and patch information.

### Project Context
This is part of **Project Taric**, which contains 3 separate projects:
- **LoL_Data_MCP_Server** (this project): MCP server for League of Legends data
- **Lol_Sim_Env**: LoL simulation environment for AI training  
- **Taric_AI_Agent**: AI agent that plays Taric champion

Each project has its own virtual environment and focuses on different aspects of the LoL AI ecosystem.

## 🔄 **DEVELOPMENT ENVIRONMENT SETUP**

**CRITICAL**: Activate the virtual environment for Python operations:

```bash
# Navigate to project directory 
cd LoL_Data_MCP_Server

# Activate virtual environment (Windows)
.\venv\Scripts\Activate.ps1

# Verify activation - should see (venv) in terminal prompt
```

**When to use venv:**
- ✅ Running tests: `pytest`
- ✅ Running MCP server: `python -m src.mcp_server.stdio_server`
- ✅ Code quality tools: `black .`, `mypy .`, `flake8 .`, `isort .`
- ✅ Installing dependencies: `pip install -r requirements.txt`

**When venv is NOT needed:**
- ❌ File editing/reading
- ❌ Git operations: `git add`, `git commit`, `git push`
- ❌ Basic file operations

### 🚨 **CRITICAL QUESTIONS RULE**

**When you have REALLY IMPORTANT questions about the project or during task execution:**

- **YOU CAN ASK QUESTIONS even if it stops the generation progress**
- **Important questions include:**
  - Architecture decisions that affect multiple components
  - Unclear requirements that could lead to wrong implementation
  - Breaking changes that might affect existing functionality
  - Technical approach questions when multiple valid options exist
  - Data model or API design questions
  - Integration concerns with existing systems
- **When to ask**: If the question is critical for correct implementation
- **How to ask**: Stop generation, ask the question clearly, wait for clarification
- **Priority**: Getting the right answer is more important than continuous generation

**Example scenarios where you SHOULD ask:**
- "I'm not sure if this new API should be REST or GraphQL - this affects the entire architecture"
- "Should I modify the existing ChampionService or create a new one? This impacts all existing tools"
- "The task mentions 'extend the ability tool' but I see multiple ways to do this - which approach do you prefer?"

**Remember**: It's better to ask and get it right than to implement the wrong solution.

### 🎯 **TASK-BASED DEVELOPMENT WORKFLOW**

#### Before Starting ANY Development Task:

1. **📋 ANALYZE THE TASK**
   - Read the task description completely
   - Understand requirements and acceptance criteria
   - Check dependencies and prerequisites
   - Identify which files/modules will be affected

2. **🧠 THINKING LEVELS FOR PROBLEM COMPLEXITY - UPDATED RULES**
   - **DEFAULT LEVEL**: Always start with **"think"** as the baseline for ALL tasks
   - **think**: Default level - ALL tasks start here, straightforward implementation
   - **think hard**: Multi-step tasks, moderate complexity  
   - **think harder**: Complex analysis, integration challenges, architecture decisions
   - **ultrathink**: Critical system changes, cross-project impacts, complex debugging
   - **ESCALATION RULE**: For critical/complex problems, escalate one level higher than normal
     - Normal "think" task → Use "think hard" if critical
     - Normal "think hard" task → Use "think harder" if critical  
     - Normal "think harder" task → Use "ultrathink" if critical
   - **MANDATORY GEMINI VALIDATION**: Always use Gemini CLI to check everything is okay
   - **CRITICAL**: Always explain what you're thinking and planning to the user
   - **Stay visible**: Communicate your process and get user approval before proceeding

### 🧠 **MANDATORY PRE-COMMIT VALIDATION**

**🚨 CRITICAL RULE**: Before every commit and push to GitHub, ALWAYS validate your work based on complexity.

#### **Validation by Complexity - UPDATED RULES:**
- **DEFAULT**: Always start with **"think"** level validation as baseline
- **think**: Default level - basic review and testing + MANDATORY Gemini CLI validation
- **think hard**: Multi-step changes - check integrations and test coverage + MANDATORY Gemini CLI validation
- **think harder**: Complex changes - validate assumptions and end-to-end workflows + MANDATORY Gemini CLI validation
- **ultrathink**: Critical changes - comprehensive review of all potential impacts + MANDATORY Gemini CLI validation
- **ESCALATION RULE**: For critical problems, escalate validation one level higher
- **GEMINI PRINCIPLE**: Claude is smarter for code writing, Gemini handles big structures and massive token analysis

#### **Pre-Commit Process - UPDATED WITH MANDATORY GEMINI:**
1. **Review all changes made** - What files were modified and why?
2. **Check integration points** - Do the changes properly connect with existing systems?
3. **Validate assumptions** - Are there hidden dependencies or requirements we missed?
4. **Test end-to-end flows** - Do complete user workflows actually work?
5. **MANDATORY GEMINI CLI VALIDATION** - Use Gemini to analyze entire codebase for gaps, issues, and completeness
6. **Identify potential gaps** - What could we have overlooked? (Enhanced by Gemini analysis)
7. **Verify non-obvious connections** - Could this change affect seemingly unrelated functionality? (Gemini checks all files)

#### **Red Flags That Require Deeper Thinking - UPDATED WITH ESCALATION:**
- ✅ Changes to configuration systems (think hard → escalate to think harder if critical)
- ✅ Integration of multiple components (think hard → escalate to think harder if critical)
- ✅ Updates to core functionality (think hard → escalate to think harder if critical)
- ✅ Environment or deployment changes (think harder → escalate to ultrathink if critical)
- ✅ Cross-project modifications (think harder → escalate to ultrathink if critical)
- ✅ Complex refactoring tasks (think harder → escalate to ultrathink if critical)
- ✅ **ALL TASKS**: Start with "think" level, apply escalation rule for critical scenarios

3. **🏗️ CHECK & PLAN FOLDER STRUCTURE**
   - **BE FLEXIBLE**: Don't force exact folder structure from documentation
   - **USE EXISTING**: If there's a logical existing folder, use it
   - **CREATE WHEN NEEDED**: Only create new folders if absolutely necessary
   - **THINK LOGICALLY**: Place files where they make the most sense
   - **EXAMPLE**: If task says "create in `data_sources/` but there's already a `src/apis/` folder for API code, use `src/apis/`"

4. **💻 WRITE THE CODE**
   - **ALWAYS SHOW CODE FIRST**: Display the code you plan to write before implementing
   - **CRITICAL**: When using sequential thinking, user can't accept/reject - show code blocks clearly
   - **GET CONFIRMATION**: Ask user to confirm before proceeding with file edits
   - Follow the task requirements
   - Implement with proper error handling
   - Add comprehensive docstrings
   - Use type hints throughout

5. **🧪 TEST THE CODE**
   - Write unit tests for new functionality
   - Run existing tests to ensure no regressions
   - Test manually if needed
   - Ensure >80% test coverage
   - **🔄 MCP SERVER TESTING**: When testing MCP server changes, wait 10 seconds for user to restart server before testing tools

6. **📚 UPDATE DOCUMENTATION**
   - **ALWAYS update lol_data_mcp_server.md**

7. **🧠 VALIDATION & COMMIT - UPDATED WITH NEW RULES**
   - **DEFAULT LEVEL**: Start with "think" level validation for ALL tasks
   - **ESCALATION**: Apply escalation rule for critical/complex scenarios
   - **MANDATORY GEMINI**: Always use Gemini CLI for comprehensive codebase validation
   - **Check for**: Missing integrations, overlooked dependencies, false assumptions
   - **Validate**: That fixes actually work end-to-end, not just in isolation
   - **Gemini Analysis**: Let Gemini handle massive token analysis and structural checks

8. **🚀 COMMIT & PUSH TO GITHUB**
   - Stage all changes: `git add .`
   - Write descriptive commit message (NO CLAUDE ATTRIBUTION)
   - Push to GitHub: `git push origin master`
   - Verify the push was successful

**🚫 COMMIT MESSAGE RULES:**
- **DO NOT add Claude Code attribution**: No "🤖 Generated with [Claude Code]" text
- **DO NOT add Co-Authored-By**: No "Co-Authored-By: Claude <noreply@anthropic.com>" text  
- **Keep it clean**: Only include the actual commit message content
- **Use HEREDOC format** for multi-line messages without attribution:
```bash
git commit -m "$(cat <<'EOF'
✅ COMPLETED Task X.Y.Z: Brief Description

Detailed description of changes made.

Key features:
- Feature 1 description
- Feature 2 description
- Feature 3 description

Files created/modified:
- path/to/file1.py
- path/to/file2.py
EOF
)"
```

#### Example Task Development Flow:
```bash
# 1. Check the task (e.g., "Add champion data fetcher")
# 2. Plan: "This goes in data_sources/ or maybe existing src/apis/"
cd LoL_Data_MCP_Server
.\venv\Scripts\Activate.ps1

# 3. Check existing structure
ls src/
# Found: data_sources/ exists - use it!

# 4. Write code in src/data_sources/champion_fetcher.py
# 5. Write tests in tests/test_champion_fetcher.py
# 6. Update README.md and docs/architecture.md
# 7. Commit and push
git add .
git commit -m "Add champion data fetcher to data_sources module"
git push origin master
```

## 🏗️ ARCHITECTURE & IMPLEMENTATION

### Tech Stack & Dependencies
- **Core Framework**: FastAPI with WebSocket support for MCP protocol
- **Data Processing**: BeautifulSoup4 + lxml for HTML parsing
- **Browser Automation**: Selenium WebDriver for interactive scraping
- **Async Operations**: httpx for async HTTP requests
- **Data Validation**: Pydantic for type-safe data models
- **Configuration**: YAML-based configuration with environment support
- **Testing**: pytest with comprehensive coverage
- **Code Quality**: black, mypy, flake8, isort

### Data Sources
- **Primary**: League of Legends Wiki (wiki.leagueoflegends.com)
- **Planned**: Riot Games API integration, community data sources
- **Caching**: File-based caching with 24-hour TTL
- **Rate Limiting**: 1 request per second for responsible scraping

### MCP Tools Implemented
The server provides these MCP tools for IDE integration:
- `get_champion_stats` - Champion statistics with optional level parameter
- `get_champion_abilities` - Comprehensive ability details with enhanced mechanics
- `get_champion_patch_note` - Historical patch changes
- `ping` / `server_info` - Basic connectivity and status tools

### 📁 **FOLDER STRUCTURE FLEXIBILITY RULES**

#### Core Principle: **LOGICAL PLACEMENT OVER RIGID STRUCTURE**

1. **🔍 FIRST**: Check what folders already exist
2. **🤔 THINK**: Where does this logically belong?
3. **📂 USE**: Existing folders when they make sense
4. **📝 DOCUMENT**: Update README/docs when you make structural decisions

#### Common Flexibility Examples:
- **API clients** → Could go in `data_sources/`, `apis/`, or `clients/`
- **Utilities** → Could go in `utils/`, `helpers/`, or `common/`
- **Models** → Could go in `models/`, `schemas/`, or `data_models/`
- **Tests** → Always in `tests/` but mirror the source structure

#### When to Create New Folders:
- ✅ When existing folders don't make logical sense
- ✅ When you have 3+ related files that form a logical group
- ✅ When project documentation specifically requires it
- ❌ Don't create for 1-2 files that fit elsewhere

## 🎯 PROJECT PURPOSE & INTEGRATION

### Primary Purpose
Provide comprehensive, structured access to League of Legends game data through the Model Context Protocol, enabling:
- **Real-time champion statistics** with level-specific accuracy
- **Detailed ability mechanics** with enhanced game interaction data
- **Historical patch analysis** for meta evolution tracking
- **Training data generation** for AI/ML projects
- **IDE integration** for seamless development workflows

### Integration with Project Taric Ecosystem
- **Lol_Sim_Env** uses this server for accurate game data and mechanics
- **Taric_AI_Agent** leverages this for training data and real-time game information
- **External developers** can integrate via MCP protocol for LoL-related projects

### Future Expansion Areas
Based on comprehensive project plan in `docs/lol_data_mcp_server.md`:
- **Item data system** with fuzzy search and recipe trees
- **Runes system** integration for complete champion builds
- **Player analytics** and high-ELO demonstration data
- **Training data generation** for imitation learning
- **Simulation environment support** with complete game mechanics

## 🐍 **CODE STANDARDS**

### Python Requirements
- **Python 3.9+** required for modern type hints and async features
- **Type hints mandatory** - all functions and classes must have proper typing
- **Docstrings required** - comprehensive documentation for all public APIs
- **PEP 8 compliance** - enforced via black formatter
- **Async/await patterns** - all I/O operations must be non-blocking

### 🧪 **Testing Requirements**
- pytest framework across all projects
- Unit tests for core functionality
- Integration tests for cross-project dependencies
- Maintain >80% test coverage
- Mock external dependencies appropriately

### 📦 **Dependencies Management**
- Each project has its own requirements.txt
- Pin dependency versions for reproducibility
- Document cross-project version compatibility
- Regular dependency updates with testing

### 🚀 **Development Workflow Examples**

#### Working on MCP Server:
```bash
cd LoL_Data_MCP_Server
.\venv\Scripts\Activate.ps1  # Windows
# Verify: (venv) appears in prompt
# Now develop MCP server features
```

#### Working on Simulation Environment:
```bash
cd Lol_Sim_Env  
.\venv\Scripts\Activate.ps1  # Windows
# Verify: (venv) appears in prompt
# Now develop simulation features
```

#### Working on AI Agent:
```bash
cd Taric_AI_Agent
.\venv\Scripts\Activate.ps1  # Windows  
# Verify: (venv) appears in prompt
# Now develop agent features
```

### 🔍 **Code Quality Checklist - UPDATED WITH NEW RULES**
Before any commit to ANY project:
- [ ] **Correct virtual environment is active**
- [ ] **Currently in correct project directory**
- [ ] **Task analyzed and understood completely**
- [ ] **Applied "think" level as baseline (escalate if critical)**
- [ ] **Folder structure decision documented**
- [ ] Tests pass: `pytest`
- [ ] Code formatted: `black .`
- [ ] Type checking: `mypy .`
- [ ] Linting: `flake8 .`
- [ ] Import sorting: `isort .`
- [ ] **README.md updated** if structure changed
- [ ] **Relevant .md files updated** in docs/
- [ ] **🧠 THINKING LEVEL VALIDATION**: Applied appropriate thinking level with escalation rule
- [ ] **🔍 MANDATORY GEMINI CLI VALIDATION**: Used Gemini to analyze entire codebase
- [ ] **Committed and pushed to GitHub**

### 📚 **DOCUMENTATION UPDATE REQUIREMENTS**

#### Always Update When:
- ✅ **Folder structure changes** → Update README.md
- ✅ **New modules added** → Update architecture docs
- ✅ **API endpoints change** → Update API documentation  
- ✅ **Dependencies change** → Update requirements and docs
- ✅ **Configuration changes** → Update setup instructions

### 🔍 **GEMINI CLI FOR LARGE CODEBASE ANALYSIS**

When Claude Code's context window is insufficient for large-scale analysis, use the Gemini CLI with its massive context capacity.

#### **When to Use Gemini CLI:**
- Analyzing entire codebases or large directories
- Comparing multiple large files  
- Understanding project-wide patterns or architecture
- Working with files totaling more than 100KB
- Verifying if specific features, patterns, or security measures are implemented
- Checking for coding patterns across the entire codebase

#### **File and Directory Inclusion Syntax:**

Use the `@` syntax to include files and directories. Paths are relative to your current working directory:

```bash
# Single file analysis
gemini -p "@src/services/stats_service.py Explain this service's architecture"

# Multiple files
gemini -p "@pyproject.toml @requirements.txt Analyze the project dependencies"

# Entire directory
gemini -p "@src/ Summarize the MCP server architecture"

# Multiple directories
gemini -p "@src/ @tests/ Analyze test coverage for the source code"

# Current directory and subdirectories
gemini -p "@./ Give me an overview of this entire LoL MCP server project"

# Or use --all_files flag
gemini --all_files -p "Analyze the project structure and dependencies"
```

#### **Project-Specific Examples:**

```bash
# Check MCP implementation completeness
gemini -p "@src/mcp_server/ @src/services/ Are all MCP tools properly implemented? List missing functionality"

# Verify scraping implementation  
gemini -p "@src/data_sources/ @src/services/ Is web scraping properly implemented for all LoL data types?"

# Check error handling patterns
gemini -p "@src/ Is proper error handling implemented across all services? Show examples"

# Verify async patterns
gemini -p "@src/ Are async/await patterns consistently used? List any blocking operations"

# Check test coverage
gemini -p "@src/services/ @tests/ Is the champion stats service fully tested? List test gaps"

# Verify specific implementations
gemini -p "@src/ @config/ Is Redis caching implemented? List all cache-related functions"
```

#### **Important Notes:**
- Paths in `@` syntax are relative to your current working directory
- The CLI includes file contents directly in the context
- Gemini's context window can handle entire codebases that exceed Claude's limits
- Be specific about what you're looking for to get accurate results

### 🎯 **MAIN PROJECT: LoL Data MCP Server**

This project provides structured League of Legends data via the Model Context Protocol.

#### **Architecture Overview**:
- **`src/mcp_server/`**: MCP protocol implementation with FastAPI WebSocket server
- **`src/services/`**: Business logic for champion stats, abilities, and patch notes
- **`src/data_sources/scrapers/`**: Web scraping modules (BeautifulSoup + Selenium) 
- **`src/models/`**: Pydantic data models and exceptions
- **`src/core/`**: Configuration management and environment loading
- **`config/`**: YAML configuration files for different environments
- **`tests/`**: Unit tests with pytest

#### **Key Development Commands**:
```bash
# Activate virtual environment (ALWAYS FIRST)
.\venv\Scripts\Activate.ps1

# Testing
pytest                    # Run all tests
pytest tests/stats_test.py # Run specific test file  
pytest -v                 # Verbose output

# Code Quality
black .                   # Format code
mypy .                    # Type checking  
flake8 .                  # Linting
isort .                   # Import sorting

# MCP Server
python -m src.mcp_server.stdio_server  # Start MCP server
```

#### **Current Development Status**:
- **Phase**: Task 2.2 - Item data integration and MCP tools
- **Recently Completed**: Tasks 2.1.8-2.1.12 (per-level stats, abilities, patch history)
- **Focus**: Adding item data scraping and MCP tool integration

#### **Important Implementation Notes**:
- **Data Sources**: Primary source is League of Legends Wiki (wiki.leagueoflegends.com)
- **Selenium**: Chrome browser required for level-specific stats (takes ~8-10 seconds)
- **Async Patterns**: All I/O operations must use async/await
- **Error Handling**: All services have fallback mock data for development
- **Type Safety**: Strict typing with mypy validation required

### Error Handling & Reliability
- **Comprehensive error handling** - graceful degradation with fallback mock data
- **Selenium compatibility** - Chrome WebDriver required for level-specific stats
- **Network resilience** - retry logic with exponential backoff
- **Data validation** - Pydantic models ensure type safety and data integrity

## 🚨 **CRITICAL DEVELOPMENT RULES**

1. **Environment Management**: Always activate virtual environment for Python operations
2. **Code Quality**: Run all quality checks before committing (pytest, black, mypy, flake8)  
3. **Documentation**: Update `docs/lol_data_mcp_server.md` when making architectural changes
4. **Pattern Consistency**: Follow existing code patterns and service architectures
5. **Ask When Uncertain**: Clarify requirements before implementing major changes
6. **Large-Scale Analysis**: Use Gemini CLI when Claude Code's context is insufficient

### 📚 **Documentation References**
- **MCP Protocol**: https://spec.modelcontextprotocol.io/
- **LoL Wiki**: https://wiki.leagueoflegends.com/en-us/
- **Riot API**: https://developer.riotgames.com/
- **Gymnasium**: https://gymnasium.farama.org/
- **Stable-Baselines3**: https://stable-baselines3.readthedocs.io/