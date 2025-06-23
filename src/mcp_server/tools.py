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


class ChampionRole(str, Enum):
    """Valid champion roles"""

    TOP = "top"
    JUNGLE = "jungle"
    MID = "mid"
    ADC = "adc"
    SUPPORT = "support"


class RankTier(str, Enum):
    """Valid rank tiers for meta data"""

    ALL = "all"
    DIAMOND_PLUS = "diamond+"
    MASTER_PLUS = "master+"


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


class GetItemDataInput(BaseModel):
    """Input schema for get_item_data tool"""

    item: str = Field(..., description="Item name or ID")
    include: List[str] = Field(
        default=["stats", "cost"], description="Data sections to include"
    )

    @field_validator("include")
    @classmethod
    def validate_include_options(cls, v: List[str]) -> List[str]:
        valid_options = {"stats", "components", "passive", "cost"}
        invalid = set(v) - valid_options
        if invalid:
            raise ValueError(f"Invalid include options: {invalid}")
        return v


class SearchChampionsInput(BaseModel):
    """Input schema for search_champions tool"""

    query: Optional[str] = Field(None, description="Search query")
    role: Optional[ChampionRole] = Field(None, description="Champion role filter")
    tags: Optional[List[str]] = Field(None, description="Champion tags filter")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")


class GetMetaBuildsInput(BaseModel):
    """Input schema for get_meta_builds tool"""

    champion: str = Field(..., description="Champion name")
    role: Optional[str] = Field(None, description="Champion role")
    rank: RankTier = Field(RankTier.ALL, description="Rank tier for statistics")
    patch: str = Field("current", description="Game patch version")


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
        """Execute ability details retrieval with direct mock data"""
        validated_params = GetAbilityDetailsInput(**params)
        
        # Direct mock data to avoid import issues
        champion_abilities = {
            "taric": {
                "passive": {
                    "name": "Bravado",
                    "description": "Taric's spells grant him and his Bastion charges that enhance his next two basic attacks to deal bonus magic damage, reduce his basic ability cooldowns, and grant him and his Bastion charges of Bravado.",
                    "cooldown": "N/A",
                    "cost": "N/A",
                    "range": "N/A",
                    "effect": "Enhanced basic attacks reduce cooldowns and grant charges"
                },
                "q": {
                    "name": "Starlight's Touch",
                    "description": "Taric heals himself and his Bastion. Healing is increased based on charges of Bravado consumed.",
                    "cooldown": "14/13/12/11/10 seconds",
                    "cost": "60/65/70/75/80 mana + 3 charges",
                    "range": "Self/Bastion",
                    "effect": "Heals self and Bastion, enhanced by Bravado charges"
                },
                "w": {
                    "name": "Bastion",
                    "description": "Taric shields himself and links to an ally champion. Linked allies gain Bastion passive and are healed by Taric's abilities.",
                    "cooldown": "20/18/16/14/12 seconds",
                    "cost": "60 mana",
                    "range": "800",
                    "effect": "Links to ally, shares abilities and provides passive benefits"
                },
                "e": {
                    "name": "Dazzle",
                    "description": "Taric shoots out a beam of starlight that damages and stuns enemies. The stun duration increases with range.",
                    "cooldown": "13/12/11/10/9 seconds",
                    "cost": "60 mana",
                    "range": "575",
                    "effect": "Stuns enemies, duration increases with distance"
                },
                "r": {
                    "name": "Cosmic Radiance",
                    "description": "After a delay, Taric and his Bastion become invulnerable for a short duration.",
                    "cooldown": "160/120/80 seconds",
                    "cost": "100 mana",
                    "range": "Self/Bastion",
                    "effect": "Grants invulnerability after delay to self and Bastion"
                }
            },
            "ezreal": {
                "passive": {
                    "name": "Rising Spell Force",
                    "description": "Hitting enemies with abilities grants attack speed.",
                    "cooldown": "N/A",
                    "cost": "N/A",
                    "range": "N/A",
                    "effect": "Attack speed buff when hitting abilities"
                },
                "q": {
                    "name": "Mystic Shot",
                    "description": "Fires a projectile that deals damage and reduces cooldowns on hit.",
                    "cooldown": "6.5/6/5.5/5/4.5 seconds",
                    "cost": "28/31/34/37/40 mana",
                    "range": "1150",
                    "effect": "Skillshot that reduces cooldowns on hit"
                },
                "w": {
                    "name": "Essence Flux",
                    "description": "Fires an orb that damages enemies and marks them.",
                    "cooldown": "12/11/10/9/8 seconds",
                    "cost": "50/60/70/80/90 mana",
                    "range": "1000",
                    "effect": "Marks enemies for additional damage"
                },
                "e": {
                    "name": "Arcane Shift",
                    "description": "Teleports to target location and fires a homing bolt.",
                    "cooldown": "25/22/19/16/13 seconds",
                    "cost": "90 mana",
                    "range": "475",
                    "effect": "Blink ability with damage component"
                },
                "r": {
                    "name": "Trueshot Barrage",
                    "description": "Fires a global skillshot that damages all enemies hit.",
                    "cooldown": "120/105/90 seconds",
                    "cost": "100 mana",
                    "range": "Global",
                    "effect": "Global skillshot with decreasing damage"
                }
            }
        }
        
        # Get ability details
        champion_key = validated_params.champion.lower()
        ability_key = validated_params.ability.value.lower()
        
        ability_details = {}
        if champion_key in champion_abilities and ability_key in champion_abilities[champion_key]:
            ability_details = champion_abilities[champion_key][ability_key]
            
        return {
            "champion": validated_params.champion,
            "ability": validated_params.ability.value,
            "level": validated_params.level,
            "scaling_included": validated_params.include_scaling,
            "details": ability_details
        }


