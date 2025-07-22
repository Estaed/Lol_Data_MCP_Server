"""
Tests for ItemScraper - Task 2.2.2

Comprehensive test suite for the individual item page scraping functionality,
including infobox parsing, stats extraction, passive abilities, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bs4 import BeautifulSoup

from src.data_sources.scrapers.item_scraper import (
    ItemScraper, ItemData, ItemStats, ItemPassive, ItemRecipe, ItemAvailability
)


class TestItemScraper:
    """Test suite for ItemScraper functionality"""

    @pytest.fixture
    def scraper(self):
        """Create ItemScraper instance for testing"""
        return ItemScraper(enable_cache=False)  # Disable cache for testing

    @pytest.fixture
    def mock_item_html(self):
        """Mock HTML content for a typical item page"""
        return """
        <div class="infobox">
            <div class="infobox-title">Test Item</div>
            <div class="infobox-image">
                <img alt="Test Item" src="/images/test_item.png"/>
            </div>
            <div class="infobox-header">Stats</div>
            <div class="infobox-section-stacked">
                +50 attack damage
                +25 ability power
                +300 health
            </div>
            <div class="infobox-header">Passive</div>
            <div class="infobox-section">
                Unique – Test Passive: Grants special effects when attacking enemies.
            </div>
            <div class="infobox-header">Recipe</div>
            <div class="infobox-section-cell">
                <div class="infobox-data-row">
                    <div class="infobox-data-label">Cost</div>
                    <div class="infobox-data-value">3000</div>
                </div>
                <div class="infobox-data-row">
                    <div class="infobox-data-label">Sell</div>
                    <div class="infobox-data-value">1500</div>
                </div>
                <div class="infobox-data-row">
                    <div class="infobox-data-label">ID</div>
                    <div class="infobox-data-value">9999</div>
                </div>
            </div>
            <div class="infobox-header">Availability</div>
            <div class="infobox-section-cell-row">SR 5v5 ARAM</div>
            <div class="infobox-header">Keywords</div>
            <div class="infobox-section">Fighter Legendary Damage</div>
        </div>
        """

    @pytest.fixture
    def mock_soup(self, mock_item_html):
        """Create BeautifulSoup object from mock HTML"""
        return BeautifulSoup(mock_item_html, "lxml")

    @pytest.mark.asyncio
    async def test_scraper_initialization(self, scraper):
        """Test ItemScraper initialization"""
        assert scraper is not None
        assert hasattr(scraper, 'logger')
        assert scraper.BASE_URL == "https://wiki.leagueoflegends.com/en-us/"

    @pytest.mark.asyncio
    async def test_scrape_item_with_url(self, scraper, mock_item_html):
        """Test scraping item with provided URL"""
        mock_response = MagicMock()
        mock_response.text = mock_item_html
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            item_data = await scraper.scrape_item("Test Item", "/en-us/Test_Item")
            
            # Verify basic info
            assert item_data.name == "Test Item"
            assert item_data.item_id == "9999"
            assert item_data.image_url == "https://wiki.leagueoflegends.com/images/test_item.png"
            
            # Verify stats
            assert item_data.stats.attack_damage == 50.0
            assert item_data.stats.ability_power == 25.0
            assert item_data.stats.health == 300.0
            
            # Verify passive
            assert item_data.passive is not None
            assert item_data.passive.name == "Test Passive"
            assert "special effects" in item_data.passive.description
            
            # Verify recipe
            assert item_data.recipe.total_cost == 3000
            assert item_data.recipe.sell_price == 1500
            
            # Verify availability
            assert "SR" in " ".join(item_data.availability.game_modes)
            assert "ARAM" in " ".join(item_data.availability.game_modes)
            
            # Verify keywords
            assert "Fighter" in item_data.keywords
            assert "Legendary" in item_data.keywords

    @pytest.mark.asyncio
    async def test_scrape_item_without_url(self, scraper, mock_item_html):
        """Test scraping item without provided URL (using name normalization)"""
        mock_response = MagicMock()
        mock_response.text = mock_item_html
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            item_data = await scraper.scrape_item("Test Item")
            
            assert item_data.name == "Test Item"
            assert item_data.source_url.endswith("Test_Item")

    @pytest.mark.asyncio
    async def test_fetch_item_page_success(self, scraper, mock_item_html):
        """Test successful item page fetching"""
        mock_response = MagicMock()
        mock_response.text = mock_item_html
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            soup = await scraper._fetch_item_page("https://wiki.leagueoflegends.com/en-us/Test_Item")
            
            assert isinstance(soup, BeautifulSoup)
            assert soup.find("div", class_="infobox") is not None

    @pytest.mark.asyncio
    async def test_fetch_item_page_no_infobox(self, scraper):
        """Test handling of page without infobox"""
        mock_response = MagicMock()
        mock_response.text = "<html><body><div>No infobox here</div></body></html>"
        
        with patch.object(scraper, '_make_request', return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                await scraper._fetch_item_page("https://wiki.leagueoflegends.com/en-us/Test_Item")
            
            assert "infobox" in str(exc_info.value).lower()

    def test_parse_basic_info(self, scraper, mock_soup):
        """Test parsing of basic item information"""
        item_data = ItemData(name="Original")
        infobox = mock_soup.find("div", class_="infobox")
        
        scraper._parse_basic_info(infobox, item_data)
        
        assert item_data.name == "Test Item"  # Should be updated from HTML
        assert item_data.image_url == "https://wiki.leagueoflegends.com/images/test_item.png"

    def test_parse_stats_section(self, scraper):
        """Test parsing of item statistics"""
        # Create mock section div with stats
        html = """
        <div class="infobox-section-stacked">
            +75 attack damage
            +20% critical strike chance
            +15 ability haste
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_stats_section(section_divs, item_data)
        
        assert item_data.stats.attack_damage == 75.0
        assert item_data.stats.critical_strike_chance == 20.0
        assert item_data.stats.ability_haste == 15.0

    def test_parse_passive_section(self, scraper):
        """Test parsing of passive abilities"""
        html = """
        <div class="infobox-section">
            Unique – Lifeline: When you take damage that would reduce you below 30% health, gain a shield.
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_passive_section(section_divs, item_data)
        
        assert item_data.passive is not None
        assert item_data.passive.name == "Lifeline"
        assert "shield" in item_data.passive.description
        assert item_data.passive.ability_type == "passive"

    def test_parse_recipe_section_with_rows(self, scraper):
        """Test parsing of recipe information with data rows"""
        html = """
        <div class="infobox-section-cell">
            <div class="infobox-data-row">
                <div class="infobox-data-label">Cost</div>
                <div class="infobox-data-value">2500</div>
            </div>
            <div class="infobox-data-row">
                <div class="infobox-data-label">Sell</div>
                <div class="infobox-data-value">1250</div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_recipe_section(section_divs, item_data)
        
        assert item_data.recipe.total_cost == 2500
        assert item_data.recipe.sell_price == 1250

    def test_parse_recipe_section_raw_text(self, scraper):
        """Test parsing of recipe information from raw text"""
        html = """
        <div class="infobox-section-cell">Cost450Sell180ID1083</div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_recipe_section(section_divs, item_data)
        
        assert item_data.recipe.total_cost == 450
        assert item_data.recipe.sell_price == 180
        assert item_data.item_id == "1083"

    def test_parse_availability_section(self, scraper):
        """Test parsing of availability information"""
        html = """
        <div class="infobox-section-cell-row">SR 5v5 ARAM FGM</div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_availability_section(section_divs, item_data)
        
        game_modes_text = " ".join(item_data.availability.game_modes)
        assert "SR" in game_modes_text
        assert "ARAM" in game_modes_text
        assert "FGM" in game_modes_text

    def test_parse_keywords_section(self, scraper):
        """Test parsing of keywords"""
        html = """
        <div class="infobox-section">Fighter Marksman Assassin</div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_keywords_section(section_divs, item_data)
        
        assert "Fighter" in item_data.keywords
        assert "Marksman" in item_data.keywords
        assert "Assassin" in item_data.keywords

    def test_parse_menu_section(self, scraper):
        """Test parsing of menu/category information"""
        html = """
        <div class="infobox-section">FighterMarksmanAssassinAttackDamage</div>
        """
        soup = BeautifulSoup(html, "lxml")
        section_divs = [soup.find("div")]
        
        item_data = ItemData(name="Test")
        scraper._parse_menu_section(section_divs, item_data)
        
        assert "Fighter" in item_data.keywords
        assert "Marksman" in item_data.keywords
        assert "Attack" in item_data.keywords
        assert "Damage" in item_data.keywords

    def test_parse_stat_value_patterns(self, scraper):
        """Test various stat parsing patterns"""
        stats = ItemStats()
        
        test_cases = [
            ("+50 attack damage", "attack_damage", 50.0),
            ("+75 ability power", "ability_power", 75.0),
            ("+300 health", "health", 300.0),
            ("+20% critical strike", "critical_strike_chance", 20.0),
            ("+15 ability haste", "ability_haste", 15.0),
            ("+40 armor", "armor", 40.0),
            ("+25 magic resist", "magic_resist", 25.0),
            ("+10% life steal", "life_steal", 10.0),
        ]
        
        for stat_text, stat_name, expected_value in test_cases:
            stats = ItemStats()  # Reset for each test
            scraper._parse_stat_value(stat_text, stats)
            
            actual_value = getattr(stats, stat_name)
            assert actual_value == expected_value, f"Failed to parse '{stat_text}', expected {expected_value}, got {actual_value}"

    def test_normalize_item_name(self, scraper):
        """Test item name normalization for URL generation"""
        test_cases = [
            ("Simple Item", "Simple_Item"),
            ("Doran's Blade", "Doran%27s_Blade"),
            ("Item with Spaces", "Item_with_Spaces"),
            ("Multiple  Spaces", "Multiple__Spaces"),
        ]
        
        for input_name, expected_output in test_cases:
            result = scraper._normalize_item_name(input_name)
            assert result == expected_output

    @pytest.mark.asyncio
    async def test_scrape_item_error_handling(self, scraper):
        """Test error handling during item scraping"""
        with patch.object(scraper, '_fetch_item_page', side_effect=Exception("Network error")):
            with pytest.raises(Exception) as exc_info:
                await scraper.scrape_item("Test Item", "/en-us/Test_Item")
            
            assert "Test Item" in str(exc_info.value)

    def test_item_data_models(self):
        """Test item data model creation and validation"""
        # Test ItemStats
        stats = ItemStats(attack_damage=50.0, health=300.0)
        assert stats.attack_damage == 50.0
        assert stats.health == 300.0
        assert stats.ability_power is None  # Default value
        
        # Test ItemPassive
        passive = ItemPassive(name="Test", description="Test passive", ability_type="passive")
        assert passive.name == "Test"
        assert passive.description == "Test passive"
        assert passive.ability_type == "passive"
        
        # Test ItemRecipe
        recipe = ItemRecipe(total_cost=3000, sell_price=1500)
        assert recipe.total_cost == 3000
        assert recipe.sell_price == 1500
        
        # Test ItemAvailability
        availability = ItemAvailability(game_modes=["SR", "ARAM"])
        assert "SR" in availability.game_modes
        assert "ARAM" in availability.game_modes
        
        # Test complete ItemData
        item_data = ItemData(
            name="Test Item",
            item_id="9999",
            stats=stats,
            passive=passive,
            recipe=recipe,
            availability=availability
        )
        assert item_data.name == "Test Item"
        assert item_data.item_id == "9999"
        assert item_data.stats.attack_damage == 50.0
        assert item_data.passive.name == "Test"


# Integration tests
class TestItemScraperIntegration:
    """Integration tests for ItemScraper with complex scenarios"""

    @pytest.fixture
    def complex_item_html(self):
        """Complex item HTML for integration testing"""
        return """
        <div class="infobox">
            <div class="infobox-title">Infinity Edge</div>
            <div class="infobox-image">
                <img alt="Infinity Edge" src="/images/infinity_edge.png"/>
            </div>
            <div class="infobox-header">Stats</div>
            <div class="infobox-section-stacked">
                +70 attack damage
                +20% critical strike chance
            </div>
            <div class="infobox-header">Passive</div>
            <div class="infobox-section">
                Unique – Perfection: Critical strikes deal 35% bonus critical strike damage.
            </div>
            <div class="infobox-header">Recipe</div>
            <div class="infobox-section-cell">
                Cost3400Sell2380ID3031
            </div>
            <div class="infobox-header">Availability</div>
            <div class="infobox-section-cell-row">SR 5v5</div>
            <div class="infobox-header">Menu</div>
            <div class="infobox-section">FighterMarksmanAssassinAttackDamageCriticalStrike</div>
            <div class="infobox-header">Keywords</div>
            <div class="infobox-section">legendary damage crit</div>
        </div>
        """

    @pytest.mark.asyncio
    async def test_complex_item_parsing(self, complex_item_html):
        """Test parsing of complex item with all sections"""
        scraper = ItemScraper(enable_cache=False)
        soup = BeautifulSoup(complex_item_html, "lxml")
        
        item_data = scraper._parse_item_data(soup, "Infinity Edge", "test_url")
        
        # Verify comprehensive data extraction
        assert item_data.name == "Infinity Edge"
        assert item_data.item_id == "3031"
        assert item_data.image_url.endswith("infinity_edge.png")
        
        # Verify stats
        assert item_data.stats.attack_damage == 70.0
        assert item_data.stats.critical_strike_chance == 20.0
        
        # Verify passive
        assert item_data.passive is not None
        assert item_data.passive.name == "Perfection"
        assert "35% bonus" in item_data.passive.description
        
        # Verify recipe
        assert item_data.recipe.total_cost == 3400
        assert item_data.recipe.sell_price == 2380
        
        # Verify availability
        game_modes_text = " ".join(item_data.availability.game_modes)
        assert "SR" in game_modes_text
        
        # Verify keywords (from both menu and keywords sections)
        keywords_text = " ".join(item_data.keywords)
        assert "Fighter" in keywords_text
        assert "legendary" in keywords_text
        assert "crit" in keywords_text

    @pytest.mark.asyncio
    async def test_different_item_types(self):
        """Test parsing of different item types (starter, consumable, trinket)"""
        scraper = ItemScraper(enable_cache=False)
        
        # Test cases for different item structures
        test_cases = [
            {
                "input_name": "Starter Item",  # This is what we pass to parse_item_data
                "html_title": "Doran's Blade",  # This is what's in the HTML
                "html": """
                <div class="infobox">
                    <div class="infobox-title">Doran's Blade</div>
                    <div class="infobox-header">Stats</div>
                    <div class="infobox-section-stacked">+8 attack damage+80 health</div>
                    <div class="infobox-header">Recipe</div>
                    <div class="infobox-section-cell">Cost450Sell180</div>
                </div>
                """,
                "expected_ad": 8.0,
                "expected_health": 80.0
            },
            {
                "input_name": "Consumable",
                "html_title": "Health Potion",
                "html": """
                <div class="infobox">
                    <div class="infobox-title">Health Potion</div>
                    <div class="infobox-header">Consume</div>
                    <div class="infobox-section">Restores health over time</div>
                    <div class="infobox-header">Recipe</div>
                    <div class="infobox-section-cell">Cost50</div>
                </div>
                """,
                "expected_cost": 50
            }
        ]
        
        for case in test_cases:
            soup = BeautifulSoup(case["html"], "lxml")
            item_data = scraper._parse_item_data(soup, case["input_name"], "test_url")
            
            # The parser should update the name from HTML title, not keep the input name
            assert item_data.name == case["html_title"]
            
            if "expected_ad" in case:
                assert item_data.stats.attack_damage == case["expected_ad"]
            if "expected_health" in case:
                assert item_data.stats.health == case["expected_health"]
            if "expected_cost" in case:
                assert item_data.recipe.total_cost == case["expected_cost"]