"""
League of Legends Wiki Scraper

A comprehensive web scraper for extracting champion data from the League of Legends Wiki.
Implements rate limiting, error handling, and proper HTTP client configuration.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup, Tag


class WikiScraperError(Exception):
    """Base exception for wiki scraper errors"""
    pass


class ChampionNotFoundError(WikiScraperError):
    """Raised when a champion page cannot be found"""
    pass


class WikiScraper:
    """
    League of Legends Wiki scraper with rate limiting and error handling.
    
    Features:
    - Rate limiting (1 request per second)
    - Proper HTTP headers and user agent
    - Connection timeout and retry logic
    - Basic logging for scraper operations
    - LoL Wiki URL handling
    """
    
    BASE_URL = "https://wiki.leagueoflegends.com/en-us"
    CHAMPION_URL_TEMPLATE = "/{champion_name}"
    
    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize the WikiScraper.
        
        Args:
            rate_limit_delay: Delay between requests in seconds (default: 1.0)
            timeout: HTTP request timeout in seconds (default: 30.0)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 2.0)
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0.0
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # HTTP client configuration
        self.headers = {
            "User-Agent": (
                "LoL-Data-MCP-Server/1.0 "
                "(https://github.com/user/lol-data-mcp-server) "
                "Educational Research Bot"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # HTTP client (will be created when needed)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True
            )
            self.logger.info("HTTP client initialized")
    
    async def close(self) -> None:
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self.logger.info("HTTP client closed")
    
    async def _rate_limit(self) -> None:
        """Implement rate limiting to respect server resources"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _build_champion_url(self, champion_name: str) -> str:
        """
        Build a properly formatted champion URL for the LoL Wiki.
        
        Args:
            champion_name: Name of the champion (e.g., "Taric", "Kai'Sa")
            
        Returns:
            Full URL to the champion's wiki page
        """
        # Handle special characters and formatting
        formatted_name = champion_name.replace("'", "'").replace(" ", "_")
        champion_path = self.CHAMPION_URL_TEMPLATE.format(champion_name=quote(formatted_name))
        url = urljoin(self.BASE_URL, champion_path)
        
        self.logger.debug(f"Built champion URL: {url}")
        return url
    
    async def _make_request(self, url: str) -> httpx.Response:
        """
        Make an HTTP request with retry logic and rate limiting.
        
        Args:
            url: URL to request
            
        Returns:
            HTTP response object
            
        Raises:
            WikiScraperError: If request fails after all retries
        """
        await self._ensure_client()
        await self._rate_limit()
        
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"Making request to {url} (attempt {attempt + 1})")
                if self._client is None:
                    raise WikiScraperError("HTTP client is not initialized")
                response = await self._client.get(url)
                
                                 # Check for success status codes
                if response is not None and response.status_code == 200:
                    self.logger.info(f"Successfully fetched {url}")
                    return response
                elif response is not None and response.status_code == 404:
                    raise ChampionNotFoundError(f"Champion page not found: {url}")
                elif response is not None:
                    response.raise_for_status()
                    
            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.max_retries:
                    retry_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {retry_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")
        
        raise WikiScraperError(f"Failed to fetch {url} after {self.max_retries + 1} attempts") from last_exception
    
    async def fetch_champion_page(self, champion_name: str) -> BeautifulSoup:
        """
        Fetch and parse a champion's wiki page.
        
        Args:
            champion_name: Name of the champion (e.g., "Taric")
            
        Returns:
            BeautifulSoup object containing the parsed HTML
            
        Raises:
            ChampionNotFoundError: If champion page doesn't exist
            WikiScraperError: If page cannot be fetched
        """
        url = self._build_champion_url(champion_name)
        
        try:
            response = await self._make_request(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Basic validation that we got a champion page
            title = soup.find('title')
            if title is not None:
                title_text = title.get_text()
                if 'League of Legends Wiki' not in title_text:
                    self.logger.warning(f"Unusual page title: {title_text}")
            
            self.logger.info(f"Successfully parsed champion page for {champion_name}")
            return soup
            
        except Exception as e:
            self.logger.error(f"Failed to fetch champion page for {champion_name}: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """
        Test connection to the LoL Wiki.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test connection using the base URL
            response = await self._make_request(self.BASE_URL)
            self.logger.info("Wiki connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Wiki connection test failed: {e}")
            return False

    def find_champion_data_sections(self, soup: BeautifulSoup) -> Dict[str, Optional[Tag]]:
        """
        Find and identify different data sections on a champion page.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary mapping section names to BeautifulSoup elements:
            - 'stats': Champion statistics section (infobox)
            - 'abilities': Abilities section 
            - 'overview': General champion overview
            None values indicate missing sections
        """
        self.logger.info("Finding champion data sections")
        
        sections = {
            'stats': self._find_stats_section(soup),
            'abilities': self._find_abilities_section(soup),
            'overview': self._find_overview_section(soup)
        }
        
        # Log what was found
        found_sections = [name for name, section in sections.items() if section is not None]
        missing_sections = [name for name, section in sections.items() if section is None]
        
        self.logger.info(f"Found sections: {found_sections}")
        if missing_sections:
            self.logger.warning(f"Missing sections: {missing_sections}")
            
        return sections
    
    def _find_stats_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the champion stats infobox section.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing stats, or None if not found
        """
        self.logger.debug("Looking for stats section")
        
        # Primary approach: Look for infobox with champion stats class
        def has_stats_classes(class_list):
            if not class_list:
                return False
            return 'infobox' in class_list and 'type-champion-stats' in class_list
        
        stats_infobox = soup.find('div', class_=has_stats_classes)
        
        if stats_infobox and isinstance(stats_infobox, Tag):
            self.logger.debug("Found stats section via type-champion-stats infobox")
            return stats_infobox
        
        # Fallback 1: Look for any infobox containing stat-like content
        infoboxes = soup.find_all('div', class_='infobox')
        for infobox in infoboxes:
            if isinstance(infobox, Tag):
                text = infobox.get_text().lower()
                # Check for common stat abbreviations
                if any(stat in text for stat in ['hp', 'mp', 'ar', 'ad', 'mr', 'attack damage']):
                    self.logger.debug("Found stats section via infobox content analysis")
                    return infobox
        
        # Fallback 2: Look for tables containing stats
        tables = soup.find_all('table')
        for table in tables:
            if isinstance(table, Tag):
                text = table.get_text().lower()
                if 'base statistics' in text or 'champion stats' in text:
                    self.logger.debug("Found stats section via table content")
                    return table
        
        self.logger.warning("Could not find stats section")
        return None
    
    def _find_abilities_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the abilities section on the champion page.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing abilities, or None if not found
        """
        self.logger.debug("Looking for abilities section")
        
        # Primary approach: Look for "Abilities" heading and get following content
        def contains_ability(text):
            if not text:
                return False
            return 'abilit' in text.lower()
        
        abilities_span = soup.find('span', class_='mw-headline', string=contains_ability)
        
        if abilities_span and isinstance(abilities_span, Tag):
            # Find the parent heading element
            heading = abilities_span.find_parent(['h1', 'h2', 'h3', 'h4'])
            if heading and isinstance(heading, Tag):
                # Get the section after this heading until the next heading
                section_content = []
                current = heading.next_sibling
                
                while current:
                    if isinstance(current, Tag) and current.name in ['h1', 'h2', 'h3', 'h4']:
                        # Stop at next heading of same or higher level
                        break
                    if isinstance(current, Tag):
                        section_content.append(current)
                    current = current.next_sibling
                
                if section_content:
                    self.logger.debug("Found abilities section via mw-headline")
                    # Create a wrapper div containing all abilities content
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'abilities-section'
                    for element in section_content:
                        wrapper.append(element.extract())
                    return wrapper
        
        # Fallback 1: Look for any heading containing "ability"
        ability_headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        
        for header in ability_headers:
            if isinstance(header, Tag) and header.string and 'abilit' in header.string.lower():
                # Get content after this header
                content = []
                current = header.next_sibling
                while current and not (isinstance(current, Tag) and current.name in ['h1', 'h2', 'h3']):
                    if isinstance(current, Tag):
                        content.append(current)
                    current = current.next_sibling
                
                if content:
                    self.logger.debug("Found abilities section via header search")
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'abilities-section-fallback'
                    for element in content:
                        wrapper.append(element.extract())
                    return wrapper
        
        # Fallback 2: Look for divs/sections with ability-related classes or content
        def has_ability_classes(class_list):
            if not class_list:
                return False
            return any(term in ' '.join(class_list).lower() for term in ['ability', 'skill'])
        
        ability_divs = soup.find_all('div', class_=has_ability_classes)
        
        if ability_divs:
            for div in ability_divs:
                if isinstance(div, Tag):
                    self.logger.debug("Found abilities section via class-based search")
                    return div
        
        self.logger.warning("Could not find abilities section")
        return None
    
    def _find_overview_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the champion overview/summary section.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing overview, or None if not found
        """
        self.logger.debug("Looking for overview section")
        
        # Look for champion description/overview paragraphs near the top
        # Usually the first few paragraphs after the infobox
        main_content = soup.find('div', {'id': 'mw-content-text'})
        if main_content and isinstance(main_content, Tag):
            # Find first substantial paragraph
            paragraphs = main_content.find_all('p')
            for p in paragraphs:
                if isinstance(p, Tag):
                    text = p.get_text().strip()
                    if len(text) > 50:  # Substantial content
                        self.logger.debug("Found overview section via first substantial paragraph")
                        return p
        
        # Fallback: look for any div with summary/description content
        def has_summary_classes(class_list):
            if not class_list:
                return False
            return any(term in ' '.join(class_list).lower() for term in ['summary', 'description', 'overview'])
        
        summary_divs = soup.find_all('div', class_=has_summary_classes)
        
        if summary_divs:
            for div in summary_divs:
                if isinstance(div, Tag):
                    self.logger.debug("Found overview section via class-based search")
                    return div
        
        self.logger.debug("No specific overview section found")
        return None
    
    def _validate_page_structure(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """
        Validate that expected sections exist and contain meaningful data.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary mapping section names to validation results
        """
        self.logger.debug("Validating page structure")
        
        sections = self.find_champion_data_sections(soup)
        validation = {}
        
        # Validate stats section
        stats = sections.get('stats')
        if stats:
            stats_text = stats.get_text().lower()
            has_hp = 'hp' in stats_text or 'health' in stats_text
            has_stats = any(stat in stats_text for stat in ['ad', 'armor', 'attack', 'damage'])
            validation['stats'] = has_hp and has_stats
        else:
            validation['stats'] = False
        
        # Validate abilities section
        abilities = sections.get('abilities')
        if abilities:
            abilities_text = abilities.get_text().lower()
            has_abilities = any(term in abilities_text for term in [
                'passive', 'cooldown', 'damage', 'ability', 'skill'
            ])
            validation['abilities'] = has_abilities
        else:
            validation['abilities'] = False
        
        # Validate overview section
        overview = sections.get('overview')
        if overview:
            overview_text = overview.get_text().strip()
            validation['overview'] = len(overview_text) > 30  # Has substantial content
        else:
            validation['overview'] = False
        
        # Overall page validation
        validation['page_valid'] = any(validation.values())
        
        self.logger.info(f"Page validation results: {validation}")
        return validation


# Example usage and testing functions
async def test_wiki_scraper():
    """Test function to verify WikiScraper functionality"""
    async with WikiScraper() as scraper:
        # Test connection
        if not await scraper.test_connection():
            print("❌ Connection test failed")
            return
        
        print("✅ Connection test successful")
        
        # Test fetching Taric's page
        try:
            soup = await scraper.fetch_champion_page("Taric")
            title_elem = soup.find('title')
            title = title_elem.get_text() if title_elem is not None else "No title"
            print(f"✅ Successfully fetched Taric's page: {title}")
        except Exception as e:
            print(f"❌ Failed to fetch Taric's page: {e}")


if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_wiki_scraper()) 