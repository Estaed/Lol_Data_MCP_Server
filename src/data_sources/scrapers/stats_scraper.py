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
    'hp_regen': '#HealthRegen__lvl',
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
}

# Resource-specific selectors based on champion resource type
RESOURCE_SELECTORS = {
    'mana': {
        'resource': '#ResourceBar__lvl',
        'resource_regen': '#ResourceRegen__lvl'
    },
    'energy': {
        'resource': '#ResourceBar__lvl',  # Try the standard mana selector for energy too
        'resource_regen': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox'
    },
    'secondary_bar': {
        'resource': None,  # N/A for secondary bar champions
        'secondary_bar': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox'
    }
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

            # Extract all level-specific stats in correct order
            stats = {}
            
            # First, try to determine resource type by checking what's available
            resource_type = self._determine_resource_type(driver, champion_name)
            
            # Build stats dictionary in the correct order
            # 1. Level
            stats['Level'] = level
            
            # 2. HP
            try:
                hp_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['hp'])
                stats['Hp'] = self._parse_stat_value(hp_element.text.strip())
            except NoSuchElementException:
                stats['Hp'] = None
            
            # 3. HP Regen
            try:
                hp_regen_element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS['hp_regen'])
                stats['Hp Regen'] = self._parse_stat_value(hp_regen_element.text.strip())
            except NoSuchElementException:
                stats['Hp Regen'] = None
            
            # 4. Resource stats (after HP Regen)
            self._extract_resource_stats(driver, stats, resource_type)
            
            # 5. Resource Regen (extract now to maintain order)
            resource_regen_key, resource_regen_value = self._get_resource_regen_stat(driver, resource_type)
            
            # Add Resource Regen (or Secondary Bar)
            if resource_regen_key:
                stats[resource_regen_key] = resource_regen_value
            
            # 6. Rest of the stats
            remaining_stats = ['armor', 'attack_damage', 'magic_resist', 'movement_speed', 
                             'attack_range', 'bonus_attack_speed', 'critical_damage', 
                             'base_attack_speed', 'windup_percent', 'as_ratio']
            
            for stat_name in remaining_stats:
                if stat_name in LEVEL_SELECTORS:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, LEVEL_SELECTORS[stat_name])
                        raw_value = element.text.strip()
                        mapped_stat_name = self._map_basic_stat_name(stat_name)
                        stats[mapped_stat_name] = self._parse_stat_value(raw_value)
                    except NoSuchElementException:
                        mapped_stat_name = self._map_basic_stat_name(stat_name)
                        stats[mapped_stat_name] = None
            
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
        """
        Determine what type of resource this champion uses.
        Returns: 'mana', 'energy', or 'secondary_bar'
        """
        # Try to determine resource type by checking what regen elements exist and have values
        mana_regen_found = False
        energy_regen_found = False
        
        # Check for mana regen (most common)
        try:
            mana_regen_element = driver.find_element(By.CSS_SELECTOR, RESOURCE_SELECTORS['mana']['resource_regen'])
            mana_regen_text = mana_regen_element.text.strip()
            # Valid mana regen should be a number > 0
            if mana_regen_text and mana_regen_text not in ['0', 'N/A', '']:
                try:
                    mana_regen_val = float(mana_regen_text)
                    if mana_regen_val > 0:
                        mana_regen_found = True
                except ValueError:
                    pass
        except NoSuchElementException:
            pass
        
        # Check for energy regen (specific champions)
        try:
            energy_regen_element = driver.find_element(By.CSS_SELECTOR, RESOURCE_SELECTORS['energy']['resource_regen'])
            energy_regen_text = energy_regen_element.text.strip()
            # Valid energy regen should be a number > 0
            if energy_regen_text and energy_regen_text not in ['0', 'N/A', '']:
                try:
                    energy_regen_val = float(energy_regen_text)
                    if energy_regen_val > 0:
                        energy_regen_found = True
                except ValueError:
                    pass
        except NoSuchElementException:
            pass
        
        # Decision logic: if we found valid regen, use that type
        if mana_regen_found and not energy_regen_found:
            return 'mana'
        elif energy_regen_found and not mana_regen_found:
            return 'energy'
        elif mana_regen_found and energy_regen_found:
            # Both found - this shouldn't happen, default to mana
            return 'mana'
        else:
            # No valid regen found - check if any resource exists at all
            try:
                resource_element = driver.find_element(By.CSS_SELECTOR, RESOURCE_SELECTORS['mana']['resource'])
                resource_text = resource_element.text.strip()
                if resource_text and resource_text not in ['0', 'N/A', '']:
                    # Has some kind of resource but no regen - probably secondary bar or special case
                    return 'secondary_bar'
            except NoSuchElementException:
                pass
            
            # No resource at all - definitely secondary bar
            return 'secondary_bar'

    def _extract_resource_stats(self, driver, stats: Dict[str, Any], resource_type: str) -> None:
        """Extract only the resource stat (not regen) based on resource type."""
        selectors = RESOURCE_SELECTORS.get(resource_type, {})
        
        if resource_type == 'mana':
            # Mana champions: Resource (Mana)
            try:
                resource_element = driver.find_element(By.CSS_SELECTOR, selectors['resource'])
                stats['Resource (Mana)'] = self._parse_stat_value(resource_element.text.strip())
            except NoSuchElementException:
                stats['Resource (Mana)'] = None
                
        elif resource_type == 'energy':
            # Energy champions: Resource (Energy)
            try:
                resource_element = driver.find_element(By.CSS_SELECTOR, selectors['resource'])
                stats['Resource (Energy)'] = self._parse_stat_value(resource_element.text.strip())
            except NoSuchElementException:
                stats['Resource (Energy)'] = None
                
        else:  # secondary_bar
            # Secondary bar champions: Resource: N/A
            stats['Resource'] = 'N/A'

    def _get_resource_regen_stat(self, driver, resource_type: str) -> tuple:
        """Get resource regen stat key and value based on resource type."""
        selectors = RESOURCE_SELECTORS.get(resource_type, {})
        
        if resource_type == 'mana':
            # Mana champions: Resource Regen (Mana)
            try:
                regen_element = driver.find_element(By.CSS_SELECTOR, selectors['resource_regen'])
                return ('Resource Regen (Mana)', self._parse_stat_value(regen_element.text.strip()))
            except NoSuchElementException:
                return ('Resource Regen (Mana)', None)
                
        elif resource_type == 'energy':
            # Energy champions: Resource Regen (Energy)
            try:
                regen_element = driver.find_element(By.CSS_SELECTOR, selectors['resource_regen'])
                return ('Resource Regen (Energy)', self._parse_stat_value(regen_element.text.strip()))
            except NoSuchElementException:
                return ('Resource Regen (Energy)', None)
                
        else:  # secondary_bar
            # Secondary bar champions: Secondary Bar (return raw text, not parsed number)
            try:
                secondary_bar_element = driver.find_element(By.CSS_SELECTOR, selectors['secondary_bar'])
                secondary_bar_text = secondary_bar_element.text.strip()
                # For secondary bars, return the raw text (like "Crimson Rush") not parsed as number
                return ('Secondary Bar', secondary_bar_text if secondary_bar_text else None)
            except NoSuchElementException:
                return ('Secondary Bar', None)

    def _map_basic_stat_name(self, stat_name: str) -> str:
        """Map internal stat names to expected output format."""
        stat_mapping = {
            'hp': 'Hp',
            'hp_regen': 'Hp Regen',
            'armor': 'Armor',
            'attack_damage': 'Attack Damage',
            'magic_resist': 'Magic Resist',
            'movement_speed': 'Movement Speed',
            'attack_range': 'Attack Range',
            'bonus_attack_speed': 'Bonus Attack Speed',
            'critical_damage': 'Critical Damage',
            'base_attack_speed': 'Base Attack Speed',
            'windup_percent': 'Windup Percent',
            'as_ratio': 'As Ratio'
        }
        return stat_mapping.get(stat_name, stat_name)

    async def scrape_default_stat_ranges(self, champion_name: str) -> Dict[str, Any]:
        """
        Scrape default stat ranges from champion page (no Selenium needed).
        Gets the range values shown by default like "600 – 2623" that appear on first page load.
        This is much more efficient than making 2 Selenium calls.
        """
        self.logger.info(f"Scraping default stat ranges for {champion_name}")
        
        # Get champion page with regular HTTP request
        soup = await self.fetch_champion_page(champion_name)
        
        # Base selectors for default stat ranges (without __lvl suffix)
        BASE_SELECTORS = {
            'hp': '#Health_',
            'hp_regen': '#HealthRegen_', 
            'armor': '#Armor_',
            'attack_damage': '#AttackDamage_',
            'magic_resist': '#MagicResist_',
            'movement_speed': '#MovementSpeed_',
            'attack_range': '#AttackRange_',
            'bonus_attack_speed': '#AttackSpeedBonus_',
            # Resource selectors (will determine type dynamically)
            'resource': '#ResourceBar_',
            'resource_regen': '#ResourceRegen_',
            # Advanced stats from the full CSS selectors 
            'critical_damage': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(8) > div.infobox-data-value.statsbox',
            'base_attack_speed': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(1) > div.infobox-data-value.statsbox',
            'windup_percent': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(2) > div.infobox-data-value.statsbox',
            'as_ratio': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox',
            # Secondary bar selector (for champions like Vladimir)
            'secondary_bar': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(4) > div.infobox-data-value.statsbox'
        }
        
        # Extract all stats and determine resource type
        raw_stats = {}
        
        # Get all .infobox-data-value elements for positional extraction
        all_stat_values = soup.select('.infobox-data-value')
        self.logger.debug(f"Found {len(all_stat_values)} .infobox-data-value elements")
        
        # First, extract basic stats using direct ID selectors
        for stat_name, selector in BASE_SELECTORS.items():
            if stat_name in ['resource', 'resource_regen', 'secondary_bar']:
                continue  # Handle these separately
            if stat_name in ['critical_damage', 'base_attack_speed', 'windup_percent', 'as_ratio']:
                continue  # Handle these with positional indexing
            
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                raw_value = element.get_text(strip=True)
                raw_stats[stat_name] = raw_value  # Keep as string for ranges like "600 – 2623"
            else:
                self.logger.debug(f"Stat '{stat_name}' not found for {champion_name}")
                raw_stats[stat_name] = None
        
        # Extract advanced stats using positional indexing from .infobox-data-value elements
        if len(all_stat_values) >= 15:  # Ensure we have enough elements
            try:
                # Based on debug output patterns for Akali:
                # Index 7: Critical Damage (175%)
                # Index 10: Base Attack Speed (0.625)  
                # Index 11: Windup Percent (13.9%)
                # Index 12: AS Ratio (N/A)
                # Index 13: Bonus Attack Speed (+3.2% - will be from bonus_attack_speed selector)
                raw_stats['critical_damage'] = all_stat_values[7].get_text(strip=True) if len(all_stat_values) > 7 else None
                raw_stats['base_attack_speed'] = all_stat_values[10].get_text(strip=True) if len(all_stat_values) > 10 else None
                raw_stats['windup_percent'] = all_stat_values[11].get_text(strip=True) if len(all_stat_values) > 11 else None
                raw_stats['as_ratio'] = all_stat_values[12].get_text(strip=True) if len(all_stat_values) > 12 else None
            except IndexError:
                self.logger.warning(f"Could not extract advanced stats for {champion_name} - insufficient elements")
                raw_stats['critical_damage'] = None
                raw_stats['base_attack_speed'] = None
                raw_stats['windup_percent'] = None
                raw_stats['as_ratio'] = None
        else:
            self.logger.warning(f"Could not extract advanced stats for {champion_name} - only {len(all_stat_values)} elements found")
            raw_stats['critical_damage'] = None
            raw_stats['base_attack_speed'] = None
            raw_stats['windup_percent'] = None
            raw_stats['as_ratio'] = None
        
        # Determine resource type and extract resource stats
        resource_type = self._determine_resource_type_from_soup(soup)
        self.logger.info(f"Detected resource type for {champion_name}: {resource_type}")
        
        # Build the final stats dictionary in the correct order  
        stats = {}
        
        # 1. HP and HP Regen
        stats['Hp'] = raw_stats.get('hp')
        stats['Hp Regen'] = raw_stats.get('hp_regen')
        
        # 2. Resource stats (in correct position after HP Regen)
        if resource_type == 'mana':
            # Extract mana values
            resource_element = soup.select_one(BASE_SELECTORS['resource'])
            resource_regen_element = soup.select_one(BASE_SELECTORS['resource_regen'])
            
            stats['Resource (Mana)'] = resource_element.get_text(strip=True) if resource_element else None
            stats['Resource Regen (Mana)'] = resource_regen_element.get_text(strip=True) if resource_regen_element else None
            
        elif resource_type == 'energy':
            # Extract energy values  
            resource_element = soup.select_one(BASE_SELECTORS['resource'])
            # Energy regen uses a different selector pattern
            energy_regen_element = soup.select_one(BASE_SELECTORS['secondary_bar'])
            
            stats['Resource (Energy)'] = resource_element.get_text(strip=True) if resource_element else None
            stats['Resource Regen (Energy)'] = energy_regen_element.get_text(strip=True) if energy_regen_element else None
            
        else:  # secondary_bar
            # Secondary bar champions like Vladimir
            stats['Resource'] = 'N/A'
            secondary_bar_element = soup.select_one(BASE_SELECTORS['secondary_bar'])
            stats['Secondary Bar'] = secondary_bar_element.get_text(strip=True) if secondary_bar_element else None
        
        # 3. Rest of the stats in order
        stats['Armor'] = raw_stats.get('armor')
        stats['Attack Damage'] = raw_stats.get('attack_damage')
        stats['Magic Resist'] = raw_stats.get('magic_resist')
        stats['Critical Damage'] = raw_stats.get('critical_damage')
        stats['Movement Speed'] = raw_stats.get('movement_speed')
        stats['Attack Range'] = raw_stats.get('attack_range')
        # Attack speed stats
        stats['Base Attack Speed'] = raw_stats.get('base_attack_speed')
        stats['Windup Percent'] = raw_stats.get('windup_percent')
        stats['As Ratio'] = raw_stats.get('as_ratio')
        stats['Bonus Attack Speed'] = raw_stats.get('bonus_attack_speed')
        
        self.logger.info(f"Successfully scraped {len(stats)} default stat ranges for {champion_name}")
        return {
            "stats": stats,
            "data_source": "wiki_default_ranges"
        }

    def _determine_resource_type_from_soup(self, soup) -> str:
        """
        Determine resource type from BeautifulSoup object by checking what elements exist.
        Returns: 'mana', 'energy', or 'secondary_bar'
        """
        # Check for mana regen (most common indicator)
        mana_regen_element = soup.select_one('#ResourceRegen_')
        if mana_regen_element:
            mana_regen_text = mana_regen_element.get_text(strip=True)
            # Valid mana regen should be a number > 0
            if mana_regen_text and mana_regen_text not in ['0', 'N/A', '']:
                try:
                    mana_regen_val = float(mana_regen_text.split(' ')[0])  # Handle ranges like "8.5 - 21.9"
                    if mana_regen_val > 0:
                        return 'mana'
                except (ValueError, IndexError):
                    pass
        
        # Check for energy (specific champions) by checking resource value
        resource_element = soup.select_one('#ResourceBar_')
        if resource_element:
            resource_text = resource_element.get_text(strip=True)
            # Energy champions typically show "200" for energy
            if resource_text and resource_text.strip() == '200':
                return 'energy'
            # Some mana champions might have ranges, check if it's a mana-like value
            elif resource_text and ('–' in resource_text or '-' in resource_text):
                return 'mana'
        
        # No clear resource found - probably secondary bar
        return 'secondary_bar'

    def _parse_stat_value(self, text: str) -> Optional[float]:
        """Parse numerical values from stat text."""
        if not text:
            return None
        try:
            return float(text.replace(',', ''))
        except (ValueError, TypeError):
            self.logger.debug(f"Could not parse stat value: {text}")
            return None 