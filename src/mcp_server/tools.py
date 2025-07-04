"""
MCP Tool Schemas for League of Legends Data Server

This module defines the MCP tools with their input/output schemas for providing
League of Legends game data through the Model Context Protocol.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AbilityType(str, Enum):
    """Valid ability types for champions"""

    PASSIVE = "passive"
    Q = "Q"
    W = "W"
    E = "E"
    R = "R"


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


class GetAbilityDetailsInput(BaseModel):
    """Input schema for get_ability_details tool"""

    champion: str = Field(..., description="Champion name")
    ability: AbilityType = Field(..., description="Ability slot")
    level: Optional[int] = Field(
        None, ge=1, le=18, description="Champion level for scaling calculations"
    )
    include_scaling: bool = Field(True, description="Include scaling information")


class GetChampionStatsAtLevelInput(BaseModel):
    """Input schema for get_champion_stats_at_level tool"""
    
    champion: str = Field(..., description="Champion name")
    level: int = Field(..., ge=1, le=18, description="Champion level (1-18)")
    include_progression: bool = Field(False, description="Include stats for all levels 1-18")


# Tool Implementations


class GetChampionDataTool(MCPTool):
    """Tool for retrieving comprehensive champion information"""

    def __init__(self, champion_service=None) -> None:
        super().__init__(
            name="get_champion_data",
            description="Get comprehensive champion information including stats, abilities, and builds",
        )
        # Champion service injected via dependency injection
        self._champion_service = champion_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion": {"type": "string", "description": "Champion name"},
                    "patch": {
                        "type": "string",
                        "default": "current",
                        "description": "Game patch version",
                    },
                    "include": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["stats", "abilities", "builds", "history"],
                        },
                        "default": ["stats", "abilities"],
                        "description": "Data sections to include",
                    },
                },
                "required": ["champion"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute champion data retrieval using ChampionService"""
        # Use the injected champion service to get actual data
        if not self._champion_service:
            raise RuntimeError("ChampionService not properly injected")
        
        result = await self._champion_service.get_champion_data(
            champion=params.get("champion", ""),
            patch=params.get("patch", "current"),
            include=params.get("include", ["stats", "abilities"])
        )
        
        # Transform the service response to match the expected API
        # The service returns "name" but the API should return "champion" for consistency
        if "name" in result:
            result["champion"] = result["name"]
            # Keep both for backwards compatibility during development
        
        return result


class GetAbilityDetailsTool(MCPTool):
    """Tool for retrieving detailed ability information"""

    def __init__(self, champion_service=None) -> None:
        super().__init__(
            name="get_ability_details",
            description="Get detailed ability information including damage, cooldowns, and scaling",
        )
        # Champion service injected via dependency injection
        self._champion_service = champion_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion": {"type": "string", "description": "Champion name"},
                    "ability": {
                        "type": "string",
                        "enum": ["passive", "Q", "W", "E", "R"],
                        "description": "Ability slot",
                    },
                    "level": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 18,
                        "description": "Champion level for scaling calculations",
                    },
                    "include_scaling": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include scaling information",
                    },
                },
                "required": ["champion", "ability"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ability details retrieval using WikiScraper-enabled ChampionService"""
        validated_params = GetAbilityDetailsInput(**params)
        
        try:
            # Use the injected champion service to get actual data
            if not self._champion_service:
                raise RuntimeError("ChampionService not properly injected")
            
            champion_data = await self._champion_service.get_champion_data(
                champion=validated_params.champion,
                include=["abilities"]  # Only need abilities for this tool
            )
            
            # Extract the specific ability from champion data
            abilities = champion_data.get("abilities", {})
            ability_key = validated_params.ability.value.lower()
            ability_details = abilities.get(ability_key, {})
            
            # Return in the same format as before
            return {
                "champion": validated_params.champion,
                "ability": validated_params.ability.value,
                "level": validated_params.level,
                "scaling_included": validated_params.include_scaling,
                "details": ability_details
            }
            
        except Exception as e:
            # Proper error handling for wiki scraping failures and invalid champions
            return {
                "champion": validated_params.champion,
                "ability": validated_params.ability.value,
                "level": validated_params.level,
                "scaling_included": validated_params.include_scaling,
                "error": f"Failed to retrieve ability data: {str(e)}",
                "details": {}
            }


class GetChampionStatsAtLevelTool(MCPTool):
    """Tool for calculating champion stats at a specific level using stat formulas"""
    
    def __init__(self, champion_service=None) -> None:
        super().__init__(
            name="get_champion_stats_at_level",
            description="Calculate champion stats at a specific level using stat formulas",
        )
        # Champion service injected via dependency injection
        self._champion_service = champion_service

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
                        "description": "Champion level (1-18)"
                    },
                    "include_progression": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include stats for all levels 1-18"
                    }
                },
                "required": ["champion", "level"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute level-specific stat calculation"""
        try:
            # Use the injected champion service
            if not self._champion_service:
                raise RuntimeError("ChampionService not properly injected")
            
            champion_name = params.get("champion", "")
            level = params.get("level", 1)
            include_progression = params.get("include_progression", False)
            
            # First get the champion data to populate formulas
            champion_data = await self._champion_service.get_champion_data(
                champion=champion_name,
                include=["stats"]
            )
            
            if not champion_data or "stats" not in champion_data:
                return {"error": f"Could not retrieve stats for champion '{champion_name}'"}
            
            # Calculate stats at the specified level
            level_stats = self._champion_service.calculate_stats_at_level(level)
            
            result = {
                "champion": champion_name,
                "level": level,
                "stats": level_stats.dict() if level_stats else None
            }
            
            # Include progression if requested
            if include_progression:
                progression = self._champion_service.get_stat_progression(1, 18)
                result["progression"] = {
                    str(lvl): stats.dict() for lvl, stats in progression.items()
                }
            
            return result
            
        except ValueError as e:
            return {"error": f"Invalid level: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to calculate champion stats: {str(e)}"}


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
            input_schema={
                "type": "object",
                "properties": {
                    "random_string": {
                        "type": "string",
                        "description": "Dummy parameter for no-parameter tools",
                    }
                },
                "required": ["random_string"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute server info retrieval"""
        return {
            "name": "lol-data-mcp-server",
            "version": "1.0.0",
            "status": "running",
            "tools_count": 5,
            "description": "MCP server for League of Legends champion data"
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
        
        # Delay ChampionService import to avoid circular import
        try:
            from src.services.champion_service import ChampionService
            champion_service = ChampionService()
            
            # Register all LoL tools with injected ChampionService
            self.register_tool(GetChampionDataTool(champion_service))
            self.register_tool(GetAbilityDetailsTool(champion_service))
            self.register_tool(GetChampionStatsAtLevelTool(champion_service))
        except ImportError as e:
            # Log the error but continue with basic tools
            print(f"Warning: Could not import ChampionService: {e}")
            print("Only basic tools (ping, server_info) will be available")

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
