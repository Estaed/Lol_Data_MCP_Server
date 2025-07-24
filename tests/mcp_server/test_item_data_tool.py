"""
Integration tests for GetItemDataTool

Testing the MCP tool integration with ItemService
following the ultrathink approach for comprehensive validation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from mcp_server.tools import GetItemDataTool, MCPToolSchema
from services.items.item_service import ItemService
from models.exceptions import ItemNotFoundError
from data_sources.scrapers.items.item_data_scraper import WikiScraperError


class TestGetItemDataTool:
    """Comprehensive test suite for GetItemDataTool MCP integration"""

    @pytest.fixture
    def mock_item_service(self):
        """Create a mock ItemService"""
        mock_service = AsyncMock()
        return mock_service

    @pytest.fixture
    def item_data_tool(self, mock_item_service):
        """Create GetItemDataTool with mocked service"""
        return GetItemDataTool(item_service=mock_item_service)

    @pytest.fixture
    def item_data_tool_no_service(self):
        """Create GetItemDataTool without service injection"""
        return GetItemDataTool(item_service=None)

    def test_init(self, mock_item_service):
        """Test GetItemDataTool initialization"""
        tool = GetItemDataTool(item_service=mock_item_service)
        
        assert tool.name == "get_item_data"
        assert "comprehensive item data" in tool.description.lower()
        assert tool._item_service is mock_item_service

    def test_get_schema(self, item_data_tool):
        """Test GetItemDataTool schema generation"""
        schema = item_data_tool.get_schema()
        
        assert isinstance(schema, MCPToolSchema)
        assert schema.name == "get_item_data"
        assert "comprehensive item data" in schema.description.lower()
        
        # Verify input schema structure
        input_schema = schema.input_schema
        assert input_schema["type"] == "object"
        
        properties = input_schema["properties"]
        assert "item_name" in properties
        assert "sections" in properties
        
        # Verify item_name property
        item_name_prop = properties["item_name"]
        assert item_name_prop["type"] == "string"
        assert "name of the item" in item_name_prop["description"].lower()
        
        # Verify sections property
        sections_prop = properties["sections"]
        assert sections_prop["type"] == "array"
        assert sections_prop["items"]["type"] == "string"
        assert "optional list" in sections_prop["description"].lower()
        
        # Verify required fields
        assert input_schema["required"] == ["item_name"]
        assert input_schema["additionalProperties"] is False

    @pytest.mark.asyncio
    async def test_execute_success(self, item_data_tool, mock_item_service):
        """Test successful tool execution"""
        # Mock service response
        mock_response = {
            "name": "Echoes Of Helia",
            "item_type": "completed",
            "data": {
                "stats": {"health": 450, "ability_power": 60},
                "recipe": {"components": ["Kindlegem", "Needlessly Large Rod"]},
                "cost_analysis": {"total_cost": 2500, "efficiency": 95.2}
            },
            "sections_available": ["stats", "recipe", "cost_analysis"],
            "data_source": "item_data_scraper"
        }
        mock_item_service.get_item_data.return_value = mock_response
        
        params = {"item_name": "Echoes of Helia"}
        result = await item_data_tool.execute(params)
        
        # Verify service was called correctly
        mock_item_service.get_item_data.assert_called_once_with(
            item_name="Echoes of Helia",
            sections=None
        )
        
        # Verify response format (direct service result)
        assert result["name"] == "Echoes Of Helia"
        assert result["item_type"] == "completed"
        assert result["data"]["stats"]["health"] == 450

    @pytest.mark.asyncio
    async def test_execute_with_sections(self, item_data_tool, mock_item_service):
        """Test tool execution with specific sections"""
        mock_response = {
            "name": "Kindlegem",
            "item_type": "basic",
            "data": {"stats": {"health": 200}},
            "sections_available": ["stats"],
            "data_source": "item_data_scraper"
        }
        mock_item_service.get_item_data.return_value = mock_response
        
        params = {
            "item_name": "Kindlegem",
            "sections": ["stats", "recipe"]
        }
        result = await item_data_tool.execute(params)
        
        mock_item_service.get_item_data.assert_called_once_with(
            item_name="Kindlegem",
            sections=["stats", "recipe"]
        )
        
        assert result["name"] == "Kindlegem"
        assert result["item_type"] == "basic"

    @pytest.mark.asyncio
    async def test_execute_no_service(self, item_data_tool_no_service):
        """Test tool execution without service injection"""
        params = {"item_name": "Echoes of Helia"}
        
        with pytest.raises(RuntimeError, match="ItemService not properly injected"):
            await item_data_tool_no_service.execute(params)

    @pytest.mark.asyncio
    async def test_execute_empty_item_name(self, item_data_tool):
        """Test tool execution with empty item name"""
        params = {"item_name": ""}
        
        with pytest.raises(ValueError, match="item_name is required"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_missing_item_name(self, item_data_tool):
        """Test tool execution with missing item name"""
        params = {"sections": ["stats"]}
        
        with pytest.raises(ValueError, match="item_name is required"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_whitespace_item_name(self, item_data_tool):
        """Test tool execution with whitespace-only item name"""
        params = {"item_name": "   "}
        
        with pytest.raises(ValueError, match="item_name is required"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_item_not_found(self, item_data_tool, mock_item_service):
        """Test tool execution when item is not found"""
        mock_item_service.get_item_data.side_effect = ItemNotFoundError("InvalidItem")
        
        params = {"item_name": "InvalidItem"}
        
        with pytest.raises(ValueError, match="Error retrieving item data for InvalidItem"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_wiki_scraper_error(self, item_data_tool, mock_item_service):
        """Test tool execution with WikiScraperError"""
        mock_item_service.get_item_data.side_effect = WikiScraperError("Network timeout")
        
        params = {"item_name": "Echoes of Helia"}
        
        with pytest.raises(ValueError, match="Error retrieving item data for Echoes of Helia"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_general_exception(self, item_data_tool, mock_item_service):
        """Test tool execution with general exception"""
        mock_item_service.get_item_data.side_effect = Exception("Unexpected error")
        
        params = {"item_name": "Echoes of Helia"}
        
        with pytest.raises(ValueError, match="Error retrieving item data for Echoes of Helia"):
            await item_data_tool.execute(params)

    @pytest.mark.asyncio
    async def test_execute_special_characters(self, item_data_tool, mock_item_service):
        """Test tool execution with special characters in item name"""
        mock_response = {
            "name": "Doran'S Blade",
            "item_type": "basic",
            "data": {"stats": {"attack_damage": 8}},
            "sections_available": ["stats"],
            "data_source": "item_data_scraper"
        }
        mock_item_service.get_item_data.return_value = mock_response
        
        params = {"item_name": "Doran's Blade"}
        result = await item_data_tool.execute(params)
        
        mock_item_service.get_item_data.assert_called_once_with(
            item_name="Doran's Blade",
            sections=None
        )
        
        assert result["name"] == "Doran'S Blade"

    @pytest.mark.asyncio
    async def test_execute_empty_sections_list(self, item_data_tool, mock_item_service):
        """Test tool execution with empty sections list"""
        mock_response = {
            "name": "Echoes Of Helia",
            "item_type": "completed",
            "data": {},
            "sections_available": [],
            "data_source": "item_data_scraper"
        }
        mock_item_service.get_item_data.return_value = mock_response
        
        params = {
            "item_name": "Echoes of Helia",
            "sections": []
        }
        result = await item_data_tool.execute(params)
        
        mock_item_service.get_item_data.assert_called_once_with(
            item_name="Echoes of Helia",
            sections=[]
        )
        
        # Verify result is direct service response  
        assert "name" in result

    def test_name_and_description(self, item_data_tool):
        """Test tool name and description properties"""
        assert item_data_tool.name == "get_item_data"
        assert hasattr(item_data_tool, 'description')
        assert len(item_data_tool.description) > 0
        
        # Verify description contains key terms
        description_lower = item_data_tool.description.lower()
        assert "comprehensive" in description_lower
        assert "item data" in description_lower
        assert "differentiated" in description_lower


class TestGetItemDataToolIntegration:
    """Integration tests with real ItemService (mocked scraper)"""
    
    @pytest.mark.asyncio
    async def test_integration_with_real_service(self):
        """Test GetItemDataTool with real ItemService but mocked scraper"""
        # Create real ItemService with mocked scraper
        with patch('services.items.item_service.ItemDataScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper_class.return_value = mock_scraper
            
            # Mock scraper response
            mock_scraper.scrape_item_data.return_value = {
                "item_type": "completed",
                "data": {"stats": {"health": 450}},
                "sections_available": ["stats"],
                "data_source": "item_data_scraper"
            }
            
            # Create real service and tool
            item_service = ItemService(enable_wiki=True, use_cache=True)
            tool = GetItemDataTool(item_service=item_service)
            
            # Execute tool
            params = {"item_name": "Echoes of Helia"}
            result = await tool.execute(params)
            
            # Verify integration (direct service result)
            assert result["name"] == "Echoes Of Helia"
            assert result["item_type"] == "completed"
            
            # Cleanup
            await item_service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])