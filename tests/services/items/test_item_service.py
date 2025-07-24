"""
Unit tests for ItemService

Testing the ItemService functionality with mocked dependencies
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

from services.items.item_service import ItemService
from models.exceptions import ItemNotFoundError
from data_sources.scrapers.items.item_data_scraper import WikiScraperError


class TestItemService:
    """Comprehensive test suite for ItemService"""

    @pytest.fixture
    def mock_item_scraper(self):
        """Create a mock ItemDataScraper"""
        mock_scraper = AsyncMock()
        mock_scraper.close = AsyncMock()
        return mock_scraper

    @pytest.fixture
    def item_service_with_mock(self, mock_item_scraper):
        """Create ItemService with mocked scraper"""
        with patch('services.items.item_service.ItemDataScraper') as mock_scraper_class:
            mock_scraper_class.return_value = mock_item_scraper
            service = ItemService(enable_wiki=True, use_cache=True)
            return service, mock_item_scraper

    @pytest.fixture
    def item_service_disabled(self):
        """Create ItemService with wiki disabled"""
        return ItemService(enable_wiki=False, use_cache=False)

    def test_init_with_wiki_enabled(self, mock_item_scraper):
        """Test ItemService initialization with wiki enabled"""
        with patch('services.items.item_service.ItemDataScraper') as mock_scraper_class:
            mock_scraper_class.return_value = mock_item_scraper
            
            service = ItemService(enable_wiki=True, use_cache=True)
            
            assert service.enable_wiki is True
            assert service.item_scraper is mock_item_scraper
            mock_scraper_class.assert_called_once_with(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=True,
                cache_ttl_hours=24
            )

    def test_init_with_wiki_disabled(self):
        """Test ItemService initialization with wiki disabled"""
        service = ItemService(enable_wiki=False, use_cache=False)
        
        assert service.enable_wiki is False
        assert service.item_scraper is None

    def test_normalize_item_name(self, item_service_disabled):
        """Test item name normalization"""
        service = item_service_disabled
        
        # Test basic normalization
        assert service._normalize_item_name("echoes of helia") == "Echoes Of Helia"
        assert service._normalize_item_name("  kindlegem  ") == "Kindlegem"
        assert service._normalize_item_name("doran's blade") == "Doran'S Blade"
        
        # Test multiple spaces
        assert service._normalize_item_name("boots  of   speed") == "Boots Of Speed"
        
        # Test already normalized
        assert service._normalize_item_name("Locket Of The Iron Solari") == "Locket Of The Iron Solari"

    @pytest.mark.asyncio
    async def test_get_item_data_success(self, item_service_with_mock):
        """Test successful item data retrieval"""
        service, mock_scraper = item_service_with_mock
        
        # Mock successful scraper response
        mock_response = {
            "item_type": "completed",
            "data": {
                "stats": {"health": 450, "ability_power": 60},
                "recipe": {"components": ["Kindlegem", "Needlessly Large Rod"]},
                "cost_analysis": {"total_cost": 2500, "efficiency": 95.2}
            },
            "sections_available": ["stats", "recipe", "cost_analysis"],
            "data_source": "item_data_scraper",
            "url": "https://wiki.leagueoflegends.com/en-us/Echoes_of_Helia",
            "timestamp": "2024-12-01T10:00:00Z"
        }
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_item_data("Echoes of Helia")
        
        # Verify scraper was called correctly
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Echoes Of Helia",
            sections=None
        )
        
        # Verify response format
        assert result["name"] == "Echoes Of Helia"
        assert result["item_type"] == "completed"
        assert result["data"]["stats"]["health"] == 450
        assert result["sections_available"] == ["stats", "recipe", "cost_analysis"]
        assert result["data_source"] == "item_data_scraper"

    @pytest.mark.asyncio
    async def test_get_item_data_with_sections(self, item_service_with_mock):
        """Test item data retrieval with specific sections"""
        service, mock_scraper = item_service_with_mock
        
        mock_response = {
            "item_type": "basic",
            "data": {"stats": {"health": 200}},
            "sections_available": ["stats"],
            "data_source": "item_data_scraper"
        }
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_item_data("Kindlegem", sections=["stats"])
        
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Kindlegem",
            sections=["stats"]
        )
        
        assert result["name"] == "Kindlegem"
        assert result["item_type"] == "basic"

    @pytest.mark.asyncio
    async def test_get_item_data_wiki_disabled(self, item_service_disabled):
        """Test get_item_data when wiki is disabled"""
        service = item_service_disabled
        
        with pytest.raises(WikiScraperError, match="Wiki scraping is not enabled"):
            await service.get_item_data("Echoes of Helia")

    @pytest.mark.asyncio
    async def test_get_item_data_item_not_found(self, item_service_with_mock):
        """Test ItemNotFoundError when item doesn't exist"""
        service, mock_scraper = item_service_with_mock
        
        mock_scraper.scrape_item_data.side_effect = WikiScraperError("Item 'InvalidItem' not found (404)")
        
        with pytest.raises(ItemNotFoundError):
            await service.get_item_data("InvalidItem")

    @pytest.mark.asyncio
    async def test_get_item_data_general_wiki_error(self, item_service_with_mock):
        """Test WikiScraperError handling for general errors"""
        service, mock_scraper = item_service_with_mock
        
        mock_scraper.scrape_item_data.side_effect = WikiScraperError("Network timeout")
        
        with pytest.raises(WikiScraperError, match="Failed to retrieve item data"):
            await service.get_item_data("Echoes of Helia")

    @pytest.mark.asyncio
    async def test_get_item_data_value_error(self, item_service_with_mock):
        """Test ValueError handling"""
        service, mock_scraper = item_service_with_mock
        
        mock_scraper.scrape_item_data.side_effect = ValueError("Invalid parameter")
        
        with pytest.raises(ItemNotFoundError):
            await service.get_item_data("Echoes of Helia")

    @pytest.mark.asyncio
    async def test_get_item_stats(self, item_service_with_mock):
        """Test get_item_stats convenience method"""
        service, mock_scraper = item_service_with_mock
        
        mock_response = {"item_type": "completed", "data": {"stats": {"health": 450}}}
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_item_stats("Echoes of Helia")
        
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Echoes Of Helia",
            sections=["stats"]
        )
        assert result["data"]["stats"]["health"] == 450

    @pytest.mark.asyncio
    async def test_get_item_recipe(self, item_service_with_mock):
        """Test get_item_recipe convenience method"""
        service, mock_scraper = item_service_with_mock
        
        mock_response = {"item_type": "completed", "data": {"recipe": {"components": ["Kindlegem"]}}}
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_item_recipe("Echoes of Helia")
        
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Echoes Of Helia",
            sections=["recipe"]
        )
        assert result["data"]["recipe"]["components"] == ["Kindlegem"]

    @pytest.mark.asyncio
    async def test_get_item_cost_analysis(self, item_service_with_mock):
        """Test get_item_cost_analysis convenience method"""
        service, mock_scraper = item_service_with_mock
        
        mock_response = {"item_type": "completed", "data": {"cost_analysis": {"efficiency": 95.2}}}
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_item_cost_analysis("Echoes of Helia")
        
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Echoes Of Helia",
            sections=["cost_analysis"]
        )
        assert result["data"]["cost_analysis"]["efficiency"] == 95.2

    @pytest.mark.asyncio
    async def test_get_similar_items(self, item_service_with_mock):
        """Test get_similar_items convenience method"""
        service, mock_scraper = item_service_with_mock
        
        mock_response = {"item_type": "completed", "data": {"similar_items": ["Moonstone Renewer"]}}
        mock_scraper.scrape_item_data.return_value = mock_response
        
        result = await service.get_similar_items("Echoes of Helia")
        
        mock_scraper.scrape_item_data.assert_called_once_with(
            item_name="Echoes Of Helia",
            sections=["similar_items"]
        )
        assert result["data"]["similar_items"] == ["Moonstone Renewer"]

    def test_transform_item_data(self, item_service_disabled):
        """Test item data transformation"""
        service = item_service_disabled
        
        raw_data = {
            "item_type": "completed",
            "data": {"stats": {"health": 450}},
            "sections_available": ["stats"],
            "data_source": "item_data_scraper",
            "url": "https://wiki.leagueoflegends.com/en-us/Echoes_of_Helia",
            "timestamp": "2024-12-01T10:00:00Z"
        }
        
        result = service._transform_item_data(raw_data, "Echoes Of Helia")
        
        assert result["name"] == "Echoes Of Helia"
        assert result["item_type"] == "completed"
        assert result["data"]["stats"]["health"] == 450
        assert result["sections_available"] == ["stats"]
        assert result["data_source"] == "item_data_scraper"
        assert result["url"] == "https://wiki.leagueoflegends.com/en-us/Echoes_of_Helia"
        assert result["timestamp"] == "2024-12-01T10:00:00Z"

    def test_transform_item_data_missing_fields(self, item_service_disabled):
        """Test item data transformation with missing fields"""
        service = item_service_disabled
        
        raw_data = {"item_type": "basic"}
        
        result = service._transform_item_data(raw_data, "Kindlegem")
        
        assert result["name"] == "Kindlegem"
        assert result["item_type"] == "basic"
        assert result["data"] == {}
        assert result["sections_available"] == []
        assert result["data_source"] == "item_data_scraper"
        assert result["url"] is None
        assert result["timestamp"] is None

    @pytest.mark.asyncio
    async def test_cleanup(self, item_service_with_mock):
        """Test cleanup method"""
        service, mock_scraper = item_service_with_mock
        
        await service.cleanup()
        
        mock_scraper.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_wiki_disabled(self, item_service_disabled):
        """Test cleanup when wiki is disabled"""
        service = item_service_disabled
        
        # Should not raise any exceptions
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])