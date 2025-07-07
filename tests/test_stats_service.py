"""
Test suite for StatsService

This module tests the StatsService functionality including:
- Level-specific stat scraping
- Resource type detection and formatting
- Error handling and edge cases
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.services.stats_service import StatsService
from src.models.exceptions import ChampionNotFoundError


class TestStatsService:
    """Test cases for StatsService class."""

    @pytest.fixture
    def stats_service(self):
        """Create a StatsService instance for testing."""
        return StatsService(enable_wiki=True, use_cache=False)

    @pytest.fixture
    def mock_stats_scraper(self):
        """Create a mock StatsScraper."""
        mock_scraper = Mock()
        mock_scraper.scrape_level_specific_stats = AsyncMock()
        return mock_scraper

    def test_stats_service_initialization(self, stats_service):
        """Test that StatsService initializes correctly."""
        assert stats_service.enable_wiki is True
        assert stats_service.stats_scraper is not None
        assert hasattr(stats_service, 'logger')

    def test_normalize_champion_name(self, stats_service):
        """Test champion name normalization."""
        # Test basic normalization
        assert stats_service._normalize_champion_name("zed") == "Zed"
        assert stats_service._normalize_champion_name("dr mundo") == "Dr Mundo"
        assert stats_service._normalize_champion_name("  kai'sa  ") == "Kai'Sa"

    def test_format_stat_name_mana_champion(self, stats_service):
        """Test stat name formatting for mana champions."""
        # Test mana champion formatting
        assert stats_service._format_stat_name("resource", "Mana") == "Resource (Mana)"
        assert stats_service._format_stat_name("resource_regen", "Mana") == "Resource Regen (Mana)"
        assert stats_service._format_stat_name("hp", "Mana") == "Hp"
        assert stats_service._format_stat_name("attack_damage", "Mana") == "Attack Damage"

    def test_format_stat_name_energy_champion(self, stats_service):
        """Test stat name formatting for energy champions."""
        # Test energy champion formatting
        assert stats_service._format_stat_name("resource", "Energy") == "Resource (Energy)"
        assert stats_service._format_stat_name("resource_regen", "Energy") == "Resource Regen (Energy)"

    def test_format_stat_name_secondary_bar_champion(self, stats_service):
        """Test stat name formatting for secondary bar champions."""
        # Test secondary bar champion formatting
        assert stats_service._format_stat_name("resource", "N/A") == "Resource"
        assert stats_service._format_stat_name("resource_regen", "Secondary Bar") == "Secondary Bar"

    @pytest.mark.asyncio
    async def test_get_champion_stats_level_specific(self, stats_service, mock_stats_scraper):
        """Test getting level-specific champion stats."""
        # Mock the scraper response
        mock_stats_data = {
            "stats": {
                "level": 10,
                "hp": 1500.0,
                "resource": 400.0,
                "resource_regen": 10.0,
                "resource_type": "Mana"
            },
            "data_source": "selenium_level_scrape"
        }
        mock_stats_scraper.scrape_level_specific_stats.return_value = mock_stats_data
        
        # Replace the scraper
        stats_service.stats_scraper = mock_stats_scraper
        
        # Test level-specific request
        result = await stats_service.get_champion_stats("Syndra", level=10)
        
        # Verify the result
        assert result["name"] == "Syndra"
        assert result["level"] == 10
        assert "Resource (Mana)" in result["stats"]
        assert result["stats"]["Resource (Mana)"] == 400.0
        assert result["data_source"] == "selenium_level_scrape"

    @pytest.mark.asyncio
    async def test_get_champion_stats_ranges(self, stats_service, mock_stats_scraper):
        """Test getting champion stat ranges (level 1-18)."""
        # Mock level 1 stats
        mock_level1_data = {
            "stats": {
                "level": 1,
                "hp": 500.0,
                "resource": 300.0,
                "resource_regen": 8.0,
                "resource_type": "Mana"
            },
            "data_source": "selenium_level_scrape"
        }
        
        # Mock level 18 stats
        mock_level18_data = {
            "stats": {
                "level": 18,
                "hp": 2000.0,
                "resource": 1000.0,
                "resource_regen": 20.0,
                "resource_type": "Mana"
            },
            "data_source": "selenium_level_scrape"
        }
        
        # Configure mock to return different data based on level
        def side_effect(champion, level):
            if level == 1:
                return mock_level1_data
            elif level == 18:
                return mock_level18_data
        
        mock_stats_scraper.scrape_level_specific_stats.side_effect = side_effect
        stats_service.stats_scraper = mock_stats_scraper
        
        # Test range request (no level specified)
        result = await stats_service.get_champion_stats("Syndra")
        
        # Verify the result
        assert result["name"] == "Syndra"
        assert "level" not in result  # No specific level
        assert result["data_source"] == "calculated_ranges_level_1_18"
        assert result["stats"]["Hp"] == "500.0 - 2000.0"
        assert result["stats"]["Resource (Mana)"] == "300.0 - 1000.0"

    @pytest.mark.asyncio
    async def test_get_champion_stats_energy_champion(self, stats_service, mock_stats_scraper):
        """Test getting stats for energy champions like Zed."""
        mock_stats_data = {
            "stats": {
                "level": 5,
                "hp": 800.0,
                "resource": 200.0,
                "resource_regen": 50.0,
                "resource_type": "Energy"
            },
            "data_source": "selenium_level_scrape"
        }
        mock_stats_scraper.scrape_level_specific_stats.return_value = mock_stats_data
        stats_service.stats_scraper = mock_stats_scraper
        
        result = await stats_service.get_champion_stats("Zed", level=5)
        
        assert result["stats"]["Resource (Energy)"] == 200.0
        assert result["stats"]["Resource Regen (Energy)"] == 50.0

    @pytest.mark.asyncio
    async def test_get_champion_stats_health_cost_champion(self, stats_service, mock_stats_scraper):
        """Test getting stats for health cost champions like Vladimir."""
        mock_stats_data = {
            "stats": {
                "level": 8,
                "hp": 1200.0,
                "resource": None,
                "resource_regen": None,
                "resource_type": "N/A"
            },
            "data_source": "selenium_level_scrape"
        }
        mock_stats_scraper.scrape_level_specific_stats.return_value = mock_stats_data
        stats_service.stats_scraper = mock_stats_scraper
        
        result = await stats_service.get_champion_stats("Vladimir", level=8)
        
        assert result["stats"]["Resource"] is None
        assert result["stats"]["Resource Regen"] is None

    @pytest.mark.asyncio
    async def test_get_champion_stats_wiki_disabled(self):
        """Test that appropriate error is raised when wiki is disabled."""
        stats_service = StatsService(enable_wiki=False)
        
        with pytest.raises(Exception):  # Should raise WikiScraperError
            await stats_service.get_champion_stats("Zed")

    @pytest.mark.asyncio
    async def test_get_champion_stats_invalid_champion(self, stats_service, mock_stats_scraper):
        """Test error handling for invalid champion names."""
        from src.data_sources.scrapers.base_scraper import WikiScraperError
        
        # Configure mock to raise WikiScraperError
        mock_stats_scraper.scrape_level_specific_stats.side_effect = WikiScraperError("Champion not found")
        stats_service.stats_scraper = mock_stats_scraper
        
        with pytest.raises(ChampionNotFoundError):
            await stats_service.get_champion_stats("InvalidChampion")

    @pytest.mark.asyncio 
    async def test_cleanup(self, stats_service, mock_stats_scraper):
        """Test cleanup functionality."""
        mock_stats_scraper.close = AsyncMock()
        stats_service.stats_scraper = mock_stats_scraper
        
        await stats_service.cleanup()
        mock_stats_scraper.close.assert_called_once()


# Integration tests (require actual network access)
class TestStatsServiceIntegration:
    """Integration tests for StatsService with real wiki data."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_champion_stats_mana(self):
        """Test getting real stats for a mana champion."""
        stats_service = StatsService(enable_wiki=True, use_cache=False)
        
        try:
            result = await stats_service.get_champion_stats("Syndra", level=1)
            
            # Verify basic structure
            assert result["name"] == "Syndra"
            assert result["level"] == 1
            assert "Resource (Mana)" in result["stats"]
            assert isinstance(result["stats"]["Hp"], float)
            
        finally:
            await stats_service.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_champion_stats_energy(self):
        """Test getting real stats for an energy champion."""
        stats_service = StatsService(enable_wiki=True, use_cache=False)
        
        try:
            result = await stats_service.get_champion_stats("Zed", level=1)
            
            # Verify energy resource type
            assert result["name"] == "Zed"
            assert "Resource (Energy)" in result["stats"]
            assert result["stats"]["Resource (Energy)"] == 200.0
            
        finally:
            await stats_service.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.integration  
    async def test_real_champion_ranges(self):
        """Test getting real stat ranges for a champion."""
        stats_service = StatsService(enable_wiki=True, use_cache=False)
        
        try:
            result = await stats_service.get_champion_stats("Jinx")
            
            # Verify range format
            assert result["name"] == "Jinx"
            assert "level" not in result
            assert " - " in result["stats"]["Hp"]  # Should be range format
            assert "Resource (Mana)" in result["stats"]
            
        finally:
            await stats_service.cleanup()


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_stats_service.py -v
    pytest.main([__file__, "-v"]) 