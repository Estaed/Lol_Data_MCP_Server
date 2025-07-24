"""
Simplified Item Data Scraper for League of Legends Wiki

This module provides a streamlined scraper for extracting item data
from the League of Legends Wiki with clean output and differentiated 
extraction for completed vs basic/epic items.

Redesigned for Task 2.2.1 with perfect name assumptions and simplified architecture.
"""

import asyncio
import json
import logging
import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException, 
    WebDriverException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError
except ImportError:
    from ..base_scraper import BaseScraper, WikiScraperError


class ItemType(Enum):
    """Item type classification for differentiated extraction"""
    COMPLETED = "completed"     # Legendary/Mythic items
    BASIC = "basic"            # Basic items (build into other items)
    EPIC = "epic"              # Epic items (intermediate tier)
    UNKNOWN = "unknown"


class ItemDataScraper(BaseScraper):
    """
    Simplified scraper for item data using direct page content analysis.
    Assumes perfect item names and leverages visible page information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def _build_item_url(self, item_name: str) -> str:
        """
        Build item URL following champion URL pattern.
        
        Args:
            item_name: Name of the item to build URL for
            
        Returns:
            Full URL to the item page
        """
        normalized_name = self._normalize_item_name(item_name)
        return f"{self.BASE_URL}{normalized_name}"
    
    def _normalize_item_name(self, name: str) -> str:
        """
        Normalize item name for wiki lookup using champion pattern.
        Example: "Doran's Blade" -> "Doran%27s_Blade", "Echoes of Helia" -> "Echoes_of_Helia" 
        """
        # Strip whitespace and split into words
        words = name.strip().split()
        
        # Small words that should not be capitalized in titles (except at start)
        small_words = {'of', 'the', 'and', 'in', 'on', 'at', 'to', 'for', 'with'}
        
        normalized_words = []
        for i, word in enumerate(words):
            # Always capitalize first word, otherwise check if it's a small word
            if i == 0 or word.lower() not in small_words:
                # Handle apostrophes correctly - don't title case after them
                if "'" in word:
                    parts = word.split("'")
                    parts[0] = parts[0].capitalize()
                    normalized_words.append("'".join(parts))
                else:
                    normalized_words.append(word.capitalize())
            else:
                # Keep small words lowercase
                normalized_words.append(word.lower())
        
        normalized = "_".join(normalized_words)
        
        # Handle apostrophes for URL compatibility (same as champion scraper)
        normalized = normalized.replace("'", "%27")
        
        return normalized

    def _detect_item_type_from_page(self, soup: BeautifulSoup) -> ItemType:
        """
        Simple item type detection leveraging visible page information.
        No complex classification - just check the obvious indicators.
        
        Args:
            soup: BeautifulSoup object of the item page
            
        Returns:
            ItemType classification
        """
        try:
            # Strategy 1: Check main text description (most reliable)
            # Pattern: "X is a [tier] item in League of Legends"
            main_text = soup.get_text().lower()
            
            if 'legendary item in' in main_text or 'mythic item in' in main_text:
                self.logger.debug("Detected completed item (legendary/mythic in description)")
                return ItemType.COMPLETED
            
            if 'basic item in' in main_text:
                self.logger.debug("Detected basic item (basic in description)")
                return ItemType.BASIC
                
            if 'epic item in' in main_text:
                self.logger.debug("Detected epic item (epic in description)")
                return ItemType.EPIC
            
            # Strategy 2: Check wgCategories in page script (very reliable)
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.get_text()
                if 'wgCategories' in script_text:
                    categories_match = re.search(r'"wgCategories":\[(.*?)\]', script_text)
                    if categories_match:
                        categories_str = categories_match.group(1).lower()
                        if 'legendary items' in categories_str or 'mythic items' in categories_str:
                            self.logger.debug("Detected completed item (wgCategories)")
                            return ItemType.COMPLETED
                        elif 'basic items' in categories_str:
                            self.logger.debug("Detected basic item (wgCategories)")
                            return ItemType.BASIC
                        elif 'epic items' in categories_str:
                            self.logger.debug("Detected epic item (wgCategories)")
                            return ItemType.EPIC
            
            # Strategy 3: Check category links at bottom of page
            category_links = soup.find_all('a', href=lambda x: x and '/Category:' in x)
            for link in category_links:
                category_text = link.get_text().lower()
                if 'legendary items' in category_text or 'mythic items' in category_text:
                    self.logger.debug("Detected completed item (category links)")
                    return ItemType.COMPLETED
                elif 'basic items' in category_text:
                    self.logger.debug("Detected basic item (category links)")
                    return ItemType.BASIC
                elif 'epic items' in category_text:
                    self.logger.debug("Detected epic item (category links)")
                    return ItemType.EPIC
            
            self.logger.warning("Could not determine item type from page")
            return ItemType.UNKNOWN
            
        except Exception as e:
            self.logger.error(f"Error detecting item type: {e}")
            return ItemType.UNKNOWN

    def _find_section_by_pattern(self, soup: BeautifulSoup, patterns: List[str]) -> Optional[Tag]:
        """
        Find section using pattern matching (following champion scraper approach).
        
        Args:
            soup: BeautifulSoup object to search
            patterns: List of pattern strings to match against
            
        Returns:
            Found section Tag or None
        """
        try:
            # Strategy 1: Look for MediaWiki headline spans
            headlines = soup.find_all('span', class_='mw-headline')
            for headline in headlines:
                headline_text = headline.get_text().lower().strip()
                if any(pattern in headline_text for pattern in patterns):
                    self.logger.debug(f"Found section via mw-headline: {headline_text}")
                    # Get the content after this header
                    header = headline.parent
                    return self._get_content_after_header(header)
            
            # Strategy 2: Look for header elements (h2, h3, h4)
            for header_tag in ['h2', 'h3', 'h4']:
                headers = soup.find_all(header_tag)
                for header in headers:
                    header_text = header.get_text().lower().strip()
                    if any(pattern in header_text for pattern in patterns):
                        self.logger.debug(f"Found section via {header_tag}: {header_text}")
                        return self._get_content_after_header(header)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding section: {e}")
            return None

    def _get_content_after_header(self, header: Tag) -> Optional[Tag]:
        """Get content section after a header element."""
        try:
            # Look for next sibling content elements
            current = header.next_sibling
            while current:
                if isinstance(current, Tag) and current.name in ['div', 'p', 'ul', 'ol', 'table', 'dl']:
                    # Check if this is content rather than another header
                    if not current.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        return current
                current = current.next_sibling
            
            # If no direct sibling, look for content in parent container
            if header.parent:
                following_elements = header.find_next_siblings()
                for element in following_elements:
                    if element.name in ['div', 'p', 'ul', 'ol', 'table', 'dl']:
                        return element
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting content after header: {e}")
            return None

    async def scrape_item_data(self, item_name: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main entry point for simplified item data scraping.
        
        Args:
            item_name: Perfect item name (e.g., "Echoes of Helia", "Kindlegem")
            sections: Optional list of specific sections to extract
            
        Returns:
            Dictionary with clean item data based on item type
        """
        self.logger.info(f"Scraping item data for: {item_name}")
        
        try:
            # Get page content (cached or fresh)
            url = self._build_item_url(item_name)
            html_content = await self._fetch_page_content(url)
            
            if not html_content:
                raise WikiScraperError(f"Failed to fetch content for item: {item_name}")
            
            # Parse HTML and detect item type
            soup = BeautifulSoup(html_content, 'html.parser')
            item_type = self._detect_item_type_from_page(soup)
            
            self.logger.info(f"Classified {item_name} as {item_type.value} item")
            
            # Extract data based on item type (differentiated extraction)
            if item_type == ItemType.COMPLETED:
                item_data = await self._extract_completed_item_data(soup, sections, url)
            elif item_type in [ItemType.BASIC, ItemType.EPIC]:
                item_data = await self._extract_basic_epic_item_data(soup, sections, url)
            else:
                # Fallback for unknown items
                item_data = self._extract_generic_item_data(soup, sections)
            
            # Format clean response (following champion pattern)
            response = {
                'item_name': item_name,
                'item_type': item_type.value,
                'data': item_data,
                'sections_available': list(item_data.keys()) if item_data else [],
                'data_source': 'wiki_item_scrape',
                'url': url,
                'timestamp': time.time()
            }
            
            self.logger.info(f"Successfully scraped {item_name} with {len(item_data)} sections")
            return response
            
        except Exception as e:
            self.logger.error(f"Error scraping item data for {item_name}: {e}")
            raise WikiScraperError(f"Failed to scrape item data: {e}")

    async def _extract_completed_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]], url: str) -> Dict[str, Any]:
        """
        Extract data for completed items (legendary/mythic).
        Requirements: stats, recipe, cost_analysis, notes, similar_items
        """
        data = {}
        
        # Extract item stats from infobox
        if not sections or 'stats' in sections:
            stats = self._extract_item_stats(soup)
            if stats:
                data['stats'] = stats
        
        # Extract recipe section
        if not sections or 'recipe' in sections:
            recipe = self._extract_recipe_section(soup)
            if recipe:
                data['recipe'] = recipe
        
        # Extract cost analysis (may need Selenium expansion)
        if not sections or 'cost_analysis' in sections:
            cost_analysis = await self._extract_cost_analysis(soup, url)
            if cost_analysis:
                data['cost_analysis'] = cost_analysis
        
        # Extract notes section
        if not sections or 'notes' in sections:
            notes = self._extract_notes_section(soup)
            if notes:
                data['notes'] = notes
        
        # Extract similar items
        if not sections or 'similar_items' in sections:
            similar_items = self._extract_similar_items_section(soup)
            if similar_items:
                data['similar_items'] = similar_items
        
        return data

    async def _extract_basic_epic_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]], url: str) -> Dict[str, Any]:
        """
        Extract data for basic/epic items.
        Requirements: stats, recipe, builds_info, cost_analysis, similar_items
        """
        data = {}
        
        # Extract item stats from infobox
        if not sections or 'stats' in sections:
            stats = self._extract_item_stats(soup)
            if stats:
                data['stats'] = stats
        
        # Extract recipe section (what it builds from)
        if not sections or 'recipe' in sections:
            recipe = self._extract_recipe_section(soup)
            if recipe:
                data['recipe'] = recipe
        
        # Extract builds info (what it builds into)
        if not sections or 'builds_info' in sections:
            builds_info = self._extract_builds_info_section(soup)
            if builds_info:
                data['builds_info'] = builds_info
        
        # Extract cost analysis (may need Selenium expansion)
        if not sections or 'cost_analysis' in sections:
            cost_analysis = await self._extract_cost_analysis(soup, url)
            if cost_analysis:
                data['cost_analysis'] = cost_analysis
        
        # Extract similar items
        if not sections or 'similar_items' in sections:
            similar_items = self._extract_similar_items_section(soup)
            if similar_items:
                data['similar_items'] = similar_items
        
        return data

    def _extract_generic_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]]) -> Dict[str, Any]:
        """Fallback extraction for unknown item types."""
        data = {}
        
        # Try to extract basic stats
        stats = self._extract_item_stats(soup)
        if stats:
            data['stats'] = stats
        
        # Try to extract any recognizable sections
        common_patterns = {
            'recipe': ['recipe', 'components'],
            'notes': ['notes', 'gameplay'],
            'similar_items': ['similar items', 'alternatives']
        }
        
        for section_name, patterns in common_patterns.items():
            if not sections or section_name in sections:
                section_content = self._find_section_by_pattern(soup, patterns)
                if section_content:
                    data[section_name] = section_content.get_text().strip()
        
        return data

    def _extract_item_stats(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract clean item statistics from infobox (following champion pattern).
        Returns clean stats format, not raw text/base_value format.
        """
        try:
            infobox = soup.find('div', class_='infobox')
            if not infobox:
                self.logger.warning("No infobox found for stats extraction")
                return None
            
            stats_data = {}
            
            # Extract item name from infobox title
            title_elem = infobox.find('div', class_='infobox-title')
            if title_elem:
                stats_data['name'] = title_elem.get_text().strip()
            
            # Extract description/flavor text
            description = self._extract_item_description(infobox)
            if description:
                stats_data['description'] = description
            
            # Extract tabbed stats (Base, Masterwork tabs - skip Total as it's redundant)
            tabber = infobox.find('div', class_='tabber')
            if tabber:
                tabs = tabber.find_all('div', class_='tabbertab')
                for tab in tabs:
                    tab_title = tab.get('data-title', '').strip().lower()
                    # FIXED: Skip 'total' tab - it's the same as masterwork_stats with calculated totals
                    if tab_title and tab_title != 'total':
                        tab_stats = self._extract_stats_from_tab(tab)
                        if tab_stats:
                            stats_data[f'{tab_title}_stats'] = tab_stats
            
            # Extract passive abilities
            passive = self._extract_passive_ability(infobox)
            if passive:
                stats_data['passive'] = passive
            
            # Extract cost and availability info
            cost_info = self._extract_cost_sell_info(infobox)
            if cost_info:
                stats_data.update(cost_info)
            
            return stats_data if stats_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting item stats: {e}")
            return None

    def _extract_item_description(self, infobox: Tag) -> Optional[str]:
        """Extract item description/flavor text."""
        try:
            # Look for data rows without labels (usually flavor text)
            data_rows = infobox.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                label_elem = row.find('div', class_='infobox-data-label')
                
                if value_elem and not label_elem:
                    # This is likely flavor text (no label)
                    text = value_elem.get_text().strip()
                    if len(text) > 20 and ('"' in text or text.count(' ') > 3):
                        return text
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting item description: {e}")
            return None

    def _extract_stats_from_tab(self, tab: Tag) -> Optional[Dict[str, Any]]:
        """Extract statistics from a tab with website-format display (e.g., '35 (+16.67)')."""
        try:
            stats = {}
            tab_title = tab.get('data-title', '').strip().lower()
            
            # Find stat rows within the tab
            data_rows = tab.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem:
                    stat_text = value_elem.get_text().strip()
                    
                    # Parse stat using website format
                    stat_info = self._parse_website_format_stat(stat_text, tab_title)
                    if stat_info:
                        stats[stat_info['name']] = stat_info['value']
            
            return stats if stats else None
            
        except Exception as e:
            self.logger.error(f"Error extracting stats from tab: {e}")
            return None

    def _parse_website_format_stat(self, stat_text: str, tab_type: str) -> Optional[Dict[str, Any]]:
        """
        FIXED: Parse stat text with correct HTML structure parsing.
        Examples: 
        - Base tab: "+35 ability power" -> {"name": "ability_power", "value": "35"}
        - Masterwork tab: Extract total from red spans -> {"name": "ability_power", "value": "51.67"}
        - Total tab: "+51.67 ability power" -> {"name": "ability_power", "value": "51.67"}
        """
        try:
            # FIXED: For masterwork tab, look for total values in red spans
            if tab_type == 'masterwork':
                # HTML structure: "+35 <span style="color: #E34D4C">(+16.67)</span> ability power"
                # We want to extract the total: 35 + 16.67 = 51.67
                
                # Extract base value
                base_match = re.match(r'([+-]?\d+(?:\.\d+)?)', stat_text.strip())
                if not base_match:
                    return None
                
                base_value = float(base_match.group(1))
                
                # Extract bonus value from parentheses (if exists)
                bonus_match = re.search(r'\(\+?([+-]?\d+(?:\.\d+)?)\)', stat_text)
                if bonus_match:
                    bonus_value = float(bonus_match.group(1))
                    total_value = base_value + bonus_value
                else:
                    total_value = base_value
                
                # Extract stat name (everything after the last number/parentheses)
                stat_name_match = re.search(r'(?:\([^)]*\))?\s*(.+)$', stat_text)
                if stat_name_match:
                    stat_name = stat_name_match.group(1).strip()
                else:
                    # Fallback: extract everything after base value
                    stat_name = re.sub(r'^[+-]?\d+(?:\.\d+)?(?:\s*\([^)]*\))?\s*', '', stat_text).strip()
                
                formatted_value = str(total_value) if total_value == int(total_value) else f"{total_value:.2f}"
                
            else:
                # For base and total tabs, extract normally
                pattern = r'([+-]?\d+(?:\.\d+)?)\s*(.+)'
                match = re.match(pattern, stat_text.strip())
                
                if not match:
                    return None
                    
                value_str, stat_name = match.groups()
                base_value = float(value_str)
                formatted_value = str(base_value) if base_value == int(base_value) else f"{base_value:.2f}"
            
            # Clean stat name
            stat_name = stat_name.strip().lower()
            stat_name = re.sub(r'[^\w\s%]', '', stat_name)  # Keep % for percentages
            stat_name = stat_name.replace(' ', '_')
            
            # Handle percentage stats specially
            if '%' in stat_text:
                if not formatted_value.endswith('%'):
                    formatted_value += '%'
            
            return {
                'name': stat_name,
                'value': formatted_value
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing website format stat '{stat_text}': {e}")
            return None

    def _estimate_bonus_value(self, base_value: float, stat_name: str) -> float:
        """
        Estimate bonus value for masterwork stats.
        This is a simplified estimation - real values would need base/masterwork comparison.
        """
        try:
            # Common bonus ratios for different stat types (approximations)
            bonus_ratios = {
                'ability_power': 0.476,  # ~16.67/35 = 0.476
                'ability_haste': 0.533,  # ~10.67/20 = 0.533
                'health': 0.625,         # ~125/200 = 0.625
                'attack_damage': 0.5,
                'armor': 0.5,
                'magic_resistance': 0.5,
                'mana': 0.4,
                'attack_speed': 0.3
            }
            
            # Get ratio for this stat type
            ratio = bonus_ratios.get(stat_name, 0.4)  # Default 40% bonus
            bonus = base_value * ratio
            
            # Round to reasonable precision
            return round(bonus, 2)
            
        except Exception as e:
            self.logger.error(f"Error estimating bonus value: {e}")
            return 0.0

    def _extract_passive_ability(self, infobox: Tag) -> Optional[Dict[str, str]]:
        """Extract passive ability information."""
        try:
            # Look for passive section in infobox
            passive_section = infobox.find('div', class_='infobox-header', string='Passive')
            if not passive_section:
                return None
            
            passive_content = passive_section.find_next_sibling('div', class_='infobox-section')
            if not passive_content:
                return None
            
            # Extract passive name and description
            passive_text = passive_content.get_text().strip()
            
            # Look for "Unique" prefix pattern
            if 'unique' in passive_text.lower():
                if ':' in passive_text:
                    parts = passive_text.split(':', 1)
                    return {
                        'name': parts[0].strip(),
                        'description': parts[1].strip()
                    }
            
            return {'description': passive_text}
            
        except Exception as e:
            self.logger.error(f"Error extracting passive ability: {e}")
            return None

    def _extract_cost_sell_info(self, infobox: Tag) -> Optional[Dict[str, Any]]:
        """Extract cost and sell information."""
        try:
            cost_info = {}
            
            # Look for cost/sell rows in infobox
            data_rows = infobox.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                label_elem = row.find('div', class_='infobox-data-label')
                value_elem = row.find('div', class_='infobox-data-value')
                
                if label_elem and value_elem:
                    label = label_elem.get_text().strip().lower()
                    value_text = value_elem.get_text().strip()
                    
                    if 'cost' in label:
                        cost_match = re.search(r'(\d+)', value_text)
                        if cost_match:
                            cost_info['cost'] = int(cost_match.group(1))
                    elif 'sell' in label:
                        sell_match = re.search(r'(\d+)', value_text)
                        if sell_match:
                            cost_info['sell_value'] = int(sell_match.group(1))
            
            return cost_info if cost_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost/sell info: {e}")
            return None

    def _extract_recipe_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract hierarchical recipe information with component relationships and costs."""
        try:
            recipe_section = self._find_section_by_pattern(soup, ['recipe', 'components'])
            if not recipe_section:
                return None
            
            # Look for recipe table structure
            recipe_table = recipe_section.find('table', style=lambda x: x and 'border-collapse' in x)
            if not recipe_table:
                recipe_table = recipe_section.find('table')
            
            if recipe_table:
                return self._parse_hierarchical_recipe_table(recipe_table)
            else:
                # Fallback to simple component extraction
                return self._extract_simple_recipe_fallback(recipe_section)
            
        except Exception as e:
            self.logger.error(f"Error extracting recipe section: {e}")
            return None

    def _parse_hierarchical_recipe_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """Parse the hierarchical recipe table structure to extract component relationships."""
        try:
            recipe_data = {
                'main_components': [],
                'total_cost': None,
                'combine_cost': None
            }
            
            # Find all item divs in the table
            item_divs = table.find_all('div', class_='item')
            
            # Group items by their position and relationships
            main_item = None
            components = []
            
            for item_div in item_divs:
                item_info = self._extract_detailed_item_from_div(item_div)
                if item_info:
                    # Determine if this is the main item or a component
                    if self._is_main_recipe_item(item_div, item_info):
                        main_item = item_info
                    else:
                        components.append(item_info)
            
            if main_item:
                recipe_data['total_cost'] = main_item.get('total_cost')
                recipe_data['combine_cost'] = main_item.get('combine_cost')
            
            # Group components into hierarchical structure
            recipe_data['main_components'] = self._group_components_hierarchically(components)
            
            return recipe_data if recipe_data['main_components'] or recipe_data['total_cost'] else None
            
        except Exception as e:
            self.logger.error(f"Error parsing hierarchical recipe table: {e}")
            return None

    def _extract_detailed_item_from_div(self, item_div: Tag) -> Optional[Dict[str, Any]]:
        """Extract detailed item information including costs and relationships."""
        try:
            item_info = {}
            
            # Extract item name - FIXED: Use correct HTML structure
            # HTML structure: <div class="item-icon name" data-item="Kindlegem"><b><a>Kindlegem</a></b></div>
            name_elem = item_div.find('div', class_='item-icon name')
            if name_elem:
                # Look for <b><a> structure first
                bold_elem = name_elem.find('b')
                if bold_elem:
                    link = bold_elem.find('a')
                    if link:
                        item_info['name'] = link.get_text().strip()
                    else:
                        item_info['name'] = bold_elem.get_text().strip()
                else:
                    # Fallback to any link in the name element
                    link = name_elem.find('a')
                    if link:
                        item_info['name'] = link.get_text().strip()
            
            # Also try data-item attribute as fallback
            if not item_info.get('name'):
                data_item_elem = item_div.find('[data-item]')
                if data_item_elem:
                    item_info['name'] = data_item_elem.get('data-item', '').strip()
            
            # Extract costs from gold element - FIXED: Better pattern matching
            gold_elem = item_div.find('div', class_='gold')
            if gold_elem:
                # Look for gold spans with specific structure
                gold_spans = gold_elem.find_all('span', style=lambda x: x and 'white-space:normal' in x)
                
                if gold_spans and len(gold_spans) >= 1:
                    # First span is total cost, second (if exists) is combine cost in parentheses
                    total_cost_text = gold_spans[0].get_text().strip()
                    try:
                        total_cost = int(total_cost_text)
                        item_info['total_cost'] = total_cost
                        
                        # Check for combine cost in parentheses pattern: "2200 (500)"
                        full_text = gold_elem.get_text().strip()
                        combine_match = re.search(r'\((\d+)\)', full_text)
                        if combine_match:
                            combine_cost = int(combine_match.group(1))
                            item_info['combine_cost'] = combine_cost
                            item_info['component_cost'] = total_cost - combine_cost
                    except ValueError:
                        # Fallback to original regex method
                        cost_text = gold_elem.get_text().strip()
                        cost_match = re.search(r'(\d+)(?:\s*\((\d+)\))?', cost_text)
                        if cost_match:
                            total_cost = int(cost_match.group(1))
                            combine_cost = int(cost_match.group(2)) if cost_match.group(2) else 0
                            
                            item_info['total_cost'] = total_cost
                            if combine_cost > 0:
                                item_info['combine_cost'] = combine_cost
                                item_info['component_cost'] = total_cost - combine_cost
            
            # Extract icon information
            icon_elem = item_div.find('span', class_='inline-image')
            if icon_elem:
                img = icon_elem.find('img')
                if img:
                    item_info['icon_url'] = img.get('src', '')
            
            return item_info if item_info.get('name') else None
            
        except Exception as e:
            self.logger.error(f"Error extracting detailed item from div: {e}")
            return None

    def _is_main_recipe_item(self, item_div: Tag, item_info: Dict[str, Any]) -> bool:
        """FIXED: Better detection of main item vs components using table structure."""
        try:
            # Strategy 1: Check table position - main item is typically in first row
            parent_row = item_div.find_parent('tr')
            if parent_row:
                table = item_div.find_parent('table')
                if table:
                    all_rows = table.find_all('tr')
                    if all_rows and parent_row == all_rows[0]:
                        # This is in the first row - likely main item
                        return True
            
            # Strategy 2: Check for golden border indicating main item
            border_elem = item_div.find('span', class_='border')
            if border_elem:
                style_attr = border_elem.get('style', '')
                # Golden border indicates main item (completed item)
                if '#FFD700' in style_attr or 'FFD700' in style_attr:
                    return True
            
            # Strategy 3: Check item cost - main item typically has highest cost
            if item_info.get('total_cost', 0) >= 2000:  # Completed items usually 2000+ gold
                return True
            
            # Strategy 4: Check for combine cost presence - main item has combine cost
            if item_info.get('combine_cost') is not None:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error determining main recipe item: {e}")
            return False

    def _group_components_hierarchically(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group components into hierarchical structure based on costs and relationships."""
        try:
            # Sort components by cost (higher cost items are usually intermediate components)
            components.sort(key=lambda x: x.get('total_cost', 0), reverse=True)
            
            main_components = []
            basic_components = []
            
            for component in components:
                total_cost = component.get('total_cost', 0)
                combine_cost = component.get('combine_cost', 0)
                
                # Items with combine costs are intermediate components
                if combine_cost > 0:
                    main_components.append(component)
                else:
                    # Basic components (no combine cost)
                    basic_components.append(component)
            
            # Try to associate basic components with intermediate components
            for main_comp in main_components:
                main_comp['sub_components'] = []
                component_cost = main_comp.get('component_cost', 0)
                
                # Find basic components that could build into this intermediate component
                remaining_basic = []
                for basic in basic_components:
                    basic_cost = basic.get('total_cost', 0)
                    # Simple heuristic: if basic component cost is reasonable for this intermediate
                    if basic_cost <= component_cost:
                        main_comp['sub_components'].append(basic['name'])
                    else:
                        remaining_basic.append(basic)
                
                basic_components = remaining_basic
            
            # Add any remaining basic components as direct components
            for basic in basic_components:
                main_components.append(basic)
            
            return main_components
            
        except Exception as e:
            self.logger.error(f"Error grouping components hierarchically: {e}")
            return components  # Return flat list as fallback

    def _extract_simple_recipe_fallback(self, recipe_section: Tag) -> Optional[Dict[str, Any]]:
        """Fallback method for simple recipe extraction when table parsing fails."""
        try:
            recipe_data = {
                'components': [],
                'total_cost': None
            }
            
            # Extract component links
            component_links = recipe_section.find_all('a')
            for link in component_links:
                href = link.get('href', '')
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    component_name = link.get_text().strip()
                    if component_name and component_name not in recipe_data['components']:
                        recipe_data['components'].append(component_name)
            
            # Extract total cost from gold values
            gold_values = re.findall(r'(\d+).*?gold', recipe_section.get_text().lower())
            if gold_values:
                costs = [int(val) for val in gold_values if 50 <= int(val) <= 5000]
                if costs:
                    recipe_data['total_cost'] = max(costs)
            
            return recipe_data if recipe_data['components'] else None
            
        except Exception as e:
            self.logger.error(f"Error in simple recipe fallback: {e}")
            return None

    def _extract_builds_info_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract builds into information (for basic/epic items)."""
        try:
            builds_section = self._find_section_by_pattern(soup, ['builds into', 'builds'])
            if not builds_section:
                return None
            
            builds_data = {
                'builds_into': []
            }
            
            # Extract item links
            item_links = builds_section.find_all('a')
            for link in item_links:
                href = link.get('href', '')
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    item_name = link.get_text().strip()
                    if item_name and item_name not in builds_data['builds_into']:
                        builds_data['builds_into'].append(item_name)
            
            return builds_data if builds_data['builds_into'] else None
            
        except Exception as e:
            self.logger.error(f"Error extracting builds info: {e}")
            return None

    async def _extract_cost_analysis(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract cost analysis with minimal Selenium integration if needed.
        First tries static HTML, then uses Selenium for expandable sections.
        """
        try:
            # Try static extraction first
            cost_section = self._find_section_by_pattern(soup, ['cost analysis', 'gold efficiency'])
            if cost_section:
                cost_data = self._parse_cost_data(cost_section)
                if cost_data and self._is_cost_data_complete(cost_data):
                    return cost_data
            
            # Look for expandable cost analysis sections
            expandable_elements = soup.find_all('div', class_='mw-collapsible')
            cost_expandable = None
            
            for element in expandable_elements:
                element_text = element.get_text()[:200].lower()
                if 'cost' in element_text or 'efficiency' in element_text:
                    cost_expandable = element
                    break
            
            if cost_expandable:
                # Use minimal Selenium expansion
                return await self._expand_cost_analysis_with_selenium(url)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost analysis: {e}")
            return None

    def _parse_cost_data(self, section: Tag) -> Optional[Dict[str, Any]]:
        """Parse comprehensive cost analysis data from section - FIXED for correct HTML structure."""
        try:
            cost_data = {}
            
            # Look for collapsible content first
            collapsible_content = section.find('div', class_='mw-collapsible-content')
            if collapsible_content:
                section_content = collapsible_content
            else:
                section_content = section
            
            section_text = section_content.get_text()
            
            # FIXED: Extract main efficiency percentage with better pattern
            efficiency_match = re.search(r'(\d+(?:\.\d+)?)%.*?gold\s+efficient', section_text, re.IGNORECASE)
            if efficiency_match:
                cost_data['efficiency_percentage'] = float(efficiency_match.group(1))
            
            # FIXED: Extract total gold value (not total cost) - look for "Total Gold Value = XXXX"
            total_gold_match = re.search(r'total\s+gold\s+value.*?(\d+(?:\.\d+)?)', section_text, re.IGNORECASE)
            if total_gold_match:
                total_gold_value = float(total_gold_match.group(1))
                
                # Extract stat efficiency with correct structure
                stat_efficiency = self._extract_stat_efficiency_breakdown_fixed(section_content, total_gold_value)
                if stat_efficiency:
                    cost_data['stat_efficiency'] = stat_efficiency
            
            # Extract individual stat values from the unordered list
            gold_breakdown = self._extract_gold_breakdown_fixed(section_content)
            if gold_breakdown:
                cost_data['gold_breakdown'] = gold_breakdown
            
            # Extract passive value information if available
            passive_value = self._extract_passive_value_info(section_text)
            if passive_value:
                cost_data['passive_value'] = passive_value
            
            return cost_data if cost_data else None
            
        except Exception as e:
            self.logger.error(f"Error parsing cost data: {e}")
            return None

    def _extract_stat_efficiency_breakdown(self, section: Tag, section_text: str) -> Optional[Dict[str, Any]]:
        """Extract individual stat efficiency values."""
        try:
            stat_efficiency = {}
            
            # Look for patterns like "35 ability power = 761.25 gold" or "35 (+16.67) ability power = 1127.5 gold"
            stat_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:\(\+\d+(?:\.\d+)?\))?\s*([^=]+?)\s*=\s*(\d+(?:\.\d+)?)\s*gold',
                r'(\d+(?:\.\d+)?)\s*([^:]+?):\s*(\d+(?:\.\d+)?)\s*gold',
                r'([^:]+?):\s*(\d+(?:\.\d+)?)\s*(?:\(\+\d+(?:\.\d+)?\))?\s*=\s*(\d+(?:\.\d+)?)\s*gold'
            ]
            
            for pattern in stat_patterns:
                matches = re.findall(pattern, section_text, re.IGNORECASE)
                for match in matches:
                    if len(match) == 3:
                        if match[0].replace('.', '').isdigit():  # Value, stat, gold
                            value, stat_name, gold_value = match
                        else:  # Stat, value, gold
                            stat_name, value, gold_value = match
                        
                        # Clean up stat name
                        clean_stat = stat_name.strip().lower()
                        clean_stat = re.sub(r'[^\w\s%]', '', clean_stat)
                        clean_stat = clean_stat.replace(' ', '_')
                        
                        if clean_stat and value and gold_value:
                            stat_efficiency[clean_stat] = {
                                'stat_value': float(value),
                                'gold_value': float(gold_value),
                                'efficiency': round((float(gold_value) / float(value) if float(value) > 0 else 0), 2)
                            }
            
            return stat_efficiency if stat_efficiency else None
            
        except Exception as e:
            self.logger.error(f"Error extracting stat efficiency breakdown: {e}")
            return None

    def _extract_gold_breakdown(self, section: Tag, section_text: str) -> Optional[Dict[str, Any]]:
        """Extract gold value breakdown from cost analysis."""
        try:
            gold_breakdown = {}
            
            # Look for total gold value
            total_match = re.search(r'(?:total|worth)\s*:\s*(\d+(?:\.\d+)?)\s*gold', section_text, re.IGNORECASE)
            if total_match:
                gold_breakdown['total_value'] = float(total_match.group(1))
            
            # Look for stats gold value
            stats_match = re.search(r'stats?\s*:\s*(\d+(?:\.\d+)?)\s*gold', section_text, re.IGNORECASE)
            if stats_match:
                gold_breakdown['stats_value'] = float(stats_match.group(1))
            
            # Look for passive value (if mentioned)
            passive_match = re.search(r'passive\s*:\s*(\d+(?:\.\d+)?)\s*gold', section_text, re.IGNORECASE)
            if passive_match:
                gold_breakdown['passive_value'] = float(passive_match.group(1))
            
            # Calculate efficiency if we have both total value and cost
            if 'total_value' in gold_breakdown:
                # Try to find the item cost
                cost_matches = re.findall(r'(\d+)\s*gold', section_text)
                if cost_matches:
                    costs = [int(cost) for cost in cost_matches if 1000 <= int(cost) <= 5000]
                    if costs:
                        item_cost = max(costs)  # Assume highest reasonable cost is item cost
                        gold_breakdown['item_cost'] = item_cost
                        if item_cost > 0:
                            gold_breakdown['efficiency_ratio'] = round(gold_breakdown['total_value'] / item_cost, 3)
            
            return gold_breakdown if gold_breakdown else None
            
        except Exception as e:
            self.logger.error(f"Error extracting gold breakdown: {e}")
            return None

    def _extract_passive_value_info(self, section_text: str) -> Optional[Dict[str, Any]]:
        """Extract information about passive ability value."""
        try:
            passive_info = {}
            
            # Look for passive mentions
            if 'passive' in section_text.lower():
                # Check if passive is valued or not valued
                if any(phrase in section_text.lower() for phrase in ['passive not', 'no passive', 'passive: 0']):
                    passive_info['is_valued'] = False
                    passive_info['note'] = "Passive ability not included in gold efficiency calculation"
                elif 'passive' in section_text.lower() and 'gold' in section_text.lower():
                    passive_info['is_valued'] = True
                    
                    # Try to extract passive description
                    passive_desc_match = re.search(r'passive[^.]*?([^.]{10,100})', section_text, re.IGNORECASE)
                    if passive_desc_match:
                        passive_info['description'] = passive_desc_match.group(1).strip()
            
            return passive_info if passive_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting passive value info: {e}")
            return None
    
    def _extract_stat_efficiency_breakdown_fixed(self, section: Tag, total_gold_value: float) -> Optional[Dict[str, Any]]:
        """FIXED: Extract stat efficiency with correct HTML parsing."""
        try:
            stat_efficiency = {}
            
            # Look for unordered list with stat breakdown
            ul_elements = section.find_all('ul')
            for ul in ul_elements:
                li_elements = ul.find_all('li')
                for li in li_elements:
                    li_text = li.get_text().strip()
                    
                    # Match patterns like "35 ability power = 700 gold"
                    stat_match = re.match(r'(\d+(?:\.\d+)?)\s*([^=]+?)\s*=\s*(\d+(?:\.\d+)?)', li_text)
                    if stat_match:
                        stat_value, stat_name, gold_value = stat_match.groups()
                        
                        # Clean stat name
                        clean_stat = stat_name.strip().lower()
                        clean_stat = re.sub(r'[^\w\s%]', '', clean_stat)
                        clean_stat = clean_stat.replace(' ', '_')
                        
                        if clean_stat != 'total_gold_value':  # Skip total line
                            stat_efficiency[clean_stat] = {
                                'stat_value': float(stat_value),
                                'gold_value': float(gold_value),
                                'efficiency': round(float(gold_value) / float(stat_value) if float(stat_value) > 0 else 0, 2)
                            }
            
            # Add total gold value information
            if stat_efficiency:
                stat_efficiency['total_gold_value'] = {
                    'stat_value': total_gold_value,
                    'gold_value': total_gold_value,
                    'efficiency': 1.0
                }
            
            return stat_efficiency if stat_efficiency else None
            
        except Exception as e:
            self.logger.error(f"Error extracting fixed stat efficiency breakdown: {e}")
            return None
    
    def _extract_gold_breakdown_fixed(self, section: Tag) -> Optional[Dict[str, Any]]:
        """FIXED: Extract gold breakdown with correct HTML parsing."""
        try:
            gold_breakdown = {}
            
            # Look for individual stat costs in list items
            ul_elements = section.find_all('ul')
            for ul in ul_elements:
                li_elements = ul.find_all('li')
                for li in li_elements:
                    li_text = li.get_text().strip()
                    
                    # Check for total gold value
                    if 'total gold value' in li_text.lower():
                        total_match = re.search(r'(\d+(?:\.\d+)?)', li_text)
                        if total_match:
                            gold_breakdown['total_gold_value'] = float(total_match.group(1))
                    
                    # Check for individual stats
                    stat_match = re.match(r'(\d+(?:\.\d+)?)\s*([^=]+?)\s*=\s*(\d+(?:\.\d+)?)', li_text)
                    if stat_match:
                        stat_value, stat_name, gold_value = stat_match.groups()
                        clean_stat = stat_name.strip().lower().replace(' ', '_')
                        clean_stat = re.sub(r'[^\w%]', '', clean_stat)
                        
                        if clean_stat:
                            gold_breakdown[f'{clean_stat}_value'] = float(gold_value)
            
            return gold_breakdown if gold_breakdown else None
            
        except Exception as e:
            self.logger.error(f"Error extracting fixed gold breakdown: {e}")
            return None

    def _is_cost_data_complete(self, cost_data: Dict[str, Any]) -> bool:
        """Check if cost data appears complete."""
        return bool(
            cost_data.get('efficiency_percentage') or 
            cost_data.get('stat_efficiency') or 
            cost_data.get('gold_breakdown')
        )

    async def _expand_cost_analysis_with_selenium(self, url: str) -> Optional[Dict[str, Any]]:
        """Use minimal Selenium to expand cost analysis section."""
        driver = None
        try:
            self.logger.info("Using Selenium for cost analysis expansion")
            
            driver = self._create_selenium_driver()
            driver.get(url)
            
            # Find and click expandable cost analysis
            try:
                toggle_element = driver.find_element(
                    By.CSS_SELECTOR, 
                    '.mw-collapsible-toggle, [class*="toggle"], [class*="expand"]'
                )
                driver.execute_script("arguments[0].click();", toggle_element)
                time.sleep(1.5)  # Wait for expansion
            except NoSuchElementException:
                self.logger.debug("No expandable element found")
            
            # Parse expanded content
            expanded_soup = BeautifulSoup(driver.page_source, 'html.parser')
            cost_section = self._find_section_by_pattern(expanded_soup, ['cost analysis', 'gold efficiency'])
            
            if cost_section:
                return self._parse_cost_data(cost_section)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in Selenium cost analysis expansion: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _extract_notes_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """ENHANCED: Extract notes/gameplay information including map-specific differences."""
        try:
            notes_data = {
                'gameplay_notes': [],
                'interactions': [],
                'map_specific_differences': {}
            }
            
            # Extract main Notes section with enhanced Soul Siphon detection
            notes_section = self._find_section_by_pattern(soup, ['notes', 'gameplay'])
            if notes_section:
                # ENHANCED: Look for Soul Siphon specific mechanics first
                soul_siphon_notes = self._extract_soul_siphon_details(notes_section)
                if soul_siphon_notes:
                    notes_data['gameplay_notes'].extend(soul_siphon_notes)
                
                # Extract from lists
                note_lists = notes_section.find_all(['ul', 'ol'])
                for note_list in note_lists:
                    items = note_list.find_all('li')
                    for item in items:
                        note_text = item.get_text().strip()
                        if note_text:
                            # Skip if already captured in Soul Siphon details
                            if not any(existing in note_text for existing in notes_data['gameplay_notes']):
                                if any(keyword in note_text.lower() for keyword in ['damage', 'heal', 'shield', 'effect', 'siphon', 'missile', 'projectile']):
                                    notes_data['gameplay_notes'].append(note_text)
                                else:
                                    notes_data['interactions'].append(note_text)
                
                # Extract from paragraphs
                paragraphs = notes_section.find_all('p')
                for para in paragraphs:
                    para_text = para.get_text().strip()
                    if para_text and len(para_text) > 10:
                        # Skip if already captured
                        if not any(existing in para_text for existing in notes_data['gameplay_notes']):
                            notes_data['gameplay_notes'].append(para_text)
            
            # ADDED: Extract Map-Specific Differences section
            map_section = self._find_section_by_pattern(soup, ['map-specific differences', 'map differences'])
            if map_section:
                map_differences = self._extract_map_specific_differences(map_section)
                if map_differences:
                    notes_data['map_specific_differences'] = map_differences
            
            # Remove empty categories
            notes_data = {k: v for k, v in notes_data.items() if v}
            
            return notes_data if notes_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting notes section: {e}")
            return None

    def _extract_soul_siphon_details(self, notes_section: Tag) -> List[str]:
        """ENHANCED: Extract detailed Soul Siphon passive mechanics from Notes section."""
        try:
            soul_siphon_notes = []
            
            # Look for lists containing Soul Siphon mechanics
            note_lists = notes_section.find_all(['ul', 'ol'])
            for note_list in note_lists:
                items = note_list.find_all('li')
                for item in items:
                    item_text = item.get_text().strip()
                    
                    # Check if this note mentions Soul Siphon mechanics
                    if any(keyword in item_text for keyword in ['Soul Siphon', 'soul siphon']):
                        # Extract nested mechanics (sub-lists under Soul Siphon items)
                        nested_lists = item.find_all(['ul', 'ol'])
                        if nested_lists:
                            # Add main Soul Siphon mechanic
                            main_text = item_text
                            # Remove nested list text from main text
                            for nested_list in nested_lists:
                                nested_text = nested_list.get_text().strip()
                                main_text = main_text.replace(nested_text, '').strip()
                            
                            soul_siphon_notes.append(main_text)
                            
                            # Add nested mechanics as separate notes
                            for nested_list in nested_lists:
                                nested_items = nested_list.find_all('li')
                                for nested_item in nested_items:
                                    nested_text = nested_item.get_text().strip()
                                    if nested_text:
                                        soul_siphon_notes.append(f"  • {nested_text}")
                        else:
                            # Simple Soul Siphon note without nested mechanics
                            soul_siphon_notes.append(item_text)
            
            # Also check for Soul Siphon in paragraph text
            paragraphs = notes_section.find_all('p')
            for para in paragraphs:
                para_text = para.get_text().strip()
                if 'Soul Siphon' in para_text and len(para_text) > 20:
                    soul_siphon_notes.append(para_text)
            
            return soul_siphon_notes
            
        except Exception as e:
            self.logger.error(f"Error extracting Soul Siphon details: {e}")
            return []
    
    def _extract_map_specific_differences(self, section: Tag) -> Optional[Dict[str, Any]]:
        """Extract map-specific differences from the section."""
        try:
            map_differences = {}
            
            # Look for dl/dt structure for different maps
            dl_elements = section.find_all('dl')
            for dl in dl_elements:
                dt_element = dl.find('dt')
                if dt_element:
                    # Extract map name - look for glossary spans or direct text
                    map_name = None
                    glossary_span = dt_element.find('span', class_='glossary')
                    if glossary_span:
                        link = glossary_span.find('a')
                        if link:
                            map_name = link.get_text().strip()
                    
                    if not map_name:
                        map_name = dt_element.get_text().strip()
                        # Clean up map name (remove "differences" text)
                        map_name = re.sub(r'\s*differences?\s*.*', '', map_name, flags=re.IGNORECASE)
                    
                    if map_name:
                        # Extract changes - look for following ul elements
                        changes = []
                        ul_elements = dl.find_all('ul')
                        for ul in ul_elements:
                            li_elements = ul.find_all('li')
                            for li in li_elements:
                                change_text = li.get_text().strip()
                                if change_text:
                                    changes.append(change_text)
                        
                        if changes:
                            map_differences[map_name.lower().replace(' ', '_')] = changes
            
            return map_differences if map_differences else None
            
        except Exception as e:
            self.logger.error(f"Error extracting map-specific differences: {e}")
            return None

    def _extract_similar_items_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract similar items recommendations."""
        try:
            similar_section = self._find_section_by_pattern(soup, ['similar items', 'alternatives'])
            if not similar_section:
                return None
            
            similar_data = {
                'related_items': []
            }
            
            # Extract item links
            item_links = similar_section.find_all('a')
            for link in item_links:
                href = link.get('href', '')
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    item_name = link.get_text().strip()
                    if item_name and item_name not in similar_data['related_items']:
                        similar_data['related_items'].append(item_name)
            
            return similar_data if similar_data['related_items'] else None
            
        except Exception as e:
            self.logger.error(f"Error extracting similar items: {e}")
            return None

    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content from URL (with caching)."""
        try:
            await self._ensure_client()
            response = await self._make_request(url)
            return response.text
        except Exception as e:
            self.logger.error(f"Error fetching page content from {url}: {e}")
            return None