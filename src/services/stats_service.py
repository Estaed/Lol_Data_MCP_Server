"""
Champion Stats Service for League of Legends MCP Server

This module provides service layer functionality for retrieving champion
statistics data using StatsScraper for accurate per-level stats.
"""

import logging
import re
from typing import Dict, Any, Optional
import structlog

from src.data_sources.scrapers.stats_scraper import StatsScraper, WikiScraperError
from src.models.exceptions import ChampionNotFoundError


class StatsService:
    """Service class for champion stats operations using StatsScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the stats service.

        Args:
            enable_wiki: Whether to enable StatsScraper.
            use_cache: Whether to enable caching in StatsScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.stats_scraper = StatsScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.stats_scraper = None

        self.logger.info(
            "StatsService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    def _normalize_champion_name(self, name: str) -> str:
        """Normalize champion name for wiki lookup."""
        normalized = name.strip().title()
        normalized = re.sub(r'\s+', ' ', normalized)
        self.logger.debug(f"Normalized champion name: {name} -> {normalized}")
        return normalized

    def _format_stat_name(self, stat_name: str, resource_type: str) -> str:
        """Format stat names for display, especially resources."""
        if stat_name == 'resource':
            if resource_type == 'N/A':
                return 'Resource'  # Will show "N/A" as value
            else:
                return f'Resource ({resource_type})'
        elif stat_name == 'resource_regen':
            if resource_type == 'N/A':
                return 'Resource Regen'  # Will show "N/A" as value
            elif resource_type == 'Secondary Bar':
                return 'Secondary Bar'  # For Rage, Heat, Flow, etc.
            else:
                return f'Resource Regen ({resource_type})'
        else:
            # Capitalize and format other stat names
            formatted = stat_name.replace('_', ' ').title()
            return formatted

    async def get_champion_stats(
        self,
        champion: str,
        level: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve champion stats with level-specific scraping for Task 2.1.8.
        
        Args:
            champion: Champion name
            level: Optional level (1-18). If provided, scrapes exact stats for that level.
            
        Returns:
            Dictionary with champion stats
        """
        self.logger.info(
            "Champion stats request",
            champion=champion,
            level=level,
            wiki_enabled=self.enable_wiki
        )
        
        champion_name = self._normalize_champion_name(champion)

        if not self.enable_wiki or not self.stats_scraper:
            raise WikiScraperError("Wiki scraping is not enabled.")

        try:
            if level is not None:
                # Task 2.1.8: Use Selenium level-specific scraping for accurate stats
                self.logger.info(f"Using level-specific scraping for {champion_name} level {level}")
                level_stats_data = await self.stats_scraper.scrape_level_specific_stats(champion_name, level)
                
                # Process stats with proper resource formatting
                raw_stats = level_stats_data.get("stats", {})
                resource_type = raw_stats.get('resource_type', 'Mana')
                processed_stats = {}
                
                for stat_name, value in raw_stats.items():
                    if stat_name == 'resource_type':
                        continue
                    formatted_stat_name = self._format_stat_name(stat_name, resource_type)
                    processed_stats[formatted_stat_name] = value
                
                return {
                    "name": champion_name,
                    "level": level,
                    "stats": processed_stats,
                    "data_source": level_stats_data.get("data_source", "selenium_level_scrape")
                }
            else:
                # For base stats (no level specified), use the efficient default ranges method
                self.logger.info(f"Using efficient default stat ranges for {champion_name} (single HTTP call)")
                
                # Use the improved HTTP method for default ranges - much faster than 2 Selenium calls
                default_data = await self.stats_scraper.scrape_default_stat_ranges(champion_name)
                raw_stats = default_data.get("stats", {})
                
                # The new method already formats stats correctly, so just return them
                return {
                    "name": champion_name,
                    "stats": raw_stats,
                    "data_source": default_data.get("data_source", "wiki_default_ranges")
                }
                
        except (WikiScraperError, ValueError) as e:
            self.logger.error(f"Failed to get champion stats for {champion_name}: {e}")
            raise ChampionNotFoundError(champion_name) from e

    async def cleanup(self):
        """Cleanup resources (StatsScraper, etc.)"""
        if self.stats_scraper:
            await self.stats_scraper.close()
            self.logger.info("StatsScraper resources cleaned up") 