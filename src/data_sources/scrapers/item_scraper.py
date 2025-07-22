"""
Item Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting comprehensive item data
from individual League of Legends item pages, including stats, passive abilities,
recipe information, and availability details.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError


@dataclass
class ItemStats:
    """Individual item statistics and bonuses"""
    attack_damage: Optional[float] = None
    ability_power: Optional[float] = None
    health: Optional[float] = None
    mana: Optional[float] = None
    armor: Optional[float] = None
    magic_resist: Optional[float] = None
    attack_speed: Optional[float] = None
    critical_strike_chance: Optional[float] = None
    movement_speed: Optional[float] = None
    life_steal: Optional[float] = None
    omnivamp: Optional[float] = None
    ability_haste: Optional[float] = None
    health_regen: Optional[float] = None
    mana_regen: Optional[float] = None
    lethality: Optional[float] = None
    magic_penetration: Optional[float] = None
    armor_penetration: Optional[float] = None
    # Special stats
    raw_stats: Dict[str, str] = field(default_factory=dict)  # Raw stat text from page


@dataclass  
class ItemPassive:
    """Item passive or active ability"""
    name: Optional[str] = None
    description: str = ""
    ability_type: str = "passive"  # "passive" or "active"
    cooldown: Optional[str] = None
    raw_text: str = ""  # Original text from page


@dataclass
class ItemRecipe:
    """Item recipe and component information"""
    total_cost: Optional[int] = None
    combine_cost: Optional[int] = None
    sell_price: Optional[int] = None
    components: List[str] = field(default_factory=list)
    builds_into: List[str] = field(default_factory=list)


@dataclass
class ItemAvailability:
    """Item availability and restrictions"""
    game_modes: List[str] = field(default_factory=list)
    map_availability: List[str] = field(default_factory=list)
    restrictions: List[str] = field(default_factory=list)
    

@dataclass
class ItemData:
    """Complete item data from individual item page"""
    name: str
    item_id: Optional[str] = None
    tier: Optional[str] = None  # "Starter", "Basic", "Epic", "Legendary", "Mythic"
    
    # Core information
    stats: ItemStats = field(default_factory=ItemStats)
    passive: Optional[ItemPassive] = None
    active: Optional[ItemPassive] = None  # For active items
    recipe: ItemRecipe = field(default_factory=ItemRecipe)
    availability: ItemAvailability = field(default_factory=ItemAvailability)
    
    # Additional data
    description: str = ""
    flavor_text: str = ""
    keywords: List[str] = field(default_factory=list)
    image_url: Optional[str] = None
    
    # Metadata
    scraped_at: datetime = field(default_factory=datetime.now)
    source_url: str = ""
    raw_infobox_data: Dict[str, str] = field(default_factory=dict)  # For debugging


class ItemScraper(BaseScraper):
    """Scraper for individual LoL item pages"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_item(self, item_name: str, item_url: Optional[str] = None) -> ItemData:
        """
        Scrape comprehensive item data from individual item page.
        
        Args:
            item_name: Name of the item to scrape
            item_url: Optional relative URL path (from Task 2.2.1), if not provided will be generated
            
        Returns:
            ItemData: Complete item information
        """
        self.logger.info(f"Starting item scraping for: {item_name}")
        
        try:
            # Build URL
            if item_url:
                # Use provided URL from Task 2.2.1 url_mappings
                # item_url already contains the full path like "/en-us/Cull"
                full_url = f"https://wiki.leagueoflegends.com{item_url}"
            else:
                # Generate URL using name normalization
                normalized_name = self._normalize_item_name(item_name)
                full_url = urljoin(self.BASE_URL, normalized_name)
            
            # Fetch the item page
            soup = await self._fetch_item_page(full_url)
            
            # Parse the item data
            item_data = self._parse_item_data(soup, item_name, full_url)
            
            self.logger.info(f"Successfully scraped item: {item_name}")
            return item_data
            
        except Exception as e:
            self.logger.error(f"Failed to scrape item {item_name}: {e}")
            raise WikiScraperError(f"Item scraping failed for {item_name}: {e}") from e

    async def _fetch_item_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse an individual item page"""
        await self._ensure_client()
        
        try:
            response = await self._make_request(url)
            content = response.text
            soup = BeautifulSoup(content, "lxml")
            
            # Validate we have expected item page structure
            infobox = soup.find("div", class_="infobox")
            if not infobox:
                raise WikiScraperError(f"No infobox found on item page: {url}")
            
            self.logger.debug(f"Successfully fetched item page: {url}")
            return soup
            
        except Exception as e:
            self.logger.error(f"Failed to fetch item page {url}: {e}")
            raise WikiScraperError(f"Failed to fetch item page: {e}") from e

    def _parse_item_data(self, soup: BeautifulSoup, item_name: str, source_url: str) -> ItemData:
        """Parse complete item data from page soup"""
        
        # Find main infobox
        main_infobox = soup.find("div", class_="infobox")
        if not main_infobox:
            raise WikiScraperError("Main infobox not found")
        
        # Initialize item data
        item_data = ItemData(name=item_name, source_url=source_url)
        
        # Parse basic info
        self._parse_basic_info(main_infobox, item_data)
        
        # Parse infobox sections
        self._parse_infobox_sections(main_infobox, item_data)
        
        # Parse additional content
        self._parse_additional_content(soup, item_data)
        
        self.logger.debug(f"Parsed item data for: {item_name}")
        return item_data

    def _parse_basic_info(self, infobox: Tag, item_data: ItemData) -> None:
        """Parse basic item information from infobox"""
        
        # Item title
        title_elem = infobox.find("div", class_="infobox-title")
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title:
                item_data.name = title
        
        # Item image
        image_elem = infobox.find("div", class_="infobox-image")
        if image_elem:
            img_tag = image_elem.find("img")
            if img_tag and img_tag.get("src"):
                # Convert relative URL to absolute
                src = img_tag.get("src")
                if src.startswith("/"):
                    item_data.image_url = f"https://wiki.leagueoflegends.com{src}"
                else:
                    item_data.image_url = src

    def _parse_infobox_sections(self, infobox: Tag, item_data: ItemData) -> None:
        """Parse organized infobox sections (Stats, Passive, Recipe, etc.)"""
        
        # Get all sections based on actual infobox structure
        current_section = None
        sections = {}
        
        for child in infobox.children:
            if not hasattr(child, 'name') or not child.name:
                continue
                
            # Check for section headers
            if 'infobox-header' in child.get('class', []):
                current_section = child.get_text(strip=True).lower()
                sections[current_section] = []
            
            # Check for section content divs (different types)
            elif current_section and any(cls in child.get('class', []) for cls in [
                'infobox-section-stacked', 'infobox-section', 
                'infobox-section-cell', 'infobox-section-cell-row'
            ]):
                sections[current_section].append(child)
        
        # Parse each section
        for section_name, section_divs in sections.items():
            self._parse_section_content(section_name, section_divs, item_data)

    def _parse_section_content(self, section_name: str, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse content from a specific infobox section"""
        
        if section_name == "stats":
            self._parse_stats_section(section_divs, item_data)
        elif section_name == "passive":
            self._parse_passive_section(section_divs, item_data)
        elif section_name == "recipe":
            self._parse_recipe_section(section_divs, item_data)
        elif section_name == "availability":
            self._parse_availability_section(section_divs, item_data)
        elif section_name == "keywords":
            self._parse_keywords_section(section_divs, item_data)
        elif section_name == "menu":
            self._parse_menu_section(section_divs, item_data)
        else:
            # Store raw data for unknown sections
            self._parse_general_section(section_name, section_divs, item_data)

    def _parse_stats_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse item statistics from section divs"""
        
        for section_div in section_divs:
            # Get all text from the section
            section_text = section_div.get_text(strip=True)
            if not section_text:
                continue
            
            # Store raw stat text for debugging
            item_data.stats.raw_stats[f"stats_section_{len(item_data.stats.raw_stats)}"] = section_text
            
            # Parse specific stats from the combined text
            self._parse_stat_value(section_text, item_data.stats)
            
            # Also look for individual data rows within the section
            data_rows = section_div.find_all("div", class_="infobox-data-row")
            for row in data_rows:
                value_elem = row.find("div", class_="infobox-data-value")
                if value_elem:
                    value_text = value_elem.get_text(strip=True)
                    if value_text:
                        item_data.stats.raw_stats[f"row_{len(item_data.stats.raw_stats)}"] = value_text
                        self._parse_stat_value(value_text, item_data.stats)

    def _parse_stat_value(self, stat_text: str, stats: ItemStats) -> None:
        """Parse individual stat values from text"""
        
        # Common stat patterns with regex
        stat_patterns = [
            (r'(\d+\.?\d*)\s*attack\s*damage', 'attack_damage'),
            (r'(\d+\.?\d*)\s*ability\s*power', 'ability_power'),
            (r'(\d+\.?\d*)\s*health(?!\s*on)', 'health'),  # Avoid "health on-hit"
            (r'(\d+\.?\d*)\s*mana', 'mana'),
            (r'(\d+\.?\d*)\s*armor', 'armor'),
            (r'(\d+\.?\d*)\s*magic\s*resist', 'magic_resist'),
            (r'(\d+\.?\d*)%\s*attack\s*speed', 'attack_speed'),
            (r'(\d+\.?\d*)%\s*critical\s*strike', 'critical_strike_chance'),
            (r'(\d+\.?\d*)\s*movement\s*speed', 'movement_speed'),
            (r'(\d+\.?\d*)%\s*life\s*steal', 'life_steal'),
            (r'(\d+\.?\d*)\s*ability\s*haste', 'ability_haste'),
            (r'(\d+\.?\d*)\s*lethality', 'lethality'),
        ]
        
        stat_text_lower = stat_text.lower()
        
        for pattern, stat_name in stat_patterns:
            match = re.search(pattern, stat_text_lower)
            if match:
                try:
                    value = float(match.group(1))
                    setattr(stats, stat_name, value)
                    self.logger.debug(f"Parsed {stat_name}: {value}")
                except ValueError:
                    self.logger.warning(f"Failed to parse stat value: {match.group(1)}")

    def _parse_passive_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse passive ability information from section divs"""
        
        for section_div in section_divs:
            passive_text = section_div.get_text(strip=True)
            if passive_text:
                # Create passive ability object
                passive = ItemPassive(
                    description=passive_text,
                    raw_text=passive_text,
                    ability_type="passive"
                )
                
                # Try to extract passive name (often starts with "Unique -")
                if passive_text.lower().startswith("unique"):
                    # Look for pattern like "Unique – Name: Description"
                    name_match = re.match(r'unique\s*[-–]\s*([^:]+):', passive_text, re.IGNORECASE)
                    if name_match:
                        passive.name = name_match.group(1).strip()
                
                item_data.passive = passive
                break  # Usually only one passive per item

    def _parse_recipe_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse recipe and cost information from section divs"""
        
        for section_div in section_divs:
            # Look for data rows within the section
            data_rows = section_div.find_all("div", class_="infobox-data-row")
            for row in data_rows:
                label_elem = row.find("div", class_="infobox-data-label")
                value_elem = row.find("div", class_="infobox-data-value")
                
                if not value_elem:
                    continue
                    
                label_text = label_elem.get_text(strip=True) if label_elem else ""
                value_text = value_elem.get_text(strip=True)
                
                # Parse cost information
                if "cost" in label_text.lower():
                    cost_match = re.search(r'(\d+)', value_text)
                    if cost_match:
                        item_data.recipe.total_cost = int(cost_match.group(1))
                
                elif "sell" in label_text.lower():
                    sell_match = re.search(r'(\d+)', value_text)
                    if sell_match:
                        item_data.recipe.sell_price = int(sell_match.group(1))
                
                elif "id" in label_text.lower():
                    item_data.item_id = value_text
            
            # If no data rows found, try parsing from raw text
            if not data_rows:
                section_text = section_div.get_text(strip=True)
                # Look for patterns like "Cost450Sell180ID1083"
                cost_match = re.search(r'cost(\d+)', section_text, re.IGNORECASE)
                if cost_match:
                    item_data.recipe.total_cost = int(cost_match.group(1))
                
                sell_match = re.search(r'sell(\d+)', section_text, re.IGNORECASE) 
                if sell_match:
                    item_data.recipe.sell_price = int(sell_match.group(1))
                
                id_match = re.search(r'id(\d+)', section_text, re.IGNORECASE)
                if id_match:
                    item_data.item_id = id_match.group(1)

    def _parse_availability_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse item availability and game mode restrictions from section divs"""
        
        for section_div in section_divs:
            availability_text = section_div.get_text(strip=True)
            if availability_text:
                # Parse game modes (e.g., "SR 5v5", "ARAM", etc.)
                if any(mode in availability_text.upper() for mode in ["SR", "ARAM", "FGM", "5V5"]):
                    # Split by spaces and common separators
                    modes = re.findall(r'[A-Z0-9]+(?:\s+[A-Z0-9]+)*', availability_text.upper())
                    item_data.availability.game_modes.extend(modes)

    def _parse_keywords_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse item keywords and tags from section divs"""
        
        for section_div in section_divs:
            keywords_text = section_div.get_text(strip=True)
            if keywords_text:
                # Split keywords and clean them
                keywords = [kw.strip() for kw in re.split(r'[,\s]+', keywords_text) if kw.strip()]
                item_data.keywords.extend(keywords)

    def _parse_menu_section(self, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse menu/category information from section divs"""
        
        for section_div in section_divs:
            menu_text = section_div.get_text(strip=True)
            if menu_text:
                # This often contains category info like "FighterMarksmanAssassin"
                # Split on capital letters to separate categories
                categories = re.findall(r'[A-Z][a-z]+', menu_text)
                if categories:
                    item_data.keywords.extend(categories)

    def _parse_general_section(self, section_name: str, section_divs: List[Tag], item_data: ItemData) -> None:
        """Parse data from unknown/general sections"""
        
        for i, section_div in enumerate(section_divs):
            section_text = section_div.get_text(strip=True)
            if section_text:
                item_data.raw_infobox_data[f"{section_name}_section_{i}"] = section_text

    def _parse_additional_content(self, soup: BeautifulSoup, item_data: ItemData) -> None:
        """Parse additional content outside the main infobox"""
        
        # Look for item description in main content
        content_area = soup.find("div", class_="mw-content-text")
        if content_area:
            # Find paragraphs that might contain descriptions
            paragraphs = content_area.find_all("p")
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:  # Meaningful description
                    if not item_data.description:  # Use first meaningful paragraph
                        item_data.description = text
                    break

    def _normalize_item_name(self, name: str) -> str:
        """Normalize item name for URL generation (similar to champion name normalization)"""
        # Strip whitespace but preserve original casing for most characters
        normalized = name.strip()
        
        # Replace spaces with underscores
        normalized = normalized.replace(' ', '_')
        
        # Handle apostrophes for URL compatibility
        normalized = normalized.replace("'", "%27")
        
        return normalized