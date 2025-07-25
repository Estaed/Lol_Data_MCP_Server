"""
Rune Patch Note Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting rune patch history
from the League of Legends Wiki using CSS selectors for patch data extraction.

Following the item_patch_scraper.py pattern for consistency.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError
    from src.models.exceptions import RuneNotFoundError
except ImportError:
    from ..base_scraper import BaseScraper, WikiScraperError
    from ....models.exceptions import RuneNotFoundError

# CSS selectors for patch history scraping - based on runes HTML structure
PATCH_SELECTORS = {
    'patch_version': 'dt',
    'individual_change': 'li'
}


class RunePatchScraper(BaseScraper):
    """
    Scraper for extracting rune patch history from League of Legends Wiki.
    
    This scraper navigates to the rune's page and extracts patch versions
    and their associated changes using CSS selectors from the patch history section.
    
    Following the item patch scraper architecture for consistency.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_all_patch_notes(self, rune_name: str) -> Dict[str, Any]:
        """
        Scrape all patch history for a rune.
        
        Args:
            rune_name: Name of the rune (e.g., "Summon Aery")
            
        Returns:
            Dictionary containing all patch notes for the rune
            
        Raises:
            WikiScraperError: If scraping fails
            RuneNotFoundError: If rune is not found
        """
        try:
            normalized_name = self.normalize_rune_name(rune_name)
            # Build URL for rune page - runes store patch history on main page
            rune_url = urljoin(self.BASE_URL, normalized_name)
            
            self.logger.info(f"Scraping all patch notes for {rune_name} from {rune_url}")
            
            # Use httpx to fetch rune page
            await self._ensure_client()
            response = await self._make_request(rune_url)
            
            # Check if page exists
            if response.status_code == 404:
                raise RuneNotFoundError(rune_name)
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find patch history section dynamically
            patch_section = self._find_patch_history_section(soup)
            if not patch_section:
                return {
                    'rune': rune_name,
                    'patches': [],
                    'total_patches': 0,
                    'message': f'No patch history section found for {rune_name}'
                }
            
            # Extract all patch data from the patch history section
            patches = self._extract_patch_data(patch_section)
            
            if patches:
                return {
                    'rune': rune_name,
                    'patches': patches,
                    'total_patches': len(patches),
                    'message': f'Retrieved {len(patches)} patch notes for {rune_name}'
                }
            else:
                return {
                    'rune': rune_name,
                    'patches': [],
                    'total_patches': 0,
                    'message': f'No patch history found for {rune_name}'
                }
            
        except RuneNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Error scraping patch notes for {rune_name}: {str(e)}")
            raise WikiScraperError(f"Failed to scrape patch notes for {rune_name}: {str(e)}")

    async def scrape_specific_patch_note(self, rune_name: str, patch_version: str) -> Dict[str, Any]:
        """
        Scrape patch notes for a specific patch version.
        
        Args:
            rune_name: Name of the rune
            patch_version: Specific patch version (e.g., "14.19", "V14.19")
            
        Returns:
            Dictionary containing specific patch note data
            
        Raises:
            WikiScraperError: If scraping fails
            RuneNotFoundError: If rune is not found
        """
        try:
            # First get all patch notes
            all_patches = await self.scrape_all_patch_notes(rune_name)
            
            # Normalize patch version format (handle both "14.19" and "V14.19" formats)
            normalized_patch = self._normalize_patch_version(patch_version)
            
            # Find the specific patch
            specific_patch = None
            for patch in all_patches['patches']:
                if self._patch_versions_match(patch['version'], normalized_patch):
                    specific_patch = patch
                    break
            
            if specific_patch:
                return {
                    'rune': rune_name,
                    'patch_version': patch_version,
                    'patches': [specific_patch],
                    'total_patches': 1,
                    'message': f'Retrieved patch {patch_version} for {rune_name}'
                }
            else:
                return {
                    'rune': rune_name,
                    'patch_version': patch_version,
                    'patches': [],
                    'total_patches': 0,
                    'message': f'No changes found for {rune_name} in patch {patch_version}'
                }
                
        except RuneNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Error scraping patch {patch_version} for {rune_name}: {str(e)}")
            raise WikiScraperError(f"Failed to scrape patch {patch_version} for {rune_name}: {str(e)}")

    def _find_patch_history_section(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Dynamically find the patch history section without hardcoding.
        
        Args:
            soup: BeautifulSoup object of the entire page
            
        Returns:
            Section containing patch history or None if not found
        """
        # Strategy 1: Look for heading with "Patch History" text
        heading_patterns = ["patch history", "patch_history", "patches"]
        
        for pattern in heading_patterns:
            # Check h2 tags with id or text containing pattern
            h2_elements = soup.find_all('h2')
            for h2 in h2_elements:
                # Check span with id
                span = h2.find('span', id=re.compile(pattern, re.IGNORECASE))
                if span:
                    self.logger.debug(f"Found patch history section via h2 span id: {span.get('id')}")
                    # Return the parent container or next sibling with content
                    return self._get_section_content_after_heading(h2)
                
                # Check text content
                h2_text = h2.get_text(strip=True).lower()
                if pattern in h2_text:
                    self.logger.debug(f"Found patch history section via h2 text: {h2_text}")
                    return self._get_section_content_after_heading(h2)
        
        # Strategy 2: Look for divs that contain patch version patterns
        # Look for containers with multiple V*.* patterns
        potential_containers = soup.find_all(['div', 'section', 'article'])
        for container in potential_containers:
            content_text = container.get_text()
            # Count version patterns like V14.19, V13.10, etc.
            version_matches = re.findall(r'V\d+\.\d+', content_text)
            if len(version_matches) >= 2:  # At least 2 versions = likely patch history
                self.logger.debug(f"Found patch history section via version patterns: {len(version_matches)} versions")
                return container
        
        self.logger.warning("No patch history section found using any strategy")
        return None

    def _get_section_content_after_heading(self, heading_element) -> Optional[BeautifulSoup]:
        """
        Get the content section after a heading element.
        
        Args:
            heading_element: The heading element (h2, h3, etc.)
            
        Returns:
            Content section or None
        """
        # Look for the next sibling that contains actual content
        current = heading_element
        while current:
            current = current.find_next_sibling()
            if current and current.name in ['div', 'section', 'dl', 'ul']:
                # Check if this contains version patterns
                content_text = current.get_text()
                if re.search(r'V\d+\.\d+', content_text):
                    return current
        
        # Fallback: return the parent container
        return heading_element.find_parent(['div', 'section', 'article'])

    def _extract_patch_data(self, section: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract patch data from the patch history section with enhanced text processing.
        
        Args:
            section: BeautifulSoup object of the patch history section
            
        Returns:
            List of patch dictionaries
        """
        patches = []
        
        # Find all dt elements that contain patch version links
        # Structure: <dl><dt><a href="/en-us/V14.19" title="V14.19">V14.19</a></dt></dl>
        dt_elements = section.select('dt')
        
        for dt_element in dt_elements:
            # Look for a link inside the dt element
            patch_link = dt_element.find('a')
            if not patch_link:
                # Fallback: check if dt contains version text directly
                dt_text = dt_element.get_text(strip=True)
                if self._is_valid_patch_version(dt_text):
                    version_text = dt_text
                else:
                    continue
            else:
                # Extract patch version from the link text
                version_text = patch_link.get_text(strip=True)
            
            # Skip if not a valid patch version
            if not self._is_valid_patch_version(version_text):
                continue
            
            # Find the parent dl element and then look for the next ul sibling
            dl_parent = dt_element.find_parent('dl')
            if not dl_parent:
                # Fallback: use dt_element itself as reference
                current_element = dt_element
            else:
                current_element = dl_parent
            
            # Find all ul elements after the dl until we hit the next patch
            raw_changes = []
            
            # Look for all ul siblings after the dl element
            while current_element:
                current_element = current_element.find_next_sibling()
                if current_element and current_element.name == 'ul':
                    # Extract changes from this ul - HANDLE NESTED STRUCTURE
                    # Only process direct children <li> elements, not nested ones
                    direct_li_elements = current_element.find_all('li', recursive=False)
                    for li in direct_li_elements:
                        # Get text from the main li element
                        change_text = li.get_text(strip=True)
                        if change_text:
                            raw_changes.append(change_text)
                elif current_element and current_element.name in ['dl', 'h2', 'h3']:
                    # Stop if we hit another patch or section header
                    break
            
            # Simple deduplication only
            cleaned_changes = list(dict.fromkeys(raw_changes))
            
            if cleaned_changes:  # Only add if there are actual changes
                patches.append({
                    'version': version_text,
                    'changes': cleaned_changes,
                    'change_count': len(cleaned_changes)
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

    def normalize_rune_name(self, rune_name: str) -> str:
        """
        Normalize rune name for URL generation (wrapper for base class method).
        
        Args:
            rune_name: Raw rune name
            
        Returns:
            Normalized rune name for URL
        """
        return self.normalize_wiki_page_name(rune_name)