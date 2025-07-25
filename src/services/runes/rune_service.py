"""
Rune Service for League of Legends MCP Server

This module provides service layer functionality for retrieving rune
data using RuneDataScraper for accurate rune information with
sidebar, notes, and strategy sections.

Following the item_service.py pattern with perfect name processing.
"""

import logging
import re
from typing import Dict, Any, Optional, List
import structlog

try:
    from src.data_sources.scrapers.runes.rune_data_scraper import RuneDataScraper, WikiScraperError
    from src.models.exceptions import RuneNotFoundError
except ImportError:
    from ...data_sources.scrapers.runes.rune_data_scraper import RuneDataScraper, WikiScraperError
    from ...models.exceptions import RuneNotFoundError


class RuneService:
    """Service class for rune data operations using RuneDataScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the rune service.

        Args:
            enable_wiki: Whether to enable RuneDataScraper.
            use_cache: Whether to enable caching in RuneDataScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.rune_scraper = RuneDataScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.rune_scraper = None

        self.logger.info(
            "RuneService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    async def get_rune_data(self, rune_name: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get rune data for a specific rune.

        Args:
            rune_name: Name of the rune (e.g., "Summon Aery")
            sections: Optional list of sections to extract (sidebar, notes, strategy)

        Returns:
            Dictionary containing rune data

        Raises:
            RuneNotFoundError: If rune is not found
        """
        try:
            # Normalize rune name for consistent processing
            normalized_name = self._normalize_rune_name(rune_name)
            
            self.logger.info(
                "Getting rune data",
                rune_name=rune_name,
                normalized_name=normalized_name,
                sections=sections
            )

            if not self.enable_wiki or not self.rune_scraper:
                # Return mock data if wiki is disabled
                return self._get_mock_rune_data(rune_name, sections)

            # Use RuneDataScraper to fetch real data
            rune_data = await self.rune_scraper.scrape_rune_data(normalized_name, sections)
            
            # Transform data to service format
            transformed_data = self._transform_rune_data(rune_data, rune_name)
            
            self.logger.info(
                "Successfully retrieved rune data",
                rune_name=rune_name,
                sections_found=len(transformed_data.get('sections', {})),
                data_source=transformed_data.get('data_source', 'unknown')
            )
            
            return transformed_data

        except RuneNotFoundError:
            self.logger.warning(f"Rune not found: {rune_name}")
            raise
        except WikiScraperError as e:
            self.logger.error(f"Wiki scraper error for {rune_name}: {str(e)}")
            # Fallback to mock data on scraper error
            return self._get_mock_rune_data(rune_name, sections, error_fallback=True)
        except Exception as e:
            self.logger.error(f"Unexpected error getting rune data for {rune_name}: {str(e)}")
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

    def _transform_rune_data(self, scraper_data: Dict[str, Any], original_name: str) -> Dict[str, Any]:
        """
        Transform scraper data to service format.

        Args:
            scraper_data: Raw data from RuneDataScraper
            original_name: Original rune name from request

        Returns:
            Transformed data in service format
        """
        transformed = {
            'rune_name': original_name,
            'normalized_name': scraper_data.get('rune', original_name),
            'data_source': scraper_data.get('data_source', 'wiki_rune_scrape'),
            'sections': {}
        }

        # Transform each section
        raw_sections = scraper_data.get('sections', {})
        
        if 'sidebar' in raw_sections:
            transformed['sections']['sidebar'] = self._transform_sidebar_data(raw_sections['sidebar'])
            
        if 'notes' in raw_sections:
            transformed['sections']['notes'] = self._transform_section_data(raw_sections['notes'])
            
        if 'strategy' in raw_sections:
            transformed['sections']['strategy'] = self._transform_section_data(raw_sections['strategy'])

        return transformed

    def _transform_sidebar_data(self, sidebar_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform sidebar data to clean format.

        Args:
            sidebar_data: Raw sidebar data

        Returns:
            Cleaned sidebar data
        """
        return {
            'path': sidebar_data.get('path'),
            'slot': sidebar_data.get('slot'),
            'description': sidebar_data.get('description'),
            'range': sidebar_data.get('range')
        }

    def _transform_section_data(self, section_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform section data (notes/strategy) to clean format.

        Args:
            section_data: Raw section data

        Returns:
            Cleaned section data
        """
        return {
            'content': section_data.get('content', []),
            'found': section_data.get('found', False),
            'item_count': len(section_data.get('content', []))
        }

    def _get_mock_rune_data(self, rune_name: str, sections: Optional[List[str]] = None, 
                           error_fallback: bool = False) -> Dict[str, Any]:
        """
        Get mock rune data for testing/fallback purposes.

        Args:
            rune_name: Name of the rune
            sections: Optional list of sections
            error_fallback: Whether this is an error fallback

        Returns:
            Mock rune data
        """
        data_source = 'mock_fallback_error' if error_fallback else 'mock_data'
        
        mock_data = {
            'rune_name': rune_name,
            'normalized_name': self._normalize_rune_name(rune_name),
            'data_source': data_source,
            'sections': {}
        }

        sections_to_include = sections or ['sidebar', 'notes', 'strategy']
        
        if 'sidebar' in sections_to_include:
            mock_data['sections']['sidebar'] = {
                'path': 'Sorcery',
                'slot': 'Keystone',
                'description': f'Mock description for {rune_name} - this is fallback data',
                'range': 'Global'
            }
            
        if 'notes' in sections_to_include:
            mock_data['sections']['notes'] = {
                'content': [
                    f'Mock note 1 for {rune_name}',
                    f'Mock note 2 for {rune_name}'
                ],
                'found': True,
                'item_count': 2
            }
            
        if 'strategy' in sections_to_include:
            mock_data['sections']['strategy'] = {
                'content': [
                    f'Mock strategy tip 1 for {rune_name}',
                    f'Mock strategy tip 2 for {rune_name}'
                ],
                'found': True,
                'item_count': 2
            }

        return mock_data

    async def cleanup(self):
        """Clean up resources."""
        if self.rune_scraper:
            await self.rune_scraper.cleanup()
        self.logger.info("RuneService cleanup completed")