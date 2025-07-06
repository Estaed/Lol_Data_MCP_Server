"""
Champion Stats Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting champion statistics
from the League of Legends Wiki. It builds upon the BaseScraper to handle
the specific parsing logic for stats tables and level-specific data.
"""

import asyncio
from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError
from src.models import ChampionNotFoundError

# CSS selectors for level-specific stat scraping
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
     # Complex selectors for stats without simple IDs
    'crit_damage': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(8) > div.infobox-data-value.statsbox',
    'base_attack_speed': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(1) > div.infobox-data-value.statsbox',
    'windup_percent': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(2) > div.infobox-data-value.statsbox',
    'attack_speed_ratio': '#mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox'
}


class StatsScraper(BaseScraper):
    """
    A specialized scraper for champion statistics.
    Inherits from BaseScraper and provides methods to parse stats tables.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def _find_stats_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the 'infobox' containing champion stats."""
        
        def has_stats_classes(class_list: Any) -> bool:
            """Check if a tag has the necessary classes for a stats box."""
            if not isinstance(class_list, list):
                return False
            return all(c in class_list for c in ['infobox', 'type-champion-stats'])

        return soup.find('div', class_=has_stats_classes)

    def parse_champion_stats_safe(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Safely parse champion stats from a BeautifulSoup object.

        This method wraps the parsing logic in a try-except block to handle
        potential errors during scraping, such as missing sections or
        unexpected HTML structures.

        Args:
            soup: A BeautifulSoup object of the champion's wiki page.

        Returns:
            A dictionary containing the parsed stats or an error message.
        """
        try:
            stats = self.parse_comprehensive_champion_stats(soup)
            return {"stats": stats}
        except Exception as e:
            self.logger.error(f"Failed to parse champion stats: {e}")
            return {"error": str(e)}
            
    def parse_comprehensive_champion_stats(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parses the comprehensive champion stats from the infobox.
        Handles both simple (base value) and complex (base + growth) stats.
        """
        stats_section = self._find_stats_section(soup)
        if not stats_section:
            raise WikiScraperError("Could not find champion stats section.")

        stats = {}
        stat_rows = stats_section.find_all('div', class_='infobox-row')

        for row in stat_rows:
            label_tag = row.find('div', class_='infobox-label')
            value_tag = row.find('div', class_='infobox-data-value')

            if label_tag and value_tag:
                label_text = label_tag.get_text(strip=True)
                normalized_label = self._normalize_stat_name(label_text)
                
                # Check for table-like structures within a value for complex stats
                if value_tag.find('table'):
                    # Handle stats with base and growth values
                    base_value = value_tag.select_one('td:nth-of-type(1)')
                    growth_value = value_tag.select_one('td:nth-of-type(2)')
                    if base_value and growth_value:
                        stats[normalized_label] = {
                            "base": self._parse_stat_text(base_value.get_text(strip=True)),
                            "growth": self._parse_stat_text(growth_value.get_text(strip=True))
                        }
                else:
                    # Handle simple stats
                    stats[normalized_label] = self._parse_stat_text(value_tag.get_text(strip=True))
        
        return stats

    def _normalize_stat_name(self, name: str) -> str:
        """Normalize stat names to a consistent format."""
        name = name.lower()
        name = re.sub(r'[^a-z0-9_ ]', '', name)
        name = re.sub(r'\s+', '_', name)
        # Specific normalizations
        if 'health' in name and 'regen' not in name: return 'hp'
        if 'mana' in name and 'regen' not in name: return 'mp'
        if 'attack_damage' in name: return 'ad'
        if 'attack_speed' in name: return 'as'
        if 'armor' in name: return 'armor'
        if 'magic_resist' in name: return 'mr'
        if 'health_regen' in name: return 'hp5'
        if 'mana_regen' in name: return 'mp5'
        if 'movement_speed' in name: return 'ms'
        if 'attack_range' in name: return 'range'
        return name

    def _parse_stat_text(self, text: str) -> Optional[float]:
        """Parse numerical values from stat strings."""
        if not text:
            return None
        # Remove parentheses and their contents, e.g., "550 (+2.5)" -> "550"
        text = re.sub(r'\(.*?\)', '', text).strip()
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    async def scrape_level_specific_stats(self, champion_name: str, level: int) -> Dict[str, Any]:
        """
        Scrape champion stats for a specific level using Selenium.
        """
        if not (1 <= level <= 18):
            raise ValueError("Level must be between 1 and 18.")

        driver = self._create_selenium_driver()
        url = self._build_champion_url(champion_name)
        stats = {"level": level}
        
        try:
            driver.get(url)
            wait = WebDriverWait(driver, 10)

            # Select level from dropdown
            level_dropdown = Select(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, LEVEL_SELECTORS['level_dropdown']))))
            level_dropdown.select_by_value(str(level))
            
            # Allow time for stats to update via JavaScript
            await asyncio.sleep(0.5)

            for stat_name, selector in LEVEL_SELECTORS.items():
                if stat_name == 'level_dropdown':
                    continue
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    stats[stat_name] = self._parse_stat_text(element.text)
                except NoSuchElementException:
                    self.logger.warning(f"Could not find selector '{selector}' for stat '{stat_name}' on {champion_name}'s page.")
                    stats[stat_name] = None
            
            return {
                "stats": stats,
                "scraped_at": datetime.now().isoformat(),
                "data_source": "selenium_scrape"
            }
        except (TimeoutException, NoSuchElementException, WebDriverException) as e:
            self.logger.error(f"Selenium scraping failed for {champion_name} at level {level}: {e}")
            raise WikiScraperError(f"Failed to scrape level-specific stats for {champion_name}") from e
        finally:
            driver.quit() 