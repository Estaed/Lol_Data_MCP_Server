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
    'as_ratio': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox'
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
            for stat_name, selector in LEVEL_SELECTORS.items():
                if stat_name == 'level_dropdown':
                    continue
                    
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    raw_value = element.text.strip()
                    stats[stat_name] = self._parse_stat_value(raw_value)
                except NoSuchElementException:
                    self.logger.warning(f"Stat '{stat_name}' not found for {champion_name}")
                    stats[stat_name] = None
            
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

    def _parse_stat_value(self, text: str) -> Optional[float]:
        """Parse numerical values from stat text."""
        if not text:
            return None
        try:
            return float(text.replace(',', ''))
        except (ValueError, TypeError):
            self.logger.debug(f"Could not parse stat value: {text}")
            return None 