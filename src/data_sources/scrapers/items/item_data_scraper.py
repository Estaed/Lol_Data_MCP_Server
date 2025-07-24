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
        FIXED: Parse stat text with readable structure for masterwork stats.
        Examples: 
        - Base tab: "+35 ability power" -> {"name": "ability_power", "value": "35.0"}
        - Masterwork tab: "+35 (+16.67) ability power" -> {"name": "ability_power", "value": {"base": 35.0, "bonus": 16.67, "total": 51.67}}
        """
        try:
            # Extract base value
            base_match = re.match(r'([+-]?\d+(?:\.\d+)?)', stat_text.strip())
            if not base_match:
                return None
            
            base_value = float(base_match.group(1))
            
            # Extract stat name (everything after the last number/parentheses)
            stat_name_pattern = r'(?:\([^)]*\))?\s*(.+)$'
            stat_name_match = re.search(stat_name_pattern, stat_text)
            if stat_name_match:
                stat_name = stat_name_match.group(1).strip()
            else:
                # Fallback: extract everything after base value
                stat_name = re.sub(r'^[+-]?\d+(?:\.\d+)?(?:\s*\([^)]*\))?\s*', '', stat_text).strip()
            
            # FIXED: Clean stat name and remove number prefixes
            stat_name = stat_name.strip().lower()
            stat_name = re.sub(r'[^\w\s%]', '', stat_name)  # Keep % for percentages
            stat_name = stat_name.replace(' ', '_')
            
            # Remove any leading numbers and underscores (like "35_" from "35_ability_power")
            stat_name = re.sub(r'^\d+_*', '', stat_name)
            
            # FIXED: For masterwork tab, create structured object with base/bonus/total
            if tab_type == 'masterwork':
                # Extract bonus value from parentheses (if exists)
                bonus_match = re.search(r'\(\+?([+-]?\d+(?:\.\d+)?)\)', stat_text)
                if bonus_match:
                    bonus_value = float(bonus_match.group(1))
                    total_value = base_value + bonus_value
                    
                    # Return structured masterwork stats
                    stat_value = {
                        "base": base_value,
                        "bonus": bonus_value,
                        "total": total_value
                    }
                    
                    # Handle percentage stats
                    if '%' in stat_text:
                        stat_value = {
                            "base": f"{base_value}%",
                            "bonus": f"{bonus_value}%",
                            "total": f"{total_value}%"
                        }
                else:
                    # No bonus, just base value
                    stat_value = {
                        "base": base_value,
                        "bonus": 0.0,
                        "total": base_value
                    }
                    
                    if '%' in stat_text:
                        stat_value = {
                            "base": f"{base_value}%",
                            "bonus": "0%",
                            "total": f"{base_value}%"
                        }
            else:
                # For base and total tabs, return simple value
                formatted_value = str(base_value) if base_value == int(base_value) else f"{base_value:.1f}"
                
                # Handle percentage stats
                if '%' in stat_text:
                    formatted_value += '%'
                
                stat_value = formatted_value
            
            return {
                'name': stat_name,
                'value': stat_value
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
                        'description': self._format_description(parts[1].strip())
                    }
            
            return {'description': self._format_description(passive_text)}
            
        except Exception as e:
            self.logger.error(f"Error extracting passive ability: {e}")
            return None

    def _format_description(self, description: str) -> str:
        """ENHANCED: Format description text with proper sentence splitting and spacing."""
        try:
            if not description:
                return description
            
            # Clean up extra whitespace
            description = re.sub(r'\s+', ' ', description).strip()
            
            # FIXED: Split numbered points into separate sentences
            # Look for patterns like "2. Healing" and split them
            description = re.sub(r'(\d+)\.\s*([A-Z])', r'. \2', description)
            
            # Fix spacing around punctuation
            description = re.sub(r'\s+([.,:;!?])', r'\1', description)  # Remove space before punctuation
            description = re.sub(r'([.!?])([A-Z])', r'\1 \2', description)  # Add space after sentence end
            
            # Fix specific patterns
            description = description.replace('  ', ' ')  # Remove double spaces
            description = description.replace(' .', '.')  # Fix spaced periods
            
            return description.strip()
            
        except Exception as e:
            self.logger.error(f"Error formatting description: {e}")
            return description

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
        """ENHANCED: Extract recipe using specific CSS selectors for table navigation."""
        try:
            # Use the specific CSS selector for recipe table
            # Target: #mw-content-text > div.mw-content-ltr.mw-parser-output > table
            recipe_table = soup.select_one('#mw-content-text > div.mw-content-ltr.mw-parser-output > table')
            
            if recipe_table:
                return self._parse_recipe_table_with_css(recipe_table)
            else:
                # Fallback to simple component extraction from infobox
                fallback_recipe = self._extract_simple_recipe_fallback(soup)
                # Convert fallback to simple list format for consistency
                if fallback_recipe and isinstance(fallback_recipe, dict):
                    return fallback_recipe.get('structured_format', fallback_recipe.get('components', []))
                return fallback_recipe
            
        except Exception as e:
            self.logger.error(f"Error extracting recipe section: {e}")
            return None

    def _parse_recipe_table_with_css(self, table: Tag) -> Optional[List[str]]:
        """FIXED: Parse recipe table and return only hierarchical structure."""
        try:
            # Navigate the nested table structure
            item_divs = table.select('div.item-icon.name')
            
            # Extract all items first
            all_items = []
            for item_div in item_divs:
                item_info = self._extract_item_name_and_price_css(item_div)
                if item_info:
                    all_items.append(item_info)
            
            if not all_items:
                return None
            
            # FIXED: Identify and filter out main item
            main_item = self._identify_main_item(all_items)
            components = [item for item in all_items if item.get('name') != main_item.get('name')]
            
            # FIXED: Deduplicate components by name
            seen_names = set()
            unique_components = []
            for component in components:
                name = component.get('name')
                if name and name not in seen_names:
                    unique_components.append(component)
                    seen_names.add(name)
            
            # FIXED: Create hierarchical structure and return only this
            if main_item and unique_components:
                hierarchy = self._build_recipe_hierarchy(main_item, unique_components)
                return hierarchy
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing recipe table with CSS: {e}")
            return None

    def _identify_main_item(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify the main item (highest cost or has combine cost)."""
        try:
            if not items:
                return {}
            
            # Find item with highest total cost
            main_item = max(items, key=lambda x: x.get('total_cost', 0))
            
            # Prefer items with combine cost (indicates it's built from components)
            for item in items:
                if item.get('combine_cost') and item.get('total_cost', 0) >= main_item.get('total_cost', 0):
                    main_item = item
                    break
            
            return main_item
            
        except Exception as e:
            self.logger.error(f"Error identifying main item: {e}")
            return items[0] if items else {}

    def _build_recipe_hierarchy(self, main_item: Dict[str, Any], components: List[Dict[str, Any]]) -> List[str]:
        """ENHANCED: Build proper recipe tree showing component relationships."""
        try:
            hierarchy = []
            
            # Add main item
            main_name = main_item.get('name', 'Unknown')
            main_cost = main_item.get('total_cost')
            main_combine = main_item.get('combine_cost')
            
            cost_str = ""
            if main_cost:
                cost_str = f" - {main_cost}"
                if main_combine:
                    cost_str += f"({main_combine})"
            
            hierarchy.append(f"{main_name}{cost_str}")
            
            # ENHANCED: Build recipe tree based on cost relationships
            recipe_tree = self._build_component_tree(components)
            
            # Add tree structure to hierarchy
            for tree_line in recipe_tree:
                hierarchy.append(f"  {tree_line}")
            
            return hierarchy
            
        except Exception as e:
            self.logger.error(f"Error building recipe hierarchy: {e}")
            return []

    def _build_component_tree(self, components: List[Dict[str, Any]]) -> List[str]:
        """Build component tree showing which items build into others."""
        try:
            tree_lines = []
            
            # Sort components by cost (highest first)
            components.sort(key=lambda x: x.get('total_cost', 0), reverse=True)
            
            # Identify intermediate items (items with combine cost) vs basic items
            intermediate_items = [c for c in components if c.get('combine_cost', 0) > 0]
            basic_items = [c for c in components if c.get('combine_cost', 0) == 0]
            
            # Track which basic items are already assigned to intermediate items
            assigned_basic_items = set()
            
            # Process intermediate items and their sub-components
            for intermediate in intermediate_items:
                name = intermediate.get('name', 'Unknown')
                cost = intermediate.get('total_cost')
                combine = intermediate.get('combine_cost')
                
                cost_str = ""
                if cost:
                    cost_str = f" - {cost}"
                    if combine:
                        cost_str += f"({combine})"
                
                tree_lines.append(f"{name}{cost_str}")
                
                # Find basic components that could build into this intermediate item
                sub_components = self._find_sub_components_for_item(intermediate, basic_items, assigned_basic_items)
                
                for sub_comp in sub_components:
                    sub_name = sub_comp.get('name', 'Unknown')
                    sub_cost = sub_comp.get('total_cost')
                    
                    sub_cost_str = f" - {sub_cost}" if sub_cost else ""
                    tree_lines.append(f"  └── {sub_name}{sub_cost_str}")
                    assigned_basic_items.add(sub_name)
            
            # Add remaining unassigned basic items
            for basic in basic_items:
                if basic.get('name') not in assigned_basic_items:
                    name = basic.get('name', 'Unknown')
                    cost = basic.get('total_cost')
                    cost_str = f" - {cost}" if cost else ""
                    tree_lines.append(f"{name}{cost_str}")
            
            return tree_lines
            
        except Exception as e:
            self.logger.error(f"Error building component tree: {e}")
            return []

    def _find_sub_components_for_item(self, intermediate_item: Dict[str, Any], basic_items: List[Dict[str, Any]], assigned: set) -> List[Dict[str, Any]]:
        """Find basic items that likely build into the intermediate item."""
        try:
            sub_components = []
            intermediate_cost = intermediate_item.get('total_cost', 0)
            combine_cost = intermediate_item.get('combine_cost', 0)
            
            # Calculate the total cost of basic components needed
            # intermediate_cost = sum(basic_costs) + combine_cost
            target_basic_cost = intermediate_cost - combine_cost
            
            # Find combinations of basic items that sum close to target cost
            available_basic = [b for b in basic_items if b.get('name') not in assigned]
            
            # Simple heuristic: take the most expensive unassigned basic items first
            # until we reach close to the target cost
            available_basic.sort(key=lambda x: x.get('total_cost', 0), reverse=True)
            
            current_cost = 0
            for basic in available_basic:
                basic_cost = basic.get('total_cost', 0)
                if current_cost + basic_cost <= target_basic_cost + 50:  # Allow 50 gold tolerance
                    sub_components.append(basic)
                    current_cost += basic_cost
                    
                    # Usually items have 2-3 basic components, so limit it
                    if len(sub_components) >= 3:
                        break
            
            return sub_components
            
        except Exception as e:
            self.logger.error(f"Error finding sub-components: {e}")
            return []

    def _extract_item_name_and_price_css(self, item_div: Tag) -> Optional[Dict[str, Any]]:
        """Extract item name and price using specific CSS navigation."""
        try:
            item_info = {}
            
            # Extract item name from: div.item-icon.name > b > a
            name_link = item_div.select_one('b > a')
            if name_link:
                item_info['name'] = name_link.get_text().strip()
            elif item_div.find('b'):
                # Fallback: just the bold text
                item_info['name'] = item_div.find('b').get_text().strip()
            
            # Extract prices from the parent item div structure
            # Look for the parent div.item that contains both name and gold info
            parent_item_div = item_div.find_parent('div', class_='item')
            if parent_item_div:
                # Look for gold div with cost information
                gold_div = parent_item_div.find('div', class_='gold')
                if gold_div:
                    # Extract costs from spans with white-space:normal style
                    cost_spans = gold_div.find_all('span', style=lambda x: x and 'white-space:normal' in x)
                    
                    if cost_spans:
                        # First span is usually total cost
                        total_cost_text = cost_spans[0].get_text().strip()
                        try:
                            total_cost = int(total_cost_text)
                            item_info['total_cost'] = total_cost
                            
                            # Look for combine cost in parentheses pattern
                            gold_text = gold_div.get_text()
                            combine_match = re.search(r'\((\d+)\)', gold_text)
                            if combine_match:
                                item_info['combine_cost'] = int(combine_match.group(1))
                        except ValueError:
                            pass
            
            return item_info if item_info.get('name') else None
            
        except Exception as e:
            self.logger.error(f"Error extracting item name and price: {e}")
            return None

    def _parse_hierarchical_recipe_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """ENHANCED: Parse recipe table to create hierarchical tree structure like: Echoes of Helia - 2200(500)"""
        try:
            # Extract all items from the table
            all_items = []
            item_divs = table.find_all('div', class_='item')
            
            for item_div in item_divs:
                item_info = self._extract_detailed_item_from_div(item_div)
                if item_info:
                    # Determine item position/level in hierarchy based on table structure
                    row = item_div.find_parent('tr')
                    if row:
                        # Count cells/columns to determine depth
                        cells = row.find_all(['td', 'th'])
                        item_info['table_position'] = len(cells)
                        item_info['parent_row'] = row
                    
                    all_items.append(item_info)
            
            if not all_items:
                return None
            
            # Build hierarchical structure
            recipe_tree = self._build_recipe_tree(all_items)
            
            return {
                'recipe_tree': recipe_tree,
                'structured_format': self._format_recipe_tree(recipe_tree)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing hierarchical recipe table: {e}")
            return None

    def _build_recipe_tree(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build hierarchical tree structure from items based on table position."""
        try:
            if not items:
                return {}
            
            # Find the main item (typically first or with highest cost)
            main_item = None
            components = []
            
            for item in items:
                if self._is_main_recipe_item_enhanced(item, items):
                    main_item = item
                else:
                    components.append(item)
            
            if not main_item and items:
                # Fallback: use first item as main
                main_item = items[0]
                components = items[1:]
            
            # Create tree structure
            tree = {
                'name': main_item.get('name', 'Unknown'),
                'total_cost': main_item.get('total_cost'),
                'combine_cost': main_item.get('combine_cost'),
                'components': []
            }
            
            # Group components by their relationships
            processed_components = set()
            
            for component in components:
                if component.get('name') in processed_components:
                    continue
                
                component_tree = {
                    'name': component.get('name', 'Unknown'),
                    'total_cost': component.get('total_cost'),
                    'combine_cost': component.get('combine_cost'),
                    'components': []
                }
                
                # Find sub-components for this component
                sub_components = self._find_sub_components(component, components)
                for sub_comp in sub_components:
                    if sub_comp.get('name') not in processed_components:
                        component_tree['components'].append({
                            'name': sub_comp.get('name', 'Unknown'),
                            'total_cost': sub_comp.get('total_cost'),
                            'combine_cost': sub_comp.get('combine_cost'),
                            'components': []
                        })
                        processed_components.add(sub_comp.get('name'))
                
                tree['components'].append(component_tree)
                processed_components.add(component.get('name'))
            
            return tree
            
        except Exception as e:
            self.logger.error(f"Error building recipe tree: {e}")
            return {}

    def _format_recipe_tree(self, tree: Dict[str, Any]) -> List[str]:
        """Format recipe tree into readable hierarchical text format."""
        try:
            formatted_lines = []
            
            def format_item(item: Dict[str, Any], indent: int = 0) -> None:
                name = item.get('name', 'Unknown')
                total_cost = item.get('total_cost')
                combine_cost = item.get('combine_cost')
                
                # Create cost string
                cost_str = ""
                if total_cost:
                    cost_str = f" - {total_cost}"
                    if combine_cost:
                        cost_str += f"({combine_cost})"
                
                # Create indented line
                indent_str = "  " * indent
                formatted_lines.append(f"{indent_str}{name}{cost_str}")
                
                # Process components recursively
                for component in item.get('components', []):
                    format_item(component, indent + 1)
            
            format_item(tree)
            return formatted_lines
            
        except Exception as e:
            self.logger.error(f"Error formatting recipe tree: {e}")
            return []

    def _is_main_recipe_item_enhanced(self, item: Dict[str, Any], all_items: List[Dict[str, Any]]) -> bool:
        """Enhanced detection of main recipe item."""
        try:
            # Multiple strategies to identify main item
            
            # Strategy 1: Highest total cost (most reliable)
            item_cost = item.get('total_cost', 0)
            if item_cost > 0:
                max_cost = max([i.get('total_cost', 0) for i in all_items])
                if item_cost == max_cost:
                    return True
            
            # Strategy 2: Has combine cost (indicates it's built from components)
            if item.get('combine_cost'):
                return True
            
            # Strategy 3: Table position (first in layout)
            if item.get('table_position', 999) <= min([i.get('table_position', 999) for i in all_items]):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in main item detection: {e}")
            return False

    def _find_sub_components(self, component: Dict[str, Any], all_components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find sub-components that build into the given component."""
        try:
            sub_components = []
            component_cost = component.get('total_cost', 0)
            
            for other_comp in all_components:
                other_cost = other_comp.get('total_cost', 0)
                
                # Sub-components should have lower cost and not be the same item
                if (other_cost < component_cost and 
                    other_comp.get('name') != component.get('name') and
                    other_cost > 0):
                    sub_components.append(other_comp)
            
            # Sort by cost (highest first for logical hierarchy)
            sub_components.sort(key=lambda x: x.get('total_cost', 0), reverse=True)
            
            return sub_components
            
        except Exception as e:
            self.logger.error(f"Error finding sub-components: {e}")
            return []

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

    async def _extract_cost_analysis(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """SIMPLIFIED: Extract only gold efficiency statement."""
        try:
            # Try static extraction first
            cost_section = self._find_section_by_pattern(soup, ['cost analysis', 'gold efficiency'])
            if cost_section:
                efficiency_text = self._extract_gold_efficiency_statement(cost_section)
                if efficiency_text:
                    return efficiency_text
            
            # Look for expandable cost analysis sections
            expandable_elements = soup.find_all('div', class_='mw-collapsible')
            cost_expandable = None
            
            for element in expandable_elements:
                element_text = element.get_text()[:200].lower()
                if 'cost' in element_text or 'efficiency' in element_text:
                    cost_expandable = element
                    break
            
            if cost_expandable:
                # Use minimal Selenium expansion for simple efficiency text
                return await self._expand_simple_efficiency_with_selenium(url)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost analysis: {e}")
            return None

    def _extract_gold_efficiency_statement(self, section: Tag) -> Optional[str]:
        """SIMPLIFIED: Extract gold efficiency statement like 'Echoes of Helia's base stats are 124.24% gold efficient.'"""
        try:
            section_text = section.get_text()
            
            # Look for the efficiency statement pattern
            efficiency_pattern = r'([^.]*?(?:base stats are|stats are)\s+(\d+(?:\.\d+)?)%\s+gold efficient[^.]*\.)'
            match = re.search(efficiency_pattern, section_text, re.IGNORECASE)
            
            if match:
                return match.group(1).strip()
            
            # Fallback: look for any percentage with gold efficient
            fallback_pattern = r'(\d+(?:\.\d+)?)%.*?gold\s+efficient'
            fallback_match = re.search(fallback_pattern, section_text, re.IGNORECASE)
            
            if fallback_match:
                percentage = fallback_match.group(1)
                # Find item name from nearby text or use generic format
                item_name_pattern = r'([A-Z][^.]*?)(?:\'s|s)?\s+(?:base\s+)?stats?\s+(?:are\s+)?'
                name_match = re.search(item_name_pattern + fallback_pattern, section_text, re.IGNORECASE)
                
                if name_match:
                    item_name = name_match.group(1).strip()
                    return f"{item_name}'s base stats are {percentage}% gold efficient."
                else:
                    return f"Base stats are {percentage}% gold efficient."
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting gold efficiency statement: {e}")
            return None

    async def _expand_simple_efficiency_with_selenium(self, url: str) -> Optional[str]:
        """Use Selenium to expand and extract simple efficiency statement."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            driver = None
            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.get(url)
                
                # Wait for page load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "mw-collapsible"))
                )
                
                # Find and click cost analysis collapsible
                collapsibles = driver.find_elements(By.CLASS_NAME, "mw-collapsible")
                for collapsible in collapsibles:
                    if 'cost' in collapsible.text.lower() or 'efficiency' in collapsible.text.lower():
                        driver.execute_script("arguments[0].click();", collapsible)
                        time.sleep(2)  # Wait for expansion
                        
                        # Extract the efficiency statement from expanded content
                        expanded_text = collapsible.text
                        efficiency_pattern = r'([^.]*?(?:base stats are|stats are)\s+(\d+(?:\.\d+)?)%\s+gold efficient[^.]*\.)'
                        match = re.search(efficiency_pattern, expanded_text, re.IGNORECASE)
                        
                        if match:
                            return match.group(1).strip()
                
                return None
                
            except Exception as selenium_error:
                self.logger.error(f"Selenium error in simple efficiency extraction: {selenium_error}")
                return None
                
        except ImportError:
            self.logger.warning("Selenium not available for cost analysis expansion")
            return None
        except Exception as e:
            self.logger.error(f"Error in Selenium simple efficiency expansion: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

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
        """ENHANCED: Extract notes using specific CSS selectors for accurate targeting."""
        try:
            notes_data = {
                'gameplay_notes': [],
                'interactions': [],
                'map_specific_differences': {}
            }
            
            # ENHANCED: Use specific CSS selector for notes UL elements
            # Target: #mw-content-text > div.mw-content-ltr.mw-parser-output > ul
            main_content = soup.select_one('#mw-content-text > div.mw-content-ltr.mw-parser-output')
            if main_content:
                # Find all UL elements in main content
                ul_elements = main_content.find_all('ul', recursive=False)
                
                # Look for the UL that contains notes (usually comes after h2 with "Notes")
                notes_ul = None
                for i, element in enumerate(main_content.find_all(['h2', 'ul'])):
                    if element.name == 'h2' and 'notes' in element.get_text().lower():
                        # Find the next UL after the Notes heading
                        for next_elem in element.find_next_siblings():
                            if next_elem.name == 'ul':
                                notes_ul = next_elem
                                break
                        break
                
                # If found, extract all li elements from the notes UL
                if notes_ul:
                    notes_items = notes_ul.find_all('li', recursive=False)
                    for item in notes_items:
                        # Use merged text to handle fragmented spans
                        merged_text = self._merge_fragmented_text(item)
                        if merged_text and len(merged_text.strip()) > 5:
                            # ENHANCED: Add topic sentences and categorize notes
                            categorized_note = self._categorize_and_format_note(merged_text.strip())
                            if categorized_note:
                                if categorized_note['category'] == 'gameplay':
                                    notes_data['gameplay_notes'].append(categorized_note['formatted_text'])
                                else:
                                    notes_data['interactions'].append(categorized_note['formatted_text'])
            
            # ADDED: Extract Map-Specific Differences section using CSS selector
            map_section = main_content.find('h2', string=lambda text: text and 'map-specific differences' in text.lower()) if main_content else None
            if map_section:
                map_differences = self._extract_map_specific_differences_css(main_content, map_section)
                if map_differences:
                    notes_data['map_specific_differences'] = map_differences
            
            # Remove empty categories
            notes_data = {k: v for k, v in notes_data.items() if v}
            
            return notes_data if notes_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting notes section: {e}")
            return None

    def _categorize_and_format_note(self, note_text: str) -> Optional[Dict[str, str]]:
        """ENHANCED: Add topic sentences and categorize notes for better readability."""
        try:
            formatted_text = note_text
            category = 'interaction'  # default
            
            # Detect category and add topic sentences
            note_lower = note_text.lower()
            
            # Damage-related mechanics
            if any(keyword in note_lower for keyword in ['damage', 'deals', 'magic damage', 'physical damage', 'true damage']):
                if 'default damage' in note_lower:
                    formatted_text = f"**Damage Type**: {note_text}"
                elif 'blocked' in note_lower and 'spell shield' in note_lower:
                    formatted_text = f"**Spell Shield Interaction**: {note_text}"
                else:
                    formatted_text = f"**Damage Mechanics**: {note_text}"
                category = 'gameplay'
            
            # Healing and shielding mechanics
            elif any(keyword in note_lower for keyword in ['heal', 'healing', 'shield', 'shielding']):
                if 'trigger' in note_lower or 'will not' in note_lower:
                    formatted_text = f"**Trigger Conditions**: {note_text}"
                else:
                    formatted_text = f"**Healing/Shielding**: {note_text}"
                category = 'gameplay'
            
            # Projectile and missile mechanics
            elif any(keyword in note_lower for keyword in ['projectile', 'missile', 'launches']):
                formatted_text = f"**Projectile Mechanics**: {note_text}"
                category = 'gameplay'
            
            # Targeting mechanics
            elif any(keyword in note_lower for keyword in ['auto-targeted', 'target', 'range', 'global']):
                formatted_text = f"**Targeting**: {note_text}"
                category = 'gameplay'
            
            # Timing and cooldown mechanics
            elif any(keyword in note_lower for keyword in ['seconds', 'cooldown', 'after', 'land']):
                formatted_text = f"**Timing**: {note_text}"
                category = 'gameplay'
            
            # Trigger conditions
            elif any(keyword in note_lower for keyword in ['trigger', 'will not trigger', 'activate', 'effect']):
                formatted_text = f"**Trigger Conditions**: {note_text}"
                category = 'gameplay'
            
            # Bug reports
            elif any(keyword in note_lower for keyword in ['bug', 'occasionally fail', 'fixed']):
                formatted_text = f"**Known Issues**: {note_text}"
                category = 'interaction'
            
            # Champion-specific interactions
            elif any(keyword in note_lower for keyword in ['affects', 'untargetable', 'allies']):
                formatted_text = f"**Champion Interactions**: {note_text}"
                category = 'interaction'
            
            # Passive/Active ability mechanics
            elif any(keyword in note_lower for keyword in ['passive', 'active', 'unique', 'stack']):
                formatted_text = f"**Ability Mechanics**: {note_text}"
                category = 'gameplay'
            
            return {
                'formatted_text': formatted_text,
                'category': category
            }
            
        except Exception as e:
            self.logger.error(f"Error categorizing note: {e}")
            return {'formatted_text': note_text, 'category': 'interaction'}

    def _merge_fragmented_text(self, element: Tag) -> str:
        """FIXED: Merge fragmented text across spans without duplicates."""
        try:
            # Use BeautifulSoup's get_text() with separator to avoid duplicates
            # This handles nested elements automatically without manual traversal
            merged_text = element.get_text(separator=' ', strip=True)
            
            # Clean up extra whitespace and formatting
            merged_text = re.sub(r'\s+', ' ', merged_text)
            merged_text = merged_text.replace(' "', '"').replace('" ', '"')
            merged_text = merged_text.replace(' .', '.').replace(' ,', ',')
            merged_text = merged_text.strip()
            
            return merged_text
            
        except Exception as e:
            self.logger.error(f"Error merging fragmented text: {e}")
            return element.get_text().strip() if element else ""
    
    def _extract_map_specific_differences_css(self, main_content: Tag, map_section: Tag) -> Optional[Dict[str, Any]]:
        """Extract map-specific differences using CSS navigation."""
        try:
            map_differences = {}
            
            # Look for dl/dt elements after the map-specific differences heading
            for next_elem in map_section.find_next_siblings():
                if next_elem.name == 'dl':
                    # Extract map-specific sections
                    dt_elements = next_elem.find_all('dt')
                    for dt in dt_elements:
                        map_name_elem = dt.find(['a', 'span'])
                        if map_name_elem:
                            map_name = map_name_elem.get_text().strip()
                            
                            # Find associated dd or ul with differences
                            differences = []
                            next_sibling = dt.find_next_sibling()
                            if next_sibling and next_sibling.name in ['dd', 'ul']:
                                if next_sibling.name == 'ul':
                                    items = next_sibling.find_all('li')
                                    for item in items:
                                        diff_text = self._merge_fragmented_text(item)
                                        if diff_text:
                                            differences.append(diff_text.strip())
                                else:
                                    diff_text = self._merge_fragmented_text(next_sibling)
                                    if diff_text:
                                        differences.append(diff_text.strip())
                            
                            if differences:
                                map_differences[map_name] = differences
                elif next_elem.name == 'h2':
                    # Stop at next major section
                    break
            
            return map_differences if map_differences else None
            
        except Exception as e:
            self.logger.error(f"Error extracting map-specific differences: {e}")
            return None
    
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