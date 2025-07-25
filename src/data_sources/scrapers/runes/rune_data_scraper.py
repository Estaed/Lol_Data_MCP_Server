"""
Rune Data Scraper for League of Legends Wiki

This module provides a specialized scraper for extracting rune data from
the League of Legends Wiki, including sidebar info, notes, and strategy sections.

Following the established patterns used for champions and items with perfect
name assumptions and clean output structure.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

try:
    from src.data_sources.scrapers.base_scraper import BaseScraper, WikiScraperError
    from src.models.exceptions import RuneNotFoundError
except ImportError:
    from ..base_scraper import BaseScraper, WikiScraperError
    from ....models.exceptions import RuneNotFoundError


class RuneDataScraper(BaseScraper):
    """
    Scraper for extracting rune data from League of Legends Wiki.
    
    This scraper navigates to rune pages and extracts:
    - Sidebar infobox (Path, Slot, Description, Range)
    - Notes section content
    - Strategy section content
    
    Following the established architecture patterns for consistency.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def scrape_rune_data(self, rune_name: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Scrape complete rune data including sidebar, notes, and strategy.
        
        Args:
            rune_name: Name of the rune (e.g., "Summon Aery", "Arcane Comet")
            sections: Optional list of sections to extract (sidebar, notes, strategy)
            
        Returns:
            Dictionary containing rune data
            
        Raises:
            WikiScraperError: If scraping fails
            RuneNotFoundError: If rune is not found
        """
        try:
            normalized_name = self.normalize_rune_name(rune_name)
            rune_url = urljoin(self.BASE_URL, normalized_name)
            
            self.logger.info(f"Scraping rune data for {rune_name} from {rune_url}")
            
            # Use httpx to fetch rune page
            await self._ensure_client()
            response = await self._make_request(rune_url)
            
            # Check if page exists (404 handling)
            if response.status_code == 404:
                raise RuneNotFoundError(rune_name)
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # Validate this is actually a rune page
            if not self._validate_rune_page(soup, rune_name):
                raise RuneNotFoundError(rune_name)
            
            # Initialize result structure
            result = {
                'rune': rune_name,
                'data_source': 'wiki_rune_scrape',
                'sections': {}
            }
            
            # Determine which sections to extract
            sections_to_extract = sections if sections is not None else ['sidebar', 'notes', 'strategy']
            
            # Extract each requested section
            if 'sidebar' in sections_to_extract:
                result['sections']['sidebar'] = self._extract_sidebar_data(soup)
                
            if 'notes' in sections_to_extract:
                result['sections']['notes'] = self._extract_notes_section(soup)
                
            if 'strategy' in sections_to_extract:
                result['sections']['strategy'] = self._extract_strategy_section(soup)
            
            self.logger.info(f"Successfully scraped {len(result['sections'])} sections for {rune_name}")
            return result
            
        except RuneNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Error scraping rune data for {rune_name}: {str(e)}")
            raise WikiScraperError(f"Failed to scrape rune data for {rune_name}: {str(e)}")

    def _validate_rune_page(self, soup: BeautifulSoup, rune_name: str) -> bool:
        """
        Validate that this is actually a rune page.
        
        Args:
            soup: BeautifulSoup object of the page
            rune_name: Expected rune name
            
        Returns:
            True if valid rune page, False otherwise
        """
        # Strategy 1: Look for rune infobox
        rune_infobox = soup.find('div', class_='infobox theme-rune')
        if rune_infobox:
            return True
            
        # Strategy 2: Check page title contains rune name
        title_element = soup.find('title')
        if title_element and rune_name.lower() in title_element.get_text().lower():
            return True
            
        # Strategy 3: Look for rune-specific metadata
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description:
            content = meta_description.get('content', '').lower()
            if 'rune' in content and rune_name.lower() in content:
                return True
        
        self.logger.warning(f"Page validation failed for {rune_name}")
        return False

    def _extract_sidebar_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract sidebar infobox data (Path, Slot, Description, Range).
        
        Args:
            soup: BeautifulSoup object of the entire page
            
        Returns:
            Dictionary containing sidebar data
        """
        sidebar_data = {
            'path': None,
            'slot': None, 
            'description': None,
            'range': None
        }
        
        try:
            # Find the rune infobox
            infobox = soup.find('div', class_='infobox theme-rune')
            if not infobox:
                self.logger.warning("No rune infobox found")
                return sidebar_data
            
            # Extract Path information
            path_row = infobox.find('div', class_='infobox-data-label', string='Path')
            if path_row:
                path_value = path_row.find_next_sibling('div', class_='infobox-data-value')
                if path_value:
                    # Extract path name and clean it
                    path_link = path_value.find('a')
                    if path_link:
                        sidebar_data['path'] = path_link.get_text(strip=True)
                    else:
                        sidebar_data['path'] = path_value.get_text(strip=True)
            
            # Extract Slot information  
            slot_row = infobox.find('div', class_='infobox-data-label', string='Slot')
            if slot_row:
                slot_value = slot_row.find_next_sibling('div', class_='infobox-data-value')
                if slot_value:
                    sidebar_data['slot'] = slot_value.get_text(strip=True)
            
            # Extract Description from infobox
            description_header = infobox.find('div', class_='infobox-header', string='Description')
            if description_header:
                # Find the next section after the header
                description_section = description_header.find_next_sibling('div', class_='infobox-section')
                if description_section:
                    description_value = description_section.find('div', class_='infobox-data-value')
                    if description_value:
                        sidebar_data['description'] = self._clean_description_text(description_value)
            
            # Extract Range information
            range_row = infobox.find('div', class_='infobox-data-label', string='Range')
            if range_row:
                range_value = range_row.find_next_sibling('div', class_='infobox-data-value')
                if range_value:
                    sidebar_data['range'] = range_value.get_text(strip=True)
            
            self.logger.debug(f"Extracted sidebar data: {sidebar_data}")
            return sidebar_data
            
        except Exception as e:
            self.logger.error(f"Error extracting sidebar data: {str(e)}")
            return sidebar_data

    def _extract_generic_section(self, soup: BeautifulSoup, section_name: str) -> Dict[str, Any]:
        """
        Extract content for any section like 'Notes' or 'Strategy' (consolidated from duplicate methods).
        
        Args:
            soup: BeautifulSoup object of the entire page
            section_name: Name of the section to extract ('Notes', 'Strategy', etc.)
            
        Returns:
            Dictionary containing section data
        """
        section_data = {
            'content': [],
            'found': False
        }
        
        try:
            # Find section heading
            heading = self._find_section_heading(soup, [section_name])
            if not heading:
                self.logger.debug(f"No {section_name} section found")
                return section_data
            
            # Extract content after the heading
            content = self._extract_section_content(heading)
            if content:
                section_data['content'] = self._process_section_content(content)
                section_data['found'] = True
                
            self.logger.debug(f"Extracted {section_name.lower()} section: {len(section_data['content'])} items")
            return section_data
            
        except Exception as e:
            self.logger.error(f"Error extracting {section_name.lower()} section: {str(e)}")
            return section_data

    def _extract_notes_section(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract Notes section content (wrapper for generic method)."""
        return self._extract_generic_section(soup, 'Notes')

    def _extract_strategy_section(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract Strategy section content (wrapper for generic method)."""
        return self._extract_generic_section(soup, 'Strategy')

    def _find_section_heading(self, soup: BeautifulSoup, section_names: List[str]) -> Optional[Tag]:
        """
        Find section heading dynamically without hardcoding.
        
        Args:
            soup: BeautifulSoup object
            section_names: List of possible section names to look for
            
        Returns:
            Heading element or None if not found
        """
        for section_name in section_names:
            # Strategy 1: Look for span with id matching section name
            span_element = soup.find('span', id=section_name)
            if span_element:
                heading = span_element.find_parent(['h1', 'h2', 'h3', 'h4'])
                if heading:
                    self.logger.debug(f"Found {section_name} section via span id")
                    return heading
            
            # Strategy 2: Look for headings with text containing section name
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for heading in headings:
                heading_text = heading.get_text(strip=True).lower()
                if section_name.lower() in heading_text:
                    self.logger.debug(f"Found {section_name} section via heading text")
                    return heading
        
        return None

    def _extract_section_content(self, heading_element: Tag) -> Optional[Tag]:
        """
        Extract content after a section heading.
        
        Args:
            heading_element: The section heading element
            
        Returns:
            Content container or None
        """
        # Create a wrapper div to hold all content until the next heading
        content_elements = []
        current = heading_element
        
        while current:
            current = current.find_next_sibling()
            if current:
                # Stop if we hit another section heading
                if current.name in ['h1', 'h2', 'h3', 'h4']:
                    break
                    
                # Collect content elements
                if current.name in ['div', 'p', 'ul', 'ol', 'dl'] and current.get_text(strip=True):
                    content_elements.append(current)
        
        # Return the first element if we found any, or None
        return content_elements[0] if content_elements else None

    def _process_section_content(self, content_element: Tag) -> List[str]:
        """
        Process section content into clean text items.
        
        Args:
            content_element: Content container element
            
        Returns:
            List of cleaned text items
        """
        content_items = []
        
        # Handle different content structures
        if content_element.name == 'ul' or content_element.name == 'ol':
            # Extract list items
            list_items = content_element.find_all('li', recursive=False)
            for item in list_items:
                text = self._clean_text_content(item)
                if text:
                    content_items.append(text)
        else:
            # Handle paragraph or div content
            # Look for multiple paragraphs or break into sentences
            paragraphs = content_element.find_all('p')
            if paragraphs:
                for p in paragraphs:
                    text = self._clean_text_content(p)
                    if text:
                        content_items.append(text)
            else:
                # Single block of text
                text = self._clean_text_content(content_element)
                if text:
                    content_items.append(text)
        
        return content_items

    def _clean_text_content(self, element: Tag) -> str:
        """
        Clean text content from HTML element.
        
        Args:
            element: HTML element
            
        Returns:
            Cleaned text string
        """
        # Get text and clean it
        text = element.get_text(separator=' ', strip=True)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove wiki-specific artifacts
        text = re.sub(r'\[edit\]', '', text)
        text = re.sub(r'\[edit source\]', '', text)
        
        return text.strip()

    def _clean_description_text(self, element: Tag) -> str:
        """
        Clean description text from rune infobox.
        
        Args:
            element: Description element
            
        Returns:
            Cleaned description text
        """
        # Remove HTML tags but preserve text structure
        text = element.get_text(separator=' ', strip=True)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove wiki markup artifacts
        text = re.sub(r'\(\+ \d+% [A-Z]+\)', lambda m: m.group(0), text)  # Preserve scaling
        
        return text.strip()

    def normalize_rune_name(self, rune_name: str) -> str:
        """
        Normalize rune name for URL generation (wrapper for base class method).
        
        Args:
            rune_name: Raw rune name (e.g., "Summon Aery")
            
        Returns:
            Normalized rune name for URL
        """
        return self.normalize_wiki_page_name(rune_name)