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
        ability_name = self._extract_ability_name_from_container(container)
        if ability_name:
            ability_data['name'] = ability_name
        
        # Extract ability description
        description = self._extract_ability_description_from_container(container)
        if description:
            ability_data['description'] = description
        
        # Extract ability stats (cooldown, cost, range, etc.)
        stats = self._extract_ability_stats(container)
        if stats:
            ability_data.update(stats)
        
        return ability_data if ability_data else None

    def _extract_ability_name_from_container(self, container: BeautifulSoup) -> str:
        """Extract ability name from container using multiple strategies."""
        strategies = [
            # Strategy 1: Extract from skill_header id attribute (most reliable)
            self._extract_name_from_skill_header_id,
            # Strategy 2: Extract from bold text
            self._extract_name_from_bold_text,
            # Strategy 3: Extract from headings  
            self._extract_name_from_headings,
            # Strategy 4: Extract from spans (fallback)
            self._extract_name_from_spans
        ]
        
        for strategy in strategies:
            try:
                name = strategy(container)
                if name and name.strip() and len(name.strip()) > 1:
                    # Clean up the name: replace underscores with spaces, clean formatting
                    cleaned_name = name.replace('_', ' ').strip()
                    self.logger.debug(f"Extracted ability name: '{cleaned_name}' using {strategy.__name__}")
                    return cleaned_name
            except Exception as e:
                self.logger.debug(f"Strategy {strategy.__name__} failed: {e}")
                continue
        
        return "Unknown Ability"
    
    def _extract_name_from_skill_header_id(self, container: BeautifulSoup) -> str:
        """Extract ability name from skill_header id attribute."""
        skill_header = container.select_one('.skill_header')
        if skill_header and skill_header.get('id'):
            return skill_header.get('id')
        return ""
    
    def _extract_name_from_bold_text(self, container: BeautifulSoup) -> str:
        """Extract ability name from bold text."""
        bold_elements = container.select('b')
        for bold in bold_elements:
            text = bold.get_text().strip()
            # Skip wiki UI elements
            if text and not text.lower().startswith(('edit', 'current', 'passive:', 'active:')):
                return text
        return ""
    
    def _extract_name_from_headings(self, container: BeautifulSoup) -> str:
        """Extract ability name from heading elements."""
        headings = container.select('h3, h4, h5')
        for heading in headings:
            text = heading.get_text().strip()
            if text and len(text) > 1:
                return text
        return ""
    
    def _extract_name_from_spans(self, container: BeautifulSoup) -> str:
        """Extract ability name from span elements."""
        spans = container.select('span')
        for span in spans:
            text = span.get_text().strip()
            # Skip wiki UI elements and short text
            if text and len(text) > 3 and not text.lower().startswith(('edit', 'current')):
                return text
        return ""

    def _extract_ability_description_from_container(self, container: BeautifulSoup) -> str:
        """Extract ability description from container with priority for Active descriptions."""
        try:
            # Get all ability-info-description elements
            desc_elements = container.select('.ability-info-description')
            
            if desc_elements:
                # Strategy 1: Prioritize "Active:" descriptions over "Passive:" ones
                active_descriptions = []
                passive_descriptions = []
                other_descriptions = []
                
                for desc in desc_elements:
                    text = desc.get_text().strip()
                    if text:
                        if text.startswith('Active:'):
                            active_descriptions.append(text)
                        elif text.startswith('Passive:'):
                            passive_descriptions.append(text)
                        else:
                            other_descriptions.append(text)
                
                # Return the first Active description if available
                if active_descriptions:
                    self.logger.debug(f"Found {len(active_descriptions)} Active descriptions, using first one")
                    return active_descriptions[0]
                
                # Fallback to first Passive description
                if passive_descriptions:
                    self.logger.debug(f"No Active descriptions found, using first Passive description")
                    return passive_descriptions[0]
                
                # Final fallback to other descriptions
                if other_descriptions:
                    self.logger.debug(f"Using other description as fallback")
                    return other_descriptions[0]
            
            # Strategy 2: Fallback to paragraph-based extraction
            self.logger.debug("No ability-info-description found, trying paragraph extraction")
            paragraphs = container.select('p')
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 50 and not text.startswith('Edit'):
                    return text
            
            return "No description available"
            
        except Exception as e:
            self.logger.error(f"Error extracting ability description: {e}")
            return "Error extracting description"

    def _clean_description_text(self, element: BeautifulSoup) -> Optional[str]:
        """
        Clean description text to remove wiki formatting and preserve readability.
        
        Args:
            element: BeautifulSoup element containing the description
            
        Returns:
            Cleaned text with proper spacing
        """
        if not element:
            return None
        
        # Use separator=' ' to add spaces between elements
        text = element.get_text(separator=' ')
        
        if not text:
            return None
        
        # Clean up the text
        text = self._apply_text_cleaning_rules(text)
        
        return text if text and len(text) > 5 else None

    def _apply_text_cleaning_rules(self, text: str) -> str:
        """Apply minimal text cleaning rules to make wiki text more readable."""
        if not text:
            return ""
        
        # Step 1: Replace multiple spaces with single spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Step 2: Fix common wiki formatting issues
        text = re.sub(r'[\u00a0]', ' ', text)  # Remove non-breaking spaces
        
        # Step 3: Fix spacing around colons and periods
        text = re.sub(r'\s*:\s*', ': ', text)
        text = re.sub(r'\s*\.\s*', '. ', text)
        
        # Step 4: Fix Unicode dashes
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        
        # Step 5: Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _extract_ability_stats(self, container: BeautifulSoup) -> Dict[str, Any]:
        """Extract ability stats using the correct CSS selector from wiki_selectors.md."""
        stats = {}
        
        # Method 1: Use the correct selector from wiki_selectors.md for basic stats
        stats_container = container.select_one(ABILITY_DETAIL_SELECTORS['stats_list'])
        
        if stats_container:
            self.logger.debug(f"Found stats container with selector: {ABILITY_DETAIL_SELECTORS['stats_list']}")
            
            # Extract text content and look for stat patterns
            stats_text = stats_container.get_text(separator=' ', strip=True)
            self.logger.debug(f"Raw stats text from container: '{stats_text}'")
            
            # Use pattern matching to extract stats
            self._extract_stats_from_text_patterns(stats_text, stats)
        
        # Method 2: ALWAYS process the full container text to catch damage values in descriptions
        self.logger.debug(f"Processing full container text for damage values and other stats")
        container_text = container.get_text(separator=' ', strip=True)
        self.logger.debug(f"Raw container text: '{container_text[:500]}...'")
        
        # Extract additional stats from the full container text (this will catch damage values)
        self._extract_stats_from_text_patterns(container_text, stats)
        
        return stats
    
    def _extract_stats_from_text_patterns(self, text: str, stats: Dict[str, Any]) -> None:
        """Extract stats using pattern matching as fallback."""
        # Enhanced patterns to match various stat formats with proper decimal support
        # NOTE: Wiki text formats decimals with spaces: "0. 25" instead of "0.25"
        patterns = [
            # Pattern 1: "STAT: value" format with blue labels - Handle spaced decimals
            r'([A-Z\s]+?):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
            
            # Pattern 2: "Stat Name: value" format (mixed case) - Handle spaced decimals
            r'([A-Za-z][A-Za-z\s]+?):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
            
            # Pattern 3: "MAGIC DAMAGE:" or "BONUS MAGIC DAMAGE:" patterns - Handle spaced decimals
            r'([A-Z\s]*DAMAGE[A-Z\s]*):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
            
            # Pattern 4: More flexible pattern for edge cases with spaced decimal numbers
            r'([A-Za-z][A-Za-z\s]{2,}?):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
            
            # Pattern 5: Specific patterns for damage values in description text (more specific patterns first)
            r'(Magic Damage|Physical Damage|True Damage|Bonus Magic Damage|Bonus Physical Damage|Healing|Shield|Damage Per Pass|Total Mixed Damage|Total Damage):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
            
            # Pattern 6: Common ability stat patterns in wiki text
            r'(COST|COOLDOWN|CAST TIME|EFFECT RADIUS|SPEED|RANGE|WIDTH|TARGET RANGE|RADIUS|CHANNEL TIME|RECHARGE):\s*([0-9]*\.?\s*[0-9]+(?:\s*[-–/]\s*[0-9]*\.?\s*[0-9]+)*(?:\s*\([^)]+\))?)',
        ]
        
        # Track values to prevent duplicates
        seen_values = {}
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, text, re.IGNORECASE)
            for label, value in matches:
                label = label.strip()
                value = value.strip()
                
                # Fix spaced decimals: "0. 25" → "0.25", "4 – 1. 33" → "4 – 1.33"
                value = self._fix_spaced_decimals(value)
                
                # Add debugging to see what's being captured
                self.logger.debug(f"Pattern {i+1} matched: '{label}' = '{value}'")
                
                if label and value:
                    # Clean the label
                    cleaned_label = self._clean_stat_label_advanced(label)
                    
                    # Filter out unwanted labels
                    if self._should_skip_label(cleaned_label, label):
                        self.logger.debug(f"Skipping unwanted label: {cleaned_label} (original: {label})")
                        continue
                    
                    # Check for duplicate values
                    if value in seen_values:
                        self.logger.debug(f"Skipping duplicate value '{value}' for '{cleaned_label}' (already exists as '{seen_values[value]}')")
                        continue
                    
                    if cleaned_label and cleaned_label not in stats:
                        stats[cleaned_label] = value
                        seen_values[value] = cleaned_label
                        self.logger.debug(f"Added stat {cleaned_label}: {value}")
        
        # Additional debugging: log what stats were found
        self.logger.debug(f"Final extracted stats: {stats}")
    
    def _fix_spaced_decimals(self, value: str) -> str:
        """Fix spaced decimals like '0. 25' to '0.25' and '4 – 1. 33' to '4 – 1.33'."""
        if not value:
            return value
        
        # Pattern to match spaced decimals: number, space, dot, space, number
        # Examples: "0. 25" → "0.25", "1. 33" → "1.33"
        fixed_value = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', value)
        
        # Fix Unicode dash characters to regular dashes
        fixed_value = fixed_value.replace('\u2013', '-').replace('\u2014', '-')
        
        return fixed_value

    def _clean_stat_label_advanced(self, label: str) -> str:
        """Simple label cleaning to make labels consistent but preserve original meaning."""
        if not label:
            return "unknown_stat"
        
        # Convert to lowercase and clean up
        label = label.lower().strip()
        
        # Replace spaces and special characters with underscores
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', label)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        cleaned = cleaned.strip('_')
        
        # Handle specific damage and ability stat patterns
        damage_patterns = {
            'magic_damage': 'magic_damage',
            'physical_damage': 'physical_damage', 
            'true_damage': 'true_damage',
            'bonus_magic_damage': 'bonus_magic_damage',
            'bonus_physical_damage': 'bonus_physical_damage',
            'healing': 'healing',
            'shield': 'shield',
            'damage': 'damage'
        }
        
        # Check for damage patterns first
        for pattern, standardized in damage_patterns.items():
            if cleaned == pattern:
                return standardized
        
        # Enhanced standardization for common variants to prevent duplicates
        cooldown_variants = ['cd', 'cooldown_seconds', 'mana_cooldown', 'current_grit_cooldown']
        cost_variants = ['mana_cost', 'cost_mana', 'grit_cost']
        cast_time_variants = ['cast_time_seconds', 'channel_time', 'cast_time']
        range_variants = ['target_range', 'attack_range']
        radius_variants = ['effect_radius', 'radius', 'area_radius']
        
        # Map all cooldown variants to 'cooldown'
        if cleaned in cooldown_variants:
            return 'cooldown'
        # Map all cost variants to 'cost'
        elif cleaned in cost_variants:
            return 'cost'
        # Map all cast time variants to 'cast_time'
        elif cleaned in cast_time_variants:
            return 'cast_time'
        # Map all range variants to 'range'
        elif cleaned in range_variants:
            return 'range'
        # Map all radius variants to 'effect_radius'
        elif cleaned in radius_variants:
            return 'effect_radius'
        
        return cleaned if cleaned else 'unknown_stat'

    def _should_skip_label(self, cleaned_label: str, original_label: str) -> bool:
        """Check if a label should be skipped (UI elements, duplicates, etc.)."""
        
        # Skip UI editing elements
        if cleaned_label.startswith('edit_') or original_label.lower().startswith('edit '):
            return True
        
        # Skip generic "damage" if we have more specific damage types
        if cleaned_label == 'damage' and any(label.endswith('_damage') for label in cleaned_label.split()):
            return True
            
        # Skip if label is too short or meaningless
        if len(cleaned_label) < 2:
            return True
            
        # Skip common stopwords and meaningless labels
        stopwords = ['non', 'a', 'an', 'the', 'and', 'or', 'but', 'for', 'on', 'at', 'to', 'up', 'by', 'of', 'in', 'it', 'is', 'be', 'as', 'no', 'so', 'do', 'go', 'we', 'me', 'my', 'he', 'she', 'his', 'her', 'him', 'you', 'i', 'us', 'our', 'they', 'them', 'this', 'that', 'what', 'when', 'where', 'why', 'how', 'who', 'all', 'any', 'some', 'many', 'few', 'one', 'two', 'three', 'yes', 'no', 'true', 'false', 'never', 'always', 'often', 'much', 'more', 'most', 'less', 'than', 'like', 'about', 'very', 'also', 'too', 'from', 'with', 'without', 'get', 'give', 'take', 'make', 'have', 'let', 'put', 'set', 'keep', 'hold', 'come', 'go', 'move', 'run', 'walk', 'turn', 'look', 'see', 'hear', 'know', 'think', 'feel', 'want', 'need', 'like', 'love', 'try', 'work', 'play', 'use', 'buy', 'sell', 'find', 'win', 'lose', 'hit', 'cut', 'fix', 'good', 'bad', 'big', 'small', 'long', 'short', 'high', 'low', 'hot', 'cold', 'fast', 'slow', 'new', 'old', 'right', 'left', 'here', 'there', 'now', 'then', 'today', 'can', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall']
        
        if cleaned_label in stopwords:
            return True
        
        return False

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