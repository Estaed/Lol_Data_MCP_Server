"""
Champion Abilities Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting champion abilities
from the League of Legends Wiki using CSS selectors for ability containers.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError

# CSS selectors for ability containers from wiki_selectors.md
ABILITY_CONTAINERS = {
    'passive': '.skill_innate',
    'q': '.skill_q',
    'w': '.skill_w',
    'e': '.skill_e',
    'r': '.skill_r'
}

# CSS selectors for ability details within containers
ABILITY_DETAIL_SELECTORS = {
    'description': '.ability-info-description',
    'stats_list': '.ability-info-stats__list'
}

# Ability slot mapping
ABILITY_SLOTS = {
    'passive': 'Passive',
    'q': 'Q',
    'w': 'W', 
    'e': 'E',
    'r': 'R'
}


class AbilitiesScraper(BaseScraper):
    """
    A specialized scraper for champion abilities using CSS selector-based extraction.
    Focuses on Task 2.1.10: comprehensive ability detail system.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_champion_abilities(self, champion_name: str) -> Dict[str, Any]:
        """
        Scrape all champion abilities from the champion's wiki page.
        
        Args:
            champion_name: Name of champion to scrape abilities for
            
        Returns:
            Dictionary with all ability data
        """
        self.logger.info(f"Scraping abilities for {champion_name}")
        
        # Use HTTP-based scraping for abilities (no level dropdown needed)
        url = self._build_champion_url(champion_name)
        soup = await self.fetch_champion_page(champion_name)
        
        abilities = {}
        
        # Extract each ability using its container selector
        for ability_slot, container_selector in ABILITY_CONTAINERS.items():
            try:
                ability_data = self._extract_ability_from_container(
                    soup, container_selector, ability_slot
                )
                if ability_data:
                    abilities[ABILITY_SLOTS[ability_slot]] = ability_data
                    self.logger.debug(f"Extracted {ability_slot} ability for {champion_name}")
                else:
                    self.logger.warning(f"No data found for {ability_slot} ability of {champion_name}")
            except Exception as e:
                self.logger.error(f"Failed to extract {ability_slot} ability for {champion_name}: {e}")
                # Continue with other abilities even if one fails
                continue
        
        if not abilities:
            raise WikiScraperError(f"No abilities found for {champion_name}")
        
        self.logger.info(f"Successfully scraped {len(abilities)} abilities for {champion_name}")
        return {
            "abilities": abilities,
            "data_source": "wiki_abilities_scrape"
        }

    def _extract_ability_from_container(self, soup: BeautifulSoup, container_selector: str, ability_slot: str) -> Optional[Dict[str, Any]]:
        """
        Extract ability data from a specific ability container.
        
        Args:
            soup: BeautifulSoup object of the champion page
            container_selector: CSS selector for the ability container
            ability_slot: The ability slot (passive, q, w, e, r)
            
        Returns:
            Dictionary with ability data or None if not found
        """
        # Find the ability container
        container = soup.select_one(container_selector)
        if not container:
            self.logger.warning(f"No container found for {ability_slot} with selector {container_selector}")
            return None
        
        ability_data = {}
        
        # Extract ability name from container
        ability_name = self._extract_ability_name(container, ability_slot)
        if ability_name:
            ability_data['name'] = ability_name
        
        # Extract ability description
        description = self._extract_ability_description(container)
        if description:
            ability_data['description'] = description
        
        # Extract ability stats (cooldown, cost, range, etc.)
        stats = self._extract_ability_stats(container)
        if stats:
            ability_data.update(stats)
        
        return ability_data if ability_data else None

    def _extract_ability_name(self, container: BeautifulSoup, ability_slot: str) -> Optional[str]:
        """Extract ability name from container."""
        # Try multiple strategies to find ability name
        name_selectors = [
            '.skill-title .skill-name',
            '.skill-name',
            'h3',
            '.ability-name',
            'strong'
        ]
        
        for selector in name_selectors:
            name_element = container.select_one(selector)
            if name_element and name_element.get_text(strip=True):
                name = name_element.get_text(strip=True)
                # Clean up the name (remove extra whitespace, special chars)
                name = re.sub(r'\s+', ' ', name).strip()
                # Filter out generic text that isn't an ability name
                if name and len(name) > 1 and not name.lower() in ['ability', 'passive', 'q', 'w', 'e', 'r']:
                    return name
        
        # Fallback: return slot name if no specific name found
        return ABILITY_SLOTS.get(ability_slot, ability_slot.upper())

    def _extract_ability_description(self, container: BeautifulSoup) -> Optional[str]:
        """Extract ability description from container."""
        # Use the specific selector from wiki_selectors.md
        desc_element = container.select_one(ABILITY_DETAIL_SELECTORS['description'])
        if desc_element:
            description = desc_element.get_text(strip=True)
            if description:
                return description
        
        # Fallback: try other description selectors
        fallback_selectors = [
            '.ability-description',
            '.skill-description',
            'p',
            'div[class*="description"]'
        ]
        
        for selector in fallback_selectors:
            desc_element = container.select_one(selector)
            if desc_element:
                text = desc_element.get_text(strip=True)
                if text and len(text) > 20:  # Ensure it's a substantial description
                    return text
        
        return None

    def _extract_ability_stats(self, container: BeautifulSoup) -> Dict[str, Any]:
        """Extract ability stats like cooldown, cost, range, etc."""
        stats = {}
        
        # Use the stats list selector from wiki_selectors.md
        stats_container = container.select_one(ABILITY_DETAIL_SELECTORS['stats_list'])
        if not stats_container:
            # Try fallback selectors
            stats_container = container.select_one('.ability-stats') or container
        
        if stats_container:
            # Extract stats text and parse it
            stats_text = stats_container.get_text()
            
            # Parse common ability stats using regex patterns
            stat_patterns = {
                'cooldown': [
                    r'(?:cooldown|cd):\s*([0-9/.]+(?:\s*/\s*[0-9/.]+)*)',
                    r'(?:cooldown|cd)\s+([0-9/.]+(?:\s*/\s*[0-9/.]+)*)',
                ],
                'cost': [
                    r'(?:cost|mana|energy):\s*([0-9/.]+(?:\s*/\s*[0-9/.]+)*)',
                    r'(?:mana|energy)\s+cost:\s*([0-9/.]+(?:\s*/\s*[0-9/.]+)*)',
                ],
                'range': [
                    r'range:\s*([0-9/.]+)',
                    r'range\s+([0-9/.]+)',
                ],
                'cast_time': [
                    r'(?:cast time|channel time):\s*([0-9/.]+)',
                    r'(?:cast|channel)\s+([0-9/.]+)',
                ],
                'damage': [
                    r'(?:damage|physical damage|magic damage):\s*([0-9/.]+(?:\s*/\s*[0-9/.]+)*(?:\s*\([^)]+\))?)',
                ],
            }
            
            for stat_name, patterns in stat_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, stats_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        # Clean and validate the value
                        if value and value != '0':
                            stats[stat_name] = self._parse_stat_value(value)
                        break  # Use first matching pattern
        
        return stats

    def _parse_stat_value(self, value: str) -> str:
        """Parse and clean stat values."""
        if not value:
            return None
        
        # Clean the value
        value = value.strip()
        
        # Handle ranges (e.g., "10/15/20/25/30")
        if '/' in value:
            return value  # Keep ranges as strings
        
        # Handle numbers with units (e.g., "14 seconds")
        # For abilities, often better to keep as string to preserve units
        return value

    async def scrape_ability_details_with_tab(self, champion_name: str, ability_slot: str) -> Dict[str, Any]:
        """
        Scrape detailed ability information using Selenium to click the Details tab.
        This is for future Task 2.1.11 implementation.
        
        Args:
            champion_name: Name of champion
            ability_slot: Ability slot (Q, W, E, R, Passive)
            
        Returns:
            Dictionary with detailed ability information
        """
        # This method is a placeholder for Task 2.1.11
        # For now, fall back to basic ability scraping
        all_abilities = await self.scrape_champion_abilities(champion_name)
        abilities = all_abilities.get('abilities', {})
        
        if ability_slot in abilities:
            return {
                "ability": abilities[ability_slot],
                "data_source": "wiki_abilities_scrape"
            }
        else:
            raise WikiScraperError(f"Ability {ability_slot} not found for {champion_name}") 