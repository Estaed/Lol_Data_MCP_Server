"""
Comprehensive Test Suite for Runes System

This module contains tests for the entire runes system including
scrapers, services, and MCP tools integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Import rune system components
from src.data_sources.scrapers.runes.rune_data_scraper import RuneDataScraper
from src.data_sources.scrapers.runes.rune_patch_scraper import RunePatchScraper
from src.services.runes.rune_service import RuneService
from src.services.runes.rune_patch_service import RunePatchService
from src.mcp_server.tools import GetRuneDataTool, GetRunePatchNoteTool
from src.models.exceptions import RuneNotFoundError


class TestRuneDataScraper:
    """Test cases for RuneDataScraper"""

    @pytest.fixture
    def scraper(self):
        return RuneDataScraper(enable_cache=False)

    def test_normalize_rune_name(self, scraper):
        """Test rune name normalization"""
        assert scraper.normalize_rune_name("Summon Aery") == "Summon_Aery"
        assert scraper.normalize_rune_name("Arcane Comet") == "Arcane_Comet"
        assert scraper.normalize_rune_name("Fleet Footwork") == "Fleet_Footwork"

    @pytest.mark.asyncio
    async def test_scrape_rune_data_mock(self, scraper):
        """Test rune data scraping with mocked response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>Summon Aery - League of Legends Wiki</title></head>
        <body>
        <div class="infobox theme-rune">
            <div class="infobox-data-label">Path</div>
            <div class="infobox-data-value"><a href="/Sorcery">Sorcery</a></div>
            <div class="infobox-data-label">Slot</div>
            <div class="infobox-data-value">Keystone</div>
            <div class="infobox-header">Description</div>
            <div class="infobox-section">
                <div class="infobox-data-value">Damaging basic attacks signal Aery to pounce.</div>
            </div>
        </div>
        <h2><span id="Notes">Notes</span></h2>
        <ul><li>Aery applies effects on arrival</li></ul>
        <h2><span id="Strategy">Strategy</span></h2>
        <ul><li>Great for enchanters</li></ul>
        </body>
        </html>
        """

        with patch.object(scraper, '_make_request', return_value=mock_response):
            with patch.object(scraper, '_ensure_client'):
                result = await scraper.scrape_rune_data("Summon Aery")

        assert result['rune'] == "Summon Aery"
        assert result['data_source'] == 'wiki_rune_scrape'
        assert 'sidebar' in result['sections']
        assert 'notes' in result['sections']
        assert 'strategy' in result['sections']


class TestRunePatchScraper:
    """Test cases for RunePatchScraper"""

    @pytest.fixture
    def scraper(self):
        return RunePatchScraper(enable_cache=False)

    def test_normalize_rune_name(self, scraper):
        """Test rune name normalization"""
        assert scraper.normalize_rune_name("Summon Aery") == "Summon_Aery"

    def test_patch_version_validation(self, scraper):
        """Test patch version validation"""
        assert scraper._is_valid_patch_version("V14.21")
        assert scraper._is_valid_patch_version("V4.12")
        assert not scraper._is_valid_patch_version("14.21")
        assert not scraper._is_valid_patch_version("invalid")

    def test_patch_version_normalization(self, scraper):
        """Test patch version normalization"""
        assert scraper._normalize_patch_version("14.21") == "V14.21"
        assert scraper._normalize_patch_version("V14.21") == "V14.21"

    @pytest.mark.asyncio
    async def test_scrape_patch_notes_mock(self, scraper):
        """Test patch notes scraping with mocked response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <body>
        <h2>Patch History</h2>
        <dl>
            <dt><a href="/V14.21">V14.21</a></dt>
        </dl>
        <ul>
            <li>Base damage increased</li>
            <li>Cooldown reduced</li>
        </ul>
        </body>
        </html>
        """

        with patch.object(scraper, '_make_request', return_value=mock_response):
            with patch.object(scraper, '_ensure_client'):
                result = await scraper.scrape_all_patch_notes("Summon Aery")

        assert result['rune'] == "Summon Aery"
        assert result['total_patches'] >= 0


class TestRuneService:
    """Test cases for RuneService"""

    @pytest.fixture
    def service(self):
        return RuneService(enable_wiki=False)  # Use mock data

    def test_normalize_rune_name(self, service):
        """Test rune name normalization"""
        assert service._normalize_rune_name("summon aery") == "Summon Aery"
        assert service._normalize_rune_name("ARCANE COMET") == "Arcane Comet"

    @pytest.mark.asyncio
    async def test_get_rune_data_mock(self, service):
        """Test getting rune data with mock service"""
        result = await service.get_rune_data("Summon Aery")

        assert result['rune_name'] == "Summon Aery"
        assert result['data_source'] == 'mock_data'
        assert 'sections' in result
        assert 'sidebar' in result['sections']

    @pytest.mark.asyncio
    async def test_get_rune_data_with_sections(self, service):
        """Test getting specific sections"""
        result = await service.get_rune_data("Summon Aery", sections=['sidebar'])

        assert result['rune_name'] == "Summon Aery"
        assert 'sidebar' in result['sections']
        assert len(result['sections']) == 1


class TestRunePatchService:
    """Test cases for RunePatchService"""

    @pytest.fixture
    def service(self):
        return RunePatchService(enable_wiki=False)  # Use mock data

    @pytest.mark.asyncio
    async def test_get_patch_notes_mock(self, service):
        """Test getting patch notes with mock service"""
        result = await service.get_rune_patch_notes("Summon Aery")

        assert result['rune_name'] == "Summon Aery"
        assert result['data_source'] == 'mock_data'
        assert 'patches' in result
        assert result['total_patches'] >= 0

    @pytest.mark.asyncio
    async def test_get_specific_patch_note(self, service):
        """Test getting specific patch note"""
        result = await service.get_rune_patch_notes("Summon Aery", "V14.21")

        assert result['rune_name'] == "Summon Aery"
        if 'requested_patch' in result:
            assert result['requested_patch'] == "V14.21"


class TestRuneMCPTools:
    """Test cases for Rune MCP Tools"""

    @pytest.fixture
    def mock_rune_service(self):
        service = Mock()
        service.get_rune_data = AsyncMock(return_value={
            'rune_name': 'Summon Aery',
            'data_source': 'mock_data',
            'sections': {
                'sidebar': {'path': 'Sorcery', 'slot': 'Keystone'}
            }
        })
        return service

    @pytest.fixture
    def mock_rune_patch_service(self):
        service = Mock()
        service.get_rune_patch_notes = AsyncMock(return_value={
            'rune_name': 'Summon Aery',
            'patches': [{'version': 'V14.21', 'changes': ['Mock change']}],
            'total_patches': 1
        })
        return service

    def test_get_rune_data_tool_schema(self, mock_rune_service):
        """Test GetRuneDataTool schema"""
        tool = GetRuneDataTool(mock_rune_service)
        schema = tool.get_schema()

        assert schema.name == "get_rune_data"
        assert "rune_name" in schema.input_schema["properties"]
        assert "rune_name" in schema.input_schema["required"]

    @pytest.mark.asyncio
    async def test_get_rune_data_tool_execute(self, mock_rune_service):
        """Test GetRuneDataTool execution"""
        tool = GetRuneDataTool(mock_rune_service)
        result = await tool.execute({"rune_name": "Summon Aery"})

        assert result['rune_name'] == 'Summon Aery'
        mock_rune_service.get_rune_data.assert_called_once_with(
            rune_name="Summon Aery", sections=None
        )

    def test_get_rune_patch_note_tool_schema(self, mock_rune_patch_service):
        """Test GetRunePatchNoteTool schema"""
        tool = GetRunePatchNoteTool(mock_rune_patch_service)
        schema = tool.get_schema()

        assert schema.name == "get_rune_patch_note"
        assert "rune_name" in schema.input_schema["properties"]
        assert "rune_name" in schema.input_schema["required"]

    @pytest.mark.asyncio
    async def test_get_rune_patch_note_tool_execute(self, mock_rune_patch_service):
        """Test GetRunePatchNoteTool execution"""
        tool = GetRunePatchNoteTool(mock_rune_patch_service)
        result = await tool.execute({"rune_name": "Summon Aery"})

        assert result['rune_name'] == 'Summon Aery'
        mock_rune_patch_service.get_rune_patch_notes.assert_called_once_with(
            rune_name="Summon Aery", patch_version=None
        )

    @pytest.mark.asyncio
    async def test_rune_tools_error_handling(self, mock_rune_service):
        """Test error handling in rune tools"""
        tool = GetRuneDataTool(mock_rune_service)

        # Test missing rune_name
        with pytest.raises(ValueError, match="rune_name is required"):
            await tool.execute({})

        # Test empty rune_name
        with pytest.raises(ValueError, match="rune_name is required"):
            await tool.execute({"rune_name": ""})


class TestRuneSystemIntegration:
    """Integration tests for the complete rune system"""

    @pytest.mark.asyncio
    async def test_full_system_mock_integration(self):
        """Test full system integration with mock data"""
        # Initialize services
        rune_service = RuneService(enable_wiki=False)
        rune_patch_service = RunePatchService(enable_wiki=False)

        # Test rune data
        rune_data = await rune_service.get_rune_data("Summon Aery")
        assert rune_data['rune_name'] == "Summon Aery"

        # Test patch notes
        patch_data = await rune_patch_service.get_rune_patch_notes("Summon Aery")
        assert patch_data['rune_name'] == "Summon Aery"

        # Test MCP tools
        rune_tool = GetRuneDataTool(rune_service)
        patch_tool = GetRunePatchNoteTool(rune_patch_service)

        tool_result = await rune_tool.execute({"rune_name": "Summon Aery"})
        assert tool_result['rune_name'] == "Summon Aery"

        patch_result = await patch_tool.execute({"rune_name": "Summon Aery"})
        assert patch_result['rune_name'] == "Summon Aery"

    def test_exception_consistency(self):
        """Test that RuneNotFoundError is properly defined"""
        error = RuneNotFoundError("Nonexistent Rune")
        assert error.rune_name == "Nonexistent Rune"
        assert "Nonexistent Rune" in str(error)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])