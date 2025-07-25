"""
Rune Patch Service for League of Legends MCP Server

This module provides service layer functionality for retrieving rune patch
history using RunePatchScraper for accurate patch information.

Following the item_service.py pattern with perfect name processing.
"""

import logging
from typing import Dict, Any, Optional
import structlog

try:
    from src.data_sources.scrapers.runes.rune_patch_scraper import RunePatchScraper, WikiScraperError
    from src.models.exceptions import RuneNotFoundError
except ImportError:
    from ...data_sources.scrapers.runes.rune_patch_scraper import RunePatchScraper, WikiScraperError
    from ...models.exceptions import RuneNotFoundError


class RunePatchService:
    """Service class for rune patch history operations using RunePatchScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the rune patch service.

        Args:
            enable_wiki: Whether to enable RunePatchScraper.
            use_cache: Whether to enable caching in RunePatchScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.rune_patch_scraper = RunePatchScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.rune_patch_scraper = None

        self.logger.info(
            "RunePatchService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    async def get_rune_patch_notes(self, rune_name: str, patch_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Get patch notes for a specific rune.

        Args:
            rune_name: Name of the rune (e.g., "Summon Aery")
            patch_version: Optional specific patch version (e.g., "14.19", "V14.19")

        Returns:
            Dictionary containing patch history data

        Raises:
            RuneNotFoundError: If rune is not found
        """
        try:
            # Normalize rune name for consistent processing
            normalized_name = self._normalize_rune_name(rune_name)
            
            self.logger.info(
                "Getting rune patch notes",
                rune_name=rune_name,
                normalized_name=normalized_name,
                patch_version=patch_version
            )

            if not self.enable_wiki or not self.rune_patch_scraper:
                # Return mock data if wiki is disabled
                return self._get_mock_patch_data(rune_name, patch_version)

            # Use RunePatchScraper to fetch real data
            if patch_version:
                patch_data = await self.rune_patch_scraper.scrape_specific_patch_note(
                    normalized_name, patch_version
                )
            else:
                patch_data = await self.rune_patch_scraper.scrape_all_patch_notes(normalized_name)
            
            # Transform data to service format
            transformed_data = self._transform_patch_data(patch_data, rune_name)
            
            self.logger.info(
                "Successfully retrieved rune patch notes",
                rune_name=rune_name,
                patch_count=transformed_data.get('total_patches', 0)
            )
            
            return transformed_data

        except RuneNotFoundError:
            self.logger.warning(f"Rune not found: {rune_name}")
            raise
        except WikiScraperError as e:
            self.logger.error(f"Wiki scraper error for {rune_name}: {str(e)}")
            # Fallback to mock data on scraper error
            return self._get_mock_patch_data(rune_name, patch_version, error_fallback=True)
        except Exception as e:
            self.logger.error(f"Unexpected error getting rune patch notes for {rune_name}: {str(e)}")
            raise

    def _normalize_rune_name(self, rune_name: str) -> str:
        """
        Normalize rune name for processing.

        Args:
            rune_name: Raw rune name

        Returns:
            Normalized rune name
        """
        # Basic normalization - trim whitespace and handle case
        normalized = rune_name.strip()
        
        # Capitalize first letter of each word for consistency
        normalized = ' '.join(word.capitalize() for word in normalized.split())
        
        return normalized

    def _transform_patch_data(self, scraper_data: Dict[str, Any], original_name: str) -> Dict[str, Any]:
        """
        Transform scraper data to service format.

        Args:
            scraper_data: Raw data from RunePatchScraper
            original_name: Original rune name from request

        Returns:
            Transformed data in service format
        """
        transformed = {
            'rune_name': original_name,
            'normalized_name': scraper_data.get('rune', original_name),
            'data_source': 'wiki_rune_patch_scrape',
            'patches': scraper_data.get('patches', []),
            'total_patches': scraper_data.get('total_patches', 0),
            'message': scraper_data.get('message', '')
        }

        # Add patch version if it was a specific query
        if 'patch_version' in scraper_data:
            transformed['requested_patch'] = scraper_data['patch_version']

        # Transform individual patches for consistency
        transformed_patches = []
        for patch in scraper_data.get('patches', []):
            transformed_patch = {
                'version': patch.get('version', ''),
                'changes': patch.get('changes', []),
                'change_count': patch.get('change_count', 0)
            }
            transformed_patches.append(transformed_patch)
            
        transformed['patches'] = transformed_patches

        return transformed

    def _get_mock_patch_data(self, rune_name: str, patch_version: Optional[str] = None, 
                            error_fallback: bool = False) -> Dict[str, Any]:
        """
        Get mock patch data for testing/fallback purposes.

        Args:
            rune_name: Name of the rune
            patch_version: Optional patch version
            error_fallback: Whether this is an error fallback

        Returns:
            Mock patch data
        """
        data_source = 'mock_fallback_error' if error_fallback else 'mock_data'
        
        mock_patches = [
            {
                'version': 'V14.21',
                'changes': [
                    f'Mock change 1 for {rune_name} in V14.21',
                    f'Mock change 2 for {rune_name} in V14.21'
                ],
                'change_count': 2
            },
            {
                'version': 'V14.19',
                'changes': [
                    f'Mock change 1 for {rune_name} in V14.19'
                ],
                'change_count': 1
            }
        ]

        # Filter to specific patch if requested
        if patch_version:
            # Normalize the patch version for comparison
            normalized_patch = patch_version.upper()
            if not normalized_patch.startswith('V'):
                normalized_patch = f'V{normalized_patch}'
                
            filtered_patches = [p for p in mock_patches if p['version'] == normalized_patch]
            mock_patches = filtered_patches
            
        mock_data = {
            'rune_name': rune_name,
            'normalized_name': self._normalize_rune_name(rune_name),
            'data_source': data_source,
            'patches': mock_patches,
            'total_patches': len(mock_patches),
            'message': f'Mock patch data for {rune_name}'
        }

        if patch_version:
            mock_data['requested_patch'] = patch_version

        return mock_data

    async def cleanup(self):
        """Clean up resources."""
        if self.rune_patch_scraper:
            await self.rune_patch_scraper.cleanup()
        self.logger.info("RunePatchService cleanup completed")