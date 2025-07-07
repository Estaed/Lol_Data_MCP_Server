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
    
    # Additional resource selector for energy regen and secondary bars  
    'secondary_bar': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox'
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
            resource_config = self._determine_resource_type(driver, champion_name)
            
            for stat_name, selector in LEVEL_SELECTORS.items():
                if stat_name == 'level_dropdown':
                    continue
                
                # Skip resource selectors that don't apply to this champion
                if stat_name == 'secondary_bar' and not self._should_use_resource_selector(stat_name, resource_config):
                    continue
                    
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    raw_value = element.text.strip()
                    
                    # Map resource stats to standardized names with proper display formatting
                    mapped_stat_name = self._map_stat_name(stat_name, resource_config)
                    
                    # Format the value based on the stat type
                    if mapped_stat_name in ['resource', 'resource_regen', 'secondary_bar']:
                        # Apply proper display name formatting for resource stats
                        display_name = self._format_resource_display_name(mapped_stat_name, resource_config)
                        stats[display_name] = self._parse_stat_value(raw_value)
                    else:
                        stats[mapped_stat_name] = self._parse_stat_value(raw_value)
                        
                except NoSuchElementException:
                    # Only log warning for expected stats
                    if stat_name not in ['secondary_bar']:
                        self.logger.warning(f"Stat '{stat_name}' not found for {champion_name}")
                    
                    # Handle missing resource stats
                    mapped_stat_name = self._map_stat_name(stat_name, resource_config)
                    if mapped_stat_name in ['resource', 'resource_regen', 'secondary_bar']:
                        display_name = self._format_resource_display_name(mapped_stat_name, resource_config)
                        stats[display_name] = None
                    else:
                        stats[mapped_stat_name] = None
            
            # Add resource type information
            stats['resource_type'] = resource_config['primary_type']
            
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

    def _determine_resource_type(self, driver, champion_name: str) -> Dict[str, str]:
        """
        Dynamically determine what resource system this champion uses.
        Returns a dict with resource configuration for flexible handling.
        """
        resource_config = {
            'primary_type': None,
            'has_secondary': False,
            'secondary_type': None
        }
        
        # Check what resource elements exist on the page
        has_primary_resource = False
        has_primary_regen = False
        has_secondary_bar = False
        
        primary_resource_value = None
        primary_regen_value = None
        secondary_bar_value = None
        
        # Try to find primary resource (mana/energy using documented selector)
        try:
            primary_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['mana'])
            primary_resource_value = primary_element.text.strip()
            has_primary_resource = bool(primary_resource_value)
        except NoSuchElementException:
            pass
            
        # Try to find primary resource regen (using documented selector)
        try:
            regen_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['mana_regen'])
            primary_regen_value = regen_element.text.strip()
            has_primary_regen = bool(primary_regen_value)
        except NoSuchElementException:
            pass
            
        # Try to find secondary bar (energy regen position for energy champs, or actual secondary bars)
        try:
            secondary_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['secondary_bar'])
            secondary_bar_value = secondary_element.text.strip()
            has_secondary_bar = bool(secondary_bar_value)
        except NoSuchElementException:
            pass
        
        # Determine resource configuration based on what exists
        if has_primary_resource and has_primary_regen:
            # Has both primary resource and regen - determine if it's mana or energy
            try:
                resource_val = float(primary_resource_value)
                regen_val = float(primary_regen_value)
                
                # Energy detection - energy champs typically have:
                # - Resource values of 200, 400, or other fixed amounts
                # - Regen values typically in the 40-60 range (50 is most common)
                # - Unlike mana which varies widely and scales with level
                if (resource_val in [200.0, 400.0] and 40.0 <= regen_val <= 60.0) or \
                   (resource_val == 200.0 or resource_val == 400.0):
                    resource_config['primary_type'] = 'Energy'
                else:
                    # Standard mana system
                    resource_config['primary_type'] = 'Mana'
                    
            except (ValueError, TypeError):
                # Can't parse values, default to mana
                resource_config['primary_type'] = 'Mana'
                
        elif has_primary_resource and not has_primary_regen:
            # Has primary resource but no regen - could be energy or special case
            try:
                resource_val = float(primary_resource_value)
                if resource_val in [200.0, 400.0]:
                    # Likely energy champion
                    resource_config['primary_type'] = 'Energy'
                else:
                    resource_config['primary_type'] = 'Mana'
            except (ValueError, TypeError):
                resource_config['primary_type'] = 'Mana'
                
        elif not has_primary_resource and not has_primary_regen:
            # No primary resource system - health cost champion
            resource_config['primary_type'] = 'Health'
            
        else:
            # Fallback case
            resource_config['primary_type'] = 'Mana'
        
        # Check for secondary bar (Rage, Heat, Flow, Crimson Rush, etc.)
        # For energy champions, the secondary_bar selector might show their energy regen
        # For secondary bar champions, it shows their actual secondary resource
        if has_secondary_bar:
            if resource_config['primary_type'] == 'Energy':
                # For energy champs, this is likely their energy regen, not a secondary bar
                try:
                    secondary_val = float(secondary_bar_value)
                    if 40.0 <= secondary_val <= 60.0:
                        # This is energy regen, not a secondary bar
                        resource_config['has_secondary'] = False
                    else:
                        # Unusual case - energy champ with actual secondary bar
                        resource_config['has_secondary'] = True
                        resource_config['secondary_type'] = 'Secondary Bar'
                except (ValueError, TypeError):
                    resource_config['has_secondary'] = False
            else:
                # For non-energy champs, this is a real secondary bar
                resource_config['has_secondary'] = True
                resource_config['secondary_type'] = 'Secondary Bar'
            
        return resource_config

    def _should_use_resource_selector(self, stat_name: str, resource_config: Dict[str, str]) -> bool:
        """Check if we should use this resource selector for this champion."""
        if stat_name == 'secondary_bar':
            return resource_config['has_secondary']
        else:
            return True  # Use all other selectors (mana, mana_regen are always used)

    def _map_stat_name(self, stat_name: str, resource_config: Dict[str, str]) -> str:
        """Map internal stat names to standardized output names with resource type info."""
        if stat_name == 'mana':
            return 'resource'
        elif stat_name == 'mana_regen':
            return 'resource_regen'
        elif stat_name == 'secondary_bar':
            return 'secondary_bar'
        else:
            return stat_name

    def _format_resource_display_name(self, stat_name: str, resource_config: Dict[str, str]) -> str:
        """Format the display name for resource stats."""
        if stat_name == 'resource':
            if resource_config['primary_type'] == 'Energy':
                return 'Resource (Energy)'
            elif resource_config['primary_type'] == 'Mana':
                return 'Resource (Mana)'
            elif resource_config['primary_type'] == 'Health':
                return 'Resource: Uses Health'
            else:
                return 'Resource: N/A'
        elif stat_name == 'resource_regen':
            if resource_config['primary_type'] == 'Energy':
                return 'Resource Regen (Energy)'
            elif resource_config['primary_type'] == 'Mana':
                return 'Resource Regen (Mana)'
            elif resource_config['primary_type'] == 'Health':
                return 'Resource Regen: N/A'
            else:
                return 'Resource Regen: N/A'
        elif stat_name == 'secondary_bar':
            return 'Secondary Bar'
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
            # Restore the complex selectors that were working
            'base_attack_speed': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(1) > div.infobox-data-value.statsbox',
            'critical_damage': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(8) > div.infobox-data-value.statsbox',
            'windup_percent': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(2) > div.infobox-data-value.statsbox',
            'as_ratio': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox'
        }
        
        # Extract stats using base selectors
        stats = {}
        mana_value = None
        mana_regen_value = None
        
        for stat_name, selector in BASE_SELECTORS.items():
            element = soup.select_one(selector)
            
            if element and element.get_text(strip=True):
                raw_value = element.get_text(strip=True)
                stats[stat_name] = raw_value  # Keep as string for ranges like "630 – 2483"
                
                # Store mana values for resource type detection
                if stat_name == 'mana':
                    mana_value = raw_value
                elif stat_name == 'mana_regen':
                    mana_regen_value = raw_value
            else:
                self.logger.warning(f"Stat '{stat_name}' not found for {champion_name}")
                stats[stat_name] = None
        
        # Detect resource type based on default values
        resource_config = self._detect_resource_type_from_defaults(mana_value, mana_regen_value, champion_name)
        
        # Map mana stats to resource stats with proper names
        processed_stats = {}
        for stat_name, value in stats.items():
            if stat_name == 'mana':
                mapped_name = self._map_stat_name('mana', resource_config)
                display_name = self._format_resource_display_name(mapped_name, resource_config)
                processed_stats[display_name] = value
            elif stat_name == 'mana_regen':
                mapped_name = self._map_stat_name('mana_regen', resource_config)
                display_name = self._format_resource_display_name(mapped_name, resource_config)
                processed_stats[display_name] = value
            else:
                mapped_name = self._map_stat_name(stat_name, resource_config)
                processed_stats[mapped_name] = value
        
        # Add resource type for the service layer
        processed_stats['resource_type'] = resource_config['primary_type']
        
        self.logger.info(f"Successfully scraped {len(processed_stats)} default stat ranges for {champion_name}")
        return {
            "stats": processed_stats,
            "data_source": "wiki_default_ranges"
        }

    def _detect_resource_type_from_defaults(self, mana_value: str, mana_regen_value: str, champion_name: str) -> Dict[str, str]:
        """Detect resource type from default page values (range format)."""
        resource_config = {
            'primary_type': None,
            'has_secondary': False,
            'secondary_type': None
        }
        
        # Try to detect from the actual values
        if mana_value and mana_regen_value:
            try:
                # For ranges like "200" or "400" (constant) or single values
                if (mana_value.strip() in ["200", "400"]) and "50" in mana_regen_value:
                    resource_config['primary_type'] = 'Energy'
                elif mana_value.strip() in ["200", "400"]:
                    resource_config['primary_type'] = 'Energy'
                else:
                    resource_config['primary_type'] = 'Mana'
            except (ValueError, AttributeError):
                resource_config['primary_type'] = 'Mana'
        elif not mana_value or mana_value == 'N/A':
            # If no mana values found, could be health cost
            resource_config['primary_type'] = 'Health'
        else:
            # Default to Mana
            resource_config['primary_type'] = 'Mana'
            
        # For basic stats, we can't easily detect secondary bars, so assume no secondary
        resource_config['has_secondary'] = False
        
        return resource_config

    def _parse_stat_value(self, text: str) -> Optional[float]:
        """Parse numerical values from stat text."""
        if not text:
            return None
        try:
            return float(text.replace(',', ''))
        except (ValueError, TypeError):
            self.logger.debug(f"Could not parse stat value: {text}")
            return None 