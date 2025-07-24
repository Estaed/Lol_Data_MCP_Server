"""
Item Service for League of Legends MCP Server

This module provides service layer functionality for retrieving item
data using ItemDataScraper for accurate item information with
differentiated extraction for completed vs basic/epic items.

Following Task 2.2.3 requirements with perfect name processing.
"""

import logging
import re
from typing import Dict, Any, Optional, List
import structlog

from src.data_sources.scrapers.items.item_data_scraper import ItemDataScraper, WikiScraperError
from src.models.exceptions import ItemNotFoundError


class ItemService:
    """Service class for item data operations using ItemDataScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the item service.

        Args:
            enable_wiki: Whether to enable ItemDataScraper.
            use_cache: Whether to enable caching in ItemDataScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.item_scraper = ItemDataScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.item_scraper = None

        self.logger.info(
            "ItemService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    def _normalize_item_name(self, name: str) -> str:
        """
        Normalize item name for wiki lookup.
        
        Args:
            name: Raw item name input
            
        Returns:
            Normalized item name suitable for wiki URLs
        """
        # Strip whitespace and handle basic capitalization
        normalized = name.strip()
        
        # Split by words to properly handle title case while preserving apostrophes
        words = normalized.split()
        title_words = []
        
        for word in words:
            # Handle apostrophes correctly - don't title case after apostrophes
            if "'" in word:
                # Split on apostrophe and only title case the first part
                parts = word.split("'")
                parts[0] = parts[0].capitalize()
                # Keep the rest as-is (typically 's', 't', etc.)
                title_words.append("'".join(parts))
            else:
                title_words.append(word.capitalize())
        
        normalized = " ".join(title_words)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        self.logger.debug(f"Normalized item name: {name} -> {normalized}")
        return normalized

    async def get_item_data(
        self,
        item_name: str,
        sections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve item data with differentiated extraction for completed vs basic/epic items.
        
        Args:
            item_name: Perfect item name (e.g., "Echoes of Helia", "Kindlegem")
            sections: Optional list of specific sections to extract
            
        Returns:
            Dictionary with item data based on item type (differentiated extraction)
            
        Raises:
            ItemNotFoundError: If item is not found
            WikiScraperError: If scraping fails
        """
        self.logger.info(
            "Item data request",
            item_name=item_name,
            sections=sections,
            wiki_enabled=self.enable_wiki
        )
        
        item_name_normalized = self._normalize_item_name(item_name)

        if not self.enable_wiki or not self.item_scraper:
            raise WikiScraperError("Wiki scraping is not enabled.")

        try:
            # Use ItemDataScraper for differentiated data extraction
            self.logger.info(f"Scraping item data for {item_name_normalized}")
            item_data = await self.item_scraper.scrape_item_data(
                item_name=item_name_normalized,
                sections=sections
            )
            
            # Process and format the data
            processed_data = self._transform_item_data(item_data, item_name_normalized)
            
            self.logger.info(
                "Item data retrieved successfully",
                item_name=item_name_normalized,
                item_type=processed_data.get("item_type"),
                sections_extracted=list(processed_data.get("data", {}).keys())
            )
            
            return processed_data
                
        except (WikiScraperError, ValueError) as e:
            self.logger.error(f"Failed to get item data for {item_name_normalized}: {e}")
            
            # Check if it's an item not found error
            if "not found" in str(e).lower() or "404" in str(e):
                raise ItemNotFoundError(item_name_normalized) from e
            
            # Re-raise other wiki scraping errors
            raise WikiScraperError(f"Failed to retrieve item data for {item_name_normalized}: {str(e)}") from e

    def _transform_item_data(self, raw_data: Dict[str, Any], item_name: str) -> Dict[str, Any]:
        """
        Transform raw scraper data into structured service format.
        
        Args:
            raw_data: Raw data from ItemDataScraper
            item_name: Normalized item name
            
        Returns:
            Transformed item data in service format
        """
        return {
            "name": item_name,
            "item_type": raw_data.get("item_type", "unknown"),
            "data": raw_data.get("data", {}),
            "sections_available": raw_data.get("sections_available", []),
            "data_source": raw_data.get("data_source", "item_data_scraper"),
            "url": raw_data.get("url"),
            "timestamp": raw_data.get("timestamp")
        }

    async def get_item_stats(self, item_name: str) -> Dict[str, Any]:
        """
        Get item statistics (stats section only).
        
        Args:
            item_name: Perfect item name
            
        Returns:
            Dictionary with item statistics
        """
        return await self.get_item_data(item_name, sections=["stats"])

    async def get_item_recipe(self, item_name: str) -> Dict[str, Any]:
        """
        Get item recipe information (recipe section only).
        
        Args:
            item_name: Perfect item name
            
        Returns:
            Dictionary with item recipe data
        """
        return await self.get_item_data(item_name, sections=["recipe"])

    async def get_item_cost_analysis(self, item_name: str) -> Dict[str, Any]:
        """
        Get item cost analysis (cost_analysis section only).
        
        Args:
            item_name: Perfect item name
            
        Returns:
            Dictionary with item cost analysis
        """
        return await self.get_item_data(item_name, sections=["cost_analysis"])

    async def get_similar_items(self, item_name: str) -> Dict[str, Any]:
        """
        Get similar items (similar_items section only).
        
        Args:
            item_name: Perfect item name
            
        Returns:
            Dictionary with similar items data
        """
        return await self.get_item_data(item_name, sections=["similar_items"])

    async def cleanup(self):
        """Cleanup resources (ItemDataScraper, etc.)"""
        if self.item_scraper:
            await self.item_scraper.close()
            self.logger.info("ItemDataScraper resources cleaned up")