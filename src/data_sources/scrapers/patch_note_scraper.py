"""
Champion Patch Note Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting champion patch history
from the League of Legends Wiki using CSS selectors for patch data extraction.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError

# CSS selectors for patch history scraping - updated based on actual HTML structure
PATCH_SELECTORS = {
    'patch_version': 'dt',
    'individual_change': 'li'
}


class PatchNoteScraper(BaseScraper):
    """
    Scraper for extracting champion patch history from League of Legends Wiki.
    
    This scraper navigates to the champion's patch history page and extracts
    patch versions and their associated changes using CSS selectors.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_all_patch_notes(self, champion_name: str) -> Dict[str, Any]:
        """
        Scrape all patch history for a champion.
        
        Args:
            champion_name: Name of the champion
            
        Returns:
            Dictionary containing all patch notes for the champion
            
        Raises:
            WikiScraperError: If scraping fails
        """
        try:
            normalized_name = self.normalize_champion_name(champion_name)
            # Build URL for patch history page using urljoin
            patch_history_url = urljoin(self.BASE_URL, f"{normalized_name}/Patch_history")
            
            self.logger.info(f"Scraping all patch notes for {champion_name} from {patch_history_url}")
            
            # Use httpx to fetch patch history page
            await self._ensure_client()
            response = await self._make_request(patch_history_url)
            soup = BeautifulSoup(response.text, "lxml")
            
            # Extract all patch data from the main content area
            # The patch data is directly in the content, not in a specific container
            patches = self._extract_patch_data(soup)
            
            if patches:
                return {
                    'champion': champion_name,
                    'patches': patches,
                    'total_patches': len(patches),
                    'message': f'Retrieved {len(patches)} patch notes for {champion_name}'
                }
            else:
                return {
                    'champion': champion_name,
                    'patches': [],
                    'total_patches': 0,
                    'message': f'No patch history found for {champion_name}'
                }
            
        except Exception as e:
            self.logger.error(f"Error scraping patch notes for {champion_name}: {str(e)}")
            raise WikiScraperError(f"Failed to scrape patch notes for {champion_name}: {str(e)}")

    async def scrape_specific_patch_note(self, champion_name: str, patch_version: str) -> Dict[str, Any]:
        """
        Scrape patch notes for a specific patch version.
        
        Args:
            champion_name: Name of the champion
            patch_version: Specific patch version (e.g., "4.12", "14.21")
            
        Returns:
            Dictionary containing specific patch note data
            
        Raises:
            WikiScraperError: If scraping fails
        """
        try:
            # First get all patch notes
            all_patches = await self.scrape_all_patch_notes(champion_name)
            
            # Normalize patch version format (handle both "4.12" and "V4.12" formats)
            normalized_patch = self._normalize_patch_version(patch_version)
            
            # Find the specific patch
            specific_patch = None
            for patch in all_patches['patches']:
                if self._patch_versions_match(patch['version'], normalized_patch):
                    specific_patch = patch
                    break
            
            if specific_patch:
                return {
                    'champion': champion_name,
                    'patch_version': patch_version,
                    'patches': [specific_patch],
                    'total_patches': 1,
                    'message': f'Retrieved patch {patch_version} for {champion_name}'
                }
            else:
                return {
                    'champion': champion_name,
                    'patch_version': patch_version,
                    'patches': [],
                    'total_patches': 0,
                    'message': f'No changes found for {champion_name} in patch {patch_version}'
                }
                
        except Exception as e:
            self.logger.error(f"Error scraping patch {patch_version} for {champion_name}: {str(e)}")
            raise WikiScraperError(f"Failed to scrape patch {patch_version} for {champion_name}: {str(e)}")

    def _extract_patch_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract patch data from the page content.
        
        Args:
            soup: BeautifulSoup object of the entire page
            
        Returns:
            List of patch dictionaries
        """
        patches = []
        
        # Find all dt elements that contain patch version links
        # Structure: <dl><dt><a href="/en-us/V14.21" title="V14.21">V14.21</a></dt></dl>
        dt_elements = soup.select('dt')
        
        for dt_element in dt_elements:
            # Look for a link inside the dt element
            patch_link = dt_element.find('a')
            if not patch_link:
                continue
                
            # Extract patch version from the link text
            version_text = patch_link.get_text(strip=True)
            
            # Skip if not a valid patch version
            if not self._is_valid_patch_version(version_text):
                continue
            
            # Find the parent dl element and then look for the next ul sibling
            dl_parent = dt_element.find_parent('dl')
            if not dl_parent:
                continue
                
            # Find all ul elements after the dl until we hit the next patch
            current_element = dl_parent
            all_changes = []
            
            # Look for all ul siblings after the dl element
            while current_element:
                current_element = current_element.find_next_sibling()
                if current_element and current_element.name == 'ul':
                    # Extract changes from this ul
                    li_elements = current_element.select('li')
                    for li in li_elements:
                        change_text = li.get_text(strip=True)
                        if change_text:
                            all_changes.append(change_text)
                elif current_element and current_element.name in ['dl', 'h2', 'h3']:
                    # Stop if we hit another patch or section header
                    break
            
            if all_changes:  # Only add if there are actual changes
                patches.append({
                    'version': version_text,
                    'changes': all_changes,
                    'change_count': len(all_changes)
                })
        
        return patches

    def _is_valid_patch_version(self, version_text: str) -> bool:
        """
        Check if the text represents a valid patch version.
        
        Args:
            version_text: Text to check
            
        Returns:
            True if valid patch version, False otherwise
        """
        # Match patterns like "V14.21", "V4.12", "V13.24b", etc.
        pattern = r'^V\d+\.\d+[a-z]?$'
        return bool(re.match(pattern, version_text))

    def _normalize_patch_version(self, patch_version: str) -> str:
        """
        Normalize patch version format.
        
        Args:
            patch_version: Raw patch version
            
        Returns:
            Normalized patch version
        """
        # Remove 'V' prefix if present and add it back
        version = patch_version.strip().upper()
        if version.startswith('V'):
            return version
        else:
            return f'V{version}'

    def _patch_versions_match(self, wiki_version: str, requested_version: str) -> bool:
        """
        Check if two patch versions match.
        
        Args:
            wiki_version: Version from wiki
            requested_version: Version requested by user
            
        Returns:
            True if versions match, False otherwise
        """
        # Normalize both versions
        wiki_norm = self._normalize_patch_version(wiki_version)
        requested_norm = self._normalize_patch_version(requested_version)
        
        return wiki_norm == requested_norm

 