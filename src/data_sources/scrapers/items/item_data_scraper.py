"""
Item Data Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting item data
from the League of Legends Wiki with differentiated extraction for
completed vs basic/epic items following Task 2.2.1 requirements.
"""

import asyncio
import logging
import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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
    # Fallback for different import contexts
    from ..base_scraper import BaseScraper, WikiScraperError


class ItemType(Enum):
    """Item type classification for differentiated extraction"""
    COMPLETED = "completed"
    BASIC = "basic"
    EPIC = "epic"
    UNKNOWN = "unknown"


# Common section headers to search for (without hardcoding specific text)
SECTION_PATTERNS = {
    'recipe': ['recipe', 'components', 'build'],
    'cost_analysis': ['cost analysis', 'gold efficiency'],
    'notes': ['notes', 'gameplay'],
    'map_differences': ['map-specific differences', 'map differences'],
    'similar_items': ['similar items', 'alternatives'],
    'builds_info': ['builds into', 'builds'],
    'old_icons': ['old icons', 'previous versions']
}

# CSS selectors for item infoboxes and data sections
ITEM_SELECTORS = {
    'infobox': '.infobox',
    'infobox_title': '.infobox-title',
    'stats_tabs': '.tabbertab',
    'cost_analysis_section': '.mw-collapsible',
    'recipe_table': 'table[style*="border-collapse"]',
    'similar_items_section': '.columntemplate'
}

# Expandable section selectors for Selenium interaction
EXPANDABLE_SELECTORS = {
    'cost_analysis_toggle': '.mw-collapsible .mw-collapsible-toggle'
}


