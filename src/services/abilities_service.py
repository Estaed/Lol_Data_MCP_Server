"""
Champion Abilities Service for League of Legends MCP Server

This module provides service layer functionality for retrieving champion
abilities data using AbilitiesScraper for comprehensive ability details.
"""

import logging
import re
from typing import Dict, Any, Optional
import structlog

from src.data_sources.scrapers.abilities_scraper import AbilitiesScraper, WikiScraperError
from src.models.exceptions import ChampionNotFoundError


class AbilitiesService:
    """Service class for champion abilities operations using AbilitiesScraper."""

    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the abilities service.

        Args:
            enable_wiki: Whether to enable AbilitiesScraper.
            use_cache: Whether to enable caching in AbilitiesScraper.
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki

        if self.enable_wiki:
            self.abilities_scraper = AbilitiesScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.abilities_scraper = None

        self.logger.info(
            "AbilitiesService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )

    def _normalize_champion_name(self, name: str) -> str:
        """Normalize champion name for wiki lookup."""
        normalized = name.strip().title()
        normalized = re.sub(r'\s+', ' ', normalized)
        self.logger.debug(f"Normalized champion name: {name} -> {normalized}")
        return normalized

    def _normalize_ability_slot(self, ability_slot: Optional[str]) -> Optional[str]:
        """Normalize ability slot name."""
        if not ability_slot:
            return None
        
        slot = ability_slot.strip().upper()
        
        # Map common variations to standard format
        slot_mapping = {
            'PASSIVE': 'Passive',
            'P': 'Passive',
            'Q': 'Q',
            'W': 'W',
            'E': 'E',
            'R': 'R',
            'ULT': 'R',
            'ULTIMATE': 'R'
        }
        
        return slot_mapping.get(slot, slot)

    async def get_champion_abilities(
        self,
        champion: str,
        ability_slot: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve champion abilities with optional ability filtering.
        
        Args:
            champion: Champion name
            ability_slot: Optional ability slot (Q, W, E, R, Passive). If provided, returns only that ability.
            
        Returns:
            Dictionary with champion abilities
        """
        self.logger.info(
            "Champion abilities request",
            champion=champion,
            ability_slot=ability_slot,
            wiki_enabled=self.enable_wiki
        )
        
        champion_name = self._normalize_champion_name(champion)
        normalized_slot = self._normalize_ability_slot(ability_slot)

        if not self.enable_wiki or not self.abilities_scraper:
            raise WikiScraperError("Wiki scraping is not enabled.")

        try:
            # Scrape all abilities from champion page
            self.logger.info(f"Scraping all abilities for {champion_name}")
            abilities_data = await self.abilities_scraper.scrape_champion_abilities(champion_name)
            
            all_abilities = abilities_data.get("abilities", {})
            
            if not all_abilities:
                raise WikiScraperError(f"No abilities found for {champion_name}")

            # If specific ability slot requested, filter to that ability
            if normalized_slot:
                if normalized_slot in all_abilities:
                    result = {
                        "name": champion_name,
                        "ability_slot": normalized_slot,
                        "ability": all_abilities[normalized_slot],
                        "data_source": abilities_data.get("data_source", "wiki_abilities_scrape")
                    }
                    # Add champion field for compatibility
                    result["champion"] = champion_name
                    return result
                else:
                    available_slots = list(all_abilities.keys())
                    # Don't convert to ChampionNotFoundError for invalid ability slots
                    raise WikiScraperError(
                        f"Ability {normalized_slot} not found for {champion_name}. "
                        f"Available abilities: {', '.join(available_slots)}"
                    )
            else:
                # Return all abilities
                return {
                    "name": champion_name,
                    "champion": champion_name,  # Add champion field for consistency
                    "abilities": all_abilities,
                    "ability_count": len(all_abilities),
                    "data_source": abilities_data.get("data_source", "wiki_abilities_scrape")
                }
                
        except WikiScraperError as e:
            # If it's an invalid ability slot error, re-raise as is
            if "not found for" in str(e) and "Available abilities:" in str(e):
                raise e
            # For other WikiScraperErrors (champion not found, etc.), convert to ChampionNotFoundError
            self.logger.error(f"Failed to get champion abilities for {champion_name}: {e}")
            raise ChampionNotFoundError(champion_name) from e
        except ValueError as e:
            self.logger.error(f"Failed to get champion abilities for {champion_name}: {e}")
            raise ChampionNotFoundError(champion_name) from e

    async def get_ability_details(
        self,
        champion: str,
        ability_slot: str
    ) -> Dict[str, Any]:
        """
        Retrieve detailed information for a specific ability.
        This is for compatibility with existing tools.
        
        Args:
            champion: Champion name
            ability_slot: Ability slot (Q, W, E, R, Passive)
            
        Returns:
            Dictionary with detailed ability information
        """
        self.logger.info(
            "Ability details request",
            champion=champion,
            ability_slot=ability_slot
        )
        
        # Use the main method with ability filtering
        result = await self.get_champion_abilities(champion, ability_slot)
        
        # Restructure response for compatibility
        if "ability" in result:
            ability_data = result["ability"]
            
            # Ensure we have the essential fields, with dynamic support
            structured_ability = {
                "name": ability_data.get("name", f"{ability_slot} Ability"),
                "description": ability_data.get("description", "Description not available"),
                "slot": ability_slot
            }
            
            # Add dynamic stats (cooldown, cost, range, etc.) if they exist
            optional_fields = ["cooldown", "cost", "range", "cast_time", "damage"]
            for field in optional_fields:
                if field in ability_data:
                    structured_ability[field] = ability_data[field]
            
            return {
                "champion": result["name"],
                "ability_slot": ability_slot,
                "ability_details": structured_ability,
                "data_source": result["data_source"]
            }
        else:
            raise WikiScraperError(f"Ability data not found in response for {champion} {ability_slot}")

    async def cleanup(self):
        """Cleanup resources (AbilitiesScraper, etc.)"""
        if self.abilities_scraper:
            await self.abilities_scraper.close()
            self.logger.info("AbilitiesScraper resources cleaned up") 