class GetItemDataTool(MCPTool):
    """Tool for retrieving item information and statistics"""

    def __init__(self) -> None:
        super().__init__(
            name="get_item_data",
            description="Get item information including stats, components, and cost efficiency",
        )

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Item name or ID"},
                    "include": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["stats", "components", "passive", "cost"],
                        },
                        "default": ["stats", "cost"],
                        "description": "Data sections to include",
                    },
                },
                "required": ["item"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute item data retrieval"""
        validated_params = GetItemDataInput(**params)

        # TODO: Implement actual item data retrieval
        return {
            "item": validated_params.item,
            "data_included": validated_params.include,
            "stats": {} if "stats" in validated_params.include else None,
            "components": {} if "components" in validated_params.include else None,
            "passive": {} if "passive" in validated_params.include else None,
            "cost": {} if "cost" in validated_params.include else None,
        }


class SearchChampionsTool(MCPTool):
    """Tool for searching champions by various criteria"""

    def __init__(self) -> None:
        super().__init__(
            name="search_champions",
            description="Search champions by name, role, tags, or other criteria",
        )

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for champion name or description",
                    },
                    "role": {
                        "type": "string",
                        "enum": ["top", "jungle", "mid", "adc", "support"],
                        "description": "Champion role filter",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Champion tags filter",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum results to return",
                    },
                },
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute champion search"""
        validated_params = SearchChampionsInput(**params)

        # TODO: Implement actual search logic
        return {
            "query": validated_params.query,
            "filters": {
                "role": validated_params.role.value if validated_params.role else None,
                "tags": validated_params.tags,
            },
            "limit": validated_params.limit,
            "results": [],  # Will contain actual search results
        }


class GetMetaBuildsTool(MCPTool):
    """Tool for retrieving current meta builds and statistics"""

    def __init__(self) -> None:
        super().__init__(
            name="get_meta_builds",
            description="Get current meta builds, skill orders, and win rate statistics",
        )

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion": {"type": "string", "description": "Champion name"},
                    "role": {
                        "type": "string",
                        "description": "Champion role for role-specific builds",
                    },
                    "rank": {
                        "type": "string",
                        "enum": ["all", "diamond+", "master+"],
                        "default": "all",
                        "description": "Rank tier for statistics",
                    },
                    "patch": {
                        "type": "string",
                        "default": "current",
                        "description": "Game patch version",
                    },
                },
                "required": ["champion"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute meta builds retrieval"""
        validated_params = GetMetaBuildsInput(**params)

        # TODO: Implement actual meta data retrieval
        return {
            "champion": validated_params.champion,
            "role": validated_params.role,
            "rank": validated_params.rank.value,
            "patch": validated_params.patch,
            "builds": [],  # Will contain actual build data
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
        self.register_tool(GetItemDataTool())
        self.register_tool(SearchChampionsTool())
        self.register_tool(GetMetaBuildsTool())

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
