"""
Champion Stats Service for League of Legends MCP Server

This module provides service layer functionality for retrieving and processing
champion statistics data. It uses the StatsScraper to fetch data from the
LoL Wiki and provides a clean interface for the MCP server tools.
"""

import logging
import re
import httpx
from typing import Dict, Any, Optional, List
import structlog

from src.data_sources.scrapers.stats_scraper import StatsScraper, WikiScraperError
from src.models.data_models import ChampionData, ChampionStats
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
        self._stat_formulas = {}  # Store formulas for level calculations

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

    def _transform_wiki_stats(self, wiki_stats: Dict[str, Any]) -> Optional[ChampionStats]:
        """Transform WikiScraper stats format to ChampionStats model."""
        if not wiki_stats:
            return None

        self._stat_formulas = {}
        stat_mapping = {
            'hp': ('health', 'health_per_level'),
            'mp': ('mana', 'mana_per_level'),
            'ad': ('attack_damage', 'attack_damage_per_level'),
            'armor': ('armor', 'armor_per_level'),
            'mr': ('magic_resist', 'magic_resist_per_level'),
            'as': ('attack_speed', 'attack_speed_per_level'),
            'ms': ('movement_speed', None),
            'range': ('attack_range', None),
            'hp5': ('health_regen', 'health_regen_per_level'),
            'mp5': ('mana_regen', 'mana_regen_per_level'),
        }

        stats_data = {}
        for wiki_key, (base_field, growth_field) in stat_mapping.items():
            if wiki_key in wiki_stats:
                wiki_stat = wiki_stats[wiki_key]
                if isinstance(wiki_stat, dict):
                    if 'formula' in wiki_stat:
                        self._stat_formulas[base_field] = wiki_stat['formula']
                    if 'base' in wiki_stat:
                        stats_data[base_field] = float(wiki_stat['base'])
                    if growth_field and 'growth' in wiki_stat:
                        stats_data[growth_field] = float(wiki_stat['growth'])
                else:
                    try:
                        stats_data[base_field] = float(wiki_stat)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Could not convert stat {wiki_key} to float: {wiki_stat}")
        
        return ChampionStats(**stats_data) if stats_data else None

    async def get_champion_stats(
        self,
        champion: str,
        level: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive champion stats with scraper integration.
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
            champion_data = await self._get_champion_from_wiki(champion_name)
            if not champion_data or not champion_data.stats:
                raise ChampionNotFoundError(champion_name)
            
            data_source = "wiki"
        except (WikiScraperError, ChampionNotFoundError) as e:
            self.logger.error(f"Failed to get champion data from wiki for {champion_name}: {e}")
            raise

        response = {
            "name": champion_data.name,
            "data_source": data_source,
        }

        if level is not None:
            try:
                level_stats_data = await self.stats_scraper.scrape_level_specific_stats(champion_name, level)
                response["stats"] = level_stats_data.get("stats")
                response["level"] = level
                response["stats_source"] = level_stats_data.get("data_source", "selenium")
            except Exception as e:
                self.logger.warning(f"Failed to get level {level} stats for {champion_name}: {e}, returning base stats.")
                response["stats"] = champion_data.stats.model_dump()
        else:
            response["stats"] = champion_data.stats.model_dump()

        self.logger.info("Champion stats retrieved successfully", champion=champion, data_source=data_source)
        return response

    async def _get_champion_from_wiki(self, champion_name: str) -> Optional[ChampionData]:
        """Get champion data from the LoL Wiki using the StatsScraper."""
        if not self.stats_scraper:
            raise WikiScraperError("StatsScraper is not enabled")

        self.logger.info(f"Fetching champion data for '{champion_name}' from wiki")
        soup = await self.stats_scraper.fetch_champion_page(champion_name)
        wiki_stats_result = self.stats_scraper.parse_champion_stats_safe(soup)

        if 'error' in wiki_stats_result:
            raise WikiScraperError(f"Failed to parse stats for {champion_name}: {wiki_stats_result['error']}")

        stats = self._transform_wiki_stats(wiki_stats_result.get('stats', {}))
        
        if not stats:
            return None

        return ChampionData(
            name=champion_name,
            stats=stats,
        )

    async def cleanup(self):
        """Cleanup resources (StatsScraper, etc.)"""
        if self.stats_scraper:
            await self.stats_scraper.close()
            self.logger.info("StatsScraper resources cleaned up") 