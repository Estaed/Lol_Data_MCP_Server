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
from bs4 import BeautifulSoup


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