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
                result = {
                    "name": champion_name,
                    "champion": champion_name,  # Add champion field for consistency
                    "abilities": all_abilities,
                    "ability_count": len(all_abilities),
                    "data_source": abilities_data.get("data_source", "wiki_abilities_scrape")
                }
                
                # Include weapon system information if available (for complex champions like Aphelios)
                if "weapon_system" in abilities_data:
                    result["weapon_system"] = abilities_data["weapon_system"]
                    result["weapon_count"] = abilities_data.get("weapon_count", 0)
                    result["total_descriptions"] = abilities_data.get("total_descriptions", 0)
                    self.logger.info(f"Added weapon system information for {champion_name}")
                
                return result
                
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
        Retrieve detailed information for a specific ability with enhanced Details tab content.
        Includes targeting input, damage classification, and counters.
        
        Args:
            champion: Champion name
            ability_slot: Ability slot (Q, W, E, R, Passive)
            
        Returns:
            Dictionary with detailed ability information including Details tab content
        """
        self.logger.info(
            "Enhanced ability details request",
            champion=champion,
            ability_slot=ability_slot
        )
        
        # Normalize inputs
        normalized_champion = self._normalize_champion_name(champion)
        normalized_slot = self._normalize_ability_slot(ability_slot)
        
        if not normalized_slot:
            raise ValueError(f"Invalid ability slot: {ability_slot}")
        
        try:
            if self.enable_wiki and self.abilities_scraper:
                # Use enhanced scraping with Details tab
                result = await self.abilities_scraper.scrape_ability_details_with_tab(
                    normalized_champion, normalized_slot
                )
                
                if result and "ability" in result:
                    ability_data = result["ability"]
                    
                    # Build comprehensive ability response
                    enhanced_ability = {
                        "name": ability_data.get("name", f"{normalized_slot} Ability"),
                        "description": ability_data.get("description", "Description not available"),
                        "slot": normalized_slot
                    }
                    
                    # Add basic stats if they exist
                    basic_fields = ["cooldown", "cost", "range", "cast_time", "damage", "healing", "shield"]
                    for field in basic_fields:
                        if field in ability_data:
                            enhanced_ability[field] = ability_data[field]
                    
                    # Add enhanced details from Details tab
                    enhanced_details = {}
                    
                    # Add targeting input
                    if "targeting_input" in ability_data:
                        enhanced_details["targeting_input"] = ability_data["targeting_input"]
                    
                    # Add damage classification
                    if "damage_classification" in ability_data:
                        enhanced_details["damage_classification"] = ability_data["damage_classification"]
                    
                    # Add counters
                    if "counters" in ability_data:
                        enhanced_details["counters"] = ability_data["counters"]
                    
                    # Add additional notes if present
                    if "additional_notes" in ability_data:
                        enhanced_details["additional_notes"] = ability_data["additional_notes"]
                    
                    # Only add enhanced_details if we have some enhanced content
                    if enhanced_details:
                        enhanced_ability["enhanced_details"] = enhanced_details
                    
                    return {
                        "champion": normalized_champion,
                        "ability_slot": normalized_slot,
                        "ability_details": enhanced_ability,
                        "data_source": result.get("data_source", "wiki_abilities_with_details_tab")
                    }
                
                else:
                    raise WikiScraperError(f"No ability data found for {normalized_champion} {normalized_slot}")
                    
            else:
                # Fallback to basic abilities if wiki is disabled
                basic_result = await self.get_champion_abilities(normalized_champion, normalized_slot)
                
                if "ability" in basic_result:
                    ability_data = basic_result["ability"]
                    
                    enhanced_ability = {
                        "name": ability_data.get("name", f"{normalized_slot} Ability"),
                        "description": ability_data.get("description", "Description not available"),
                        "slot": normalized_slot
                    }
                    
                    # Add available stats
                    basic_fields = ["cooldown", "cost", "range", "cast_time", "damage"]
                    for field in basic_fields:
                        if field in ability_data:
                            enhanced_ability[field] = ability_data[field]
                    
                    return {
                        "champion": normalized_champion,
                        "ability_slot": normalized_slot,
                        "ability_details": enhanced_ability,
                        "data_source": basic_result.get("data_source", "wiki_disabled_fallback")
                    }
                else:
                    raise WikiScraperError(f"Ability data not found for {normalized_champion} {normalized_slot}")
                    
        except WikiScraperError:
            # Re-raise scraper errors
            raise
        except Exception as e:
            self.logger.error(
                "Error in enhanced ability details retrieval",
                champion=normalized_champion,
                ability_slot=normalized_slot,
                error=str(e)
            )
            # Try fallback to basic abilities
            try:
                basic_result = await self.get_champion_abilities(normalized_champion, normalized_slot)
                if "ability" in basic_result:
                    ability_data = basic_result["ability"]
                    
                    enhanced_ability = {
                        "name": ability_data.get("name", f"{normalized_slot} Ability"),
                        "description": ability_data.get("description", "Description not available"),
                        "slot": normalized_slot
                    }
                    
                    return {
                        "champion": normalized_champion,
                        "ability_slot": normalized_slot,
                        "ability_details": enhanced_ability,
                        "data_source": "fallback_after_error"
                    }
            except Exception as fallback_error:
                self.logger.error(f"Fallback also failed: {fallback_error}")
            
            raise ChampionNotFoundError(f"Could not retrieve ability details for {champion} {ability_slot}")

    async def cleanup(self):
        """Cleanup resources (AbilitiesScraper, etc.)"""
        if self.abilities_scraper:
            await self.abilities_scraper.close()
            self.logger.info("AbilitiesScraper resources cleaned up") 