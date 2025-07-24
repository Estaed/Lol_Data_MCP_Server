"""
Item Patch Note Service for League of Legends MCP Server

This module provides service layer functionality for retrieving item
patch history data using ItemPatchScraper for accurate patch note extraction.

Following the champion patch_note_service.py pattern for consistency.
"""

import logging
import re
from typing import Dict, Any, Optional
import structlog

from src.data_sources.scrapers.items.item_patch_scraper import ItemPatchScraper, WikiScraperError
from src.models.exceptions import ItemNotFoundError


class ItemPatchService:
    """Service class for item patch note operations using ItemPatchScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the item patch service.

        Args:
            enable_wiki: Whether to enable ItemPatchScraper.
            use_cache: Whether to enable caching in ItemPatchScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.patch_scraper = ItemPatchScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.patch_scraper = None

        self.logger.info(
            "ItemPatchService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    async def get_item_patch_notes(
        self,
        item: str,
        patch_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get patch notes for an item.

        Args:
            item: Item name
            patch_version: Optional specific patch version (e.g., "14.19", "V14.19")

        Returns:
            Dictionary containing patch note data

        Raises:
            ItemNotFoundError: If item is not found
            WikiScraperError: If scraping fails
        """
        if not self.enable_wiki:
            self.logger.warning("Wiki scraping is disabled")
            return {
                'item': item,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'message': 'Wiki scraping is disabled'
            }

        try:
            self.logger.info(
                "Fetching item patch notes",
                item=item,
                patch_version=patch_version
            )

            # Determine which scraper method to use
            if patch_version:
                # Get specific patch version
                result = await self.patch_scraper.scrape_specific_patch_note(
                    item_name=item,
                    patch_version=patch_version
                )
            else:
                # Get all patch notes
                result = await self.patch_scraper.scrape_all_patch_notes(
                    item_name=item
                )

            # Add metadata
            result['service'] = 'ItemPatchService'
            result['wiki_enabled'] = self.enable_wiki
            result['cache_enabled'] = self.patch_scraper.enable_cache if self.patch_scraper else False

            self.logger.info(
                "Item patch notes retrieved successfully",
                item=item,
                total_patches=result['total_patches'],
                patch_version=patch_version
            )

            return result

        except WikiScraperError as e:
            self.logger.error(f"Wiki scraping error for {item}: {str(e)}")
            
            # Check if it's an item not found error
            if "not found" in str(e).lower() or "404" in str(e):
                raise ItemNotFoundError(f"Item '{item}' not found")
            
            return {
                'item': item,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Failed to retrieve patch notes for {item}'
            }

        except Exception as e:
            self.logger.error(f"Unexpected error for {item}: {str(e)}")
            return {
                'item': item,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Unexpected error retrieving patch notes for {item}'
            }

    async def get_item_patch_history(self, item: str) -> Dict[str, Any]:
        """
        Get complete patch history for an item.

        Args:
            item: Item name

        Returns:
            Dictionary containing complete patch history

        Raises:
            ItemNotFoundError: If item is not found
        """
        return await self.get_item_patch_notes(item, patch_version=None)

    async def get_patch_changes(self, item: str, patch_version: str) -> Dict[str, Any]:
        """
        Get changes for a specific patch version.

        Args:
            item: Item name
            patch_version: Specific patch version

        Returns:
            Dictionary containing patch changes

        Raises:
            ItemNotFoundError: If item is not found
        """
        return await self.get_item_patch_notes(item, patch_version=patch_version)

    async def search_patch_changes(
        self,
        item: str,
        search_term: str,
        patch_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for specific changes in item patch notes.

        Args:
            item: Item name
            search_term: Term to search for in patch changes
            patch_version: Optional specific patch version to search in

        Returns:
            Dictionary containing matching patch changes
        """
        try:
            # Get patch notes
            patch_data = await self.get_item_patch_notes(item, patch_version)
            
            # Search through changes
            matching_patches = []
            
            for patch in patch_data['patches']:
                matching_changes = []
                
                for change in patch['changes']:
                    if search_term.lower() in change.lower():
                        matching_changes.append(change)
                
                if matching_changes:
                    matching_patches.append({
                        'version': patch['version'],
                        'changes': matching_changes,
                        'change_count': len(matching_changes)
                    })
            
            return {
                'item': item,
                'search_term': search_term,
                'patch_version': patch_version,
                'patches': matching_patches,
                'total_patches': len(matching_patches),
                'message': f'Found {len(matching_patches)} patches with changes matching "{search_term}"'
            }
            
        except Exception as e:
            self.logger.error(f"Error searching patch changes: {str(e)}")
            return {
                'item': item,
                'search_term': search_term,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Error searching patch changes for {item}'
            }

    async def cleanup(self):
        """Clean up service resources."""
        if self.patch_scraper:
            await self.patch_scraper.close()
            self.logger.info("ItemPatchService cleanup completed")