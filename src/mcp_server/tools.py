"""
MCP Tool Schemas for League of Legends Data Server

This module defines the MCP tools with their input/output schemas for providing
League of Legends game data through the Model Context Protocol.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class MCPToolSchema(BaseModel):
    """Base schema for MCP tool definitions"""

    name: str
    description: str
    input_schema: Dict[str, Any]

    class Config:
        extra = "forbid"


class MCPTool(ABC):
    """Base class for all MCP tools with schema validation"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def get_schema(self) -> MCPToolSchema:
        """Return the tool's schema definition"""
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with validated parameters"""
        pass

    def validate_input(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input parameters against schema"""
        # This will be implemented with pydantic validation
        return params


# Input Models for Tool Validation
# GetChampionDataInput is now imported from champion_service to avoid circular imports


# GetChampionStatsAtLevelInput removed - functionality consolidated into GetChampionDataInput


# Tool Implementations


class GetChampionStatsTool(MCPTool):
    """Tool for retrieving comprehensive champion statistics"""

    def __init__(self, stats_service=None) -> None:
        super().__init__(
            name="get_champion_stats",
            description="Retrieves comprehensive champion statistics. If a level is provided, it returns the stats for that specific level. If no level is provided, it returns the base stats.",
        )
        # Stats service injected via dependency injection
        self._stats_service = stats_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion": {"type": "string", "description": "Champion name"},
                    "level": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 18,
                        "description": "Optional specific level for stats (1-18). If not provided, returns base stats.",
                    },
                },
                "required": ["champion"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute champion stats retrieval using StatsService"""
        if not self._stats_service:
            raise RuntimeError("StatsService not properly injected")
        
        result = await self._stats_service.get_champion_stats(
            champion=params.get("champion", ""),
            level=params.get("level")
        )
        
        if "name" in result:
            result["champion"] = result["name"]
        
        return result


# GetChampionStatsAtLevelTool removed - functionality consolidated into GetChampionDataTool


class PingTool(MCPTool):
    """Basic ping tool for health checking"""
    
    def __init__(self) -> None:
        super().__init__(
            name="ping",
            description="Test connectivity and server response",
        )

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "default": "ping",
                        "description": "Optional message to echo back",
                    }
                },
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ping operation"""
        message = params.get("message", "ping")
        return {
            "status": "pong",
            "message": message,
            "timestamp": "2024-12-01T10:00:00Z"
        }


class ServerInfoTool(MCPTool):
    """Tool for getting server information and status"""
    
    def __init__(self) -> None:
        super().__init__(
            name="server_info",
            description="Get server information and status",
        )

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={"type": "object", "properties": {}},
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute server info retrieval"""
        return {
            "name": "lol-data-mcp-server",
            "version": "1.0.0",
            "status": "running",
            "tools_count": len(tool_registry.get_tool_names()),
            "description": "MCP server for League of Legends champion data",
        }


class ToolRegistry:
    """Central registry for all MCP tools"""

    def __init__(self) -> None:
        self.tools: Dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools"""
        # Register basic tools first (no dependencies)
        self.register_tool(PingTool())
        self.register_tool(ServerInfoTool())
        
        # Delay StatsService import to avoid circular import
        try:
            from src.services.stats_service import StatsService
            stats_service = StatsService()
            
            # Register all LoL tools with injected StatsService
            self.register_tool(GetChampionStatsTool(stats_service))
        except Exception as e:
            # Broaden exception handling to catch any error during startup
            print(f"CRITICAL WARNING: Could not import and register StatsService: {e}")
            print("Only basic tools (ping, server_info) will be available")
            import traceback
            traceback.print_exc()

    def register_tool(self, tool: MCPTool) -> None:
        """Register a new tool"""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list_tools(self) -> List[MCPToolSchema]:
        """Get schemas for all registered tools"""
        return [tool.get_schema() for tool in self.tools.values()]

    def get_tool_names(self) -> List[str]:
        """Get list of all tool names"""
        return list(self.tools.keys())

    async def execute_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with parameters"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        return await tool.execute(params)


# Global tool registry instance
tool_registry = ToolRegistry()
