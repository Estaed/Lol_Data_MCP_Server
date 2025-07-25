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
        
        # Extract recipe from sidebar
        if not sections or 'recipe' in sections:
            recipe = self._extract_sidebar_recipe(soup)
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
        
        # Extract recipe from sidebar
        if not sections or 'recipe' in sections:
            recipe = self._extract_sidebar_recipe(soup)
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
    
    def _extract_sidebar_recipe(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """FIXED: Extract recipe using actual HTML structure from infobox headers."""
        try:
            recipe_components = []
            
            # Strategy 1: Look for infobox-header containing "Recipe"
            infobox = soup.find('div', class_='infobox')
            if infobox:
                # Find the Recipe header specifically
                recipe_header = infobox.find('div', class_='infobox-header', string=lambda text: 
                    text and 'recipe' in text.lower())
                
                if recipe_header:
                    # Find the associated infobox-section right after the header
                    recipe_section = recipe_header.find_next_sibling('div', class_='infobox-section')
                    
                    if recipe_section:
                        # Look for item icons with data-item attributes
                        item_icons = recipe_section.find_all('span', class_='inline-image item-icon')
                        
                        for icon in item_icons:
                            # Extract from data-item attribute (most reliable)
                            data_item = icon.get('data-item', '').strip()
                            if data_item and len(data_item) > 2:
                                recipe_components.append(data_item)
                            else:
                                # Fallback: extract from nested link
                                link = icon.find('a')
                                if link:
                                    item_name = self._validate_item_link(link)
                                    if item_name:
                                        recipe_components.append(item_name)
            
            # Strategy 2: Look for Recipe section header (alternative structure)
            if not recipe_components:
                recipe_heading = soup.find(['h2', 'h3'], string=lambda text: 
                    text and 'recipe' in text.lower())
                
                if recipe_heading:
                    # Look for content after the heading
                    current = recipe_heading.find_next_sibling()
                    while current and current.name not in ['h2', 'h3', 'h4']:
                        if current.name in ['div', 'ul', 'ol', 'table']:
                            # Extract item links from this section
                            item_links = self._extract_recipe_item_links(current)
                            recipe_components.extend(item_links)
                            if recipe_components:  # Stop if we found items
                                break
                        current = current.find_next_sibling()
            
            # Strategy 3: Fallback - look for any item icons in infobox (less reliable)
            if not recipe_components:
                if infobox:
                    all_item_icons = infobox.find_all('span', class_='inline-image item-icon')
                    for icon in all_item_icons:
                        data_item = icon.get('data-item', '').strip()
                        if data_item and len(data_item) > 2:
                            # Basic filtering to avoid duplicates and non-items
                            if data_item not in recipe_components:
                                recipe_components.append(data_item)
            
            # Clean and format results
            if recipe_components:
                unique_items = []
                seen = set()
                
                for item in recipe_components:
                    if item and item not in seen and len(item) > 2:
                        # Additional validation
                        if not any(skip in item.lower() for skip in ['gold', 'icon', 'image']):
                            unique_items.append(f"+-- {item}")
                            seen.add(item)
                
                return unique_items[:6] if unique_items else None  # Limit to 6 reasonable components
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting sidebar recipe: {e}")
            return None
    
    def _extract_recipe_item_links(self, element: Tag) -> List[str]:
        """FIXED: Extract only actual recipe item links with better filtering."""
        try:
            items = []
            
            # Look for actual item links with specific validation
            links = element.find_all('a')
            for link in links:
                item_name = self._validate_item_link(link)
                if item_name:
                    items.append(item_name)
            
            return items
            
        except Exception as e:
            self.logger.error(f"Error extracting recipe item links: {e}")
            return []
    
    def _validate_item_link(self, link: Tag) -> Optional[str]:
        """Validate if a link points to an actual LoL item."""
        try:
            href = link.get('href', '')
            item_name = link.get_text().strip()
            
            # Must have proper wiki href pattern
            if not ('/wiki/' in href or href.startswith('/')):
                return None
            
            # Filter out non-item links
            if any(skip in href for skip in [
                'Category:', 'File:', 'Special:', 'Template:', 'User:', 'Help:', 
                'Talk:', 'Project:', '#', 'action=', 'oldid='
            ]):
                return None
            
            # Filter out non-item text patterns
            if not item_name or len(item_name) < 3:
                return None
            
            # Filter out UI elements and game modes
            if any(ui_word in item_name.lower() for ui_word in [
                'cost', 'sell', 'availability', 'menu', 'marksman', 'attack damage',
                'sr 5v5', 'ha aram', 'nexus blitz', 'arena', 'gold', 'edit', 'view',
                'here', 'this', 'that', 'more', 'less', 'show', 'hide'
            ]):
                return None
            
            # Must look like an actual item name (starts with capital, reasonable length)
            if not item_name[0].isupper() or len(item_name) > 50:
                return None
            
            # Filter out pure numbers or IDs
            if item_name.isdigit() or re.match(r'^\d+[A-Za-z]*\d*$', item_name):
                return None
            
            return item_name
            
        except Exception as e:
            self.logger.error(f"Error validating item link: {e}")
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
        """FIXED: Extract clean cost analysis text with proper formatting."""
        try:
            # Try static extraction first - look for mw-collapsible with Cost Analysis
            cost_section = self._find_cost_analysis_section(soup)
            if cost_section:
                formatted_text = self._extract_formatted_cost_analysis(cost_section)
                if formatted_text:
                    return formatted_text
            
            # Fallback: try the old method
            cost_section = self._find_section_by_pattern(soup, ['cost analysis', 'gold efficiency', 'gold value'])
            if cost_section:
                formatted_text = self._extract_formatted_cost_analysis(cost_section)
                if formatted_text:
                    return formatted_text
            
            # Look for expandable cost analysis sections that need Selenium
            expandable_elements = soup.find_all('div', class_='mw-collapsible')
            cost_expandable = None
            
            for element in expandable_elements:
                element_text = element.get_text()[:200].lower()
                if any(keyword in element_text for keyword in ['cost', 'efficiency', 'gold value']):
                    cost_expandable = element
                    break
            
            if cost_expandable:
                # Use minimal Selenium expansion for formatted text
                return await self._expand_formatted_cost_with_selenium(url)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost analysis: {e}")
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

    def _find_cost_analysis_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the Cost Analysis section in mw-collapsible structure."""
        try:
            # Look for mw-collapsible with Cost Analysis header
            collapsibles = soup.find_all('div', class_='mw-collapsible')
            
            for collapsible in collapsibles:
                # Check if this collapsible contains Cost Analysis
                header = collapsible.find(['h2', 'h3'], string=lambda text: 
                    text and 'cost analysis' in text.lower())
                if header:
                    return collapsible
            
            # Alternative: look for mw-headline with Cost_Analysis id
            cost_headline = soup.find('span', class_='mw-headline', id='Cost_Analysis')
            if cost_headline:
                # Find the parent collapsible
                parent = cost_headline.find_parent('div', class_='mw-collapsible')
                if parent:
                    return parent
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding cost analysis section: {e}")
            return None

    def _extract_formatted_cost_analysis(self, section: Tag) -> Optional[str]:
        """FIXED: Extract cost analysis from mw-collapsible structure properly."""
        try:
            lines = []
            
            # Look for mw-collapsible-content (the expanded content area)
            collapsible_content = section.find('div', class_='mw-collapsible-content')
            if not collapsible_content:
                # If no collapsible, try to use the section directly
                collapsible_content = section
            
            # Extract Gold Value section
            gold_value_header = collapsible_content.find(string=lambda text: 
                text and 'gold value' in text.lower())
            if gold_value_header:
                lines.append('Gold Value:')
                
                # Find the UL with individual stat entries
                parent = gold_value_header.parent if gold_value_header else None
                if parent:
                    # Look for the next UL element
                    ul_element = parent.find_next_sibling('ul') or parent.find_next('ul')
                    if ul_element:
                        li_elements = ul_element.find_all('li')
                        for li in li_elements:
                            # Extract stat line carefully
                            stat_line = self._extract_clean_stat_line(li)
                            if stat_line:
                                lines.append(stat_line)
            
            # Look for Total Gold Value
            total_patterns = ['total gold value', 'total:', 'worth:']
            for pattern in total_patterns:
                total_element = collapsible_content.find(string=lambda text: 
                    text and pattern in text.lower())
                if total_element:
                    # Extract the total value and clean it
                    total_text = total_element.strip()
                    
                    # Apply the same cleaning as stat lines
                    total_text = self._fix_spaced_decimals_and_duplicates(total_text)
                    
                    if 'total gold value' not in total_text.lower():
                        # Look for a number in nearby text
                        parent = total_element.parent
                        if parent:
                            parent_text = parent.get_text()
                            parent_text = self._fix_spaced_decimals_and_duplicates(parent_text)
                            numbers = re.findall(r'\d+(?:\.\d+)?', parent_text)
                            if numbers:
                                total_text = f'Total Gold Value = {numbers[0]}'
                    
                    lines.append('')  # Empty line for separation
                    lines.append(total_text)
                    break
            
            # Look for efficiency statement
            efficiency_patterns = ['gold efficient', 'efficiency']
            for pattern in efficiency_patterns:
                efficiency_element = collapsible_content.find(string=lambda text: 
                    text and pattern in text.lower() and 'base stats' in text.lower())
                if efficiency_element:
                    lines.append('')  # Empty line for separation
                    lines.append('Gold Efficiency')
                    lines.append(efficiency_element.strip())
                    break
            
            # Join lines and clean up
            if lines:
                # DEBUG: Check what's in the lines
                print(f"DEBUG - Lines before joining: {lines}")
                
                # Create proper line breaks by joining with newlines
                result = '\n'.join(lines)
                
                # DEBUG: Check result after joining
                print(f"DEBUG - Result after join: {repr(result)}")
                
                # Clean up any remaining issues
                result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
                # Process line breaks to ensure proper formatting
                result = self._process_line_breaks(result)
                
                # DEBUG: Final result
                print(f"DEBUG - Final result: {repr(result)}")
                
                return lines
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting formatted cost analysis: {e}")
            return None
    
    def _extract_clean_stat_line(self, li_element: Tag) -> Optional[str]:
        """Extract a clean stat line from an LI element, handling gold icons properly."""
        try:
            # Get text content first
            full_text = li_element.get_text(strip=True)
            
            # Fix spaced decimals and duplicated numbers like "2275 gold 2275"
            cleaned_text = self._fix_spaced_decimals_and_duplicates(full_text)
            
            # Clean up extra spaces and formatting
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
            cleaned_text = re.sub(r'\s*=\s*', ' = ', cleaned_text)
            
            return cleaned_text.strip() if cleaned_text else None
            
        except Exception as e:
            self.logger.error(f"Error extracting clean stat line: {e}")
            return None
    
    def _fix_spaced_decimals_and_duplicates(self, text: str) -> str:
        """Fix spaced decimals and remove duplicated numbers like '2275 gold 2275'."""
        if not text:
            return text
        
        # Fix spaced decimals like "0. 25" → "0.25"
        fixed_text = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', text)
        
        # Fix Unicode characters
        fixed_text = fixed_text.replace('\u2013', '-').replace('\u2014', '-')
        fixed_text = fixed_text.replace('\u00a0', ' ')  # Non-breaking space
        
        # Remove duplicated number patterns like "2275 gold 2275" → "2275 gold"
        # Pattern: number + (optional decimal) + space + "gold" + space + same number
        fixed_text = re.sub(r'(\d+(?:\.\d+)?)\s+gold\s+\1(?!\d)', r'\1 gold', fixed_text)
        
        # Clean up multiple spaces
        fixed_text = re.sub(r'\s+', ' ', fixed_text)
        
        return fixed_text.strip()
    
    def _process_line_breaks(self, text: str) -> str:
        """Process line breaks to render properly - convert to actual line breaks."""
        if not text:
            return text
        
        # If the text contains literal \n sequences, replace them with actual newlines
        if '\\n' in text:
            processed = text.replace('\\n', '\n')
        else:
            processed = text
        
        # Clean up excessive line breaks - max 2 consecutive newlines  
        processed = re.sub(r'\n\s*\n\s*\n+', '\n\n', processed)
        
        # Remove any trailing whitespace from lines
        lines = processed.split('\n')
        lines = [line.rstrip() for line in lines]
        processed = '\n'.join(lines)
        
        return processed.strip()
    
    def _clean_cost_analysis_text(self, text: str) -> Optional[str]:
        """FIXED: Clean up cost analysis with proper line breaks and readable formatting."""
        try:
            if not text:
                return None
            
            # Fix common encoding issues
            cleaned = text.replace('\u00a0', ' ')  # Unicode non-breaking space
            cleaned = cleaned.replace('\u2013', '-')  # En dash
            cleaned = cleaned.replace('\u2014', '-')  # Em dash
            cleaned = cleaned.replace('\u2019', "'")  # Right single quotation mark
            
            # Remove extra whitespace but preserve line breaks
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # Only collapse spaces/tabs, not line breaks
            
            # CRITICAL FIX: Add line breaks between individual stat entries
            # Pattern: "65 attack damage = 2275 25% critical strike chance = 1000"
            # Should become: "65 attack damage = 2275\n25% critical strike chance = 1000"
            cleaned = re.sub(
                r'(\d+(?:\.\d+)?\s*(?:attack damage|ability power|armor|magic resistance|health|mana|critical strike chance|critical strike damage)\s*=\s*\d+(?:\.\d+)?)\s+'
                r'(\d+(?:\.\d+)?%?\s*(?:attack damage|ability power|armor|magic resistance|health|mana|critical strike chance|critical strike damage))',
                r'\1\n\2',
                cleaned,
                flags=re.IGNORECASE
            )
            
            # CRITICAL FIX: Separate percentage stats from regular stats
            # Pattern: "= 2275 25% critical" -> "= 2275\n25% critical"
            cleaned = re.sub(r'(=\s*\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?%)', r'\1\n\2', cleaned)
            
            # Fix "Total Gold Value" patterns with proper line breaks
            cleaned = re.sub(r'Total\s+Gold\s+Value\s*=?\s*(\d+(?:\.\d+)?)', r'\nTotal Gold Value = \1', cleaned, flags=re.IGNORECASE)
            
            # Add section breaks for "Gold efficiency"
            cleaned = re.sub(r'Gold\s+efficiency', r'\n\nGold Efficiency', cleaned, flags=re.IGNORECASE)
            
            # Fix efficiency statements with proper formatting
            cleaned = re.sub(
                r'([^\n]*?)\s*(?:\'s)?\s*base\s+stats\s+are\s+(\d+(?:\.\d+)?)\s*%\s+gold\s+efficient',
                r"\1's base stats are \2% gold efficient.",
                cleaned,
                flags=re.IGNORECASE
            )
            
            # Clean up section headers
            cleaned = re.sub(r'^Gold\s*Value\s*Gold\s*Value', 'Gold Value', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'^Gold\s*Value(?!\s*=)', 'Gold Value:', cleaned, flags=re.MULTILINE)
            
            # Fix stat formatting with consistent spacing
            cleaned = re.sub(
                r'(\d+(?:\.\d+)?)\s*(attack damage|ability power|armor|magic resistance|health|mana|critical strike chance|critical strike damage)\s*=\s*(\d+(?:\.\d+)?)',
                r'\1 \2 = \3 gold',
                cleaned,
                flags=re.IGNORECASE
            )
            
            # Clean up spacing around punctuation
            cleaned = cleaned.replace(' . ', '. ')
            cleaned = cleaned.replace(' ,', ',')
            cleaned = cleaned.replace(' :', ':')
            cleaned = cleaned.replace('( ', '(')
            cleaned = cleaned.replace(' )', ')')
            
            # Fix number formatting issues
            cleaned = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', cleaned)
            
            # Final cleanup - normalize line breaks
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # Remove excessive line breaks
            cleaned = re.sub(r'^\s+|\s+$', '', cleaned, flags=re.MULTILINE)  # Remove leading/trailing whitespace per line
            cleaned = cleaned.strip()  # Remove overall leading/trailing whitespace
            
            return cleaned if cleaned else None
            
        except Exception as e:
            self.logger.error(f"Error cleaning cost analysis text: {e}")
            return text

    async def _expand_formatted_cost_with_selenium(self, url: str) -> Optional[str]:
        """FIXED: Use Selenium to expand and extract formatted cost analysis."""
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
                    collapsible_text = collapsible.text.lower()
                    if any(keyword in collapsible_text for keyword in ['cost', 'efficiency', 'gold value']):
                        driver.execute_script("arguments[0].click();", collapsible)
                        time.sleep(2)  # Wait for expansion
                        
                        # Extract and clean the expanded content
                        expanded_text = collapsible.text
                        cleaned_text = self._clean_cost_analysis_text(expanded_text)
                        
                        if cleaned_text and len(cleaned_text) > 20:
                            return cleaned_text
                
                return None
                
            except Exception as selenium_error:
                self.logger.error(f"Selenium error in cost analysis extraction: {selenium_error}")
                return None
                
        except ImportError:
            self.logger.warning("Selenium not available for cost analysis expansion")
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