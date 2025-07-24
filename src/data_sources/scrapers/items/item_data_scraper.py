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
            
            # Extract tabbed stats (Base, Masterwork, Total tabs)
            tabber = infobox.find('div', class_='tabber')
            if tabber:
                tabs = tabber.find_all('div', class_='tabbertab')
                for tab in tabs:
                    tab_title = tab.get('data-title', '').strip().lower()
                    if tab_title:
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
        """Extract clean statistics from a tab (Base, Masterwork, Total)."""
        try:
            stats = {}
            
            # Find stat rows within the tab
            data_rows = tab.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem:
                    stat_text = value_elem.get_text().strip()
                    
                    # Parse stat using clean format (no raw text/base_value)
                    stat_info = self._parse_clean_stat(stat_text)
                    if stat_info:
                        stats[stat_info['name']] = stat_info['value']
            
            return stats if stats else None
            
        except Exception as e:
            self.logger.error(f"Error extracting stats from tab: {e}")
            return None

    def _parse_clean_stat(self, stat_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse stat text into clean format (no raw/base_value format).
        Example: "+35 ability power" -> {"name": "ability_power", "value": 35}
        """
        try:
            # Pattern for stats: "+35 ability power", "200 health", etc.
            pattern = r'([+-]?\d+(?:\.\d+)?)\s*(.+)'
            match = re.match(pattern, stat_text.strip())
            
            if match:
                value_str, stat_name = match.groups()
                
                # Clean stat name
                stat_name = stat_name.strip().lower()
                stat_name = re.sub(r'[^\w\s]', '', stat_name)  # Remove special chars
                stat_name = stat_name.replace(' ', '_')
                
                return {
                    'name': stat_name,
                    'value': float(value_str)
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing stat '{stat_text}': {e}")
            return None

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
        """Extract recipe information with component details."""
        try:
            recipe_section = self._find_section_by_pattern(soup, ['recipe', 'components'])
            if not recipe_section:
                return None
            
            recipe_data = {
                'components': [],
                'total_cost': None
            }
            
            # Extract components from recipe table or list
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
            self.logger.error(f"Error extracting recipe section: {e}")
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
        """Parse cost analysis data from section."""
        try:
            cost_data = {}
            section_text = section.get_text()
            
            # Extract efficiency percentage
            efficiency_match = re.search(r'(\d+(?:\.\d+)?)%.*?efficient', section_text, re.IGNORECASE)
            if efficiency_match:
                cost_data['efficiency_percentage'] = float(efficiency_match.group(1))
            
            # Extract gold values
            gold_values = re.findall(r'(\d+(?:\.\d+)?).{0,20}gold', section_text.lower())
            if gold_values:
                cost_data['gold_values'] = [float(val) for val in gold_values]
            
            return cost_data if cost_data else None
            
        except Exception as e:
            self.logger.error(f"Error parsing cost data: {e}")
            return None

    def _is_cost_data_complete(self, cost_data: Dict[str, Any]) -> bool:
        """Check if cost data appears complete."""
        return bool(cost_data.get('efficiency_percentage') or cost_data.get('gold_values'))

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
        """Extract notes/gameplay information."""
        try:
            notes_section = self._find_section_by_pattern(soup, ['notes', 'gameplay'])
            if not notes_section:
                return None
            
            notes_data = {
                'gameplay_notes': [],
                'interactions': []
            }
            
            # Extract from lists
            note_lists = notes_section.find_all(['ul', 'ol'])
            for note_list in note_lists:
                items = note_list.find_all('li')
                for item in items:
                    note_text = item.get_text().strip()
                    if note_text:
                        if any(keyword in note_text.lower() for keyword in ['damage', 'heal', 'shield', 'effect']):
                            notes_data['gameplay_notes'].append(note_text)
                        else:
                            notes_data['interactions'].append(note_text)
            
            # Extract from paragraphs
            paragraphs = notes_section.find_all('p')
            for para in paragraphs:
                para_text = para.get_text().strip()
                if para_text and len(para_text) > 10:
                    notes_data['gameplay_notes'].append(para_text)
            
            # Remove empty categories
            notes_data = {k: v for k, v in notes_data.items() if v}
            
            return notes_data if notes_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting notes section: {e}")
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