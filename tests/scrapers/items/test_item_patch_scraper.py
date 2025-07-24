"""
Tests for ItemPatchScraper

This module contains comprehensive tests for the ItemPatchScraper class,
following the champion test pattern for consistency.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from bs4 import BeautifulSoup

from src.data_sources.scrapers.items.item_patch_scraper import ItemPatchScraper, WikiScraperError


class TestItemPatchScraper:
    """Test cases for ItemPatchScraper class"""

    @pytest.fixture
    def scraper(self):
        """Create ItemPatchScraper instance for testing"""
        return ItemPatchScraper(
            rate_limit_delay=0.1,  # Faster for testing
            timeout=5.0,
            max_retries=1,
            enable_cache=False
        )

    @pytest.fixture
    def sample_patch_html(self):
        """Sample HTML with patch history section"""
        return """
        <html>
            <body>
                <h2><span class="mw-headline" id="Patch_History">Patch History</span></h2>
                <div style="overflow:auto;">
                    <dl><dt><a href="/en-us/V14.19" title="V14.19">V14.19</a></dt></dl>
                    <ul>
                        <li>Combine cost increased to 500 from 400.</li>
                        <li>Ability power reduced to 35 from 40.</li>
                    </ul>
                    <dl><dt><a href="/en-us/V14.11" title="V14.11">V14.11</a></dt></dl>
                    <ul>
                        <li>Can no longer be upgraded to Cry of the Shrieking City.</li>
                    </ul>
                    <dl><dt><a href="/en-us/V13.10" title="V13.10">V13.10</a> - Added</dt></dl>
                </div>
            </body>
        </html>
        """

    @pytest.fixture
    def empty_patch_html(self):
        """Sample HTML without patch history"""
        return """
        <html>
            <body>
                <h1>Echoes of Helia</h1>
                <p>Item description</p>
            </body>
        </html>
        """

    def test_normalize_item_name(self, scraper):
        """Test item name normalization"""
        # Basic item names
        assert scraper.normalize_item_name("Echoes of Helia") == "Echoes_of_Helia"
        assert scraper.normalize_item_name("Kindlegem") == "Kindlegem"
        
        # Item names with apostrophes
        assert scraper.normalize_item_name("Morellonomicon's") == "Morellonomicon%27s"
        assert scraper.normalize_item_name("Kai'Sa's Plasma") == "Kai%27Sa%27s_Plasma"
        
        # Item names with spaces
        assert scraper.normalize_item_name("Long Sword") == "Long_Sword"
        assert scraper.normalize_item_name("B. F. Sword") == "B._F._Sword"

    def test_is_valid_patch_version(self, scraper):
        """Test patch version validation"""
        # Valid versions
        assert scraper._is_valid_patch_version("V14.19")
        assert scraper._is_valid_patch_version("V13.10")
        assert scraper._is_valid_patch_version("V4.12")
        assert scraper._is_valid_patch_version("V13.24b")
        
        # Invalid versions
        assert not scraper._is_valid_patch_version("14.19")  # Missing V prefix
        assert not scraper._is_valid_patch_version("V14")    # Incomplete
        assert not scraper._is_valid_patch_version("patch 14.19")  # Wrong format
        assert not scraper._is_valid_patch_version("V14.19.1")  # Too many parts

    def test_normalize_patch_version(self, scraper):
        """Test patch version normalization"""
        # Add V prefix
        assert scraper._normalize_patch_version("14.19") == "V14.19"
        assert scraper._normalize_patch_version("13.10") == "V13.10"
        
        # Keep existing V prefix
        assert scraper._normalize_patch_version("V14.19") == "V14.19"
        assert scraper._normalize_patch_version("v14.19") == "V14.19"  # Case insensitive
        
        # Strip whitespace
        assert scraper._normalize_patch_version("  14.19  ") == "V14.19"

    def test_patch_versions_match(self, scraper):
        """Test patch version matching"""
        # Exact matches
        assert scraper._patch_versions_match("V14.19", "V14.19")
        assert scraper._patch_versions_match("V14.19", "14.19")
        assert scraper._patch_versions_match("14.19", "V14.19")
        
        # Case insensitive
        assert scraper._patch_versions_match("V14.19", "v14.19")
        
        # Different versions
        assert not scraper._patch_versions_match("V14.19", "V14.18")
        assert not scraper._patch_versions_match("V14.19", "V13.19")

    def test_find_patch_history_section_success(self, scraper, sample_patch_html):
        """Test successful patch history section detection"""
        soup = BeautifulSoup(sample_patch_html, 'lxml')
        section = scraper._find_patch_history_section(soup)
        
        assert section is not None
        # Should contain version patterns
        section_text = section.get_text()
        assert "V14.19" in section_text
        assert "V14.11" in section_text

    def test_find_patch_history_section_failure(self, scraper, empty_patch_html):
        """Test patch history section detection when not found"""
        soup = BeautifulSoup(empty_patch_html, 'lxml')
        section = scraper._find_patch_history_section(soup)
        
        assert section is None

    def test_extract_patch_data_success(self, scraper, sample_patch_html):
        """Test patch data extraction from HTML"""
        soup = BeautifulSoup(sample_patch_html, 'lxml')
        section = scraper._find_patch_history_section(soup)
        patches = scraper._extract_patch_data(section)
        
        assert len(patches) == 2  # V14.19 and V14.11
        
        # Check first patch (V14.19)
        patch_14_19 = patches[0]
        assert patch_14_19['version'] == 'V14.19'
        assert len(patch_14_19['changes']) == 2
        assert 'Combine cost increased to 500 from 400.' in patch_14_19['changes']
        assert 'Ability power reduced to 35 from 40.' in patch_14_19['changes']
        
        # Check second patch (V14.11)
        patch_14_11 = patches[1]
        assert patch_14_11['version'] == 'V14.11'
        assert len(patch_14_11['changes']) == 1
        assert 'Can no longer be upgraded to Cry of the Shrieking City.' in patch_14_11['changes']

    def test_extract_patch_data_empty(self, scraper, empty_patch_html):
        """Test patch data extraction with no patches"""
        soup = BeautifulSoup(empty_patch_html, 'lxml')
        patches = scraper._extract_patch_data(soup)
        
        assert patches == []

    @pytest.mark.asyncio
    async def test_scrape_all_patch_notes_success(self, scraper, sample_patch_html):
        """Test successful scraping of all patch notes"""
        mock_response = Mock()
        mock_response.text = sample_patch_html
        
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', new_callable=AsyncMock, return_value=mock_response):
            
            result = await scraper.scrape_all_patch_notes("Echoes of Helia")
            
            assert result['item'] == "Echoes of Helia"
            assert result['total_patches'] == 2
            assert len(result['patches']) == 2
            assert 'Retrieved 2 patch notes' in result['message']

    @pytest.mark.asyncio
    async def test_scrape_all_patch_notes_no_history(self, scraper, empty_patch_html):
        """Test scraping when no patch history exists"""
        mock_response = Mock()
        mock_response.text = empty_patch_html
        
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', new_callable=AsyncMock, return_value=mock_response):
            
            result = await scraper.scrape_all_patch_notes("Test Item")
            
            assert result['item'] == "Test Item"
            assert result['total_patches'] == 0
            assert result['patches'] == []
            assert 'No patch history section found' in result['message']

    @pytest.mark.asyncio
    async def test_scrape_specific_patch_note_success(self, scraper, sample_patch_html):
        """Test scraping specific patch version"""
        mock_response = Mock()
        mock_response.text = sample_patch_html
        
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', new_callable=AsyncMock, return_value=mock_response):
            
            result = await scraper.scrape_specific_patch_note("Echoes of Helia", "14.19")
            
            assert result['item'] == "Echoes of Helia"
            assert result['patch_version'] == "14.19"
            assert result['total_patches'] == 1
            assert len(result['patches']) == 1
            assert result['patches'][0]['version'] == 'V14.19'

    @pytest.mark.asyncio
    async def test_scrape_specific_patch_note_not_found(self, scraper, sample_patch_html):
        """Test scraping specific patch version that doesn't exist"""
        mock_response = Mock()
        mock_response.text = sample_patch_html
        
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', new_callable=AsyncMock, return_value=mock_response):
            
            result = await scraper.scrape_specific_patch_note("Echoes of Helia", "15.1")
            
            assert result['item'] == "Echoes of Helia"
            assert result['patch_version'] == "15.1"
            assert result['total_patches'] == 0
            assert result['patches'] == []
            assert 'No changes found' in result['message']

    @pytest.mark.asyncio
    async def test_scrape_all_patch_notes_http_error(self, scraper):
        """Test handling of HTTP errors"""
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', side_effect=Exception("HTTP Error")):
            
            with pytest.raises(WikiScraperError):
                await scraper.scrape_all_patch_notes("Echoes of Helia")

    @pytest.mark.asyncio
    async def test_scrape_specific_patch_note_http_error(self, scraper):
        """Test handling of HTTP errors in specific patch scraping"""
        with patch.object(scraper, '_ensure_client', new_callable=AsyncMock), \
             patch.object(scraper, '_make_request', side_effect=Exception("HTTP Error")):
            
            with pytest.raises(WikiScraperError):
                await scraper.scrape_specific_patch_note("Echoes of Helia", "14.19")

    def test_get_section_content_after_heading(self, scraper):
        """Test getting content section after heading"""
        html = """
        <div>
            <h2 id="patch_history">Patch History</h2>
            <div>
                <dl><dt>V14.19</dt></dl>
                <ul><li>Change 1</li></ul>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, 'lxml')
        heading = soup.find('h2')
        
        content = scraper._get_section_content_after_heading(heading)
        assert content is not None
        assert "V14.19" in content.get_text()

    def test_item_name_url_encoding(self, scraper):
        """Test proper URL encoding for item names"""
        # Test apostrophes become %27
        result = scraper.normalize_item_name("Wit's End")
        assert result == "Wit%27s_End"
        
        # Test spaces become underscores
        result = scraper.normalize_item_name("Long Sword")
        assert result == "Long_Sword"
        
        # Test complex names
        result = scraper.normalize_item_name("Kai'Sa's Plasma Caster")
        assert result == "Kai%27Sa%27s_Plasma_Caster"