"""
Champion Abilities Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting champion abilities
from the League of Legends Wiki using CSS selectors for ability containers.
"""

import asyncio
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

# Dual-form champion detection - now uses dynamic detection instead of hardcoded selectors
DUAL_FORM_SELECTOR = "#\\32  > span > span > img"  # Legacy selector for fallback
# Alternative selectors for form switching (fallback only)
DUAL_FORM_SELECTORS = [
    "#\\32  > span > span > img",
    "#\\32  > span > span",
    "#\\32  > span",
    "#\\32",
]


class AbilitiesScraper(BaseScraper):
    """
    A specialized scraper for champion abilities using CSS selector-based extraction.
    Focuses on Task 2.1.10: comprehensive ability detail system with dual-form support.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_champion_abilities(self, champion_name: str) -> Dict[str, Any]:
        """
        Scrape all champion abilities from the champion's wiki page.
        Optimized with fast HTTP-based dual-form detection first.
        Special handling for complex champions like Aphelios.
        
        Args:
            champion_name: Name of champion to scrape abilities for
            
        Returns:
            Dictionary with all ability data (single or dual form)
        """
        self.logger.info(f"Scraping abilities for {champion_name}")
        
        # Step 1: Check for special complex champions (like Aphelios with weapon systems)
        if champion_name.lower() == 'aphelios':
            self.logger.info(f"{champion_name} is a complex weapon-system champion, using specialized scraping")
            return await self._scrape_aphelios_weapon_system(champion_name)
        
        # Step 2: Fetch page once and reuse soup for dual-form detection
        soup = await self.fetch_champion_page(champion_name)
        has_dual_form = self._detect_dual_form_from_soup(soup)
        
        if has_dual_form:
            self.logger.info(f"{champion_name} likely has dual forms, using Selenium scraping")
            return await self._scrape_dual_form_abilities(champion_name)
        else:
            self.logger.info(f"{champion_name} appears to be single form, using cached soup")
            return await self._scrape_single_form_abilities_from_soup(soup)

    async def _detect_dual_form_http_fast(self, champion_name: str) -> bool:
        """Ultra-conservative HTTP-based dual-form detection to prevent false positives."""
        try:
            # Use HTTP request to get the page content
            soup = await self.fetch_champion_page(champion_name)
            
            # Strategy 1: Look for the specific dual-form selector (most reliable)
            dual_form_element = soup.select('#\\32')
            if dual_form_element:
                self.logger.info(f"Fast dual-form detection: {champion_name} has specific dual-form element")
                return True
            
            # Strategy 2: Look for very specific transformation language that indicates true dual-form
            all_text = soup.get_text().lower()
            
            # Ultra-specific patterns that only appear in true dual-form champions
            ultra_specific_patterns = [
                'transforms into',
                'switches between', 
                'form toggle',
                'dual form',
                'changes form',
                'alternate form',
                'different forms'
            ]
            
            # Also check for specific form combination patterns
            form_combinations = [
                ('human', 'spider'),  # Elise
                ('mini', 'mega'),     # Gnar
                ('hammer', 'cannon'), # Jayce
                ('human', 'cougar'),  # Nidalee
            ]
            
            # Check for transformation patterns
            transformation_count = sum(1 for pattern in ultra_specific_patterns if pattern in all_text)
            
            # Check for form combinations
            form_combination_found = False
            for form1, form2 in form_combinations:
                if form1 in all_text and form2 in all_text:
                    # Make sure both forms appear in ability contexts
                    if (f'{form1} form' in all_text and f'{form2} form' in all_text) or \
                       (f'{form1}:' in all_text and f'{form2}:' in all_text):
                        form_combination_found = True
                        break
            
            # Only consider dual-form if we have strong evidence
            if transformation_count >= 2 and form_combination_found:
                self.logger.info(f"Fast dual-form detection: {champion_name} has {transformation_count} transformation patterns and form combinations")
                return True
            
            # Strategy 3: Look for tabber with very specific form names
            tabber_nav = soup.select('.tabbernav')
            if tabber_nav:
                tab_links = soup.select('.tabbernav a')
                if len(tab_links) >= 2:
                    tab_texts = [link.get_text().strip().lower() for link in tab_links]
                    tab_text_combined = ' '.join(tab_texts)
                    
                    # Check for specific form names in tabs
                    for form1, form2 in form_combinations:
                        if form1 in tab_text_combined and form2 in tab_text_combined:
                            self.logger.info(f"Fast dual-form detection: {champion_name} has {form1}/{form2} forms in tabs")
                            return True
            
            self.logger.info(f"Fast dual-form detection: {champion_name} appears to be single form")
            return False
            
        except Exception as e:
            self.logger.warning(f"Fast dual-form detection failed for {champion_name}: {e}, falling back to False")
            return False
    
    def _detect_dual_form_from_soup(self, soup: BeautifulSoup) -> bool:
        """Detect dual-form from already fetched soup object (optimized to avoid redundant HTTP requests)."""
        try:
            # Strategy 1: Look for the specific dual-form selector (most reliable)
            dual_form_element = soup.select('#\\32')
            if dual_form_element:
                self.logger.info("Dual-form detection: Found specific dual-form element")
                return True
            
            # Strategy 2: Look for very specific transformation language
            all_text = soup.get_text().lower()
            
            ultra_specific_patterns = [
                'transforms into', 'switches between', 'form toggle', 'dual form',
                'changes form', 'alternate form', 'different forms'
            ]
            
            form_combinations = [
                ('human', 'spider'), ('mini', 'mega'), ('hammer', 'cannon'), ('human', 'cougar')
            ]
            
            # Check for transformation patterns
            transformation_count = sum(1 for pattern in ultra_specific_patterns if pattern in all_text)
            
            # Check for form combinations
            form_combination_found = False
            for form1, form2 in form_combinations:
                if form1 in all_text and form2 in all_text:
                    if (f'{form1} form' in all_text and f'{form2} form' in all_text) or \
                       (f'{form1}:' in all_text and f'{form2}:' in all_text):
                        form_combination_found = True
                        break
            
            # Strong evidence required
            if transformation_count >= 2 and form_combination_found:
                self.logger.info(f"Dual-form detection: Found {transformation_count} transformation patterns and form combinations")
                return True
            
            # Strategy 3: Look for tabber with specific form names
            tabber_nav = soup.select('.tabbernav')
            if tabber_nav:
                tab_links = soup.select('.tabbernav a')
                if len(tab_links) >= 2:
                    tab_texts = [link.get_text().strip().lower() for link in tab_links]
                    tab_text_combined = ' '.join(tab_texts)
                    
                    for form1, form2 in form_combinations:
                        if form1 in tab_text_combined and form2 in tab_text_combined:
                            self.logger.info(f"Dual-form detection: Found {form1}/{form2} forms in tabs")
                            return True
            
            self.logger.info("Dual-form detection: Appears to be single form")
            return False
            
        except Exception as e:
            self.logger.warning(f"Dual-form detection failed: {e}, falling back to False")
            return False

    async def _detect_dual_form_with_selenium(self, champion_name: str) -> bool:
        """Check if champion has dual forms using Selenium with multiple selectors."""
        driver = None
        try:
            driver = self._create_selenium_driver()
            url = self._build_champion_url(champion_name)
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Check for second form selector using multiple strategies
            for selector in DUAL_FORM_SELECTORS:
                try:
                    second_form_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(second_form_elements) > 0:
                        self.logger.info(f"Dual form detected for {champion_name} using selector: {selector}")
                        return True
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed for {champion_name}: {e}")
                    continue
            
            self.logger.info(f"No dual form detected for {champion_name}")
            return False
            
        except Exception as e:
            self.logger.warning(f"Failed to detect dual form for {champion_name}: {e}")
            return False
        finally:
            if driver:
                driver.quit()

    async def _scrape_dual_form_abilities(self, champion_name: str) -> Dict[str, Any]:
        """Scrape abilities for champions with dual forms using tab-based form switching."""
        driver = None
        try:
            driver = self._create_selenium_driver()
            url = self._build_champion_url(champion_name)
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            self.logger.info(f"Extracting dual-form abilities for {champion_name} using tab-based approach")
            
            # Try the new tab-based approach for cleaner dual-form extraction
            dual_form_abilities = await self._extract_abilities_by_form_tabs(driver, champion_name)
            
            if dual_form_abilities:
                # Validate that we actually got different abilities for different forms
                form_1_abilities = {k: v for k, v in dual_form_abilities.items() if 'Form 1' in k}
                form_2_abilities = {k: v for k, v in dual_form_abilities.items() if 'Form 2' in k}
                
                # Check if the abilities are actually different
                if form_1_abilities and form_2_abilities:
                    form_1_names = {v.get('name', '') for v in form_1_abilities.values()}
                    form_2_names = {v.get('name', '') for v in form_2_abilities.values()}
                    
                    if form_1_names == form_2_names:
                        self.logger.warning(f"Tab-based extraction got identical abilities for both forms, falling back to container method")
                        # Fall back to container method if we got duplicates
                        dual_form_abilities = None
                    else:
                        self.logger.info(f"Tab-based extraction successful: Form 1 has {form_1_names}, Form 2 has {form_2_names}")
                
                if dual_form_abilities:
                    return {
                        "abilities": dual_form_abilities,
                        "dual_form": True,
                        "extraction_method": "direct_container_extraction",
                        "data_source": "wiki_abilities_scrape_dual_form_containers"
                    }
            
            # Fallback to container-based method 
            self.logger.warning(f"Tab-based extraction failed for {champion_name}, falling back to container extraction")
            all_forms_abilities = self._extract_complete_dual_form_abilities(driver, champion_name)
            
            return {
                "abilities": all_forms_abilities,
                "dual_form": True,
                "extraction_method": "complete_container_content",
                "data_source": "wiki_abilities_scrape_dual_form"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to scrape dual form abilities for {champion_name}: {e}")
            raise WikiScraperError(f"Failed to scrape dual form abilities for {champion_name}") from e
        finally:
            if driver:
                driver.quit()

    async def _extract_abilities_by_form_tabs(self, driver, champion_name: str) -> Optional[Dict[str, Any]]:
        """Extract abilities directly from both form containers with dynamic form name detection."""
        try:
            self.logger.info(f"Extracting dual-form abilities directly from containers for {champion_name}")
            
            # First, detect form names from the main page tab headers
            form_names = self._detect_form_names_from_tabs(driver, champion_name)
            form1_name = form_names.get('form1', 'Form 1')
            form2_name = form_names.get('form2', 'Form 2')
            
            # Extract abilities from #item-1 (first form)
            form1_abilities = {}
            try:
                form1_container = driver.find_element(By.CSS_SELECTOR, "#item-1")
                if form1_container:
                    self.logger.info(f"Found #item-1 container ({form1_name})")
                    page_source = form1_container.get_attribute('innerHTML')
                    soup = BeautifulSoup(page_source, 'lxml')
                    form1_abilities = self._extract_all_abilities_from_soup(soup, form1_name)
                    self.logger.info(f"Extracted {len(form1_abilities)} {form1_name} abilities: {list(form1_abilities.keys())}")
            except Exception as e:
                self.logger.error(f"Failed to extract first form abilities: {e}")
                return None
            
            # Extract abilities from #item-2 (second form)  
            form2_abilities = {}
            try:
                form2_container = driver.find_element(By.CSS_SELECTOR, "#item-2")
                if form2_container:
                    self.logger.info(f"Found #item-2 container ({form2_name})")
                    page_source = form2_container.get_attribute('innerHTML')
                    soup = BeautifulSoup(page_source, 'lxml')
                    form2_abilities = self._extract_all_abilities_from_soup(soup, form2_name)
                    self.logger.info(f"Extracted {len(form2_abilities)} {form2_name} abilities: {list(form2_abilities.keys())}")
            except Exception as e:
                self.logger.error(f"Failed to extract second form abilities: {e}")
                return None
            
            # Extract shared abilities (Passive and R) from the main page content
            shared_abilities = {}
            try:
                main_page_source = driver.page_source
                main_soup = BeautifulSoup(main_page_source, 'lxml')
                
                # Extract Passive ability
                passive_data = self._extract_ability_from_container(main_soup, '.skill_innate', 'passive')
                if passive_data:
                    shared_abilities['Passive'] = passive_data
                    self.logger.info(f"Extracted Passive ability: {passive_data.get('name', 'Unknown')}")
                
                # Extract R ability
                r_data = self._extract_ability_from_container(main_soup, '.skill_r', 'r')
                if r_data:
                    shared_abilities['R'] = r_data
                    self.logger.info(f"Extracted R ability: {r_data.get('name', 'Unknown')}")
                    
            except Exception as e:
                self.logger.error(f"Failed to extract shared abilities: {e}")
                # Continue without shared abilities if extraction fails
            
            # Verify we got different abilities for each form
            if not form1_abilities or not form2_abilities:
                self.logger.warning("Could not extract abilities from both form containers")
                return None
            
            # Check that we actually have different abilities
            form1_names = {v.get('name', '') for v in form1_abilities.values()}
            form2_names = {v.get('name', '') for v in form2_abilities.values()}
            
            if form1_names == form2_names:
                self.logger.warning("Got identical ability names for both forms")
                return None
            
            self.logger.info(f"SUCCESS: {form1_name} abilities: {form1_names}")
            self.logger.info(f"SUCCESS: {form2_name} abilities: {form2_names}")
            
            # Build the complete dual-form result with proper ordering
            all_abilities = {}
            
            # 1. Add Passive first
            if 'Passive' in shared_abilities:
                all_abilities['Passive'] = shared_abilities['Passive']
            
            # 2. Add form-specific abilities (Q, W, E) in order
            for ability_key in ['Q', 'W', 'E']:
                if ability_key in form1_abilities:
                    all_abilities[f"{ability_key} ({form1_name})"] = form1_abilities[ability_key]
                if ability_key in form2_abilities:
                    all_abilities[f"{ability_key} ({form2_name})"] = form2_abilities[ability_key]
            
            # 3. Add R ability at the end
            if 'R' in shared_abilities:
                all_abilities['R'] = shared_abilities['R']
            
            self.logger.info(f"Complete dual-form result: {len(all_abilities)} abilities total")
            return all_abilities
            
        except Exception as e:
            self.logger.error(f"Failed to extract dual-form abilities: {e}")
            return None

    def _detect_form_names_from_tabs(self, driver, champion_name: str) -> Dict[str, str]:
        """Detect form names from the main page tab headers."""
        try:
            # Look for tab elements that contain form names
            tab_selectors = [
                "#1",  # First form tab
                "#2",  # Second form tab
                ".tabbernav a",  # Alternative tab selector
                "[id='1']",  # Alternative first form
                "[id='2']",  # Alternative second form
            ]
            
            detected_forms = {}
            
            # Try to find form tabs
            for selector in tab_selectors:
                try:
                    tabs = driver.find_elements(By.CSS_SELECTOR, selector)
                    if tabs:
                        for i, tab in enumerate(tabs[:2]):  # Only take first 2 tabs
                            try:
                                # Try to get the title or text content
                                form_name = None
                                title = tab.get_attribute('title') or ""
                                text = tab.text.strip() if tab.text else ""
                                
                                # Prioritize title attribute if it contains "abilities"
                                if title and 'abilities' in title.lower():
                                    form_name = title.replace(' abilities', '').replace(' form', '').strip()
                                elif text and len(text) > 0 and len(text) < 20:
                                    # Only use text if it's reasonable length and not generic
                                    if text not in ['1', '2', 'Current', 'Active', 'Passive', 'SR', 'ARAM', 'Swiftplay']:
                                        form_name = text.replace(' abilities', '').replace(' form', '').strip()
                                
                                if form_name and len(form_name) > 1:
                                    # Filter out non-form names
                                    non_form_names = {'current', 'active', 'passive', 'sr', 'aram', 'swiftplay', 'urf', 'nexus'}
                                    if form_name.lower() not in non_form_names:
                                        form_name = form_name.capitalize()
                                        form_key = f'form{i+1}'
                                        if form_key not in detected_forms:
                                            detected_forms[form_key] = f"{form_name} Form"
                                            self.logger.info(f"Detected {form_key}: {form_name} Form from tab")
                                        
                            except Exception as e:
                                self.logger.debug(f"Failed to extract form name from tab: {e}")
                                continue
                                
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # If we found form names, return them
            if detected_forms:
                return detected_forms
            
            # Fallback: Use default form names
            self.logger.warning(f"Could not detect form names from tabs for {champion_name}, using defaults")
            return {'form1': 'Form 1', 'form2': 'Form 2'}
            
        except Exception as e:
            self.logger.error(f"Error detecting form names from tabs: {e}")
            return {'form1': 'Form 1', 'form2': 'Form 2'}

    def _detect_form_name_from_container(self, soup: BeautifulSoup, champion_name: str) -> Optional[str]:
        """Dynamically detect form name from container content without hard-coding."""
        try:
            # Get the main page driver to look for tab headers
            # This is a more reliable way to detect form names
            
            # Strategy 1: Look for form names in the page structure that are common patterns
            # But don't hard-code - look for specific patterns that indicate forms
            all_text = soup.get_text().lower()
            
            # Strategy 2: Look for words that commonly appear before "form" in League champions
            import re
            form_word_patterns = re.findall(r'([a-zA-Z]+)\s+form', all_text, re.IGNORECASE)
            
            # Filter to words that are likely actual form names (not UI text)
            valid_form_words = []
            for word in form_word_patterns:
                word_lower = word.lower()
                # Skip UI words that aren't actual form names
                ui_words = {'current', 'active', 'passive', 'innate', 'edit', 'this', 'that', 'next', 'previous'}
                if word_lower not in ui_words and len(word) >= 3:
                    valid_form_words.append(word.capitalize())
            
            # Return the most likely form name
            if valid_form_words:
                # Take the first unique form name
                unique_forms = list(dict.fromkeys(valid_form_words))  # Remove duplicates while preserving order
                form_name = unique_forms[0]
                self.logger.info(f"Detected form name: {form_name}")
                return f"{form_name} Form"
            
            # Strategy 3: Fallback - look for title-case words that might be form names
            title_words = re.findall(r'\b[A-Z][a-z]+\b', soup.get_text())
            for word in title_words:
                word_lower = word.lower()
                # Skip common words that aren't form names
                common_words = {'active', 'passive', 'innate', 'cost', 'cooldown', 'range', 'edit', 'current', 'ability', 'damage', 'magic', 'bonus', 'target', 'enemy', 'champion', 'seconds', 'increases', 'grants', 'deals', 'takes'}
                if word_lower not in common_words and len(word) >= 4:
                    # Check if this word appears multiple times (more likely to be a form name)
                    if all_text.count(word_lower) >= 2:
                        form_name = word.capitalize()
                        self.logger.info(f"Detected form name from repeated word: {form_name}")
                        return f"{form_name} Form"
            
            self.logger.debug("Could not detect form name from container")
            return None
            
        except Exception as e:
            self.logger.error(f"Error detecting form name: {e}")
            return None

    def _get_form_name_from_tab(self, tab_element) -> Optional[str]:
        """Extract form name from a tab element."""
        try:
            # Try different attributes and text content
            sources = [
                tab_element.get_attribute('title'),
                tab_element.get_attribute('data-form'),
                tab_element.get_attribute('data-tab'),
                tab_element.text.strip(),
                tab_element.get_attribute('alt')
            ]
            
            for source in sources:
                if source and source.strip():
                    form_name = source.strip()
                    # Clean up common form names
                    form_name = self._standardize_form_name(form_name)
                    if form_name:
                        return form_name
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to get form name from tab: {e}")
            return None

    def _extract_form_abilities_from_active_content(self, driver, form_name: str) -> Dict[str, Any]:
        """Extract abilities from the currently active form content."""
        try:
            # Convert driver page to BeautifulSoup for parsing
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            
            # Extract abilities using our existing method
            abilities = self._extract_all_abilities_from_soup(soup, form_name)
            
            return abilities
            
        except Exception as e:
            self.logger.error(f"Failed to extract abilities from active content for {form_name}: {e}")
            return {}

    def _extract_complete_dual_form_abilities(self, driver, champion_name: str) -> Dict[str, Any]:
        """Extract complete dual-form abilities from all ability containers."""
        try:
            # Get all ability containers for each ability type
            all_abilities = {}
            
            for ability_slot, container_selector in ABILITY_CONTAINERS.items():
                self.logger.debug(f"Processing {ability_slot} ability for {champion_name}")
                
                # Find all containers for this ability type
                containers = driver.find_elements(By.CSS_SELECTOR, container_selector)
                self.logger.debug(f"Found {len(containers)} {ability_slot} containers")
                
                if containers:
                    # Extract complete content from the first container (which contains both forms)
                    main_container = containers[0]
                    
                    # Get complete HTML content to preserve structure
                    container_html = main_container.get_attribute('innerHTML')
                    container_soup = BeautifulSoup(container_html, 'lxml')
                    
                    # Extract ability data with dual-form parsing
                    ability_data = self._extract_dual_form_ability_from_container(
                        container_soup, ability_slot, champion_name
                    )
                    
                    if ability_data:
                        all_abilities[ABILITY_SLOTS[ability_slot]] = ability_data
                        self.logger.debug(f"Extracted dual-form {ability_slot} ability")
                    else:
                        self.logger.warning(f"No data extracted for {ability_slot} ability")
                else:
                    self.logger.warning(f"No containers found for {ability_slot} ability")
            
            return all_abilities
            
        except Exception as e:
            self.logger.error(f"Failed to extract complete dual-form abilities: {e}")
            raise

    def _extract_dual_form_ability_from_container(self, container_soup: BeautifulSoup, ability_slot: str, champion_name: str) -> Optional[Dict[str, Any]]:
        """Extract dual-form ability data from a container with both forms."""
        try:
            # Get complete text content
            full_text = container_soup.get_text(separator=' ')
            full_text = self._apply_text_cleaning_rules(full_text)
            
            # Extract basic ability information
            ability_name = self._extract_ability_name_from_container(container_soup)
            
            # Extract stats (this will get all stats from the container)
            stats = self._extract_ability_stats(container_soup)
            
            # Parse dual-form content based on champion type
            forms = self._parse_dual_form_content(full_text, champion_name, ability_slot)
            
            if forms and len(forms) >= 2:
                # Create merged description with better formatting
                merged_description = self._create_merged_description(forms)
                
                # Return structured dual-form data with merged description
                return {
                    "name": ability_name,
                    "description": merged_description,
                    "dual_form": True,
                    **stats
                }
            else:
                # Fallback to single description if dual-form parsing fails
                return {
                    "name": ability_name,
                    "description": full_text,
                    "dual_form": False,
                    **stats
                }
                
        except Exception as e:
            self.logger.error(f"Failed to extract dual-form ability from container: {e}")
            return None

    def _create_merged_description(self, forms: Dict[str, str]) -> str:
        """Create a merged description with proper formatting for dual-form abilities."""
        if not forms:
            return ""
        
        # Sort forms to ensure consistent ordering (Mini before Mega, Human before Spider, etc.)
        sorted_forms = self._sort_forms_logically(forms)
        
        descriptions = []
        for form_name, form_description in sorted_forms.items():
            if form_description and form_description.strip():
                # Format each form with bold markdown and clean description
                cleaned_desc = form_description.strip()
                descriptions.append(f"**{form_name}**: {cleaned_desc}")
        
        # Join with double newlines for better readability
        return "\n\n".join(descriptions)

    def _sort_forms_logically(self, forms: Dict[str, str]) -> Dict[str, str]:
        """Sort forms in a logical order (base form first, then transformed form)."""
        # Define logical ordering for common form pairs
        form_order = {
            'Mini Gnar': 0,
            'Mega Gnar': 1,
            'Human Form': 0,
            'Spider Form': 1,
            'Hammer Form': 0,
            'Cannon Form': 1,
            'Human': 0,
            'Spider': 1,
            'Hammer': 0,
            'Cannon': 1,
            'Ranged Form': 0,
            'Melee Form': 1,
            'Form 1': 0,
            'Form 2': 1,
        }
        
        # Sort forms by defined order, or alphabetically if not defined
        sorted_items = sorted(forms.items(), key=lambda x: (form_order.get(x[0], 999), x[0]))
        return dict(sorted_items)

    def _create_combined_description(self, forms: Dict[str, str]) -> str:
        """Create a combined description from forms for consistency - DEPRECATED, use _create_merged_description instead."""
        # This method is kept for backward compatibility but redirects to the new method
        return self._create_merged_description(forms)

    def _parse_dual_form_content(self, full_text: str, champion_name: str, ability_slot: str) -> Optional[Dict[str, str]]:
        """Parse dual-form content using generic patterns that work for any champion."""
        if not full_text:
            return None
        
        forms = {}
        text_lower = full_text.lower()
        
        # Generic dual-form parsing strategies
        forms = self._parse_generic_dual_forms(full_text, text_lower)
        
        # Validate and clean forms - ensure both forms have meaningful content
        validated_forms = {}
        for form_name, form_content in forms.items():
            if form_content and form_content.strip():
                # Apply text cleaning to each form
                cleaned_content = self._apply_text_cleaning_rules(form_content)
                
                # Only keep forms with substantial content
                if cleaned_content and len(cleaned_content.strip()) > 15:
                    validated_forms[form_name] = cleaned_content
        
        # If we have at least 2 meaningful forms, return them
        if len(validated_forms) >= 2:
            return validated_forms
        
        # If we only have 1 form or the forms are too short, 
        # try to split the original text differently
        if len(validated_forms) == 1 and len(full_text) > 200:
            # Try a simple split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', full_text)
            if len(sentences) >= 4:
                mid_point = len(sentences) // 2
                form1 = self._apply_text_cleaning_rules(' '.join(sentences[:mid_point]))
                form2 = self._apply_text_cleaning_rules(' '.join(sentences[mid_point:]))
                
                if len(form1) > 15 and len(form2) > 15:
                    return {'Form 1': form1, 'Form 2': form2}
        
        return None

    def _parse_generic_dual_forms(self, full_text: str, text_lower: str) -> Dict[str, str]:
        """Generic dual-form parsing that dynamically detects actual form names."""
        forms = {}
        
        # Strategy 1: Extract form names dynamically from the text
        detected_form_names = self._detect_form_names_from_text(full_text, text_lower)
        
        if len(detected_form_names) >= 2:
            # Try to split content using the detected form names
            forms = self._split_content_by_detected_forms(full_text, detected_form_names)
            if forms:
                return forms
        
        # Strategy 2: Look for very specific form transition patterns
        strong_form_patterns = [
            # Pattern: "transforms into" or "switches between"
            r'(.*?)(?:transforms?\s+into|switches?\s+between|changes?\s+form|toggles?\s+between)\s+(.*)',
            # Pattern: Look for explicit dual-form indicators
            r'(.*?)(?:dual\s+form|alternate\s+form|different\s+forms)\s+(.*)',
        ]
        
        for pattern in strong_form_patterns:
            matches = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if matches and len(matches.groups()) >= 2:
                groups = matches.groups()
                part1 = groups[0].strip()
                part2 = groups[1].strip()
                
                # Only use if both parts have substantial content and are different
                if len(part1) > 100 and len(part2) > 100 and part1 != part2:
                    # Try to extract form names from the parts
                    form1_name = self._extract_form_name_from_content(part1) or "Form 1"
                    form2_name = self._extract_form_name_from_content(part2) or "Form 2"
                    forms[form1_name] = part1
                    forms[form2_name] = part2
                    return forms
        
        # Strategy 3: VERY conservative "Active:" splitting with dynamic form name detection
        active_sections = re.split(r'\s*Active:\s*', full_text, flags=re.IGNORECASE)
        active_sections = [section.strip() for section in active_sections if section.strip()]
        
        if len(active_sections) >= 2:
            # Check if the sections have form-related keywords and try to extract form names
            section_data = []
            for section in active_sections:
                section_lower = section.lower()
                
                # Count form-related keywords
                form_keywords = ['form', 'transforms', 'becomes', 'switches', 'changes', 'mode']
                keyword_count = sum(1 for keyword in form_keywords if keyword in section_lower)
                
                # Try to extract form name from this section
                form_name = self._extract_form_name_from_content(section)
                
                section_data.append((section, keyword_count, form_name))
            
            # Only split if we have strong form indicators
            if any(keyword_count >= 2 for _, keyword_count, _ in section_data):
                # Sort by keyword count and take the two highest scoring sections
                section_data.sort(key=lambda x: x[1], reverse=True)
                
                if len(section_data) >= 2:
                    form1_name = section_data[0][2] or "Form 1"
                    form2_name = section_data[1][2] or "Form 2"
                    forms[form1_name] = section_data[0][0]
                    forms[form2_name] = section_data[1][0]
                    return forms
        
        # Strategy 4: If no strong dual-form evidence, don't split
        return {'Default': full_text.strip()}

    def _detect_form_names_from_text(self, full_text: str, text_lower: str) -> List[str]:
        """Dynamically detect form names from the text content."""
        form_names = []
        
        # Enhanced form name patterns to look for
        form_patterns = [
            # Pattern: "FormName:" or "FormName Form:" (most common)
            r'(?:^|\s)((?:mini|mega|human|spider|hammer|cannon|cougar|ranged|melee)\s*(?:form|gnar|mode)?):',
            # Pattern: "FormName -" (like "Mini Gnar -", "Human Form -")
            r'(?:^|\s)((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar|mode)?)\s*[-–]',
            # Pattern: Look for repeated form references with action words
            r'(?:^|\s)((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar)?)\s+(?:gains|loses|becomes|transforms|switches|changes)',
            # Pattern: "In FormName" or "As FormName"
            r'(?:in|as)\s+((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar|mode)?)',
            # Pattern: Direct form references in abilities
            r'(?:^|\s)(mini\s+gnar|mega\s+gnar|human\s+form|spider\s+form|hammer\s+form|cannon\s+form|cougar\s+form)(?:\s|$|:|-|\'s)',
            # Pattern: Transform language
            r'transforms?\s+(?:into|to)\s+((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar|mode)?)',
            # Pattern: Possessive forms like "Mini Gnar's" or "Human Form's"
            r'(?:^|\s)((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar)?)\'s',
        ]
        
        found_names = set()
        for pattern in form_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                cleaned_name = match.strip()
                if len(cleaned_name) > 2:  # Avoid very short matches
                    # Capitalize properly and standardize
                    cleaned_name = self._standardize_form_name(cleaned_name)
                    if cleaned_name:
                        found_names.add(cleaned_name)
        
        # Convert to list and sort by specificity (longer, more specific names first)
        form_names = sorted(list(found_names), key=lambda x: (len(x), x), reverse=True)
        
        # Filter out generic terms if we have more specific ones
        if len(form_names) > 2:
            specific_names = [name for name in form_names if not any(generic in name.lower() for generic in ['first', 'second', 'primary', 'secondary', 'form 1', 'form 2'])]
            if len(specific_names) >= 2:
                form_names = specific_names
        
        # Log detected form names for debugging
        if form_names:
            self.logger.debug(f"Detected form names: {form_names}")
        
        return form_names[:4]  # Limit to max 4 forms

    def _standardize_form_name(self, form_name: str) -> Optional[str]:
        """Standardize and capitalize form names properly."""
        if not form_name:
            return None
        
        # Clean up the form name
        form_name = form_name.strip().lower()
        
        # Handle specific form name patterns
        standardization_map = {
            'mini gnar': 'Mini Gnar',
            'mega gnar': 'Mega Gnar', 
            'mini': 'Mini Gnar',
            'mega': 'Mega Gnar',
            'human form': 'Human Form',
            'spider form': 'Spider Form',
            'human': 'Human Form',
            'spider': 'Spider Form',
            'hammer form': 'Hammer Form',
            'cannon form': 'Cannon Form',
            'hammer': 'Hammer Form',
            'cannon': 'Cannon Form',
            'cougar form': 'Cougar Form',
            'cougar': 'Cougar Form',
            'ranged': 'Ranged Form',
            'melee': 'Melee Form',
        }
        
        # Check for exact matches first
        if form_name in standardization_map:
            return standardization_map[form_name]
        
        # Handle compound names like "mini gnar form"
        for key, value in standardization_map.items():
            if key in form_name:
                return value
        
        # Fallback: capitalize each word
        words = form_name.split()
        capitalized = ' '.join(word.capitalize() for word in words)
        
        # Only return if it looks like a valid form name
        if any(indicator in form_name for indicator in ['mini', 'mega', 'human', 'spider', 'hammer', 'cannon', 'cougar', 'form', 'gnar']):
            return capitalized
        
        return None

    def _split_content_by_detected_forms(self, full_text: str, form_names: List[str]) -> Dict[str, str]:
        """Split content using dynamically detected form names."""
        forms = {}
        
        # Sort form names by length (longer first for better matching)
        sorted_form_names = sorted(form_names, key=len, reverse=True)
        
        # Try to find content sections for each detected form
        for form_name in sorted_form_names:
            # Create multiple patterns to match this form's content
            form_lower = form_name.lower()
            
            # Build pattern alternatives for this form
            form_alternatives = [form_lower]
            
            # Add variations (e.g., "Mini Gnar" -> ["mini gnar", "mini", "gnar"])
            if 'gnar' in form_lower:
                form_alternatives.append(form_lower.replace(' gnar', '').strip())
                form_alternatives.append(form_lower.replace('gnar', '').strip())
            if 'form' in form_lower:
                form_alternatives.append(form_lower.replace(' form', '').strip())
                form_alternatives.append(form_lower.replace('form', '').strip())
            
            # Remove empty alternatives and duplicates
            form_alternatives = list(set([alt for alt in form_alternatives if alt.strip()]))
            
            # Create patterns for content matching
            other_forms = [other for other in sorted_form_names if other != form_name]
            other_patterns = []
            for other in other_forms:
                other_lower = other.lower()
                other_alternatives = [other_lower]
                if 'gnar' in other_lower:
                    other_alternatives.append(other_lower.replace(' gnar', '').strip())
                if 'form' in other_lower:
                    other_alternatives.append(other_lower.replace(' form', '').strip())
                other_patterns.extend([re.escape(alt) for alt in other_alternatives if alt.strip()])
            
            # Build the lookahead pattern for stopping
            if other_patterns:
                stop_pattern = f"(?={'|'.join(other_patterns)})"
            else:
                stop_pattern = "$"
            
            form_patterns = []
            for alt in form_alternatives:
                if alt.strip():
                    escaped_alt = re.escape(alt)
                    form_patterns.extend([
                        # Pattern: "FormName: content" or "FormName Form: content"
                        f'{escaped_alt}\\s*(?:form)?:?\\s*(.*?)(?:{stop_pattern})',
                        # Pattern: "FormName - content"
                        f'{escaped_alt}\\s*[-–]\\s*(.*?)(?:{stop_pattern})',
                        # Pattern: "Active: content" after FormName mention
                        f'{escaped_alt}.*?active:\\s*(.*?)(?:{stop_pattern})',
                        # Pattern: Content that starts with FormName
                        f'(?:^|\\s){escaped_alt}\\b\\s*(.*?)(?:{stop_pattern})',
                    ])
            
            # Try each pattern until we find content
            for pattern in form_patterns:
                try:
                    matches = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                    if matches:
                        content = matches.group(1).strip()
                        if len(content) > 30:  # Only use substantial content
                            forms[form_name] = content
                            self.logger.debug(f"Found content for {form_name}: {content[:50]}...")
                            break
                except Exception as e:
                    self.logger.debug(f"Pattern failed for {form_name}: {e}")
                    continue
        
        # Only return if we found content for at least 2 forms
        if len(forms) >= 2:
            self.logger.debug(f"Successfully split content into {len(forms)} forms: {list(forms.keys())}")
            return forms
        
        return {}

    def _extract_form_name_from_content(self, content: str) -> Optional[str]:
        """Extract form name from a piece of content."""
        content_lower = content.lower()
        
        # Look for form name patterns at the beginning of content
        form_patterns = [
            r'^((?:mini|mega|human|spider|hammer|cannon|cougar)\s*(?:form|gnar|mode)?)',
            r'^((?:ranged|melee|first|second)\s*(?:form|mode)?)',
        ]
        
        for pattern in form_patterns:
            match = re.search(pattern, content_lower)
            if match:
                form_name = match.group(1).strip()
                # Capitalize properly
                words = form_name.split()
                return ' '.join(word.capitalize() for word in words)
        
        return None

    async def _scrape_aphelios_weapon_system(self, champion_name: str) -> Dict[str, Any]:
        """Scrape Aphelios' complex weapon system with all 5 Moonstone Weapons."""
        try:
            # Use HTTP-based scraping for Aphelios
            soup = await self.fetch_champion_page(champion_name)
            
            # Get all ability description elements for Aphelios
            desc_elements = soup.select('.ability-info-description')
            self.logger.info(f"Found {len(desc_elements)} ability description elements for {champion_name}")
            
            # Process all descriptions and organize by weapon
            weapon_info = {
                'calibrum': [],
                'severum': [],
                'gravitum': [],
                'infernum': [],
                'crescendum': []
            }
            
            basic_abilities = {}
            weapon_names = ['calibrum', 'severum', 'gravitum', 'infernum', 'crescendum']
            
            for i, desc_element in enumerate(desc_elements):
                try:
                    # Apply enhanced text cleaning
                    desc_text = self._apply_text_cleaning_rules(desc_element.get_text(separator=' '))
                    
                    if desc_text and len(desc_text) > 20:
                        self.logger.debug(f"Processing description {i+1} ({len(desc_text)} chars)")
                        
                        # Check which weapon this description belongs to
                        desc_lower = desc_text.lower()
                        
                        # Categorize by weapon
                        for weapon in weapon_names:
                            if weapon in desc_lower:
                                weapon_info[weapon].append(desc_text)
                                self.logger.debug(f"Assigned description {i+1} to {weapon}")
                                break
                        
                        # Also check for basic abilities (Passive, Q, W, E, R)
                        if desc_text.startswith('INNATE:'):
                            basic_abilities['Passive'] = {'description': desc_text}
                        elif 'varies based on his current main weapon' in desc_text:
                            basic_abilities['Q'] = {'description': desc_text}
                        elif 'switches between his main weapon and off-hand weapon' in desc_text:
                            basic_abilities['W'] = {'description': desc_text}
                        elif 'receives a text prompt of the weapon' in desc_text:
                            basic_abilities['E'] = {'description': desc_text}
                        elif 'casts forth a lunar spotlight' in desc_text:
                            basic_abilities['R'] = {'description': desc_text}
                            
                except Exception as e:
                    self.logger.error(f"Error processing description {i+1}: {e}")
                    continue
            
            # Extract basic ability information using standard method
            standard_abilities = self._extract_all_abilities_from_soup(soup, "aphelios_standard")
            
            # Merge standard abilities with our custom parsing
            for ability_key, ability_data in standard_abilities.items():
                if ability_key in basic_abilities:
                    # Merge the information
                    basic_abilities[ability_key].update(ability_data)
                else:
                    basic_abilities[ability_key] = ability_data
            
            # Build comprehensive weapon system information
            weapon_system = {}
            for weapon_name in weapon_names:
                if weapon_info[weapon_name]:
                    weapon_system[weapon_name.title()] = {
                        'descriptions': weapon_info[weapon_name],
                        'description_count': len(weapon_info[weapon_name])
                    }
            
            result = {
                "abilities": basic_abilities,
                "weapon_system": weapon_system,
                "weapon_count": len([w for w in weapon_system.keys() if weapon_system[w]['descriptions']]),
                "total_descriptions": len(desc_elements),
                "data_source": "wiki_abilities_scrape_weapon_system"
            }
            
            self.logger.info(f"Successfully scraped Aphelios: {len(basic_abilities)} abilities, {len(weapon_system)} weapons, {len(desc_elements)} descriptions")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to scrape Aphelios weapon system: {e}")
            raise WikiScraperError(f"Failed to scrape Aphelios weapon system") from e

    async def _scrape_single_form_abilities(self, champion_name: str) -> Dict[str, Any]:
        """Scrape abilities for champions with single form (original method)."""
        # Use HTTP-based scraping for single form abilities
        soup = await self.fetch_champion_page(champion_name)
        abilities = self._extract_all_abilities_from_soup(soup, "single_form")
        
        if not abilities:
            raise WikiScraperError(f"No abilities found for {champion_name}")
        
        self.logger.info(f"Successfully scraped {len(abilities)} abilities for {champion_name}")
        return {
            "abilities": abilities,
            "dual_form": False,
            "data_source": "wiki_abilities_scrape"
        }
    
    async def _scrape_single_form_abilities_from_soup(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Scrape abilities for single form champions using cached soup object (optimized to avoid redundant HTTP requests)."""
        abilities = self._extract_all_abilities_from_soup(soup, "single_form")
        
        if not abilities:
            raise WikiScraperError("No abilities found in cached soup")
        
        self.logger.info(f"Successfully scraped {len(abilities)} abilities from cached soup")
        return {
            "abilities": abilities,
            "dual_form": False,
            "data_source": "wiki_abilities_scrape_cached"
        }

    def _extract_all_abilities_from_soup(self, soup: BeautifulSoup, form_label: str) -> Dict[str, Any]:
        """Extract all abilities from a BeautifulSoup object."""
        abilities = {}
        
        # Extract each ability using its container selector
        for ability_slot, container_selector in ABILITY_CONTAINERS.items():
            try:
                ability_data = self._extract_ability_from_container(
                    soup, container_selector, ability_slot
                )
                if ability_data:
                    abilities[ABILITY_SLOTS[ability_slot]] = ability_data
                    self.logger.debug(f"Extracted {ability_slot} ability for {form_label}")
                else:
                    self.logger.warning(f"No data found for {ability_slot} ability in {form_label}")
            except Exception as e:
                self.logger.error(f"Failed to extract {ability_slot} ability for {form_label}: {e}")
                # Continue with other abilities even if one fails
                continue
        
        return abilities

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
            # Strategy 1: Extract from the COST pattern (most reliable based on debug)
            self._extract_name_from_cost_pattern,
            # Strategy 2: Extract from skill_header id attribute 
            self._extract_name_from_skill_header_id,
            # Strategy 3: Extract from bold text
            self._extract_name_from_bold_text,
            # Strategy 4: Extract from headings  
            self._extract_name_from_headings,
            # Strategy 5: Extract from spans (fallback)
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
    
    def _extract_name_from_cost_pattern(self, container: BeautifulSoup) -> str:
        """Extract ability name from the COST pattern (most reliable method)."""
        import re
        
        # Get the text content
        all_text = container.get_text()
        
        # Pattern discovered from debug: ability name before "COST:"
        pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*COST:'
        match = re.search(pattern, all_text, re.MULTILINE | re.IGNORECASE)
        
        if match:
            ability_name = match.group(1).strip()
            # Clean up the name: remove "Edit" prefix and newlines
            ability_name = re.sub(r'^Edit\s*', '', ability_name, flags=re.IGNORECASE)
            ability_name = re.sub(r'\n+', ' ', ability_name)
            ability_name = re.sub(r'\s+', ' ', ability_name).strip()
            
            # Filter out generic words
            if ability_name not in ['Edit', 'Active', 'Passive', 'Innate', 'Nidalee', 'Mana']:
                return ability_name
        
        return ""
    
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
        """Extract ability description from container with priority for Active descriptions and enhanced text cleaning."""
        try:
            # Get all ability-info-description elements
            desc_elements = container.select('.ability-info-description')
            
            if desc_elements:
                # Strategy 1: Prioritize "Active:" descriptions over "Passive:" ones
                active_descriptions = []
                passive_descriptions = []
                other_descriptions = []
                
                for desc in desc_elements:
                    # Apply enhanced text cleaning
                    text = self._apply_text_cleaning_rules(desc.get_text(separator=' '))
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
                text = self._apply_text_cleaning_rules(p.get_text(separator=' '))
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
        """Apply enhanced text cleaning rules to handle Unicode characters and formatting."""
        if not text:
            return ""
        
        # Step 1: Remove wiki UI elements first
        text = re.sub(r'^Edit\s+', '', text, flags=re.IGNORECASE)  # Remove "Edit " at start
        text = re.sub(r'\s+Edit\s+', ' ', text, flags=re.IGNORECASE)  # Remove " Edit " in middle
        text = re.sub(r'Edit\s*$', '', text, flags=re.IGNORECASE)  # Remove "Edit" at end
        
        # Step 2: Replace multiple spaces with single spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Step 3: Fix common wiki formatting issues and Unicode characters
        text = re.sub(r'[\u00a0]', ' ', text)  # Non-breaking spaces
        text = re.sub(r'[\u300c\u300d]', '', text)  # Remove corner brackets (〈 〉)
        text = re.sub(r'[\u2060\u200b\u200c\u200d]', '', text)  # Remove zero-width chars
        text = re.sub(r'[\u202f\u2009\u2008\u2007\u2006\u2005\u2004\u2003\u2002\u2001]', ' ', text)  # Various spaces
        
        # Step 4: Fix spacing around colons and periods
        text = re.sub(r'\s*:\s*', ': ', text)
        text = re.sub(r'\s*\.\s*', '. ', text)
        
        # Step 5: Fix Unicode dashes
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        
        # Step 6: Clean up extra whitespace and ensure proper sentence structure
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Step 7: Fix common wiki formatting artifacts
        text = re.sub(r'\s*\|\s*', ' | ', text)  # Fix pipe spacing
        text = re.sub(r'\s*\(\s*', ' (', text)  # Fix parenthesis spacing
        text = re.sub(r'\s*\)\s*', ') ', text)  # Fix closing parenthesis spacing
        
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
        Extracts enhanced details including targeting input, damage classification, and counters.
        
        Args:
            champion_name: Name of champion
            ability_slot: Ability slot (Q, W, E, R, Passive)
            
        Returns:
            Dictionary with detailed ability information including details tab content
        """
        driver = None
        try:
            # Get base ability data first
            all_abilities = await self.scrape_champion_abilities(champion_name)
            abilities = all_abilities.get('abilities', {})
            
            if ability_slot not in abilities:
                raise WikiScraperError(f"Ability {ability_slot} not found for {champion_name}")
            
            base_ability = abilities[ability_slot]
            
            # Use Selenium to get Details tab content
            driver = self._create_selenium_driver()
            url = self._build_champion_url(champion_name)
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Find the ability container based on slot
            ability_container_selector = self._get_ability_container_selector(ability_slot)
            ability_container = driver.find_element(By.CSS_SELECTOR, ability_container_selector)
            
            # Extract details tab content (Details tab comes after the ability container, not inside it)
            details_content = self._extract_details_tab_content(driver, ability_container)
            
            # Combine base ability with enhanced details
            enhanced_ability = base_ability.copy()
            if details_content:
                enhanced_ability.update(details_content)
            
            return {
                "ability": enhanced_ability,
                "data_source": "wiki_abilities_with_details_tab"
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting details tab for {champion_name} {ability_slot}: {e}")
            # Fallback to base ability data
            all_abilities = await self.scrape_champion_abilities(champion_name)
            abilities = all_abilities.get('abilities', {})
            
            if ability_slot in abilities:
                return {
                    "ability": abilities[ability_slot],
                    "data_source": "wiki_abilities_scrape_fallback"
                }
            else:
                raise WikiScraperError(f"Ability {ability_slot} not found for {champion_name}")
        finally:
            if driver:
                driver.quit()

    def _get_ability_container_selector(self, ability_slot: str) -> str:
        """Get the CSS selector for the ability container based on slot."""
        ability_slot_lower = ability_slot.lower()
        if ability_slot_lower == 'passive':
            return '.skill_innate'
        elif ability_slot_lower == 'q':
            return '.skill_q'
        elif ability_slot_lower == 'w':
            return '.skill_w'
        elif ability_slot_lower == 'e':
            return '.skill_e'
        elif ability_slot_lower == 'r':
            return '.skill_r'
        else:
            raise ValueError(f"Invalid ability slot: {ability_slot}")

    def _extract_details_tab_content(self, driver, ability_container) -> Dict[str, Any]:
        """
        Extract content from the Details tab that follows the ability container.
        Returns targeting input, damage classification, and counters.
        """
        details_data = {}
        
        try:
            # The Details tab comes AFTER the ability container in a separate tabber section
            # Use XPath to find the next tabbertab with data-title="Details " after this ability container
            details_container = driver.execute_script("""
                var abilityContainer = arguments[0];
                var nextElement = abilityContainer.nextElementSibling;
                
                // Look for the next Details tab within a few subsequent elements
                for (let i = 0; i < 5 && nextElement; i++) {
                    var detailsTab = nextElement.querySelector('div.tabbertab[data-title="Details "]');
                    if (detailsTab) {
                        return detailsTab;
                    }
                    nextElement = nextElement.nextElementSibling;
                }
                return null;
            """, ability_container)
            
            if not details_container:
                return details_data
            
            # Extract targeting input
            targeting_input = self._extract_targeting_input_js(driver, details_container)
            if targeting_input:
                details_data['targeting_input'] = targeting_input
            
            # Extract damage classification
            damage_classification = self._extract_damage_classification_js(driver, details_container)
            if damage_classification:
                details_data['damage_classification'] = damage_classification
            
            # Extract counters
            counters = self._extract_counters_js(driver, details_container)
            if counters:
                details_data['counters'] = counters
            
            # Extract additional notes/bullets if present
            additional_notes = self._extract_additional_notes_js(driver, details_container)
            if additional_notes:
                details_data['additional_notes'] = additional_notes
                
        except Exception as e:
            self.logger.warning(f"Could not extract details tab content: {e}")
            # Return empty dict if details tab extraction fails
            
        return details_data

    def _extract_targeting_input_js(self, driver, details_container) -> Optional[str]:
        """Extract targeting input information from details container using JavaScript."""
        try:
            targeting_input = driver.execute_script("""
                var container = arguments[0];
                if (!container) return null;
                
                var rows = container.querySelectorAll('.infobox-data-row');
                for (var i = 0; i < rows.length; i++) {
                    var label = rows[i].querySelector('.infobox-data-label');
                    if (label && label.textContent.toLowerCase().includes('targeting input')) {
                        var value = rows[i].querySelector('.infobox-data-value');
                        if (value) {
                            return value.textContent.trim();
                        }
                    }
                }
                return null;
            """, details_container)
            
            return targeting_input if targeting_input else None
                        
        except Exception as e:
            self.logger.debug(f"Could not extract targeting input: {e}")
            return None

    def _extract_damage_classification_js(self, driver, details_container) -> Optional[Dict[str, str]]:
        """Extract damage classification (type and sub-types) from details container using JavaScript."""
        try:
            classification = driver.execute_script("""
                var container = arguments[0];
                if (!container) return null;
                
                var result = {};
                var headers = container.querySelectorAll('.infobox-header');
                
                for (var i = 0; i < headers.length; i++) {
                    if (headers[i].textContent.toLowerCase().includes('damage classification')) {
                        var nextSection = headers[i].nextElementSibling;
                        if (nextSection && nextSection.classList.contains('infobox-section-cell')) {
                            var rows = nextSection.querySelectorAll('.infobox-data-row');
                            for (var j = 0; j < rows.length; j++) {
                                var label = rows[j].querySelector('.infobox-data-label');
                                var value = rows[j].querySelector('.infobox-data-value');
                                if (label && value) {
                                    var labelText = label.textContent.toLowerCase().trim();
                                    var valueText = value.textContent.trim();
                                    
                                    if (labelText.includes('type') && !labelText.includes('sub')) {
                                        result.type = valueText;
                                    } else if (labelText.includes('sub-type') || labelText.includes('subtype')) {
                                        result.sub_type = valueText;
                                    }
                                }
                            }
                        }
                        break;
                    }
                }
                
                return Object.keys(result).length > 0 ? result : null;
            """, details_container)
            
            return classification if classification else None
                        
        except Exception as e:
            self.logger.debug(f"Could not extract damage classification: {e}")
            return None

    def _extract_counters_js(self, driver, details_container) -> Optional[Dict[str, str]]:
        """Extract counters information from details container using JavaScript."""
        try:
            counters = driver.execute_script("""
                var container = arguments[0];
                if (!container) return null;
                
                var result = {};
                var headers = container.querySelectorAll('.infobox-header');
                
                for (var i = 0; i < headers.length; i++) {
                    if (headers[i].textContent.toLowerCase().includes('counters')) {
                        var nextSection = headers[i].nextElementSibling;
                        if (nextSection && nextSection.classList.contains('infobox-section-cell')) {
                            var rows = nextSection.querySelectorAll('.infobox-data-row');
                            for (var j = 0; j < rows.length; j++) {
                                var label = rows[j].querySelector('.infobox-data-label');
                                var value = rows[j].querySelector('.infobox-data-value');
                                if (label && value) {
                                    var labelText = label.textContent.toLowerCase().trim();
                                    var valueText = value.textContent.trim();
                                    result[labelText] = valueText;
                                }
                            }
                        }
                        break;
                    }
                }
                
                return Object.keys(result).length > 0 ? result : null;
            """, details_container)
            
            return counters if counters else None
                        
        except Exception as e:
            self.logger.debug(f"Could not extract counters: {e}")
            return None

    def _extract_additional_notes_js(self, driver, details_container) -> Optional[List[str]]:
        """Extract additional notes/bullet points from details container using JavaScript."""
        try:
            notes = driver.execute_script("""
                var container = arguments[0];
                if (!container) return null;
                
                var result = [];
                var lists = container.querySelectorAll('ul');
                
                for (var i = 0; i < lists.length; i++) {
                    var listItems = lists[i].querySelectorAll('li');
                    for (var j = 0; j < listItems.length; j++) {
                        var text = listItems[j].textContent.trim();
                        if (text && text.length > 10) {
                            result.push(text);
                        }
                    }
                }
                
                return result.length > 0 ? result : null;
            """, details_container)
            
            return notes if notes else None
                        
        except Exception as e:
            self.logger.debug(f"Could not extract additional notes: {e}")
            return None

    def _extract_additional_notes(self, details_container) -> Optional[List[str]]:
        """Extract additional notes/bullet points from details container."""
        notes = []
        
        try:
            # Look for bullet lists or paragraphs with additional notes
            note_elements = details_container.find_elements(By.CSS_SELECTOR, 'ul li, p')
            
            for element in note_elements:
                text = element.text.strip()
                if text and len(text) > 10:  # Filter out very short text
                    notes.append(text)
        except Exception as e:
            self.logger.debug(f"Could not extract additional notes: {e}")
            
        return notes if notes else None