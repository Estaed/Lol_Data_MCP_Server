"""
Champion Patch Note Service for League of Legends MCP Server

This module provides service layer functionality for retrieving champion
patch history data using PatchNoteScraper for accurate patch note extraction.
"""

import logging
import re
from typing import Dict, Any, Optional
import structlog

from src.data_sources.scrapers.patch_note_scraper import PatchNoteScraper, WikiScraperError
from src.models.exceptions import ChampionNotFoundError


class PatchNoteService:
    """Service class for champion patch note operations using PatchNoteScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the patch note service.

        Args:
            enable_wiki: Whether to enable PatchNoteScraper.
            use_cache: Whether to enable caching in PatchNoteScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.patch_scraper = PatchNoteScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.patch_scraper = None

        self.logger.info(
            "PatchNoteService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )



    async def get_champion_patch_notes(
        self,
        champion: str,
        patch_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get patch notes for a champion.

        Args:
            champion: Champion name
            patch_version: Optional specific patch version (e.g., "4.12", "14.21")

        Returns:
            Dictionary containing patch note data

        Raises:
            ChampionNotFoundError: If champion is not found
            WikiScraperError: If scraping fails
        """
        if not self.enable_wiki:
            self.logger.warning("Wiki scraping is disabled")
            return {
                'champion': champion,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'message': 'Wiki scraping is disabled'
            }

        try:
            normalized_champion = self.patch_scraper.normalize_champion_name(champion)
            
            self.logger.info(
                "Fetching patch notes",
                champion=champion,
                normalized_champion=normalized_champion,
                patch_version=patch_version
            )

            # Determine which scraper method to use
            if patch_version:
                # Get specific patch version
                result = await self.patch_scraper.scrape_specific_patch_note(
                    champion_name=normalized_champion,
                    patch_version=patch_version
                )
            else:
                # Get all patch notes
                result = await self.patch_scraper.scrape_all_patch_notes(
                    champion_name=normalized_champion
                )

            # Add metadata
            result['service'] = 'PatchNoteService'
            result['wiki_enabled'] = self.enable_wiki
            result['cache_enabled'] = self.patch_scraper.enable_cache if self.patch_scraper else False

            self.logger.info(
                "Patch notes retrieved successfully",
                champion=champion,
                total_patches=result['total_patches'],
                patch_version=patch_version
            )

            return result

        except WikiScraperError as e:
            self.logger.error(f"Wiki scraping error for {champion}: {str(e)}")
            
            # Check if it's a champion not found error
            if "not found" in str(e).lower() or "404" in str(e):
                raise ChampionNotFoundError(f"Champion '{champion}' not found")
            
            return {
                'champion': champion,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Failed to retrieve patch notes for {champion}'
            }

        except Exception as e:
            self.logger.error(f"Unexpected error for {champion}: {str(e)}")
            return {
                'champion': champion,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Unexpected error retrieving patch notes for {champion}'
            }

    async def get_champion_patch_history(self, champion: str) -> Dict[str, Any]:
        """
        Get complete patch history for a champion.

        Args:
            champion: Champion name

        Returns:
            Dictionary containing complete patch history

        Raises:
            ChampionNotFoundError: If champion is not found
        """
        return await self.get_champion_patch_notes(champion, patch_version=None)

    async def get_patch_changes(self, champion: str, patch_version: str) -> Dict[str, Any]:
        """
        Get changes for a specific patch version.

        Args:
            champion: Champion name
            patch_version: Specific patch version

        Returns:
            Dictionary containing patch changes

        Raises:
            ChampionNotFoundError: If champion is not found
        """
        return await self.get_champion_patch_notes(champion, patch_version=patch_version)

    async def search_patch_changes(
        self,
        champion: str,
        search_term: str,
        patch_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for specific changes in patch notes.

        Args:
            champion: Champion name
            search_term: Term to search for in patch changes
            patch_version: Optional specific patch version to search in

        Returns:
            Dictionary containing matching patch changes
        """
        try:
            # Get patch notes
            patch_data = await self.get_champion_patch_notes(champion, patch_version)
            
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
                'champion': champion,
                'search_term': search_term,
                'patch_version': patch_version,
                'patches': matching_patches,
                'total_patches': len(matching_patches),
                'message': f'Found {len(matching_patches)} patches with changes matching "{search_term}"'
            }
            
        except Exception as e:
            self.logger.error(f"Error searching patch changes: {str(e)}")
            return {
                'champion': champion,
                'search_term': search_term,
                'patch_version': patch_version,
                'patches': [],
                'total_patches': 0,
                'error': str(e),
                'message': f'Error searching patch changes for {champion}'
            }

    async def cleanup(self):
        """Clean up service resources."""
        if self.patch_scraper:
            await self.patch_scraper.close()
            self.logger.info("PatchNoteService cleanup completed") 