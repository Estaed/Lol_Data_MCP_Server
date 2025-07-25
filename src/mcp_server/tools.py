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


class GetChampionAbilitiesTool(MCPTool):
    """Tool for retrieving comprehensive champion abilities"""

    def __init__(self, abilities_service=None) -> None:
        super().__init__(
            name="get_champion_abilities",
            description="Retrieves comprehensive champion abilities. If an ability_slot is provided, it returns only that specific ability. If no ability_slot is provided, it returns all abilities.",
        )
        # Abilities service injected via dependency injection
        self._abilities_service = abilities_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion": {"type": "string", "description": "Champion name"},
                    "ability_slot": {
                        "type": "string",
                        "enum": ["Q", "W", "E", "R", "Passive"],
                        "description": "Optional specific ability slot (Q, W, E, R, Passive). If not provided, returns all abilities.",
                    },
                },
                "required": ["champion"],
            },
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute champion abilities retrieval using AbilitiesService"""
        if not self._abilities_service:
            raise RuntimeError("AbilitiesService not properly injected")
        
        champion = params.get("champion", "")
        ability_slot = params.get("ability_slot")
        
        # If specific ability requested, use enhanced details method
        if ability_slot:
            result = await self._abilities_service.get_ability_details(
                champion=champion,
                ability_slot=ability_slot
            )
            
            # Format response to maintain compatibility while providing enhanced details
            return {
                "champion": result.get("champion", champion),
                "data_source": result.get("data_source", "wiki_abilities_with_details"),
                "ability": result.get("ability_details", {}),
                "name": result.get("champion", champion)
            }
        else:
            # If no specific ability, get all abilities (existing behavior)
            result = await self._abilities_service.get_champion_abilities(
                champion=champion,
                ability_slot=None
            )
            
            if "name" in result:
                result["champion"] = result["name"]
            
            return result


class GetChampionPatchNoteTool(MCPTool):
    """Tool for retrieving champion patch notes from League of Legends Wiki"""

    def __init__(self, patch_note_service=None) -> None:
        super().__init__(
            name="get_champion_patch_note",
            description="Retrieves patch history for a champion. If no patch version is specified, returns all patch notes. If a specific patch version is provided, returns only that patch note."
        )
        self.patch_note_service = patch_note_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "champion_name": {
                        "type": "string",
                        "description": "Name of the champion to get patch notes for"
                    },
                    "patch_version": {
                        "type": "string",
                        "description": "Optional specific patch version (e.g., '4.12', '14.21'). If not provided, returns all patch notes."
                    }
                },
                "required": ["champion_name"],
                "additionalProperties": False
            }
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the get_champion_patch_note tool"""
        champion = params.get("champion_name", "").strip()
        patch_version = params.get("patch_version")
        
        if not champion:
            raise ValueError("champion_name is required")
        
        if not self.patch_note_service:
            raise ValueError("PatchNoteService not available")
        
        try:
            # Get patch notes data
            patch_data = await self.patch_note_service.get_champion_patch_notes(
                champion=champion,
                patch_version=patch_version
            )
            
            return {
                "success": True,
                "data": patch_data
            }
        except Exception as e:
            raise ValueError(f"Error retrieving patch notes for {champion}: {str(e)}")


class GetItemPatchNoteTool(MCPTool):
    """Tool for retrieving item patch notes from League of Legends Wiki"""

    def __init__(self, item_patch_service=None) -> None:
        super().__init__(
            name="get_item_patch_note",
            description="Retrieves patch history for an item. If no patch version is specified, returns all patch notes. If a specific patch version is provided, returns only that patch note."
        )
        self.item_patch_service = item_patch_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to get patch notes for (e.g., 'Echoes of Helia')"
                    },
                    "patch_version": {
                        "type": "string",
                        "description": "Optional specific patch version (e.g., '14.19', 'V14.19'). If not provided, returns all patch notes."
                    }
                },
                "required": ["item_name"],
                "additionalProperties": False
            }
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the get_item_patch_note tool"""
        item_name = params.get("item_name", "").strip()
        patch_version = params.get("patch_version")
        
        if not item_name:
            raise ValueError("item_name is required")
        
        if not self.item_patch_service:
            raise ValueError("ItemPatchService not available")
        
        try:
            # Get patch notes data directly from ItemPatchService
            patch_data = await self.item_patch_service.get_item_patch_notes(
                item=item_name,
                patch_version=patch_version
            )
            
            return patch_data
        except Exception as e:
            raise ValueError(f"Error retrieving patch notes for {item_name}: {str(e)}")


class GetItemDataTool(MCPTool):
    """Tool for retrieving comprehensive item data with differentiated extraction"""

    def __init__(self, item_service=None) -> None:
        super().__init__(
            name="get_item_data",
            description="Retrieves comprehensive item data including stats, recipe, cost analysis, notes, and similar items. Returns differentiated data based on item type (completed vs basic/epic items)."
        )
        self._item_service = item_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to get data for (e.g., 'Echoes of Helia', 'Kindlegem')"
                    },
                    "sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of specific sections to extract (e.g., ['stats', 'recipe', 'cost_analysis']). If not provided, returns all available sections."
                    }
                },
                "required": ["item_name"],
                "additionalProperties": False
            }
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute item data retrieval using ItemService"""
        if not self._item_service:
            raise RuntimeError("ItemService not properly injected")
        
        item_name = params.get("item_name", "").strip()
        sections = params.get("sections")
        
        if not item_name:
            raise ValueError("item_name is required")
        
        try:
            result = await self._item_service.get_item_data(
                item_name=item_name,
                sections=sections
            )
            
            return result
        except Exception as e:
            raise ValueError(f"Error retrieving item data for {item_name}: {str(e)}")


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