class ItemDataScraper(BaseScraper):
    """
    A specialized scraper for item data using dynamic section detection.
    Supports differentiated extraction for completed vs basic/epic items.
    Task 2.2.1: Perfect item name assumption with dynamic scraping.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def _build_item_url(self, item_name: str) -> str:
        """
        Build item URL following champion URL pattern with proper normalization.
        
        Args:
            item_name: Name of the item to build URL for
            
        Returns:
            Full URL to the item page
        """
        # Use the same robust normalization as champion URLs
        normalized_name = self.normalize_item_name(item_name)
        return f"{self.BASE_URL}{normalized_name}"
    
    def normalize_item_name(self, name: str) -> str:
        """
        Normalize item name for wiki lookup using same pattern as champion names.
        Example: "Doran's Blade" -> "Doran%27s_Blade", "Echoes of Helia" -> "Echoes_of_Helia" 
        """
        # Title case and strip whitespace
        normalized = name.strip().title()
        
        # Replace spaces with underscores for URL compatibility
        normalized = normalized.replace(' ', '_')
        
        # Handle apostrophes for URL compatibility (same as champion scraper)
        normalized = normalized.replace("'", "%27")
        
        return normalized

    def _classify_item_type_from_page(self, soup: BeautifulSoup) -> ItemType:
        """
        Dynamically classify item type from page structure analysis.
        No hardcoded item names - uses page structure patterns.
        
        Args:
            soup: BeautifulSoup object of the item page
            
        Returns:
            ItemType classification
        """
        try:
            # Strategy 1: Look for item tier in main text description
            # Pattern: "X is a [tier] item in League of Legends"
            main_text = soup.get_text().lower()
            
            # Check for explicit tier mentions in description
            if 'legendary item in' in main_text or 'mythic item in' in main_text:
                self.logger.debug("Classified as completed item (legendary/mythic in description)")
                return ItemType.COMPLETED
            
            if 'basic item in' in main_text:
                self.logger.debug("Classified as basic item (basic in description)")
                return ItemType.BASIC
                
            if 'epic item in' in main_text:
                self.logger.debug("Classified as epic item (epic in description)")
                return ItemType.EPIC
            
            # Strategy 2: Look for category information in page metadata
            # Check categories in wgCategories or category links
            category_links = soup.find_all('a', href=lambda x: x and '/Category:' in x)
            category_text = ' '.join([link.get_text().lower() for link in category_links])
            
            if any(tier in category_text for tier in ['legendary', 'mythic']):
                self.logger.debug("Classified as completed item (category classification)")
                return ItemType.COMPLETED
            elif 'basic' in category_text:
                self.logger.debug("Classified as basic item (category classification)")
                return ItemType.BASIC
            elif 'epic' in category_text:
                self.logger.debug("Classified as epic item (category classification)")
                return ItemType.EPIC
            
            # Strategy 3: Analyze infobox structure
            infobox = soup.find('div', class_='infobox')
            if infobox:
                infobox_text = infobox.get_text().lower()
                
                # Look for tier indicators in infobox
                if any(tier in infobox_text for tier in ['legendary', 'mythic']):
                    self.logger.debug("Classified as completed item (infobox tier)")
                    return ItemType.COMPLETED
                elif 'basic' in infobox_text:
                    self.logger.debug("Classified as basic item (infobox tier)")
                    return ItemType.BASIC
                elif 'epic' in infobox_text:
                    self.logger.debug("Classified as epic item (infobox tier)")
                    return ItemType.EPIC
            
            # Strategy 4: Analyze recipe vs builds patterns
            # Completed items have recipes but don't build into other items
            # Basic/Epic items may have both recipes and "builds into" sections
            recipe_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['recipe'])
            builds_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['builds_info'])
            
            if recipe_section and not builds_section:
                self.logger.debug("Classified as completed item (has recipe, no builds)")
                return ItemType.COMPLETED
            elif recipe_section and builds_section:
                self.logger.debug("Classified as basic/epic item (has both recipe and builds)")
                # Try to distinguish between basic and epic
                # Basic items typically have simpler recipes
                if self._analyze_recipe_complexity(recipe_section):
                    return ItemType.EPIC
                else:
                    return ItemType.BASIC
            elif not recipe_section and builds_section:
                # Items that don't build from anything but build into others are basic
                self.logger.debug("Classified as basic item (no recipe, has builds)")
                return ItemType.BASIC
            
            # Strategy 5: Fallback cost analysis
            # Generally: Basic < 1000g, Epic 1000-2999g, Completed 3000g+
            cost_info = self._extract_item_cost_info(soup)
            if cost_info:
                cost = cost_info.get('total_cost', 0)
                if cost >= 3000:
                    self.logger.debug(f"Classified as completed item (high cost: {cost}g)")
                    return ItemType.COMPLETED
                elif cost >= 1000:
                    self.logger.debug(f"Classified as epic item (medium cost: {cost}g)")
                    return ItemType.EPIC
                else:
                    self.logger.debug(f"Classified as basic item (low cost: {cost}g)")
                    return ItemType.BASIC
            
            self.logger.warning("Could not determine item type from page structure")
            return ItemType.UNKNOWN
            
        except Exception as e:
            self.logger.error(f"Error classifying item type: {e}")
            return ItemType.UNKNOWN

    def _analyze_recipe_complexity(self, recipe_section: Tag) -> bool:
        """
        Analyze recipe complexity to distinguish between basic and epic items.
        
        Args:
            recipe_section: BeautifulSoup Tag containing recipe information
            
        Returns:
            True if recipe suggests epic item, False for basic item
        """
        try:
            recipe_text = recipe_section.get_text()
            
            # Count number of components
            # Epic items typically have more complex recipes
            component_count = recipe_text.count('+')  # Count + symbols
            
            # Look for gold cost indicators
            gold_mentions = len(re.findall(r'\d+\s*(?:gold|g)', recipe_text.lower()))
            
            # Epic items typically have 2+ components and combine cost
            is_complex = component_count >= 2 or gold_mentions >= 3
            
            self.logger.debug(f"Recipe complexity analysis: components={component_count}, gold_mentions={gold_mentions}, complex={is_complex}")
            return is_complex
            
        except Exception as e:
            self.logger.error(f"Error analyzing recipe complexity: {e}")
            return False  # Default to basic

    def _extract_item_cost_info(self, soup: BeautifulSoup) -> Optional[Dict[str, int]]:
        """
        Extract basic cost information for item classification.
        
        Args:
            soup: BeautifulSoup object of the item page
            
        Returns:
            Dictionary with cost information or None
        """
        try:
            # Look for cost information in infobox
            infobox = soup.find('div', class_='infobox')
            if not infobox:
                return None
            
            cost_info = {}
            
            # Find cost row in infobox
            cost_rows = infobox.find_all('div', class_='infobox-data-row')
            for row in cost_rows:
                label_elem = row.find('div', class_='infobox-data-label')
                value_elem = row.find('div', class_='infobox-data-value')
                
                if label_elem and value_elem:
                    label = label_elem.get_text().lower().strip()
                    value_text = value_elem.get_text()
                    
                    if 'cost' in label:
                        # Extract numeric cost value
                        cost_match = re.search(r'(\d+)', value_text)
                        if cost_match:
                            cost_info['total_cost'] = int(cost_match.group(1))
                    elif 'sell' in label:
                        # Extract sell value
                        sell_match = re.search(r'(\d+)', value_text)
                        if sell_match:
                            cost_info['sell_value'] = int(sell_match.group(1))
            
            return cost_info if cost_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost info: {e}")
            return None

    def _find_section_by_content_scan(self, soup: BeautifulSoup, patterns: List[str]) -> Optional[Tag]:
        """
        Generic section finder using content patterns without hardcoding.
        Scans page structure for sections matching pattern keywords.
        
        Args:
            soup: BeautifulSoup object to search
            patterns: List of pattern strings to match against
            
        Returns:
            Found section Tag or None
        """
        try:
            # Strategy 1: Look for MediaWiki headline spans (most accurate)
            headlines = soup.find_all('span', class_='mw-headline')
            for headline in headlines:
                headline_text = headline.get_text().lower().strip()
                if any(pattern in headline_text for pattern in patterns):
                    self.logger.debug(f"Found section via mw-headline: {headline_text}")
                    # Get the parent header element and find the next content section
                    header = headline.parent
                    section_content = self._get_section_content_after_header(header)
                    return section_content if section_content else header.parent
            
            # Strategy 2: Look for header elements (h2, h3, h4) with pattern text
            for header_tag in ['h2', 'h3', 'h4']:
                headers = soup.find_all(header_tag)
                for header in headers:
                    header_text = header.get_text().lower().strip()
                    if any(pattern in header_text for pattern in patterns):
                        self.logger.debug(f"Found section via {header_tag} header: {header_text}")
                        # Get section content following this header
                        section_content = self._get_section_content_after_header(header)
                        return section_content if section_content else header
            
            # Strategy 3: Look for section containers with relevant class names
            section_containers = soup.find_all(['div', 'section'], class_=True)
            for container in section_containers:
                class_names = ' '.join(container.get('class', [])).lower()
                if any(pattern.replace(' ', '-') in class_names for pattern in patterns):
                    self.logger.debug(f"Found section via class names: {class_names}")
                    return container
            
            # Strategy 4: Look for table structures (common for recipes)
            if 'recipe' in patterns or 'components' in patterns:
                recipe_tables = soup.find_all('table', style=lambda x: x and 'border-collapse' in x)
                if recipe_tables:
                    self.logger.debug("Found recipe section via table structure")
                    return recipe_tables[0]
            
            # Strategy 5: Look for div elements with strong pattern matches in early content
            divs = soup.find_all('div')
            for div in divs:
                # Check first text node for section identification
                first_text = div.get_text()[:200].lower().strip()
                # Require stronger pattern matching for divs to avoid false positives
                strong_matches = sum(1 for pattern in patterns if pattern in first_text)
                if strong_matches > 0 and len(first_text) > 20:  # Avoid empty divs
                    self.logger.debug(f"Found section via div content: {first_text[:50]}...")
                    return div
            
            self.logger.debug(f"No section found for patterns: {patterns}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error in section content scan: {e}")
            return None

    def _get_section_content_after_header(self, header: Tag) -> Optional[Tag]:
        """
        Get the content section that follows a header element.
        
        Args:
            header: Header Tag element
            
        Returns:
            Content Tag or None
        """
        try:
            # Strategy 1: Look for immediate next sibling
            next_sibling = header.find_next_sibling()
            if next_sibling and next_sibling.name in ['div', 'p', 'ul', 'ol', 'table']:
                return next_sibling
            
            # Strategy 2: Look for the next content element after this header
            current = header.next_sibling
            while current:
                if isinstance(current, Tag) and current.name in ['div', 'p', 'ul', 'ol', 'table', 'dl']:
                    # Check if this looks like content rather than another header
                    if not current.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        return current
                current = current.next_sibling
            
            # Strategy 3: Look in parent container for related content
            parent = header.parent
            if parent:
                # Find content elements within the same parent after this header
                following_elements = header.find_next_siblings()
                for element in following_elements:
                    if element.name in ['div', 'p', 'ul', 'ol', 'table', 'dl']:
                        return element
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting section content after header: {e}")
            return None

    def _detect_expandable_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Find collapsible/expandable sections like cost analysis.
        
        Args:
            soup: BeautifulSoup object to search
            
        Returns:
            List of dictionaries with expandable section info
        """
        expandable_sections = []
        
        try:
            # Strategy 1: Look for mw-collapsible class (MediaWiki collapsible sections)
            collapsible_sections = soup.find_all('div', class_='mw-collapsible')
            for section in collapsible_sections:
                section_info = {
                    'element': section,
                    'type': 'mw-collapsible',
                    'classes': section.get('class', []),
                    'toggle_element': section.find(class_='mw-collapsible-toggle'),
                    'content_element': section.find(class_='mw-collapsible-content')
                }
                
                # Try to identify what this section is about
                section_text = section.get_text()[:100].lower()
                if 'cost' in section_text or 'efficiency' in section_text:
                    section_info['purpose'] = 'cost_analysis'
                elif 'note' in section_text:
                    section_info['purpose'] = 'notes'
                else:
                    section_info['purpose'] = 'unknown'
                
                expandable_sections.append(section_info)
                self.logger.debug(f"Found mw-collapsible section: {section_info['purpose']}")
            
            # Strategy 2: Look for sections with toggle buttons or click handlers
            toggle_sections = soup.find_all(['div', 'span'], class_=lambda x: x and any(
                keyword in ' '.join(x).lower() for keyword in ['toggle', 'expand', 'collapse', 'show', 'hide']
            ))
            for section in toggle_sections:
                # Avoid duplicates from Strategy 1
                if not any(existing['element'] == section for existing in expandable_sections):
                    section_info = {
                        'element': section,
                        'type': 'toggle-button',
                        'classes': section.get('class', []),
                        'toggle_element': section,
                        'content_element': None,  # Will be determined later
                        'purpose': 'unknown'
                    }
                    expandable_sections.append(section_info)
                    self.logger.debug(f"Found toggle section: {section.get('class', [])}")
            
            # Strategy 3: Look for sections with JavaScript click handlers
            js_sections = soup.find_all(attrs={'onclick': True})
            for section in js_sections:
                onclick_text = section.get('onclick', '').lower()
                if any(keyword in onclick_text for keyword in ['toggle', 'expand', 'show', 'hide']):
                    # Avoid duplicates
                    if not any(existing['element'] == section for existing in expandable_sections):
                        section_info = {
                            'element': section,
                            'type': 'js-toggle',
                            'classes': section.get('class', []),
                            'toggle_element': section,
                            'content_element': None,
                            'purpose': 'unknown'
                        }
                        expandable_sections.append(section_info)
                        self.logger.debug(f"Found JS toggle section: {onclick_text[:50]}")
            
            # Strategy 4: Look for common collapsible patterns by structure
            # Find sections that have both a header-like element and content
            potential_sections = soup.find_all('div', class_=['collapsible', 'expandable', 'accordion'])
            for section in potential_sections:
                if not any(existing['element'] == section for existing in expandable_sections):
                    header = section.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span'])
                    content = section.find(['div', 'p', 'ul', 'ol'])
                    
                    if header and content:
                        section_info = {
                            'element': section,
                            'type': 'structural-collapsible',
                            'classes': section.get('class', []),
                            'toggle_element': header,
                            'content_element': content,
                            'purpose': 'unknown'
                        }
                        expandable_sections.append(section_info)
                        self.logger.debug(f"Found structural collapsible: {section.get('class', [])}")
            
            self.logger.info(f"Detected {len(expandable_sections)} expandable sections")
            return expandable_sections
            
        except Exception as e:
            self.logger.error(f"Error detecting expandable sections: {e}")
            return []

    def _validate_section_content(self, section: Optional[Tag], expected_patterns: List[str]) -> bool:
        """
        Validate that a found section contains expected content patterns.
        
        Args:
            section: BeautifulSoup Tag to validate
            expected_patterns: List of patterns that should be present
            
        Returns:
            True if section is valid and contains expected content
        """
        if not section:
            return False
        
        try:
            section_text = section.get_text().lower()
            
            # Check if section has meaningful content (not just empty or very short)
            if len(section_text.strip()) < 10:
                self.logger.debug("Section rejected: too short")
                return False
            
            # Check for expected patterns
            pattern_matches = sum(1 for pattern in expected_patterns if pattern in section_text)
            pattern_ratio = pattern_matches / len(expected_patterns) if expected_patterns else 0
            
            # Require at least 30% of expected patterns to be present
            if pattern_ratio < 0.3:
                self.logger.debug(f"Section rejected: pattern ratio {pattern_ratio:.2f} too low")
                return False
            
            # Additional validation: check for common section indicators
            has_structured_content = bool(
                section.find(['table', 'ul', 'ol', 'dl']) or
                len(section.find_all(['p', 'div'])) > 1
            )
            
            if not has_structured_content:
                self.logger.debug("Section rejected: no structured content")
                return False
            
            self.logger.debug(f"Section validated: pattern ratio {pattern_ratio:.2f}, structured content present")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating section content: {e}")
            return False

    def _log_section_detection_results(self, section_name: str, section: Optional[Tag], patterns: List[str]) -> None:
        """
        Log detailed results of section detection for debugging.
        
        Args:
            section_name: Name of the section being detected
            section: Found section Tag or None
            patterns: Patterns that were searched for
        """
        try:
            if section:
                section_text = section.get_text()[:200].replace('\n', ' ').strip()
                self.logger.info(f"✅ {section_name} section found: {section_text[:100]}...")
                self.logger.debug(f"Section element: {section.name}, classes: {section.get('class', [])}")
            else:
                self.logger.warning(f"❌ {section_name} section not found (patterns: {patterns})")
                
        except Exception as e:
            self.logger.error(f"Error logging section detection results: {e}")

    async def scrape_item_data(self, item_name: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main entry point for item data scraping with differentiated extraction.
        
        Args:
            item_name: Perfect item name (e.g., "Echoes of Helia", "Kindlegem")
            sections: Optional list of specific sections to extract
            
        Returns:
            Dictionary with item data based on item type
        """
        self.logger.info(f"Scraping item data for: {item_name}")
        
        try:
            # Get cached content or fetch from web
            cached_content = self.get_cached_content(item_name)
            if cached_content:
                self.logger.info(f"Using cached content for {item_name}")
                html_content = cached_content
            else:
                url = self._build_item_url(item_name)
                html_content = await self._fetch_page_content(url)
                if html_content:
                    self.cache_content(item_name, html_content)
            
            if not html_content:
                raise WikiScraperError(f"Failed to fetch content for item: {item_name}")
            
            # Parse HTML and classify item type
            soup = BeautifulSoup(html_content, 'html.parser')
            item_type = self._classify_item_type_from_page(soup)
            
            self.logger.info(f"Classified {item_name} as {item_type.value} item")
            
            # Extract data based on item type
            item_url = self._build_item_url(item_name)
            if item_type == ItemType.COMPLETED:
                item_data = await self._extract_completed_item_data(soup, sections, item_url)
            elif item_type in [ItemType.BASIC, ItemType.EPIC]:
                item_data = await self._extract_basic_epic_item_data(soup, sections, item_url)
            else:
                # Fallback: try to extract what we can
                item_data = await self._extract_generic_item_data(soup, sections)
            
            # Add metadata
            item_data.update({
                'item_name': item_name,
                'item_type': item_type.value,
                'data_source': 'wiki_item_scrape',
                'sections_extracted': sections or 'all'
            })
            
            self.logger.info(f"Successfully scraped data for {item_name}")
            return item_data
            
        except Exception as e:
            self.logger.error(f"Error scraping item data for {item_name}: {e}")
            raise WikiScraperError(f"Failed to scrape item data: {e}")

    async def _extract_completed_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]], item_url: str = None) -> Dict[str, Any]:
        """
        Extract data for completed items (legendary/mythic items).
        Data requirements: sidebar info, recipe, cost analysis, notes, map differences, similar items
        """
        data = {}
        
        # Extract sidebar stats (excluding recipe section)
        sidebar_data = self._extract_sidebar_stats(soup)
        if sidebar_data:
            data['stats'] = sidebar_data
        
        # Extract recipe section
        if not sections or 'recipe' in sections:
            recipe_data = self._extract_recipe_section(soup)
            if recipe_data:
                data['recipe'] = recipe_data
        
        # Extract cost analysis (requires expansion)
        if not sections or 'cost_analysis' in sections:
            cost_data = await self._extract_cost_analysis_with_expansion(soup, item_url)
            if cost_data:
                data['cost_analysis'] = cost_data
        
        # Extract notes section
        if not sections or 'notes' in sections:
            notes_data = self._extract_notes_section(soup)
            if notes_data:
                data['notes'] = notes_data
        
        # Extract map-specific differences
        if not sections or 'map_differences' in sections:
            map_data = self._extract_map_differences_section(soup)
            if map_data:
                data['map_differences'] = map_data
        
        # Extract similar items
        if not sections or 'similar_items' in sections:
            similar_data = self._extract_similar_items_section(soup)
            if similar_data:
                data['similar_items'] = similar_data
        
        return data

    async def _extract_basic_epic_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]], item_url: str = None) -> Dict[str, Any]:
        """
        Extract data for basic/epic items.
        Data requirements: sidebar info, recipe, builds info, cost analysis, similar items, old icons
        """
        data = {}
        
        # Extract sidebar stats (excluding recipe and builds sections)
        sidebar_data = self._extract_sidebar_stats(soup)
        if sidebar_data:
            data['stats'] = sidebar_data
        
        # Extract recipe section (what it builds from)
        if not sections or 'recipe' in sections:
            recipe_data = self._extract_recipe_section(soup)
            if recipe_data:
                data['recipe'] = recipe_data
        
        # Extract builds info section (what it builds into)
        if not sections or 'builds_info' in sections:
            builds_data = self._extract_builds_info_section(soup)
            if builds_data:
                data['builds_info'] = builds_data
        
        # Extract cost analysis (requires expansion)
        if not sections or 'cost_analysis' in sections:
            cost_data = await self._extract_cost_analysis_with_expansion(soup, item_url)
            if cost_data:
                data['cost_analysis'] = cost_data
        
        # Extract similar items
        if not sections or 'similar_items' in sections:
            similar_data = self._extract_similar_items_section(soup)
            if similar_data:
                data['similar_items'] = similar_data
        
        # Extract old icons section
        if not sections or 'old_icons' in sections:
            icons_data = self._extract_old_icons_section(soup)
            if icons_data:
                data['old_icons'] = icons_data
        
        return data

    async def _extract_generic_item_data(self, soup: BeautifulSoup, sections: Optional[List[str]]) -> Dict[str, Any]:
        """
        Fallback extraction for unknown item types.
        Attempts to extract any available data sections.
        """
        data = {}
        
        # Try to extract sidebar stats
        sidebar_data = self._extract_sidebar_stats(soup)
        if sidebar_data:
            data['stats'] = sidebar_data
        
        # Try to extract any recognizable sections
        for section_name, patterns in SECTION_PATTERNS.items():
            if not sections or section_name in sections:
                section_content = self._find_section_by_content_scan(soup, patterns)
                if section_content:
                    data[section_name] = section_content.get_text().strip()
        
        return data

    # Placeholder methods for specific extraction functionality
    # These will be implemented in subsequent phases
    
    def _extract_sidebar_stats(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract item statistics from sidebar infobox tabs.
        Handles Base, Masterwork, and Total tabs as seen in Echoes of Helia.
        """
        try:
            infobox = soup.find('div', class_='infobox')
            if not infobox:
                self.logger.warning("No infobox found for sidebar stats extraction")
                return None
            
            stats_data = {}
            
            # Extract item name and description
            title_elem = infobox.find('div', class_='infobox-title')
            if title_elem:
                stats_data['name'] = title_elem.get_text().strip()
            
            # Extract flavor text/description
            description_rows = infobox.find_all('div', class_='infobox-data-row')
            for row in description_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem and not row.find('div', class_='infobox-data-label'):
                    # This is likely the flavor text (no label)
                    text = value_elem.get_text().strip()
                    if len(text) > 20 and '"' in text:  # Flavor text usually has quotes
                        stats_data['description'] = text
                        break
            
            # Extract tabbed stats (Base, Masterwork, Total)
            tabber = infobox.find('div', class_='tabber')
            if tabber:
                tabs = tabber.find_all('div', class_='tabbertab')
                for tab in tabs:
                    tab_title = tab.get('data-title', '').strip()
                    if tab_title:
                        tab_stats = self._extract_stats_from_tab(tab)
                        if tab_stats:
                            stats_data[f'{tab_title.lower()}_stats'] = tab_stats
            
            # Extract passive abilities
            passive_section = infobox.find('div', class_='infobox-header', string='Passive')
            if passive_section:
                passive_content = passive_section.find_next_sibling('div', class_='infobox-section')
                if passive_content:
                    stats_data['passive'] = self._extract_passive_ability(passive_content)
            
            # Extract limitations
            limitations_header = infobox.find('div', class_='infobox-header', string='Limitations')
            if limitations_header:
                limitations_content = limitations_header.find_next_sibling('div', class_='infobox-section')
                if limitations_content:
                    stats_data['limitations'] = limitations_content.get_text().strip()
            
            # Extract basic cost and availability info
            cost_sell_info = self._extract_cost_sell_info(infobox)
            if cost_sell_info:
                stats_data.update(cost_sell_info)
            
            # Extract availability info
            availability_info = self._extract_availability_info(infobox)
            if availability_info:
                stats_data['availability'] = availability_info
            
            return stats_data if stats_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting sidebar stats: {e}")
            return None

    def _extract_stats_from_tab(self, tab: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract statistics from a single tab (Base, Masterwork, Total).
        
        Args:
            tab: BeautifulSoup Tag representing a tab
            
        Returns:
            Dictionary with stat information
        """
        try:
            stats = {}
            
            # Find the infobox-section-stacked within the tab
            stacked_section = tab.find('div', class_='infobox-section-stacked')
            if not stacked_section:
                return None
            
            # Extract individual stat rows
            data_rows = stacked_section.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem:
                    value_text = value_elem.get_text().strip()
                    
                    # Parse stat value and type
                    stat_info = self._parse_stat_value(value_text)
                    if stat_info:
                        stats[stat_info['stat_name']] = stat_info
            
            return stats if stats else None
            
        except Exception as e:
            self.logger.error(f"Error extracting stats from tab: {e}")
            return None

    def _parse_stat_value(self, value_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a stat value string to extract stat name, value, and bonus.
        Examples: "+35 ability power", "+20 ability haste", "+200 health"
        """
        try:
            # Pattern for stats with bonus (e.g., "+35 (+16.67) ability power")
            bonus_pattern = r'([+-]?\d+(?:\.\d+)?)\s*(?:\(([+-]?\d+(?:\.\d+)?)\))?\s*(.+)'
            match = re.match(bonus_pattern, value_text.strip())
            
            if match:
                base_value, bonus_value, stat_name = match.groups()
                
                # Clean up stat name
                stat_name = stat_name.strip()
                # Remove percentage indicators that might be in the name
                stat_name = re.sub(r'\s*%.*$', '', stat_name)
                
                stat_info = {
                    'stat_name': stat_name.lower().replace(' ', '_'),
                    'display_name': stat_name,
                    'base_value': float(base_value),
                    'raw_text': value_text
                }
                
                if bonus_value:
                    stat_info['bonus_value'] = float(bonus_value)
                    stat_info['total_value'] = float(base_value) + float(bonus_value)
                
                # Handle percentage stats
                if '%' in value_text:
                    stat_info['is_percentage'] = True
                
                return stat_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing stat value '{value_text}': {e}")
            return None

    def _extract_passive_ability(self, passive_content: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract passive ability information from infobox.
        
        Args:
            passive_content: BeautifulSoup Tag with passive content
            
        Returns:
            Dictionary with passive ability info
        """
        try:
            passive_info = {}
            
            # Extract passive name and description
            data_rows = passive_content.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem:
                    text = value_elem.get_text().strip()
                    
                    # Look for passive name (usually in bold or has "Unique" prefix)
                    if text.startswith('Unique'):
                        passive_info['name'] = text
                        
                        # Extract the actual description
                        # Remove HTML tags and get clean text
                        description = value_elem.get_text()
                        # Find the colon and take everything after it as description
                        if ':' in description:
                            parts = description.split(':', 1)
                            if len(parts) > 1:
                                passive_info['description'] = parts[1].strip()
                        
                        break
            
            return passive_info if passive_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting passive ability: {e}")
            return None

    def _extract_cost_sell_info(self, infobox: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract cost and sell information from infobox.
        
        Args:
            infobox: BeautifulSoup Tag representing the infobox
            
        Returns:
            Dictionary with cost and sell info
        """
        try:
            cost_info = {}
            
            # Look for cost and sell rows
            section_cells = infobox.find_all('div', class_='infobox-section-cell')
            for cell in section_cells:
                data_rows = cell.find_all('div', class_='infobox-data-row')
                for row in data_rows:
                    label_elem = row.find('div', class_='infobox-data-label')
                    value_elem = row.find('div', class_='infobox-data-value')
                    
                    if label_elem and value_elem:
                        label = label_elem.get_text().strip().lower()
                        value_text = value_elem.get_text().strip()
                        
                        if 'cost' in label:
                            # Extract numeric cost
                            cost_match = re.search(r'(\d+)', value_text)
                            if cost_match:
                                cost_info['cost'] = int(cost_match.group(1))
                                cost_info['cost_display'] = value_text
                        elif 'sell' in label:
                            # Extract sell value
                            sell_match = re.search(r'(\d+)', value_text)
                            if sell_match:
                                cost_info['sell_value'] = int(sell_match.group(1))
                                cost_info['sell_display'] = value_text
                        elif 'id' in label:
                            # Extract item ID
                            cost_info['item_id'] = value_text
            
            return cost_info if cost_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost/sell info: {e}")
            return None

    def _extract_availability_info(self, infobox: Tag) -> Optional[List[str]]:
        """
        Extract availability information (which game modes).
        
        Args:
            infobox: BeautifulSoup Tag representing the infobox
            
        Returns:
            List of available game modes
        """
        try:
            # Look for availability section
            availability_header = infobox.find('div', class_='infobox-header', string='Availability')
            if not availability_header:
                return None
            
            availability_content = availability_header.find_next_sibling('div', class_='infobox-section-cell-row')
            if not availability_content:
                return None
            
            game_modes = []
            data_rows = availability_content.find_all('div', class_='infobox-data-row')
            for row in data_rows:
                value_elem = row.find('div', class_='infobox-data-value')
                if value_elem:
                    # Extract game mode names
                    links = value_elem.find_all('a')
                    for link in links:
                        mode_name = link.get_text().strip()
                        if mode_name:
                            game_modes.append(mode_name)
            
            return game_modes if game_modes else None
            
        except Exception as e:
            self.logger.error(f"Error extracting availability info: {e}")
            return None
    
    def _extract_recipe_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract recipe/component information from recipe tables.
        Handles complex recipe trees with multiple components.
        """
        try:
            # First, try to find recipe section by header
            recipe_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['recipe'])
            if not recipe_section:
                self.logger.debug("No recipe section found")
                return None
            
            recipe_data = {}
            
            # Extract recipe table structure
            recipe_tables = recipe_section.find_all('table', style=lambda x: x and 'border-collapse' in x)
            if not recipe_tables:
                # Try alternative table detection
                recipe_tables = recipe_section.find_all('table')
            
            if recipe_tables:
                # Process the main recipe table
                main_table = recipe_tables[0]
                recipe_tree = self._parse_recipe_table(main_table)
                if recipe_tree:
                    recipe_data['recipe_tree'] = recipe_tree
            
            # Extract simple component list from infobox (if available)
            infobox = soup.find('div', class_='infobox')
            if infobox:
                recipe_header = infobox.find('div', class_='infobox-header', string='Recipe')
                if recipe_header:
                    recipe_content = recipe_header.find_next_sibling('div', class_='infobox-section')
                    if recipe_content:
                        simple_recipe = self._extract_simple_recipe(recipe_content)
                        if simple_recipe:
                            recipe_data['components'] = simple_recipe
            
            return recipe_data if recipe_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting recipe section: {e}")
            return None

    def _parse_recipe_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """
        Parse recipe table structure to extract component hierarchy.
        
        Args:
            table: BeautifulSoup Tag representing recipe table
            
        Returns:
            Dictionary with recipe tree structure
        """
        try:
            recipe_tree = {
                'components': [],
                'total_cost': None,
                'combine_cost': None
            }
            
            # Find all item elements in the table
            item_divs = table.find_all('div', class_='item')
            
            for item_div in item_divs:
                item_info = self._extract_item_from_div(item_div)
                if item_info:
                    recipe_tree['components'].append(item_info)
            
            # Try to extract costs from the table
            cost_info = self._extract_costs_from_table(table)
            if cost_info:
                recipe_tree.update(cost_info)
            
            return recipe_tree if recipe_tree['components'] else None
            
        except Exception as e:
            self.logger.error(f"Error parsing recipe table: {e}")
            return None

    def _extract_item_from_div(self, item_div: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract item information from an item div element.
        
        Args:
            item_div: BeautifulSoup Tag representing an item
            
        Returns:
            Dictionary with item information
        """
        try:
            item_info = {}
            
            # Extract item name
            name_elem = item_div.find('div', class_='item-icon name')
            if name_elem:
                # Get the link text (item name)
                link = name_elem.find('a')
                if link:
                    item_info['name'] = link.get_text().strip()
                else:
                    item_info['name'] = name_elem.get_text().strip()
            
            # Extract item cost
            gold_elem = item_div.find('div', class_='gold')
            if gold_elem:
                cost_text = gold_elem.get_text()
                # Extract numeric cost and combine cost
                cost_match = re.search(r'(\d+)(?:\s*\((\d+)\))?', cost_text)
                if cost_match:
                    total_cost = int(cost_match.group(1))
                    combine_cost = int(cost_match.group(2)) if cost_match.group(2) else 0
                    
                    item_info['total_cost'] = total_cost
                    if combine_cost > 0:
                        item_info['combine_cost'] = combine_cost
                        item_info['component_cost'] = total_cost - combine_cost
            
            # Extract item icon/image info
            icon_elem = item_div.find('span', class_='inline-image item-icon')
            if icon_elem:
                img = icon_elem.find('img')
                if img:
                    item_info['icon_url'] = img.get('src', '')
            
            return item_info if item_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting item from div: {e}")
            return None

    def _extract_costs_from_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract cost information from recipe table.
        
        Args:
            table: BeautifulSoup Tag representing recipe table
            
        Returns:
            Dictionary with cost information
        """
        try:
            costs = {}
            
            # Look for gold values in the table
            gold_elements = table.find_all(string=re.compile(r'\d+'))
            gold_values = []
            
            for element in gold_elements:
                # Extract numeric values that might be costs
                numbers = re.findall(r'\d+', str(element))
                for number in numbers:
                    value = int(number)
                    if 50 <= value <= 5000:  # Reasonable item cost range
                        gold_values.append(value)
            
            if gold_values:
                # The highest value is usually the total cost
                costs['estimated_total_cost'] = max(gold_values)
                # Lower values might be component costs
                if len(gold_values) > 1:
                    costs['component_costs'] = sorted(gold_values[:-1])
            
            return costs if costs else None
            
        except Exception as e:
            self.logger.error(f"Error extracting costs from table: {e}")
            return None

    def _extract_simple_recipe(self, recipe_content: Tag) -> Optional[List[str]]:
        """
        Extract simple component list from infobox recipe section.
        
        Args:
            recipe_content: BeautifulSoup Tag with recipe content
            
        Returns:
            List of component names
        """
        try:
            components = []
            
            # Look for item links in the recipe content
            links = recipe_content.find_all('a')
            for link in links:
                # Check if this looks like an item link
                href = link.get('href', '')
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    component_name = link.get_text().strip()
                    if component_name and component_name not in components:
                        components.append(component_name)
            
            # Also look for item icons with data-item attributes
            item_icons = recipe_content.find_all('span', attrs={'data-item': True})
            for icon in item_icons:
                item_name = icon.get('data-item', '')
                if item_name and item_name not in components:
                    components.append(item_name)
            
            return components if components else None
            
        except Exception as e:
            self.logger.error(f"Error extracting simple recipe: {e}")
            return None
    
    def _extract_builds_info_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract builds into information for basic/epic items"""
        try:
            # Find builds section using patterns
            builds_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['builds_info'])
            if not builds_section:
                self.logger.debug("No builds info section found")
                return None
            
            builds_data = {
                'builds_into': [],
                'upgrade_paths': []
            }
            
            # Extract item links from builds section
            item_links = builds_section.find_all('a')
            for link in item_links:
                href = link.get('href', '')
                # Filter for item pages (exclude categories, files, etc.)
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    item_name = link.get_text().strip()
                    if item_name and item_name not in builds_data['builds_into']:
                        builds_data['builds_into'].append(item_name)
            
            # Look for item icons with data-item attributes
            item_icons = builds_section.find_all('span', attrs={'data-item': True})
            for icon in item_icons:
                item_name = icon.get('data-item', '')
                if item_name and item_name not in builds_data['builds_into']:
                    builds_data['builds_into'].append(item_name)
            
            # Extract upgrade paths from tables if present
            upgrade_tables = builds_section.find_all('table')
            for table in upgrade_tables:
                upgrade_path = self._extract_upgrade_path_from_table(table)
                if upgrade_path:
                    builds_data['upgrade_paths'].append(upgrade_path)
            
            # Extract descriptive text about builds
            text_content = builds_section.get_text().strip()
            if text_content and len(text_content) > 20:
                builds_data['description'] = text_content
            
            return builds_data if (builds_data['builds_into'] or builds_data['upgrade_paths']) else None
            
        except Exception as e:
            self.logger.error(f"Error extracting builds info section: {e}")
            return None
    
    async def _extract_cost_analysis_with_expansion(self, soup: BeautifulSoup, item_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Extract cost analysis by expanding collapsible section with Selenium.
        Uses Selenium to click expand toggles and extract hidden content.
        """
        try:
            # First, try to find cost analysis section in the current HTML
            cost_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['cost_analysis'])
            if cost_section:
                # Check if section is already expanded
                expanded_content = self._extract_cost_data_from_section(cost_section)
                if expanded_content and self._is_cost_data_complete(expanded_content):
                    self.logger.debug("Cost analysis already expanded in static HTML")
                    return expanded_content
            
            # Detect expandable sections that might contain cost analysis
            expandable_sections = self._detect_expandable_sections(soup)
            cost_expandables = [
                section for section in expandable_sections 
                if section['purpose'] == 'cost_analysis' or 
                'cost' in section['element'].get_text()[:200].lower() or
                'efficiency' in section['element'].get_text()[:200].lower()
            ]
            
            if not cost_expandables:
                self.logger.debug("No expandable cost analysis sections found")
                return None
            
            # Use Selenium to expand and extract content
            return await self._expand_and_extract_with_selenium(cost_expandables[0], item_url)
            
        except Exception as e:
            self.logger.error(f"Error extracting cost analysis with expansion: {e}")
            return None

    async def _expand_and_extract_with_selenium(self, expandable_info: Dict[str, Any], item_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Use Selenium to expand a section and extract its content.
        
        Args:
            expandable_info: Dictionary containing expandable section information
            
        Returns:
            Extracted cost analysis data or None
        """
        driver = None
        try:
            self.logger.info("Starting Selenium expansion for cost analysis")
            
            # Create Selenium driver (following stats_scraper pattern)
            driver = self._create_selenium_driver()
            
            # Use the provided item URL for Selenium navigation
            if not item_url:
                self.logger.error("No item URL provided for Selenium expansion")
                return None
            
            page_url = item_url
            
            driver.get(page_url)
            wait = WebDriverWait(driver, 10)
            
            # Find the expandable element on the live page
            expandable_element = self._find_expandable_element_in_driver(
                driver, expandable_info
            )
            
            if not expandable_element:
                self.logger.error("Could not find expandable element in live page")
                return None
            
            # Click to expand
            self._click_to_expand(driver, expandable_element, expandable_info)
            
            # Wait for content to load
            time.sleep(1.5)  # Allow time for JavaScript to update DOM
            
            # Extract the expanded content
            expanded_soup = BeautifulSoup(driver.page_source, 'html.parser')
            cost_section = self._find_section_by_content_scan(
                expanded_soup, SECTION_PATTERNS['cost_analysis']
            )
            
            if cost_section:
                cost_data = self._extract_cost_data_from_section(cost_section)
                if cost_data:
                    self.logger.info("Successfully extracted expanded cost analysis")
                    return cost_data
            
            self.logger.warning("Could not extract cost data after expansion")
            return None
            
        except Exception as e:
            self.logger.error(f"Error in Selenium expansion: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    self.logger.error(f"Error closing Selenium driver: {e}")

    def _extract_page_url_from_soup(self, element: Tag) -> Optional[str]:
        """
        Extract the current page URL from soup elements.
        This is a workaround - ideally URL would be passed in context.
        """
        try:
            # Look for canonical URL in head
            soup = element.find_parent('html') or element
            canonical = soup.find('link', rel='canonical')
            if canonical and canonical.get('href'):
                return canonical['href']
            
            # Look for URL in script tags or other metadata
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.get_text()
                if 'wgPageName' in script_text:
                    # Extract page name from MediaWiki config
                    import re
                    match = re.search(r'"wgPageName":"([^"]+)"', script_text)
                    if match:
                        page_name = match.group(1)
                        return f"{self.BASE_URL}{page_name}"
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting page URL: {e}")
            return None

    def _find_expandable_element_in_driver(self, driver, expandable_info: Dict[str, Any]) -> Optional[Any]:
        """
        Find the expandable element in the live Selenium driver page.
        
        Args:
            driver: Selenium WebDriver instance
            expandable_info: Information about the expandable section
            
        Returns:
            Selenium WebElement or None
        """
        try:
            element_classes = expandable_info.get('classes', [])
            element_type = expandable_info.get('type', '')
            
            # Strategy 1: Find by classes
            if element_classes:
                class_selector = '.' + '.'.join(element_classes)
                try:
                    element = driver.find_element(By.CSS_SELECTOR, class_selector)
                    return element
                except NoSuchElementException:
                    pass
            
            # Strategy 2: Find by common expandable patterns
            common_selectors = [
                '.mw-collapsible',
                '.mw-collapsible-toggle',
                '[class*="toggle"]',
                '[class*="expand"]',
                '[class*="collapse"]'
            ]
            
            for selector in common_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Check if this element contains cost-related text
                        element_text = element.text.lower()
                        if 'cost' in element_text or 'efficiency' in element_text:
                            return element
                except NoSuchElementException:
                    continue
            
            # Strategy 3: Find by text content
            try:
                element = driver.find_element(
                    By.XPATH, 
                    "//*[contains(text(), 'Cost Analysis') or contains(text(), 'cost analysis')]"
                )
                return element
            except NoSuchElementException:
                pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding expandable element: {e}")
            return None

    def _click_to_expand(self, driver, element, expandable_info: Dict[str, Any]) -> None:
        """
        Click on element to expand the section.
        
        Args:
            driver: Selenium WebDriver instance
            element: WebElement to click
            expandable_info: Information about the expandable section
        """
        try:
            element_type = expandable_info.get('type', '')
            
            # Different click strategies based on element type
            if element_type == 'mw-collapsible':
                # Look for the toggle element within the collapsible section
                try:
                    toggle = element.find_element(By.CSS_SELECTOR, '.mw-collapsible-toggle')
                    toggle.click()
                    self.logger.debug("Clicked mw-collapsible toggle")
                    return
                except NoSuchElementException:
                    pass
            
            # Default: click the element itself
            try:
                # Scroll element into view
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                
                # Click the element
                element.click()
                self.logger.debug(f"Clicked expandable element: {element.tag_name}")
                
            except Exception as click_error:
                # Try JavaScript click as fallback
                driver.execute_script("arguments[0].click();", element)
                self.logger.debug("Used JavaScript click as fallback")
                
        except Exception as e:
            self.logger.error(f"Error clicking to expand: {e}")

    def _extract_cost_data_from_section(self, section: Tag) -> Optional[Dict[str, Any]]:
        """
        Extract cost analysis data from a cost section.
        
        Args:
            section: BeautifulSoup Tag containing cost analysis
            
        Returns:
            Dictionary with cost analysis data
        """
        try:
            cost_data = {}
            
            # Extract gold values from the section
            gold_values = []
            gold_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:gold|g)',
                r'(\d+(?:\.\d+)?)\s*ability power',
                r'(\d+(?:\.\d+)?)\s*ability haste',  
                r'(\d+(?:\.\d+)?)\s*health',
                r'(\d+(?:\.\d+)?)\s*mana regeneration'
            ]
            
            section_text = section.get_text()
            for pattern in gold_patterns:
                matches = re.findall(pattern, section_text, re.IGNORECASE)
                gold_values.extend([float(match) for match in matches])
            
            if gold_values:
                cost_data['gold_values'] = gold_values
            
            # Extract efficiency percentage
            efficiency_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:gold\s*)?efficient?', section_text, re.IGNORECASE)
            if efficiency_match:
                cost_data['efficiency_percentage'] = float(efficiency_match.group(1))
            
            # Extract total gold value
            total_match = re.search(r'total\s*gold\s*value\s*[=:]\s*(\d+(?:\.\d+)?)', section_text, re.IGNORECASE)
            if total_match:
                cost_data['total_gold_value'] = float(total_match.group(1))
            
            # Extract stat breakdowns from lists
            stat_lists = section.find_all(['ul', 'ol'])
            for stat_list in stat_lists:
                items = stat_list.find_all('li')
                for item in items:
                    item_text = item.get_text()
                    # Look for stat = gold patterns
                    stat_match = re.search(r'(\d+)\s*([^=]+?)\s*=\s*(\d+(?:\.\d+)?)', item_text)
                    if stat_match:
                        amount, stat_name, gold_value = stat_match.groups()
                        stat_key = stat_name.strip().lower().replace(' ', '_')
                        cost_data[f'{stat_key}_value'] = {
                            'amount': int(amount),
                            'gold_equivalent': float(gold_value)
                        }
            
            return cost_data if cost_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting cost data: {e}")
            return None

    def _is_cost_data_complete(self, cost_data: Dict[str, Any]) -> bool:
        """
        Check if extracted cost data appears complete.
        
        Args:
            cost_data: Dictionary with cost analysis data
            
        Returns:
            True if data appears complete
        """
        try:
            # Check for key indicators of complete cost analysis
            has_efficiency = 'efficiency_percentage' in cost_data
            has_gold_values = 'gold_values' in cost_data and len(cost_data['gold_values']) > 0
            has_stat_breakdowns = any(key.endswith('_value') for key in cost_data.keys())
            
            is_complete = has_efficiency or (has_gold_values and has_stat_breakdowns)
            self.logger.debug(f"Cost data completeness: efficiency={has_efficiency}, gold_values={has_gold_values}, stat_breakdowns={has_stat_breakdowns}")
            
            return is_complete
            
        except Exception as e:
            self.logger.error(f"Error checking cost data completeness: {e}")
            return False
    
    def _extract_notes_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract notes/gameplay information"""
        try:
            # Find notes section using patterns
            notes_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['notes'])
            if not notes_section:
                self.logger.debug("No notes section found")
                return None
            
            notes_data = {
                'gameplay_notes': [],
                'trivia': [],
                'interactions': []
            }
            
            # Extract structured notes from lists
            note_lists = notes_section.find_all(['ul', 'ol'])
            for note_list in note_lists:
                list_items = note_list.find_all('li')
                for item in list_items:
                    note_text = item.get_text().strip()
                    if note_text:
                        # Categorize notes based on content
                        note_text_lower = note_text.lower()
                        if any(keyword in note_text_lower for keyword in ['damage', 'heal', 'shield', 'effect']):
                            notes_data['gameplay_notes'].append(note_text)
                        elif any(keyword in note_text_lower for keyword in ['interact', 'stack', 'trigger']):
                            notes_data['interactions'].append(note_text)
                        else:
                            notes_data['trivia'].append(note_text)
            
            # Extract paragraph notes
            paragraphs = notes_section.find_all('p')
            for paragraph in paragraphs:
                para_text = paragraph.get_text().strip()
                if para_text and len(para_text) > 10:
                    # Categorize paragraph content
                    para_text_lower = para_text.lower()
                    if any(keyword in para_text_lower for keyword in ['damage', 'heal', 'shield', 'effect']):
                        notes_data['gameplay_notes'].append(para_text)
                    elif any(keyword in para_text_lower for keyword in ['interact', 'stack', 'trigger']):
                        notes_data['interactions'].append(para_text)
                    else:
                        notes_data['trivia'].append(para_text)
            
            # Extract general text content if no structured elements found
            if not any(notes_data.values()):
                general_text = notes_section.get_text().strip()
                if general_text and len(general_text) > 20:
                    notes_data['general_notes'] = general_text
            
            # Remove empty categories
            notes_data = {k: v for k, v in notes_data.items() if v}
            
            return notes_data if notes_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting notes section: {e}")
            return None
    
    def _extract_map_differences_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract map-specific differences"""
        try:
            # Find map differences section using patterns
            map_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['map_differences'])
            if not map_section:
                self.logger.debug("No map differences section found")
                return None
            
            map_data = {
                'summoners_rift': {},
                'howling_abyss': {},
                'twisted_treeline': {},
                'general_differences': []
            }
            
            # Look for map-specific subsections
            map_keywords = {
                'summoners_rift': ["summoner's rift", "classic", "sr"],
                'howling_abyss': ["howling abyss", "aram", "ha"],
                'twisted_treeline': ["twisted treeline", "3v3", "tt"]
            }
            
            # Extract map-specific information
            for map_name, keywords in map_keywords.items():
                map_content = self._extract_map_specific_content(map_section, keywords)
                if map_content:
                    map_data[map_name] = map_content
            
            # Extract general differences from lists and paragraphs
            difference_lists = map_section.find_all(['ul', 'ol'])
            for diff_list in difference_lists:
                list_items = diff_list.find_all('li')
                for item in list_items:
                    diff_text = item.get_text().strip()
                    if diff_text and len(diff_text) > 10:
                        map_data['general_differences'].append(diff_text)
            
            # Extract paragraph differences
            paragraphs = map_section.find_all('p')
            for paragraph in paragraphs:
                para_text = paragraph.get_text().strip()
                if para_text and len(para_text) > 20:
                    map_data['general_differences'].append(para_text)
            
            # Extract table-based differences
            difference_tables = map_section.find_all('table')
            for table in difference_tables:
                table_data = self._extract_map_differences_from_table(table)
                if table_data:
                    map_data['table_differences'] = table_data
            
            # Remove empty categories
            map_data = {k: v for k, v in map_data.items() if v}
            
            return map_data if map_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting map differences section: {e}")
            return None
    
    def _extract_similar_items_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract similar items recommendations"""
        try:
            # Find similar items section using patterns
            similar_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['similar_items'])
            if not similar_section:
                self.logger.debug("No similar items section found")
                return None
            
            similar_data = {
                'alternative_items': [],
                'related_items': [],
                'categories': []
            }
            
            # Extract item links from similar section
            item_links = similar_section.find_all('a')
            for link in item_links:
                href = link.get('href', '')
                # Filter for item pages
                if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                    item_name = link.get_text().strip()
                    if item_name:
                        # Try to categorize the relationship
                        link_context = self._get_link_context(link)
                        if any(keyword in link_context.lower() for keyword in ['alternative', 'instead', 'replace']):
                            if item_name not in similar_data['alternative_items']:
                                similar_data['alternative_items'].append(item_name)
                        else:
                            if item_name not in similar_data['related_items']:
                                similar_data['related_items'].append(item_name)
            
            # Look for item icons with data-item attributes
            item_icons = similar_section.find_all('span', attrs={'data-item': True})
            for icon in item_icons:
                item_name = icon.get('data-item', '')
                if item_name and item_name not in similar_data['related_items']:
                    similar_data['related_items'].append(item_name)
            
            # Extract category information
            category_links = similar_section.find_all('a', href=lambda x: x and '/Category:' in x)
            for cat_link in category_links:
                category_name = cat_link.get_text().strip()
                if category_name and category_name not in similar_data['categories']:
                    similar_data['categories'].append(category_name)
            
            # Extract structured recommendations from column templates
            column_templates = similar_section.find_all('div', class_='columntemplate')
            for template in column_templates:
                template_items = self._extract_items_from_column_template(template)
                if template_items:
                    similar_data['structured_recommendations'] = template_items
            
            # Extract descriptive text about similar items
            text_content = similar_section.get_text().strip()
            if text_content and len(text_content) > 30:
                similar_data['description'] = text_content
            
            # Remove empty categories
            similar_data = {k: v for k, v in similar_data.items() if v}
            
            return similar_data if similar_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting similar items section: {e}")
            return None
    
    def _extract_old_icons_section(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract old icons/versions for basic/epic items"""
        try:
            # Find old icons section using patterns
            icons_section = self._find_section_by_content_scan(soup, SECTION_PATTERNS['old_icons'])
            if not icons_section:
                self.logger.debug("No old icons section found")
                return None
            
            icons_data = {
                'version_history': [],
                'icon_changes': [],
                'historical_versions': {}
            }
            
            # Extract version information from tables
            version_tables = icons_section.find_all('table')
            for table in version_tables:
                version_info = self._extract_version_info_from_table(table)
                if version_info:
                    icons_data['version_history'].extend(version_info)
            
            # Extract image elements (old icons)
            icon_images = icons_section.find_all('img')
            for img in icon_images:
                icon_info = {
                    'url': img.get('src', ''),
                    'alt_text': img.get('alt', ''),
                    'title': img.get('title', '')
                }
                
                # Try to extract version information from image context
                img_context = self._get_image_context(img)
                if img_context:
                    icon_info['version_context'] = img_context
                
                icons_data['icon_changes'].append(icon_info)
            
            # Extract version-specific information from lists
            version_lists = icons_section.find_all(['ul', 'ol'])
            for version_list in version_lists:
                list_items = version_list.find_all('li')
                for item in list_items:
                    item_text = item.get_text().strip()
                    if item_text:
                        # Look for version patterns (V1.0, Patch 1.0, etc.)
                        version_match = re.search(r'(V?\d+\.\d+|[Pp]atch\s+\d+\.\d+)', item_text)
                        if version_match:
                            version = version_match.group(1)
                            description = item_text
                            icons_data['historical_versions'][version] = description
            
            # Extract general historical information
            paragraphs = icons_section.find_all('p')
            for paragraph in paragraphs:
                para_text = paragraph.get_text().strip()
                if para_text and len(para_text) > 20:
                    # Look for historical change descriptions
                    if any(keyword in para_text.lower() for keyword in ['changed', 'updated', 'modified', 'replaced']):
                        icons_data['icon_changes'].append({
                            'description': para_text,
                            'type': 'text_description'
                        })
            
            # Remove empty categories
            icons_data = {k: v for k, v in icons_data.items() if v}
            
            return icons_data if icons_data else None
            
        except Exception as e:
            self.logger.error(f"Error extracting old icons section: {e}")
            return None
    
    # Helper methods for specific extraction functionality
    
    def _extract_upgrade_path_from_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """Extract upgrade path information from table structure."""
        try:
            upgrade_path = {
                'items': [],
                'costs': [],
                'description': ''
            }
            
            # Look for item elements in table cells
            cells = table.find_all(['td', 'th'])
            for cell in cells:
                # Extract item names from links
                item_links = cell.find_all('a')
                for link in item_links:
                    href = link.get('href', '')
                    if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                        item_name = link.get_text().strip()
                        if item_name:
                            upgrade_path['items'].append(item_name)
                
                # Extract cost information
                cell_text = cell.get_text()
                cost_matches = re.findall(r'(\d+)\s*(?:gold|g)', cell_text)
                for cost in cost_matches:
                    upgrade_path['costs'].append(int(cost))
            
            # Extract table caption as description
            caption = table.find('caption')
            if caption:
                upgrade_path['description'] = caption.get_text().strip()
            
            return upgrade_path if upgrade_path['items'] else None
            
        except Exception as e:
            self.logger.error(f"Error extracting upgrade path from table: {e}")
            return None
    
    def _extract_map_specific_content(self, section: Tag, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Extract content specific to a particular map."""
        try:
            map_content = {
                'differences': [],
                'stats': {},
                'notes': []
            }
            
            section_text = section.get_text().lower()
            
            # Check if this section contains map-specific information
            if not any(keyword in section_text for keyword in keywords):
                return None
            
            # Extract paragraphs that mention the map
            paragraphs = section.find_all('p')
            for paragraph in paragraphs:
                para_text = paragraph.get_text().strip()
                para_text_lower = para_text.lower()
                
                if any(keyword in para_text_lower for keyword in keywords):
                    if any(stat_keyword in para_text_lower for stat_keyword in ['damage', 'health', 'mana', 'cooldown']):
                        # This looks like a stat difference
                        stat_info = self._parse_stat_difference(para_text)
                        if stat_info:
                            map_content['stats'].update(stat_info)
                    else:
                        map_content['differences'].append(para_text)
            
            # Extract list items that mention the map
            list_items = section.find_all('li')
            for item in list_items:
                item_text = item.get_text().strip()
                item_text_lower = item_text.lower()
                
                if any(keyword in item_text_lower for keyword in keywords):
                    map_content['notes'].append(item_text)
            
            # Remove empty categories
            map_content = {k: v for k, v in map_content.items() if v}
            
            return map_content if map_content else None
            
        except Exception as e:
            self.logger.error(f"Error extracting map-specific content: {e}")
            return None
    
    def _parse_stat_difference(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse stat differences from text."""
        try:
            stat_diffs = {}
            
            # Look for patterns like "damage reduced by 50%" or "cooldown increased to 120 seconds"
            stat_patterns = [
                r'(\w+)\s+(?:reduced|increased|changed)\s+(?:by|to)\s+(\d+(?:\.\d+)?)\s*(%|seconds?|g)',
                r'(\w+)\s*[=:]\s*(\d+(?:\.\d+)?)\s*(%|seconds?|g)',
                r'(\d+(?:\.\d+)?)\s*(%|seconds?|g)?\s+(\w+)'
            ]
            
            for pattern in stat_patterns:
                matches = re.findall(pattern, text.lower())
                for match in matches:
                    if len(match) == 3:
                        stat_name, value, unit = match
                        stat_diffs[stat_name] = {
                            'value': float(value),
                            'unit': unit
                        }
            
            return stat_diffs if stat_diffs else None
            
        except Exception as e:
            self.logger.error(f"Error parsing stat difference: {e}")
            return None
    
    def _extract_map_differences_from_table(self, table: Tag) -> Optional[Dict[str, Any]]:
        """Extract map differences from table structure."""
        try:
            table_data = {
                'headers': [],
                'rows': [],
                'map_columns': {}
            }
            
            # Extract table headers
            header_row = table.find('tr')
            if header_row:
                headers = header_row.find_all(['th', 'td'])
                for i, header in enumerate(headers):
                    header_text = header.get_text().strip()
                    table_data['headers'].append(header_text)
                    
                    # Identify map-specific columns
                    header_lower = header_text.lower()
                    if "summoner's rift" in header_lower or 'classic' in header_lower:
                        table_data['map_columns']['summoners_rift'] = i
                    elif 'howling abyss' in header_lower or 'aram' in header_lower:
                        table_data['map_columns']['howling_abyss'] = i
                    elif 'twisted treeline' in header_lower or '3v3' in header_lower:
                        table_data['map_columns']['twisted_treeline'] = i
            
            # Extract table rows
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text().strip() for cell in cells]
                if row_data:
                    table_data['rows'].append(row_data)
            
            return table_data if table_data['rows'] else None
            
        except Exception as e:
            self.logger.error(f"Error extracting map differences from table: {e}")
            return None
    
    def _get_link_context(self, link: Tag) -> str:
        """Get context text around a link element."""
        try:
            # Get parent element and surrounding text
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                # Find the link text within parent and get surrounding context
                link_text = link.get_text()
                link_start = parent_text.find(link_text)
                if link_start != -1:
                    # Get 50 characters before and after the link
                    start = max(0, link_start - 50)
                    end = min(len(parent_text), link_start + len(link_text) + 50)
                    return parent_text[start:end].strip()
            
            return ''
            
        except Exception as e:
            self.logger.error(f"Error getting link context: {e}")
            return ''
    
    def _extract_items_from_column_template(self, template: Tag) -> Optional[Dict[str, List[str]]]:
        """Extract items from column template structure."""
        try:
            template_items = {}
            
            # Look for columns within the template
            columns = template.find_all('div', class_=lambda x: x and 'column' in ' '.join(x).lower())
            
            for i, column in enumerate(columns):
                column_items = []
                
                # Extract item links from this column
                item_links = column.find_all('a')
                for link in item_links:
                    href = link.get('href', '')
                    if '/en-us/' in href and not any(skip in href for skip in ['Category:', 'File:', 'Special:']):
                        item_name = link.get_text().strip()
                        if item_name:
                            column_items.append(item_name)
                
                # Extract item icons
                item_icons = column.find_all('span', attrs={'data-item': True})
                for icon in item_icons:
                    item_name = icon.get('data-item', '')
                    if item_name and item_name not in column_items:
                        column_items.append(item_name)
                
                if column_items:
                    # Try to identify column purpose from header or context
                    column_header = column.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    if column_header:
                        column_name = column_header.get_text().strip().lower()
                    else:
                        column_name = f'column_{i + 1}'
                    
                    template_items[column_name] = column_items
            
            return template_items if template_items else None
            
        except Exception as e:
            self.logger.error(f"Error extracting items from column template: {e}")
            return None
    
    def _extract_version_info_from_table(self, table: Tag) -> Optional[List[Dict[str, Any]]]:
        """Extract version information from table structure."""
        try:
            version_info = []
            
            # Look for version-related headers
            headers = table.find_all(['th', 'td'])
            version_column = None
            description_column = None
            
            # Identify columns
            for i, header in enumerate(headers[:10]):  # Check first row
                header_text = header.get_text().lower()
                if 'version' in header_text or 'patch' in header_text:
                    version_column = i
                elif 'change' in header_text or 'description' in header_text:
                    description_column = i
            
            # Extract version data from rows
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) > max(version_column or 0, description_column or 0):
                    version_data = {}
                    
                    if version_column is not None and len(cells) > version_column:
                        version_text = cells[version_column].get_text().strip()
                        if version_text:
                            version_data['version'] = version_text
                    
                    if description_column is not None and len(cells) > description_column:
                        desc_text = cells[description_column].get_text().strip()
                        if desc_text:
                            version_data['description'] = desc_text
                    
                    # If no specific columns identified, extract any version patterns
                    if not version_data:
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            version_match = re.search(r'(V?\d+\.\d+|[Pp]atch\s+\d+\.\d+)', cell_text)
                            if version_match:
                                version_data['version'] = version_match.group(1)
                                version_data['description'] = cell_text
                                break
                    
                    if version_data:
                        version_info.append(version_data)
            
            return version_info if version_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting version info from table: {e}")
            return None
    
    def _get_image_context(self, img: Tag) -> str:
        """Get context information for an image element."""
        try:
            context_info = []
            
            # Get alt text and title
            alt_text = img.get('alt', '')
            title_text = img.get('title', '')
            
            if alt_text:
                context_info.append(f"Alt: {alt_text}")
            if title_text:
                context_info.append(f"Title: {title_text}")
            
            # Get caption or nearby text
            parent = img.parent
            if parent:
                # Look for caption elements
                caption = parent.find('caption') or parent.find_next('caption')
                if caption:
                    context_info.append(f"Caption: {caption.get_text().strip()}")
                
                # Get surrounding text
                parent_text = parent.get_text().strip()
                if parent_text and len(parent_text) < 200:  # Avoid very long text
                    context_info.append(f"Context: {parent_text}")
            
            return ' | '.join(context_info)
            
        except Exception as e:
            self.logger.error(f"Error getting image context: {e}")
            return ''
    
    # Cache and content fetching methods
    
    def get_cached_content(self, item_name: str) -> Optional[str]:
        """Get cached HTML content for an item if valid."""
        try:
            if self.enable_cache and self.cache_manager:
                return self.cache_manager.get_cached_content(item_name)
            return None
        except Exception as e:
            self.logger.error(f"Error getting cached content for {item_name}: {e}")
            return None
    
    def cache_content(self, item_name: str, content: str) -> None:
        """Cache HTML content for an item."""
        try:
            if self.enable_cache and self.cache_manager:
                self.cache_manager.cache_content(item_name, content)
        except Exception as e:
            self.logger.error(f"Error caching content for {item_name}: {e}")
    
    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content from URL."""
        try:
            await self._ensure_client()
            response = await self._make_request(url)
            return response.text
        except Exception as e:
            self.logger.error(f"Error fetching page content from {url}: {e}")
            return None