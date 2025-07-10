"""
Tests for AbilitiesService

This module contains unit tests for the champion abilities service functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.abilities_service import AbilitiesService
from src.models.exceptions import ChampionNotFoundError
from src.data_sources.scrapers.base_scraper import WikiScraperError


class TestAbilitiesService:
    """Test cases for AbilitiesService"""

    @pytest.fixture
    def abilities_service(self):
        """Create AbilitiesService instance for testing"""
        return AbilitiesService(enable_wiki=False)

    @pytest.fixture
    def abilities_service_with_wiki(self):
        """Create AbilitiesService with wiki enabled for testing"""
        return AbilitiesService(enable_wiki=True, use_cache=False)

    @pytest.fixture
    def mock_abilities_data(self):
        """Mock abilities data for testing"""
        return {
            "abilities": {
                "Passive": {
                    "name": "Bravado",
                    "description": "Taric's next basic attack gains bonus range and deals bonus magic damage.",
                    "cooldown": None,
                    "cost": None,
                    "range": None
                },
                "Q": {
                    "name": "Starlight's Touch", 
                    "description": "Taric heals himself and nearby allied champions.",
                    "cooldown": "14/13/12/11/10",
                    "cost": "60/70/80/90/100",
                    "range": "750"
                },
                "W": {
                    "name": "Bastion",
                    "description": "Taric shields himself and linked ally.",
                    "cooldown": "18/17/16/15/14",
                    "cost": "60",
                    "range": "800"
                },
                "E": {
                    "name": "Dazzle",
                    "description": "Taric fires a beam that stuns enemies.",
                    "cooldown": "15/14/13/12/11",
                    "cost": "60/65/70/75/80",
                    "range": "575"
                },
                "R": {
                    "name": "Cosmic Radiance",
                    "description": "After a delay, Taric and nearby allies become invulnerable.",
                    "cooldown": "160/135/110",
                    "cost": "100",
                    "range": "400",
                    "cast_time": "2.5"
                }
            },
            "data_source": "wiki_abilities_scrape"
        }

    def test_service_initialization_wiki_disabled(self, abilities_service):
        """Test AbilitiesService initialization with wiki disabled"""
        assert abilities_service.enable_wiki is False
        assert abilities_service.abilities_scraper is None

    def test_service_initialization_wiki_enabled(self, abilities_service_with_wiki):
        """Test AbilitiesService initialization with wiki enabled"""
        assert abilities_service_with_wiki.enable_wiki is True
        assert abilities_service_with_wiki.abilities_scraper is not None

    def test_normalize_champion_name(self, abilities_service):
        """Test champion name normalization"""
        assert abilities_service._normalize_champion_name("taric") == "Taric"
        assert abilities_service._normalize_champion_name("  TARIC  ") == "Taric"
        assert abilities_service._normalize_champion_name("kai'sa") == "Kai'Sa"

    def test_normalize_ability_slot(self, abilities_service):
        """Test ability slot normalization"""
        assert abilities_service._normalize_ability_slot("q") == "Q"
        assert abilities_service._normalize_ability_slot("PASSIVE") == "Passive"
        assert abilities_service._normalize_ability_slot("p") == "Passive"
        assert abilities_service._normalize_ability_slot("ult") == "R"
        assert abilities_service._normalize_ability_slot("ultimate") == "R"
        assert abilities_service._normalize_ability_slot(None) is None

    @pytest.mark.asyncio
    async def test_get_champion_abilities_wiki_disabled(self, abilities_service):
        """Test get_champion_abilities with wiki disabled"""
        with pytest.raises(WikiScraperError):
            await abilities_service.get_champion_abilities("Taric")

    @pytest.mark.asyncio
    async def test_get_champion_abilities_all_success(self, abilities_service_with_wiki, mock_abilities_data):
        """Test successful retrieval of all champion abilities"""
        # Mock the scraper
        abilities_service_with_wiki.abilities_scraper.scrape_champion_abilities = AsyncMock(return_value=mock_abilities_data)
        
        result = await abilities_service_with_wiki.get_champion_abilities("Taric")
        
        assert result["name"] == "Taric"
        assert result["champion"] == "Taric"
        assert "abilities" in result
        assert result["ability_count"] == 5
        assert result["data_source"] == "wiki_abilities_scrape"
        
        abilities = result["abilities"]
        assert "Passive" in abilities
        assert "Q" in abilities
        assert "W" in abilities
        assert "E" in abilities
        assert "R" in abilities
        
        # Check specific ability data
        assert abilities["Q"]["name"] == "Starlight's Touch"
        assert abilities["Q"]["cooldown"] == "14/13/12/11/10"

    @pytest.mark.asyncio
    async def test_get_champion_abilities_specific_ability(self, abilities_service_with_wiki, mock_abilities_data):
        """Test retrieval of specific champion ability"""
        # Mock the scraper
        abilities_service_with_wiki.abilities_scraper.scrape_champion_abilities = AsyncMock(return_value=mock_abilities_data)
        
        result = await abilities_service_with_wiki.get_champion_abilities("Taric", "Q")
        
        assert result["name"] == "Taric"
        assert result["champion"] == "Taric"
        assert result["ability_slot"] == "Q"
        assert "ability" in result
        assert result["data_source"] == "wiki_abilities_scrape"
        
        ability = result["ability"]
        assert ability["name"] == "Starlight's Touch"
        assert ability["cooldown"] == "14/13/12/11/10"

    @pytest.mark.asyncio
    async def test_get_champion_abilities_invalid_ability_slot(self, abilities_service_with_wiki, mock_abilities_data):
        """Test retrieval with invalid ability slot"""
        # Mock the scraper
        abilities_service_with_wiki.abilities_scraper.scrape_champion_abilities = AsyncMock(return_value=mock_abilities_data)
        
        with pytest.raises(WikiScraperError) as exc_info:
            await abilities_service_with_wiki.get_champion_abilities("Taric", "Z")
        
        assert "Ability Z not found for Taric" in str(exc_info.value)
        assert "Available abilities:" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_champion_abilities_champion_not_found(self, abilities_service_with_wiki):
        """Test handling of champion not found"""
        # Mock the scraper to raise an error
        abilities_service_with_wiki.abilities_scraper.scrape_champion_abilities = AsyncMock(
            side_effect=WikiScraperError("Champion not found")
        )
        
        with pytest.raises(ChampionNotFoundError):
            await abilities_service_with_wiki.get_champion_abilities("InvalidChampion")

    @pytest.mark.asyncio
    async def test_get_ability_details_success(self, abilities_service_with_wiki, mock_abilities_data):
        """Test get_ability_details method"""
        # Mock the scraper
        abilities_service_with_wiki.abilities_scraper.scrape_champion_abilities = AsyncMock(return_value=mock_abilities_data)
        
        result = await abilities_service_with_wiki.get_ability_details("Taric", "Q")
        
        assert result["champion"] == "Taric"
        assert result["ability_slot"] == "Q"
        assert "ability_details" in result
        
        ability_details = result["ability_details"]
        assert ability_details["name"] == "Starlight's Touch"
        assert ability_details["slot"] == "Q"
        assert ability_details["description"] == "Taric heals himself and nearby allied champions."
        assert ability_details["cooldown"] == "14/13/12/11/10"
        assert ability_details["cost"] == "60/70/80/90/100"
        assert ability_details["range"] == "750"

    @pytest.mark.asyncio
    async def test_cleanup(self, abilities_service_with_wiki):
        """Test cleanup method"""
        # Mock the cleanup method
        abilities_service_with_wiki.abilities_scraper.close = AsyncMock()
        
        await abilities_service_with_wiki.cleanup()
        
        abilities_service_with_wiki.abilities_scraper.close.assert_called_once() 