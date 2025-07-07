"""
Champion Stats Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting champion statistics
from the League of Legends Wiki using Selenium level dropdown interaction.
"""

import logging
import time
from typing import Any, Dict, Optional

from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError

# CSS selectors for level-specific stat scraping from wiki_selectors.md
LEVEL_SELECTORS = {
    'level_dropdown': '#lvl_',
    'hp': '#Health__lvl',
    'mana': '#ResourceBar__lvl',
    'hp_regen': '#HealthRegen__lvl',
    'mana_regen': '#ResourceRegen__lvl',
    'armor': '#Armor__lvl',
    'attack_damage': '#AttackDamage__lvl',
    'magic_resist': '#MagicResist__lvl',
    'movement_speed': '#MovementSpeed_',
    'attack_range': '#AttackRange_',
    'bonus_attack_speed': '#AttackSpeedBonus__lvl',
    'critical_damage': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(8) > div.infobox-data-value.statsbox',
    'base_attack_speed': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(1) > div.infobox-data-value.statsbox',
    'windup_percent': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(2) > div.infobox-data-value.statsbox',
    'as_ratio': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox',
    
    # Additional resource types
    'energy': '#ResourceBar__lvl',  # Energy uses same selector as mana
    'energy_regen': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox',  # Energy regen
    'secondary_bar': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox'  # All secondary bars (Rage, Heat, Flow, etc.)
}

# Champion-specific resource selectors - ADD NEW CHAMPIONS HERE
# Format: 'ChampionName': {'resource': 'css_selector', 'resource_regen': 'css_selector_or_None'}
CHAMPION_RESOURCE_SELECTORS = {
    # Empty - let the system auto-detect resource types
}

