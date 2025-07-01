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


class GetChampionDataInput(BaseModel):
    """Input schema for get_champion_data tool"""

    champion: str = Field(..., description="Champion name")
    patch: str = Field("current", description="Game patch version")
    include: List[str] = Field(
        default=["stats", "abilities"], description="Data sections to include"
    )

    @field_validator("include")
    @classmethod
    def validate_include_options(cls, v: List[str]) -> List[str]:
        valid_options = {"stats", "abilities", "builds", "history"}
        invalid = set(v) - valid_options
        if invalid:
            raise ValueError(f"Invalid include options: {invalid}")
        return v


class GetAbilityDetailsInput(BaseModel):
    """Input schema for get_ability_details tool"""

    champion: str = Field(..., description="Champion name")
    ability: AbilityType = Field(..., description="Ability slot")
    level: Optional[int] = Field(
        None, ge=1, le=18, description="Champion level for scaling calculations"
    )
    include_scaling: bool = Field(True, description="Include scaling information")


# Tool Implementations


class GetChampionDataTool(MCPTool):
    """Tool for retrieving comprehensive champion information"""

    def __init__(self) -> None:
        super().__init__(
            name="get_champion_data",
            description="Get comprehensive champion information including stats, abilities, and builds",
        )
        # Champion service will be initialized lazily to avoid circular imports
        self._champion_service = None
    
    def _get_champion_service(self):
        """Lazy initialization of champion service to avoid circular imports"""
        if self._champion_service is None:
            from src.services.champion_service import ChampionService
            self._champion_service = ChampionService()
        return self._champion_service

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
        # Use the champion service to get actual data
        champion_service = self._get_champion_service()
        result = await champion_service.get_champion_data(
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

    def __init__(self) -> None:
        super().__init__(
            name="get_ability_details",
            description="Get detailed ability information including damage, cooldowns, and scaling",
        )
        # Champion service will be initialized lazily to avoid circular imports
        self._champion_service = None
    
    def _get_champion_service(self):
        """Lazy initialization of champion service to avoid circular imports"""
        if self._champion_service is None:
            from src.services.champion_service import ChampionService
            self._champion_service = ChampionService()
        return self._champion_service

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
            # Use WikiScraper-enabled ChampionService instead of hardcoded data
            champion_service = self._get_champion_service()
            champion_data = await champion_service.get_champion_data(
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


class ToolRegistry:
    """Central registry for all MCP tools"""

    def __init__(self) -> None:
        self.tools: Dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools"""
        # Register all LoL tools
        self.register_tool(GetChampionDataTool())
        self.register_tool(GetAbilityDetailsTool())

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