class GetRuneDataTool(MCPTool):
    """Tool for retrieving comprehensive rune data including sidebar, notes, and strategy"""

    def __init__(self, rune_service=None) -> None:
        super().__init__(
            name="get_rune_data",
            description="Retrieves comprehensive rune data including sidebar information, notes, and strategy sections."
        )
        self._rune_service = rune_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "rune_name": {
                        "type": "string",
                        "description": "Name of the rune to get data for (e.g., 'Summon Aery', 'Arcane Comet')"
                    },
                    "sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of specific sections to extract (e.g., ['sidebar', 'notes', 'strategy']). If not provided, returns all available sections."
                    }
                },
                "required": ["rune_name"],
                "additionalProperties": False
            }
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute rune data retrieval using RuneService"""
        if not self._rune_service:
            raise RuntimeError("RuneService not properly injected")
        
        rune_name = params.get("rune_name", "").strip()
        sections = params.get("sections")
        
        if not rune_name:
            raise ValueError("rune_name is required")
        
        try:
            result = await self._rune_service.get_rune_data(
                rune_name=rune_name,
                sections=sections
            )
            
            return result
        except Exception as e:
            raise ValueError(f"Error retrieving rune data for {rune_name}: {str(e)}")


class GetRunePatchNoteTool(MCPTool):
    """Tool for retrieving rune patch notes from League of Legends Wiki"""

    def __init__(self, rune_patch_service=None) -> None:
        super().__init__(
            name="get_rune_patch_note",
            description="Retrieves patch history for a rune. If no patch version is specified, returns all patch notes. If a specific patch version is provided, returns only that patch note."
        )
        self.rune_patch_service = rune_patch_service

    def get_schema(self) -> MCPToolSchema:
        return MCPToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "rune_name": {
                        "type": "string",
                        "description": "Name of the rune to get patch notes for (e.g., 'Summon Aery')"
                    },
                    "patch_version": {
                        "type": "string",
                        "description": "Optional specific patch version (e.g., '14.19', 'V14.19'). If not provided, returns all patch notes."
                    }
                },
                "required": ["rune_name"],
                "additionalProperties": False
            }
        )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the get_rune_patch_note tool"""
        rune_name = params.get("rune_name", "").strip()
        patch_version = params.get("patch_version")
        
        if not rune_name:
            raise ValueError("rune_name is required")
        
        if not self.rune_patch_service:
            raise ValueError("RunePatchService not available")
        
        try:
            # Get patch notes data directly from RunePatchService
            patch_data = await self.rune_patch_service.get_rune_patch_notes(
                rune_name=rune_name,
                patch_version=patch_version
            )
            
            return patch_data
        except Exception as e:
            raise ValueError(f"Error retrieving patch notes for {rune_name}: {str(e)}")


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
        
        # Delay service imports to avoid circular import
        try:
            from src.services.champions.stats_service import StatsService
            from src.services.champions.abilities_service import AbilitiesService
            from src.services.champions.patch_note_service import PatchNoteService
            from src.services.items.item_patch_service import ItemPatchService
            from src.services.items.item_service import ItemService
            from src.services.runes.rune_service import RuneService
            from src.services.runes.rune_patch_service import RunePatchService
            
            stats_service = StatsService()
            abilities_service = AbilitiesService()
            patch_note_service = PatchNoteService()
            item_patch_service = ItemPatchService()
            item_service = ItemService()
            rune_service = RuneService()
            rune_patch_service = RunePatchService()
            
            # Register all LoL tools with injected services (following champion pattern)
            self.register_tool(GetChampionStatsTool(stats_service))
            self.register_tool(GetChampionAbilitiesTool(abilities_service))
            self.register_tool(GetChampionPatchNoteTool(patch_note_service))
            self.register_tool(GetItemPatchNoteTool(item_patch_service))
            self.register_tool(GetItemDataTool(item_service))
            self.register_tool(GetRuneDataTool(rune_service))
            self.register_tool(GetRunePatchNoteTool(rune_patch_service))
        except Exception as e:
            # Broaden exception handling to catch any error during startup
            print(f"CRITICAL WARNING: Could not import and register services: {e}")
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