class StatsScraper(BaseScraper):
    """
    A specialized scraper for champion statistics using Selenium level dropdown.
    Focuses on Task 2.1.8: accurate per-level stat scraping.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_level_specific_stats(self, champion_name: str, level: int) -> Dict[str, Any]:
        """
        Scrape champion stats for a specific level using Selenium dropdown interaction.
        
        Args:
            champion_name: Name of champion to scrape
            level: Level (1-18) to get stats for
            
        Returns:
            Dictionary with level-specific stats
        """
        if not (1 <= level <= 18):
            raise ValueError("Level must be between 1 and 18.")

        self.logger.info(f"Scraping level {level} stats for {champion_name}")
        driver = self._create_selenium_driver()
        url = self._build_champion_url(champion_name)
        
        try:
            # Load the champion page
            driver.get(url)
            wait = WebDriverWait(driver, 10)

            # Find and interact with level dropdown
            level_dropdown_element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LEVEL_SELECTORS['level_dropdown']))
            )
            level_dropdown = Select(level_dropdown_element)
            level_dropdown.select_by_value(str(level))
            
            # Wait for JavaScript to update the stats
            time.sleep(1.0)

            # Extract all level-specific stats
            stats = {'level': level}
            
            # First, try to determine resource type by checking what's available
            resource_type = self._determine_resource_type(driver, champion_name)
            
            for stat_name, selector in LEVEL_SELECTORS.items():
                if stat_name == 'level_dropdown':
                    continue
                
                # Skip resource selectors that don't apply to this champion
                if stat_name in ['energy', 'energy_regen', 'secondary_bar'] and not self._should_use_resource_selector(stat_name, resource_type):
                    continue
                    
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    raw_value = element.text.strip()
                    
                    # Map resource stats to standardized names
                    mapped_stat_name = self._map_stat_name(stat_name, resource_type)
                    stats[mapped_stat_name] = self._parse_stat_value(raw_value)
                except NoSuchElementException:
                    # Only log warning for expected stats
                    if stat_name not in ['energy', 'energy_regen', 'secondary_bar']:
                        self.logger.warning(f"Stat '{stat_name}' not found for {champion_name}")
                    mapped_stat_name = self._map_stat_name(stat_name, resource_type)
                    stats[mapped_stat_name] = None
            
            # Add resource type information
            stats['resource_type'] = resource_type
            
            self.logger.info(f"Successfully scraped {len(stats)} stats for {champion_name} level {level}")
            return {
                "stats": stats,
                "data_source": "selenium_level_scrape"
            }
            
        except (TimeoutException, NoSuchElementException, WebDriverException) as e:
            self.logger.error(f"Selenium scraping failed for {champion_name} level {level}: {e}")
            raise WikiScraperError(f"Failed to scrape level {level} stats for {champion_name}") from e
        finally:
            driver.quit()

    def _determine_resource_type(self, driver, champion_name: str) -> str:
        """Determine what type of resource this champion uses by examining the page content."""
        # Check if champion has specific resource mapping first
        if champion_name in CHAMPION_RESOURCE_SELECTORS:
            mapping = CHAMPION_RESOURCE_SELECTORS[champion_name]
            if 'energy' in str(mapping.get('resource', '')):
                return 'Energy'
            elif mapping.get('resource') == 'N/A':
                return 'N/A'
            else:
                return 'Mana'
        
        # Auto-detect resource type by examining the actual content
        try:
            # Get the resource value and regen value
            mana_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['mana'])
            mana_value = mana_element.text.strip()
            
            # Get the resource regen value 
            mana_regen_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['mana_regen'])
            mana_regen_value = mana_regen_element.text.strip()
            
            # Energy champions typically have 200 energy and 50 energy regen
            try:
                resource_val = float(mana_value)
                regen_val = float(mana_regen_value)
                
                # Energy detection: 200 resource + 50 regen is classic energy pattern
                if resource_val == 200.0 and regen_val == 50.0:
                    return 'Energy'
                    
                # If resource value is exactly 200 but different regen, still likely energy
                if resource_val == 200.0:
                    return 'Energy'
                    
            except (ValueError, TypeError):
                pass
                
        except NoSuchElementException:
            # If no mana element found, might be health-cost champion
            try:
                # Check if secondary bar exists instead
                driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['secondary_bar'])
                return 'Secondary Bar'
            except NoSuchElementException:
                # No mana, no secondary bar = health cost champion
                return 'N/A'
            
        # Check if there's a secondary bar in addition to mana (like Gnar)
        try:
            driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['secondary_bar'])
            # Has both mana and secondary bar - the secondary bar is probably the main resource
            return 'Secondary Bar'
        except NoSuchElementException:
            pass
            
        # Default to Mana for standard champions
        return 'Mana'

    def _should_use_resource_selector(self, stat_name: str, resource_type: str) -> bool:
        """Check if we should use this resource selector for this champion."""
        if resource_type == 'Energy' and stat_name in ['energy', 'energy_regen']:
            return True
        elif resource_type == 'Secondary Bar' and stat_name == 'secondary_bar':
            return True
        else:
            return False

    def _map_stat_name(self, stat_name: str, resource_type: str) -> str:
        """Map internal stat names to standardized output names."""
        if stat_name == 'energy':
            return 'resource'
        elif stat_name == 'energy_regen':
            return 'resource_regen'
        elif stat_name == 'secondary_bar':
            return 'resource_regen'
        elif stat_name == 'mana':
            return 'resource'
        elif stat_name == 'mana_regen':
            return 'resource_regen'
        else:
            return stat_name

    async def scrape_default_stat_ranges(self, champion_name: str) -> Dict[str, Any]:
        """
        Scrape default stat ranges from champion page (no Selenium needed).
        Gets the range values shown by default like "630 – 2483" that appear on first page load.
        """
        self.logger.info(f"Scraping default stat ranges for {champion_name}")
        
        # Get champion page with regular HTTP request
        soup = await self.fetch_champion_page(champion_name)
        
        # Base selectors for default stat ranges (without level dropdown interaction)
        BASE_SELECTORS = {
            'hp': '#Health',
            'mana': '#ResourceBar', 
            'hp_regen': '#HealthRegen',
            'mana_regen': '#ResourceRegen',
            'armor': '#Armor',
            'attack_damage': '#AttackDamage',
            'magic_resist': '#MagicResist',
            'movement_speed': '#MovementSpeed',
            'attack_range': '#AttackRange',
            'bonus_attack_speed': '#AttackSpeedBonus',
            'base_attack_speed': 'div.infobox-data-value.statsbox',  # Simplified selector
            'critical_damage': 'div.infobox-data-value.statsbox',     # These will need testing
            'windup_percent': 'div.infobox-data-value.statsbox',
            'as_ratio': 'div.infobox-data-value.statsbox'
        }
        
        # Extract stats using base selectors
        stats = {}
        for stat_name, selector in BASE_SELECTORS.items():
            element = soup.select_one(selector)
            
            if element and element.get_text(strip=True):
                raw_value = element.get_text(strip=True)
                stats[stat_name] = raw_value  # Keep as string for ranges like "630 – 2483"
            else:
                self.logger.warning(f"Stat '{stat_name}' not found for {champion_name}")
                stats[stat_name] = None
        
        self.logger.info(f"Successfully scraped {len(stats)} default stat ranges for {champion_name}")
        return {
            "stats": stats,
            "data_source": "wiki_default_ranges"
        }

    def _parse_stat_value(self, text: str) -> Optional[float]:
        """Parse numerical values from stat text."""
        if not text:
            return None
        try:
            return float(text.replace(',', ''))
        except (ValueError, TypeError):
            self.logger.debug(f"Could not parse stat value: {text}")
            return None 