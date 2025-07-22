"""
Item List Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting comprehensive item data
from the main League of Legends Items page, building searchable item directories
and indexes for the item system.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup, Tag

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError


@dataclass
class ItemData:
    """Represents individual item data from the main page grid"""
    name: str
    category: str
    search_terms: List[str] = field(default_factory=list)
    game_modes: List[str] = field(default_factory=list)
    url: str = ""
    preview_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemDirectory:
    """Complete item directory with search capabilities"""
    categories: Dict[str, List[str]] = field(default_factory=dict)  # category -> item names
    items: Dict[str, ItemData] = field(default_factory=dict)  # item name -> ItemData
    search_index: Dict[str, List[str]] = field(default_factory=dict)  # search term -> item names
    url_mappings: Dict[str, str] = field(default_factory=dict)  # item name -> URL
    normalized_names: Dict[str, str] = field(default_factory=dict)  # normalized -> original name
    last_updated: datetime = field(default_factory=datetime.now)


class ItemListScraper(BaseScraper):
    """Scraper for the main LoL Items page to build comprehensive item directory"""

    ITEMS_URL = "https://wiki.leagueoflegends.com/en-us/Item"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_items_main_page(self) -> ItemDirectory:
        """
        Main entry point to scrape the items page and build comprehensive directory.
        
        Returns:
            ItemDirectory: Complete item directory with search capabilities
        """
        self.logger.info("Starting main items page scraping")
        
        try:
            # Fetch the main items page
            soup = await self._fetch_items_page()
            
            # Parse the HTML structure
            directory = self._parse_item_grid(soup)
            
            # Build search indexes
            self._build_search_indexes(directory)
            
            # Generate URL mappings
            self._generate_url_mappings(directory)
            
            self.logger.info(f"Successfully scraped {len(directory.items)} items across {len(directory.categories)} categories")
            return directory
            
        except Exception as e:
            self.logger.error(f"Failed to scrape items main page: {e}")
            raise WikiScraperError(f"Items main page scraping failed: {e}") from e

    async def _fetch_items_page(self) -> BeautifulSoup:
        """Fetch and parse the main items page"""
        await self._ensure_client()
        
        try:
            response = await self._make_request(self.ITEMS_URL)
            content = response.text
            soup = BeautifulSoup(content, "lxml")
            
            # Validate we have the expected structure
            item_grid = soup.find("div", id="item-grid")
            if not item_grid:
                raise WikiScraperError("Main items page structure not found - no item-grid div")
            
            self.logger.info("Successfully fetched and parsed main items page")
            return soup
            
        except Exception as e:
            self.logger.error(f"Failed to fetch items page: {e}")
            raise WikiScraperError(f"Failed to fetch items page: {e}") from e

    def _parse_item_grid(self, soup: BeautifulSoup) -> ItemDirectory:
        """
        Parse the item grid structure to extract categories and items.
        
        Updated approach: Find all item-icon divs directly, then try to determine categories
        from the surrounding HTML structure.
        """
        directory = ItemDirectory()
        
        # Find the main item grid container
        item_grid = soup.find("div", id="item-grid")
        if not item_grid:
            raise WikiScraperError("Item grid container not found")
        
        # Find all item icons directly in the grid
        all_item_icons = item_grid.find_all("div", class_="item-icon")
        self.logger.info(f"Found {len(all_item_icons)} item icons in the grid")
        
        if not all_item_icons:
            self.logger.warning("No item-icon divs found in the item grid")
            return directory
        
        # Try to organize items by categories based on structure
        category_items = self._organize_items_by_categories(item_grid, all_item_icons)
        
        # Build directory from organized items
        for category_name, items in category_items.items():
            directory.categories[category_name] = []
            for item_data in items:
                directory.items[item_data.name] = item_data
                directory.categories[category_name].append(item_data.name)
        
        # If no categories were determined, create a general category
        if not directory.categories and all_item_icons:
            self.logger.info("No categories determined, creating 'All Items' category")
            directory.categories["All Items"] = []
            for item_icon in all_item_icons:
                item_data = self._parse_single_item(item_icon, "All Items")
                if item_data:
                    directory.items[item_data.name] = item_data
                    directory.categories["All Items"].append(item_data.name)
        
        self.logger.info(f"Parsed {len(directory.categories)} categories with {len(directory.items)} total items")
        return directory

    def _organize_items_by_categories(self, item_grid: Tag, all_item_icons: List[Tag]) -> Dict[str, List[ItemData]]:
        """
        Try to organize items by categories based on the HTML structure.
        This method attempts different strategies to determine item categories.
        """
        category_items = {}
        used_items = set()  # Track items already assigned to avoid duplicates
        
        # Strategy 1: Look for category headers and try to find associated items
        category_elements = item_grid.find_all("dt")
        self.logger.debug(f"Found {len(category_elements)} category headers")
        
        for category_dt in category_elements:
            category_name = category_dt.get_text().strip()
            if not category_name:
                continue
            
            # Try to find items associated with this category
            items_for_category = self._find_items_for_category(category_dt, all_item_icons, used_items)
            
            if items_for_category:
                category_items[category_name] = items_for_category
                # Mark these items as used
                for item_data in items_for_category:
                    used_items.add(item_data.name)
                self.logger.debug(f"Found {len(items_for_category)} items for category '{category_name}'")
        
        # Strategy 2: If Strategy 1 failed, try to infer categories from visual structure
        if not category_items:
            category_items = self._infer_categories_from_structure(item_grid, all_item_icons)
        
        return category_items

    def _find_items_for_category(self, category_dt: Tag, all_item_icons: List[Tag], used_items: set) -> List[ItemData]:
        """
        Try to find items associated with a specific category header.
        """
        items = []
        
        # Strategy 1: Look in parent container for items
        parent = category_dt.parent
        if parent:
            parent_items = parent.find_all("div", class_="item-icon")
            for item_icon in parent_items:
                if item_icon in all_item_icons:  # Make sure it's one of our main items
                    item_name = item_icon.get("data-item", "")
                    if item_name and item_name not in used_items:  # Skip already used items
                        item_data = self._parse_single_item(item_icon, category_dt.get_text().strip())
                        if item_data:
                            items.append(item_data)
        
        # Strategy 2: Look for items after the category in document order
        if not items:
            current = category_dt
            items_found = 0
            max_items_to_check = 50  # Limit search to avoid infinite loops
            
            while current and items_found < max_items_to_check:
                current = current.find_next()
                if not current:
                    break
                
                # If we find another category header, stop
                if current.name == 'dt' and current != category_dt:
                    break
                
                # If we find an item icon, add it
                if (current.name == 'div' and 
                    'item-icon' in current.get('class', []) and 
                    current in all_item_icons):
                    item_name = current.get("data-item", "")
                    if item_name and item_name not in used_items:  # Skip already used items
                        item_data = self._parse_single_item(current, category_dt.get_text().strip())
                        if item_data:
                            items.append(item_data)
                            items_found += 1
                        
                        # Stop after finding a reasonable number of items for this category
                        if items_found >= 20:  # Most categories don't have more than 20 items
                            break
        
        return items

    def _infer_categories_from_structure(self, item_grid: Tag, all_item_icons: List[Tag]) -> Dict[str, List[ItemData]]:
        """
        Fallback method to infer categories from the HTML structure.
        """
        category_items = {}
        
        # For now, create categories based on common search terms or put all in one category
        # This is a fallback when we can't determine the structure
        
        # Group items by common search terms that might indicate categories
        starter_keywords = ['starter', 'doran', 'dblade', 'dring', 'dshield']
        legendary_keywords = ['legendary']
        support_keywords = ['support']
        boots_keywords = ['boots', 'treads', 'greaves']
        
        starter_items = []
        legendary_items = []
        support_items = []
        boots_items = []
        other_items = []
        
        for item_icon in all_item_icons:
            search_terms = item_icon.get("data-search", "").lower()
            item_name = item_icon.get("data-item", "")
            
            # Determine category based on search terms
            category = "Other Items"  # Default
            
            if any(keyword in search_terms for keyword in starter_keywords):
                category = "Starter items"
                items_list = starter_items
            elif any(keyword in search_terms for keyword in legendary_keywords):
                category = "Legendary items"
                items_list = legendary_items
            elif any(keyword in search_terms for keyword in support_keywords):
                category = "Support items" 
                items_list = support_items
            elif any(keyword in search_terms for keyword in boots_keywords) or 'boots' in item_name.lower():
                category = "Boots"
                items_list = boots_items
            else:
                items_list = other_items
            
            item_data = self._parse_single_item(item_icon, category)
            if item_data:
                items_list.append(item_data)
        
        # Add non-empty categories
        if starter_items:
            category_items["Starter items"] = starter_items
        if legendary_items:
            category_items["Legendary items"] = legendary_items
        if support_items:
            category_items["Support items"] = support_items
        if boots_items:
            category_items["Boots"] = boots_items
        if other_items:
            category_items["Other Items"] = other_items
        
        self.logger.info(f"Inferred categories from structure: {list(category_items.keys())}")
        return category_items

    def _parse_category_items(self, item_list_div: Tag, category_name: str) -> List[ItemData]:
        """Parse individual items from a category's item list div"""
        items = []
        
        # Find all item icons within the list
        item_icons = item_list_div.find_all("div", class_="item-icon")
        
        for item_icon in item_icons:
            try:
                item_data = self._parse_single_item(item_icon, category_name)
                if item_data:
                    items.append(item_data)
            except Exception as e:
                self.logger.warning(f"Failed to parse item in category {category_name}: {e}")
                continue
        
        self.logger.debug(f"Parsed {len(items)} items from category: {category_name}")
        return items

    def _parse_single_item(self, item_icon: Tag, category_name: str) -> Optional[ItemData]:
        """Parse a single item from its icon div element"""
        
        # Extract data attributes
        item_name = item_icon.get("data-item")
        if not item_name:
            self.logger.warning("Item with missing data-item attribute")
            return None
        
        # Parse search terms from data-search attribute
        search_attr = item_icon.get("data-search", "")
        search_terms = [term.strip() for term in search_attr.split(",") if term.strip()]
        
        # Parse game modes from data-modes attribute  
        modes_attr = item_icon.get("data-modes", "")
        game_modes = [mode.strip() for mode in modes_attr.split(",") if mode.strip()]
        
        # Extract any preview data (tooltip content, etc.)
        preview_data = self._extract_preview_data(item_icon)
        
        item_data = ItemData(
            name=item_name,
            category=category_name,
            search_terms=search_terms,
            game_modes=game_modes,
            preview_data=preview_data
        )
        
        self.logger.debug(f"Parsed item: {item_name} (category: {category_name})")
        return item_data

    def _extract_preview_data(self, item_icon: Tag) -> Dict[str, Any]:
        """Extract any available preview data from the item icon element"""
        preview_data = {}
        
        try:
            # Look for image alt text or title attributes
            img_tag = item_icon.find("img")
            if img_tag:
                alt_text = img_tag.get("alt", "")
                title_text = img_tag.get("title", "")
                if alt_text:
                    preview_data["alt_text"] = alt_text
                if title_text:
                    preview_data["title"] = title_text
            
            # Look for any data attributes that might contain additional info
            for attr_name, attr_value in item_icon.attrs.items():
                if attr_name.startswith("data-") and attr_name not in ["data-item", "data-search", "data-modes"]:
                    preview_data[attr_name] = attr_value
                    
        except Exception as e:
            self.logger.debug(f"Failed to extract preview data: {e}")
        
        return preview_data

    def _build_search_indexes(self, directory: ItemDirectory) -> None:
        """Build comprehensive search indexes for fast item lookup"""
        
        # Initialize search index
        search_index = {}
        normalized_names = {}
        
        for item_name, item_data in directory.items.items():
            # Normalize item name for search
            normalized_name = self._normalize_item_name(item_name)
            normalized_names[normalized_name] = item_name
            
            # Index by exact name (both original and normalized)
            self._add_to_search_index(search_index, item_name.lower(), item_name)
            self._add_to_search_index(search_index, normalized_name.lower(), item_name)
            
            # Index by category
            self._add_to_search_index(search_index, item_data.category.lower(), item_name)
            
            # Index by search terms
            for term in item_data.search_terms:
                if term:  # Skip empty terms
                    self._add_to_search_index(search_index, term.lower(), item_name)
            
            # Index by game modes
            for mode in item_data.game_modes:
                if mode:  # Skip empty modes
                    self._add_to_search_index(search_index, mode.lower(), item_name)
            
            # Index individual words from item name for partial matching
            name_words = re.findall(r'\w+', item_name.lower())
            for word in name_words:
                if len(word) > 2:  # Skip very short words
                    self._add_to_search_index(search_index, word, item_name)
        
        # Store indexes in directory
        directory.search_index = search_index
        directory.normalized_names = normalized_names
        
        self.logger.info(f"Built search index with {len(search_index)} search terms")

    def _add_to_search_index(self, search_index: Dict[str, List[str]], term: str, item_name: str) -> None:
        """Add an item to the search index under a specific term"""
        if term not in search_index:
            search_index[term] = []
        if item_name not in search_index[term]:
            search_index[term].append(item_name)

    def _generate_url_mappings(self, directory: ItemDirectory) -> None:
        """Generate URL mappings for individual item pages"""
        
        url_mappings = {}
        
        for item_name in directory.items.keys():
            # Generate URL for individual item page
            normalized_name = self._normalize_item_name_for_url(item_name)
            item_url = f"/en-us/{normalized_name}"
            url_mappings[item_name] = item_url
            
        directory.url_mappings = url_mappings
        self.logger.info(f"Generated URL mappings for {len(url_mappings)} items")

    def _normalize_item_name(self, name: str) -> str:
        """Normalize item name for search (preserve readability)"""
        # Remove extra whitespace and title case
        normalized = " ".join(name.strip().split())
        return normalized

    def _normalize_item_name_for_url(self, name: str) -> str:
        """Normalize item name for URL generation"""
        # Handle special characters for URLs
        normalized = name.strip()
        
        # Replace spaces with underscores
        normalized = normalized.replace(" ", "_")
        
        # Use quote but allow apostrophes to be encoded properly (include ' in safe chars initially)
        normalized = quote(normalized, safe="_-'")
        
        # Now manually encode apostrophes to %27 
        normalized = normalized.replace("'", "%27")
        
        return normalized

    async def search_items(self, query: str, directory: ItemDirectory, max_results: int = 10) -> List[Tuple[str, float]]:
        """
        Search for items using the built search index.
        
        Args:
            query: Search query string
            directory: ItemDirectory with search index
            max_results: Maximum number of results to return
            
        Returns:
            List of (item_name, relevance_score) tuples
        """
        if not query or not directory.search_index:
            return []
        
        query_lower = query.lower().strip()
        results = {}
        exact_match_items = set()
        
        # Direct search index lookups (exact match)
        if query_lower in directory.search_index:
            for item_name in directory.search_index[query_lower]:
                results[item_name] = 1.0  # Exact match gets full score
                exact_match_items.add(item_name)
        
        # Partial word matching (only for items not already matched exactly)
        query_words = re.findall(r'\w+', query_lower)
        for word in query_words:
            if len(word) > 2:  # Skip short words
                for search_term, item_names in directory.search_index.items():
                    if word in search_term and search_term != query_lower:  # Avoid re-scoring exact matches
                        for item_name in item_names:
                            if item_name not in exact_match_items:  # Don't downgrade exact matches
                                results[item_name] = results.get(item_name, 0) + 0.5
        
        # Sort by relevance score
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_results[:max_results]