"""
League of Legends Wiki Scraper

A comprehensive web scraper for extracting champion data from the League of Legends Wiki.
Implements rate limiting, error handling, and proper HTTP client configuration.
"""

import asyncio
import json
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup, Tag


class WikiScraperError(Exception):
    """Base exception for wiki scraper errors"""
    pass


class ChampionNotFoundError(WikiScraperError):
    """Raised when a champion page cannot be found"""
    pass


@dataclass
class ScrapingMetrics:
    """Performance metrics for scraping operations"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    parsing_successes: int = 0
    parsing_failures: int = 0
    total_request_time: float = 0.0
    avg_request_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class CacheManager:
    """Manages file-based caching for scraped pages"""
    
    def __init__(self, cache_dir: str = "cache/wiki_pages", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.logger = logging.getLogger(__name__)
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Cache directory ensured: {self.cache_dir}")
        except OSError as e:
            self.logger.error(f"Failed to create cache directory: {e}")
            
    def _get_cache_key(self, champion_name: str) -> str:
        """Generate cache key for champion"""
        return hashlib.md5(champion_name.lower().encode()).hexdigest()
        
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load cache metadata: {e}")
                return {}
        return {}
        
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
        except IOError as e:
            self.logger.warning(f"Failed to save cache metadata: {e}")
            
    def is_cache_valid(self, champion_name: str) -> bool:
        """Check if cached data is still valid"""
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        if not cache_file.exists():
            return False
            
        metadata = self._load_metadata()
        if cache_key not in metadata:
            return False
            
        try:
            cached_time = datetime.fromisoformat(metadata[cache_key]['timestamp'])
            is_valid = datetime.now() - cached_time < self.ttl
            self.logger.debug(f"Cache validity check for {champion_name}: {is_valid}")
            return is_valid
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Invalid cache metadata for {champion_name}: {e}")
            return False
        
    def get_cached_content(self, champion_name: str) -> Optional[str]:
        """Get cached HTML content if valid"""
        if not self.is_cache_valid(champion_name):
            return None
            
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.logger.debug(f"Retrieved cached content for {champion_name} ({len(content)} chars)")
                return content
        except IOError as e:
            self.logger.warning(f"Failed to read cached content for {champion_name}: {e}")
            return None
            
    def cache_content(self, champion_name: str, content: str) -> None:
        """Cache HTML content"""
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
            metadata = self._load_metadata()
            metadata[cache_key] = {
                'champion_name': champion_name,
                'timestamp': datetime.now().isoformat(),
                'file_size': len(content)
            }
            self._save_metadata(metadata)
            self.logger.info(f"Cached content for {champion_name} ({len(content)} chars)")
        except IOError as e:
            self.logger.warning(f"Failed to cache content for {champion_name}: {e}")
            
    def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        metadata = self._load_metadata()
        removed_count = 0
        
        for cache_key, data in list(metadata.items()):
            try:
                cached_time = datetime.fromisoformat(data['timestamp'])
                if datetime.now() - cached_time >= self.ttl:
                    cache_file = self.cache_dir / f"{cache_key}.html"
                    try:
                        cache_file.unlink(missing_ok=True)
                        del metadata[cache_key]
                        removed_count += 1
                        self.logger.debug(f"Removed expired cache entry: {cache_key}")
                    except IOError as e:
                        self.logger.warning(f"Failed to remove cache file {cache_key}: {e}")
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Invalid cache entry {cache_key}: {e}")
                
        if removed_count > 0:
            self._save_metadata(metadata)
            self.logger.info(f"Cleaned up {removed_count} expired cache entries")
            
        return removed_count


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
        retry_delay: float = 2.0,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize the WikiScraper.
        
        Args:
            rate_limit_delay: Delay between requests in seconds (default: 1.0)
            timeout: HTTP request timeout in seconds (default: 30.0)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 2.0)
            enable_cache: Enable file-based caching (default: True)
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0.0
        
        # Configure caching and metrics
        self.enable_cache = enable_cache
        self.cache_manager = CacheManager(ttl_hours=cache_ttl_hours) if enable_cache else None
        self.metrics = ScrapingMetrics()
        
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
    
    async def __aenter__(self) -> 'WikiScraper':
        """Async context manager entry"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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
    
    def _update_metrics(self, start_time: float, success: bool, cache_hit: bool = False, error: Optional[str] = None) -> None:
        """Update performance metrics"""
        request_time = time.time() - start_time
        self.metrics.total_requests += 1
        self.metrics.total_request_time += request_time
        self.metrics.avg_request_time = self.metrics.total_request_time / self.metrics.total_requests
        
        if success:
            self.metrics.parsing_successes += 1
        else:
            self.metrics.parsing_failures += 1
            if error:
                error_entry = f"{datetime.now().isoformat()}: {error}"
                self.metrics.errors.append(error_entry)
                
        self.logger.debug(f"Updated metrics: requests={self.metrics.total_requests}, "
                         f"successes={self.metrics.parsing_successes}, "
                         f"cache_hits={self.metrics.cache_hits}, "
                         f"avg_time={self.metrics.avg_request_time:.3f}s")
    
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
        # Replace spaces with underscores for wiki URLs, let quote() handle other characters
        formatted_name = champion_name.replace(" ", "_")
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
        Fetch and parse a champion's wiki page with caching support.
        
        Args:
            champion_name: Name of the champion (e.g., "Taric")
            
        Returns:
            BeautifulSoup object containing the parsed HTML
            
        Raises:
            ChampionNotFoundError: If champion page doesn't exist
            WikiScraperError: If page cannot be fetched
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Fetching champion page for: {champion_name}")
            
            # Check cache first
            if self.enable_cache and self.cache_manager:
                cached_content = self.cache_manager.get_cached_content(champion_name)
                if cached_content:
                    self.metrics.cache_hits += 1
                    self.logger.info(f"Cache hit for champion: {champion_name}")
                    soup = BeautifulSoup(cached_content, 'html.parser')
                    self._update_metrics(start_time, success=True, cache_hit=True)
                    return soup
                else:
                    self.metrics.cache_misses += 1
                    self.logger.debug(f"Cache miss for champion: {champion_name}")
            
            # Fetch from web
            url = self._build_champion_url(champion_name)
            response = await self._make_request(url)
            content = response.text
            
            # Cache the content
            if self.enable_cache and self.cache_manager:
                self.cache_manager.cache_content(champion_name, content)
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Basic validation that we got a champion page
            title = soup.find('title')
            if title is not None:
                title_text = title.get_text()
                if 'League of Legends Wiki' not in title_text:
                    self.logger.warning(f"Unusual page title: {title_text}")
            
            self.logger.info(f"Successfully parsed champion page for {champion_name}")
            self._update_metrics(start_time, success=True, cache_hit=False)
            
            return soup
            
        except Exception as e:
            self._update_metrics(start_time, success=False, error=str(e))
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
        def has_stats_classes(class_list: Any) -> bool:
            """Check if element has champion stats related classes"""
            if not class_list:
                return False
            
            stats_indicators = [
                'infobox', 'champion-stats', 'stats', 'champion-info', 
                'character-info', 'data-box'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in stats_indicators)
        
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
        def contains_ability(text: str) -> bool:
            """Check if text contains ability-related keywords"""
            if not text:
                return False
            
            text_lower = text.lower()
            ability_keywords = [
                'abilities', 'skills', 'spells', 'passive', 'active',
                'cooldown', 'mana cost', 'damage', 'cast', 'ability'
            ]
            
            return any(keyword in text_lower for keyword in ability_keywords)
        
        # Look for specific "Abilities" heading
        abilities_spans = soup.find_all('span', class_='mw-headline')
        abilities_span = None
        
        for span in abilities_spans:
            if isinstance(span, Tag) and span.string:
                if 'abilities' in span.string.lower():
                    abilities_span = span
                    break
                # Also look for individual ability headings (like "Bravado", "Starlight's Touch", etc.)
                elif any(word in span.string.lower() for word in ['passive', 'bravado', 'starlight', 'bastion', 'dazzle', 'cosmic']):
                    # Found an ability heading, look for a parent section containing all abilities
                    heading = span.find_parent(['h1', 'h2', 'h3', 'h4'])
                    if heading and isinstance(heading, Tag):
                        parent_section = heading.find_parent(['div', 'section'])
                        if parent_section and isinstance(parent_section, Tag):
                            self.logger.debug("Found abilities section via individual ability heading")
                            return parent_section
        
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
                    # Create a wrapper div containing all abilities content (copy, don't extract)
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'abilities-section'
                    for element in section_content:
                        # Use copy instead of extract to avoid modifying original soup
                        element_copy = element.__copy__()
                        wrapper.append(element_copy)
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
                        # Use copy instead of extract to avoid modifying original soup
                        element_copy = element.__copy__()
                        wrapper.append(element_copy)
                    return wrapper
        
        # Fallback 2: Look for divs/sections with ability-related classes or content
        def has_ability_classes(class_list) -> bool:
            """Check if element has ability-related classes"""
            if not class_list:
                return False
            
            ability_indicators = [
                'ability', 'skill', 'spell', 'abilities', 'champion-abilities'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in ability_indicators)
        
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
        def has_summary_classes(class_list) -> bool:
            """Check if element has summary/overview related classes"""
            if not class_list:
                return False
            
            summary_indicators = [
                'summary', 'overview', 'description', 'champion-description',
                'intro', 'character-summary'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in summary_indicators)
        
        summary_divs = soup.find_all('div', class_=has_summary_classes)
        
        if summary_divs:
            for div in summary_divs:
                if isinstance(div, Tag):
                    self.logger.debug("Found overview section via class-based search")
                    return div
        
        self.logger.debug("No specific overview section found")
        return None
    
    def parse_champion_stats(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse champion statistics from the stats section of a champion page.
        
        Extracts base stats and per-level growth for:
        - HP (Health Points)
        - MP (Mana Points) 
        - AD (Attack Damage)
        - AS (Attack Speed)
        - AR (Armor)
        - MR (Magic Resistance)
        - MS (Movement Speed)
        - Range (Attack Range)
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary containing structured champion stats:
            {
                "hp": {"base": 645.0, "growth": 99.0},
                "mp": {"base": 300.0, "growth": 60.0},
                "ad": {"base": 55.0, "growth": 3.5},
                ...
            }
            
        Raises:
            WikiScraperError: If stats section cannot be found or parsed
        """
        self.logger.info("Parsing champion statistics")
        
        # Find the stats section
        stats_section = self._find_stats_section(soup)
        if not stats_section:
            raise WikiScraperError("Could not find stats section for parsing")
        
        # Extract all text content from the stats section
        stats_text = stats_section.get_text()
        self.logger.debug(f"Stats section text: {stats_text[:200]}...")
        
        # Initialize stats dictionary
        parsed_stats = {}
        
        # Define stat patterns and their variations
        stat_patterns = {
            'hp': ['hp', 'health', 'health points'],
            'mp': ['mp', 'mana', 'mana points'],
            'ad': ['ad', 'attack damage', 'attack dmg', 'damage'],
            'armor': ['ar', 'armor', 'armour'],
            'mr': ['mr', 'magic resistance', 'magic resist', 'magic res'],
            'attack_speed': ['as', 'attack speed', 'attackspeed'],
            'movement_speed': ['ms', 'movement speed', 'movespeed', 'move speed'],
            'range': ['range', 'attack range', 'atk range']
        }
        
        # Parse each stat type
        for stat_key, stat_names in stat_patterns.items():
            stat_data = self._extract_stat_value(stats_text, stat_names)
            if stat_data:
                parsed_stats[stat_key] = stat_data
                self.logger.debug(f"Parsed {stat_key}: {stat_data}")
        
        # Validate parsed data
        validated_stats = self._validate_stat_data(parsed_stats)
        
        self.logger.info(f"Successfully parsed {len(validated_stats)} champion stats")
        return validated_stats

    def _extract_stat_value(self, text: str, stat_names: list) -> Optional[Dict[str, Any]]:
        """
        Extract stat formula from text using the new StatFormulaParser.
        
        Handles complex formats like:
        - "605 (+ 88 × M²)" (quadratic growth - Soraka style)
        - "645 (+ 99 × M)" (linear growth)
        - "175%" (percentage values) 
        - "550" (simple values)
        - "HP: 645 (+99)" (legacy format)
        
        Args:
            text: Text content to search
            stat_names: List of possible names for this stat
            
        Returns:
            Dictionary with 'formula', 'base', and optionally 'growth'/'growth_quadratic' values,
            or None if not found
        """
        from src.utils.stat_calculator import StatFormulaParser
        
        parser = StatFormulaParser()
        formula = parser.parse_formula(text, stat_names)
        
        if not formula:
            return None
        
        # Return both the formula and legacy format for backwards compatibility
        result = {
            "formula": formula,
            "base": formula.base_value
        }
        
        # Add growth for linear formulas to maintain compatibility
        if formula.growth_type == "linear":
            result["growth"] = formula.growth_coefficient
        elif formula.growth_type == "quadratic":
            # For quadratic, we'll store the coefficient but note it's quadratic
            result["growth_quadratic"] = formula.growth_coefficient
        
        # Add percentage flag if applicable
        if formula.is_percentage:
            result["is_percentage"] = True
        
        self.logger.debug(f"Extracted formula for {stat_names[0]}: {formula}")
        return result

    def _normalize_stat_name(self, name: str) -> str:
        """
        Normalize stat names to standard format.
        
        Args:
            name: Raw stat name from wiki
            
        Returns:
            Normalized stat name
        """
        name_lower = name.lower().strip()
        
        # Normalization mapping
        normalizations = {
            'health': 'hp',
            'health points': 'hp',
            'mana': 'mp', 
            'mana points': 'mp',
            'attack damage': 'ad',
            'attack dmg': 'ad',
            'damage': 'ad',
            'armour': 'armor',
            'ar': 'armor',
            'magic resistance': 'mr',
            'magic resist': 'mr', 
            'magic res': 'mr',
            'attack speed': 'attack_speed',
            'attackspeed': 'attack_speed',
            'as': 'attack_speed',
            'movement speed': 'movement_speed',
            'movespeed': 'movement_speed',
            'move speed': 'movement_speed',
            'ms': 'movement_speed',
            'attack range': 'range',
            'atk range': 'range'
        }
        
        return normalizations.get(name_lower, name_lower)

    def _validate_stat_data(self, stats: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """
        Validate parsed stat data and log warnings for outliers.
        
        Args:
            stats: Dictionary of parsed champion stats
            
        Returns:
            Validated stats dictionary (same as input, with logging)
        """
        # Define expected ranges for champion stats
        stat_ranges = {
            'hp': {'min_base': 300, 'max_base': 800, 'min_growth': 50, 'max_growth': 150},
            'mp': {'min_base': 0, 'max_base': 500, 'min_growth': 0, 'max_growth': 100},
            'ad': {'min_base': 40, 'max_base': 80, 'min_growth': 2, 'max_growth': 6},
            'armor': {'min_base': 20, 'max_base': 60, 'min_growth': 2, 'max_growth': 8},
            'mr': {'min_base': 25, 'max_base': 45, 'min_growth': 0, 'max_growth': 3},
            'attack_speed': {'min_base': 0.5, 'max_base': 1.0, 'min_growth': 1, 'max_growth': 5},
            'movement_speed': {'min_base': 300, 'max_base': 400},  # No growth typically
            'range': {'min_base': 125, 'max_base': 650}  # No growth typically
        }
        
        for stat_name, stat_data in stats.items():
            if stat_name in stat_ranges:
                ranges = stat_ranges[stat_name]
                
                # Check base value
                if 'base' in stat_data and isinstance(ranges, dict) and 'min_base' in ranges and 'max_base' in ranges:
                    base_val = stat_data['base']
                    if base_val < ranges['min_base'] or base_val > ranges['max_base']:
                        self.logger.warning(
                            f"{stat_name} base value {base_val} outside expected range "
                            f"[{ranges['min_base']}-{ranges['max_base']}]"
                        )
                
                # Check growth value (if applicable)
                if 'growth' in stat_data and isinstance(ranges, dict) and 'min_growth' in ranges and 'max_growth' in ranges:
                    growth_val = stat_data['growth']
                    if growth_val < ranges['min_growth'] or growth_val > ranges['max_growth']:
                        self.logger.warning(
                            f"{stat_name} growth value {growth_val} outside expected range "
                            f"[{ranges['min_growth']}-{ranges['max_growth']}]"
                        )
        
        return stats

    def parse_champion_abilities(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse champion abilities from the abilities section of a champion page.
        
        Extracts detailed ability information for Passive, Q, W, E, R abilities including:
        - Ability names and descriptions
        - Cooldowns, mana costs, and ranges
        - Damage values and scaling information
        - Special effects and mechanics
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary containing structured ability data:
            {
                "passive": {
                    "name": "Ability Name",
                    "description": "What the ability does...",
                    "cooldown": None,  # Passives typically don't have cooldowns
                    "cost": None,
                    "range": None,
                    "damage": "25-199 (+0.15 Bonus AD)",
                    "effects": ["Effect 1", "Effect 2"]
                },
                "Q": {
                    "name": "Q Ability Name",
                    "description": "Q ability description...",
                    "cooldown": "14/13/12/11/10",
                    "cost": "60/70/80/90/100",
                    "range": "750",
                    "damage": "80/120/160/200/240 (+0.4 AP)",
                    "effects": ["Channel ability", "Heals allies"]
                },
                # ... W, E, R similar structure
            }
            
        Raises:
            WikiScraperError: If abilities section cannot be found or parsed
        """
        self.logger.info("Parsing champion abilities")
        
        # Find the abilities section using existing method
        abilities_section = self._find_abilities_section(soup)
        if not abilities_section:
            raise WikiScraperError("Could not find abilities section for parsing")
        
        # Initialize abilities dictionary
        abilities = {}
        
        # Define ability types to look for
        ability_types = ['passive', 'Q', 'W', 'E', 'R']
        
        # Parse each ability type
        for ability_type in ability_types:
            ability_data = self._extract_single_ability(abilities_section, ability_type)
            if ability_data:
                abilities[ability_type] = ability_data
                self.logger.debug(f"Parsed {ability_type}: {ability_data.get('name', 'Unknown')}")
            else:
                self.logger.warning(f"Could not parse {ability_type} ability")
        
        # Validate the parsed abilities data
        validated_abilities = self._validate_ability_data(abilities)
        
        self.logger.info(f"Successfully parsed {len(validated_abilities)} abilities")
        return {
            "abilities": validated_abilities,
            "total_found": len(validated_abilities),
            "parsing_successful": True
        }

    def _extract_single_ability(self, abilities_section: Tag, ability_type: str) -> Optional[Dict[str, Any]]:
        """
        Extract data for a single ability from the abilities section.
        
        Args:
            abilities_section: BeautifulSoup element containing abilities
            ability_type: Type of ability ('passive', 'Q', 'W', 'E', 'R')
            
        Returns:
            Dictionary with ability data or None if not found
        """
        self.logger.debug(f"Extracting {ability_type} ability data")
        
        # Initialize ability data structure
        ability_data: Dict[str, Any] = {
            "name": None,
            "description": None,
            "cooldown": None,
            "cost": None,
            "range": None,
            "damage": None,
            "healing": None,
            "effects": []
        }
        
        # Map ability types to CSS class patterns used in real wiki
        ability_class_map = {
            'passive': 'skill_innate',
            'q': 'skill_q', 
            'w': 'skill_w',
            'e': 'skill_e',
            'r': 'skill_r'
        }
        
        # Strategy 1: Look for skill containers with specific CSS classes
        ability_type_lower = ability_type.lower()
        skill_class = ability_class_map.get(ability_type_lower)
        
        skill_container = None
        if skill_class:
            # Look for div with specific skill class (e.g., "skill_q", "skill_w")
            skill_container = abilities_section.find('div', class_=skill_class)
            
        # Strategy 2: If specific class not found, look for skill containers with ability indicators
        if not skill_container:
            skill_containers = abilities_section.find_all('div', class_='skill')
            for container in skill_containers:
                if isinstance(container, Tag):
                    # Check if container contains indicators for this ability type
                    container_text = container.get_text().lower()
                    
                    # Define ability indicators
                    indicators = {
                        'passive': ['passive', 'innate'],
                        'q': ['q ', 'q:', 'q-', 'first ability'],
                        'w': ['w ', 'w:', 'w-', 'second ability'],
                        'e': ['e ', 'e:', 'e-', 'third ability'],
                        'r': ['r ', 'r:', 'r-', 'ultimate', 'ult ']
                    }
                    
                    ability_indicators = indicators.get(ability_type_lower, [ability_type_lower])
                    for indicator in ability_indicators:
                        if indicator in container_text:
                            skill_container = container
                            break
                    
                    if skill_container:
                        break
        
        if not skill_container:
            self.logger.warning(f"Could not find {ability_type} skill container")
            return None
        
        # Extract ability name from the skill container
        if isinstance(skill_container, Tag):
            ability_data["name"] = self._extract_ability_name_from_container(skill_container, ability_type)
            
            # Extract description from ability-json section
            ability_data["description"] = self._extract_ability_description_from_container(skill_container)
            
            # Parse numerical values from the container content
            container_text = skill_container.get_text()
            values = self._parse_ability_values(container_text)
            ability_data.update(values)
            
            # Extract effects list
            ability_data["effects"] = self._extract_ability_effects(container_text)
            
            self.logger.debug(f"Extracted {ability_type} ability: {ability_data['name']}")
        else:
            self.logger.warning(f"skill_container is not a Tag for {ability_type}")
            return None
        
        return ability_data

    def _extract_ability_name(self, ability_elements: list, ability_type: str) -> Optional[str]:
        """Extract the ability name from ability elements."""
        # Look for bold text, headings, or structured name patterns
        for element in ability_elements:
            if isinstance(element, Tag):
                # Check for heading text first (most common case)
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    name = element.get_text().strip()
                    # Handle patterns like "Passive - Bravado" or "Q - Starlight's Touch"
                    if " - " in name:
                        parts = name.split(" - ", 1)
                        if len(parts) == 2:
                            ability_name = parts[1].strip()
                            if len(ability_name) > 1:
                                return ability_name
                    # Handle patterns like "Passive: Bravado" 
                    elif ":" in name:
                        parts = name.split(":", 1)
                        if len(parts) == 2:
                            ability_name = parts[1].strip()
                            if len(ability_name) > 1:
                                return ability_name
                    # If no separator, remove ability type prefix
                    for prefix in [f"{ability_type}:", f"{ability_type} -", f"{ability_type}"]:
                        if name.lower().startswith(prefix.lower()):
                            ability_name = name[len(prefix):].strip()
                            if len(ability_name) > 1:
                                return ability_name
                    # If nothing else works and it's not just the ability type
                    if len(name) > 3 and name.lower() != ability_type.lower():
                        return name
                
                # Check for bold/strong tags
                bold_elements = element.find_all(['b', 'strong'])
                for bold in bold_elements:
                    if isinstance(bold, Tag):
                        name = bold.get_text().strip()
                        if len(name) > 3 and not name.lower().startswith(ability_type.lower()):
                            return name
        
        return None

    def _clean_ability_description(self, text: str) -> Optional[str]:
        """Clean and extract the main description from ability text."""
        # Remove common prefixes and suffixes
        text = re.sub(r'^(passive|q|w|e|r)[\s\-:]+', '', text, flags=re.IGNORECASE)
        
        # Take the first substantial sentence/paragraph as description
        sentences = text.split('.')
        description = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and not re.search(r'\d+/\d+', sentence):  # Avoid stat lines
                description = sentence + "."
                break
        
        if not description and len(text) > 50:
            # Fallback: take first 200 characters
            description = text[:200].strip() + "..."
        
        return description.strip() if description else None

    def _parse_ability_values(self, text: str) -> Dict[str, Optional[str]]:
        """Parse cooldown, cost, range, and damage values from ability text."""
        values: Dict[str, Optional[str]] = {
            "cooldown": None,
            "cost": None,
            "range": None,
            "damage": None,
            "healing": None
        }
        
        # Cooldown patterns: "Cooldown: 14/13/12/11/10" or "CD: 8/7/6"
        cooldown_match = re.search(r'cooldown[:\s]+(\d+(?:/\d+)*)', text, re.IGNORECASE)
        if cooldown_match:
            values["cooldown"] = cooldown_match.group(1)
        
        # Cost patterns: "Mana Cost: 60/70/80" or "Cost: 50 mana"
        cost_match = re.search(r'(?:mana\s+)?cost[:\s]+(\d+(?:/\d+)*)', text, re.IGNORECASE)
        if cost_match:
            values["cost"] = cost_match.group(1)
        
        # Range patterns: "Range: 750" or "Cast Range: 600"
        range_match = re.search(r'(?:cast\s+)?range[:\s]+(\d+)', text, re.IGNORECASE)
        if range_match:
            values["range"] = range_match.group(1)
        
        # Damage patterns: "80/120/160/200/240 (+0.4 AP)" or "Damage: 100-300"
        damage_match = re.search(r'damage[:\s]*(\d+(?:[/-]\d+)*(?:\s*\([^)]+\))?)', text, re.IGNORECASE)
        if damage_match:
            values["damage"] = damage_match.group(1)
        
        # Healing patterns: similar to damage but for heals
        healing_match = re.search(r'heal(?:ing)?.*?(\d+(?:/\d+)*(?:\s*\([^)]+\))?)', text, re.IGNORECASE)
        if healing_match:
            values["healing"] = healing_match.group(1)
        
        return values

    def _extract_ability_name_from_container(self, skill_container: Tag, ability_type: str) -> Optional[str]:
        """Extract ability name from skill container using CSS selectors."""
        # Strategy 1: Look for ability name in specific CSS class
        name_element = skill_container.find('div', class_='ability-info-stats__ability')
        if name_element:
            name = name_element.get_text().strip()
            if name and len(name) > 1:
                return name
        
        # Strategy 2: Look for name in ability-json data
        json_element = skill_container.find('div', class_='ability-json')
        if json_element:
            try:
                import json
                json_data = json.loads(json_element.get_text())
                if 'name' in json_data:
                    return json_data['name']
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Strategy 3: Look for headings within the container
        headings = skill_container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            if isinstance(heading, Tag):
                name = heading.get_text().strip()
                # Handle patterns like "Passive - Bravado" or "Q - Starlight's Touch"
                if " - " in name:
                    parts = name.split(" - ", 1)
                    if len(parts) == 2:
                        ability_name = parts[1].strip()
                        if len(ability_name) > 1:
                            return ability_name
                # Handle patterns like "Passive: Bravado" 
                elif ":" in name:
                    parts = name.split(":", 1)
                    if len(parts) == 2:
                        ability_name = parts[1].strip()
                        if len(ability_name) > 1:
                            return ability_name
        
        # Strategy 4: Look for bold text that could be the name
        bold_elements = skill_container.find_all(['b', 'strong'])
        for bold in bold_elements:
            if isinstance(bold, Tag):
                name = bold.get_text().strip()
                if len(name) > 3 and not name.lower().startswith(ability_type.lower()):
                    return name
        
        return None
    
    def _extract_ability_description_from_container(self, skill_container: Tag) -> Optional[str]:
        """Extract ability description from skill container."""
        # Strategy 1: Look for description in ability-json
        json_element = skill_container.find('div', class_='ability-json')
        if json_element:
            try:
                import json
                json_data = json.loads(json_element.get_text())
                if 'description' in json_data:
                    return json_data['description']
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Strategy 2: Look for description in specific CSS classes
        desc_classes = ['ability-description', 'ability-text', 'skill-description']
        for class_name in desc_classes:
            desc_element = skill_container.find('div', class_=class_name)
            if desc_element:
                desc = desc_element.get_text().strip()
                if desc and len(desc) > 20:
                    return desc
        
        # Strategy 3: Extract first substantial paragraph from container
        paragraphs = skill_container.find_all('p')
        for p in paragraphs:
            if isinstance(p, Tag):
                text = p.get_text().strip()
                if len(text) > 30 and not re.search(r'\d+/\d+', text):  # Avoid stat lines
                    return text
        
        # Strategy 4: Fallback to container text with cleaning
        container_text = skill_container.get_text()
        return self._clean_ability_description(container_text)

    def _extract_ability_effects(self, text: str) -> List[str]:
        """Extract list of ability effects from description text."""
        effects: List[str] = []
        
        # Look for common effect keywords
        effect_patterns = [
            r'channel(?:ing|s)?',
            r'stun(?:s)?',
            r'slow(?:s)?',
            r'heal(?:s|ing)?',
            r'shield(?:s)?',
            r'dash(?:es)?',
            r'teleport(?:s)?',
            r'stealth',
            r'invisib(?:le|ility)',
            r'knockup',
            r'knockback',
            r'silence(?:s)?',
            r'root(?:s)?',
            r'reduce(?:s)?\s+cooldown',
            r'increase(?:s)?\s+(?:attack\s+speed|movement\s+speed|damage)',
        ]
        
        for pattern in effect_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Extract the context around the effect
                match = re.search(f'.{{0,20}}{pattern}.{{0,30}}', text, re.IGNORECASE)
                if match:
                    effect_text = match.group(0).strip()
                    if effect_text not in effects:
                        effects.append(effect_text)
        
        return effects[:5]  # Limit to 5 most relevant effects

    def _validate_ability_data(self, abilities: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Validate and clean up parsed ability data."""
        validated = {}
        
        for ability_type, ability_data in abilities.items():
            if ability_data and isinstance(ability_data, dict):
                # Ensure all required fields exist
                validated_ability = {
                    "name": ability_data.get("name"),
                    "description": ability_data.get("description"),
                    "cooldown": ability_data.get("cooldown"),
                    "cost": ability_data.get("cost"),
                    "range": ability_data.get("range"),
                    "damage": ability_data.get("damage"),
                    "healing": ability_data.get("healing"),
                    "effects": ability_data.get("effects", [])
                }
                
                # Validate that we have at least a name or description
                if validated_ability["name"] or validated_ability["description"]:
                    validated[ability_type] = validated_ability
                    self.logger.debug(f"Validated {ability_type}: {validated_ability['name']}")
                else:
                    self.logger.warning(f"Skipping {ability_type}: insufficient data")
        
        return validated

    def _validate_page_structure(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """
        Validate the structure and content of a champion page
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary with validation results for different sections
        """
        validation_results = {}
        
        # Check for stats content (infoboxes, stat tables)
        stats_indicators = soup.find_all(['div', 'table'], class_=re.compile(r'infobox|stats?|champion'))
        has_stat_text = any(
            keyword in soup.get_text().lower() 
            for keyword in ['health', 'mana', 'armor', 'attack damage', 'magic resist']
        )
        validation_results['stats'] = len(stats_indicators) > 0 or has_stat_text
        
        # Check for abilities content
        ability_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'abilit|passive|spell', re.IGNORECASE))
        has_ability_text = any(
            keyword in soup.get_text().lower()
            for keyword in ['passive', 'cooldown', 'ability', 'mana cost']
        )
        validation_results['abilities'] = len(ability_headers) > 0 or has_ability_text
        
        # Check for overview/description content
        # Look for content divs and substantial text paragraphs
        content_divs = soup.find_all(['div', 'p'], id=re.compile(r'content|text'))
        long_paragraphs = soup.find_all('p')
        has_substantial_content = any(
            len(p.get_text().strip()) > 50 for p in long_paragraphs
        )
        validation_results['overview'] = len(content_divs) > 0 or has_substantial_content
        
        # Determine overall page validity
        # A page is valid if it has at least 2 of the 3 sections
        valid_sections = sum(validation_results.values())
        validation_results['page_valid'] = valid_sections >= 2
        
        # Log missing sections for debugging
        missing_sections = [section for section, valid in validation_results.items() 
                          if not valid and section != 'page_valid']
        if missing_sections:
            self.logger.warning(f"Missing sections: {missing_sections}")
        
        return validation_results

    def parse_champion_stats_safe(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced stats parsing with graceful degradation"""
        try:
            result = self.parse_champion_stats(soup)
            self.metrics.parsing_successes += 1
            self.logger.debug("Stats parsing successful")
            return result
        except Exception as e:
            self.logger.warning(f"Stats parsing failed: {e}")
            self.metrics.parsing_failures += 1
            error_entry = f"{datetime.now().isoformat()}: Stats parsing failed: {e}"
            self.metrics.errors.append(error_entry)
            return {
                "error": "Failed to parse stats",
                "partial_data": True,
                "stats": {},
                "error_details": str(e)
            }
            
    def parse_champion_abilities_safe(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced abilities parsing with graceful degradation"""  
        try:
            result = self.parse_champion_abilities(soup)
            self.metrics.parsing_successes += 1
            self.logger.debug("Abilities parsing successful")
            return result
        except Exception as e:
            self.logger.warning(f"Abilities parsing failed: {e}")
            self.metrics.parsing_failures += 1
            error_entry = f"{datetime.now().isoformat()}: Abilities parsing failed: {e}"
            self.metrics.errors.append(error_entry)
            return {
                "error": "Failed to parse abilities", 
                "partial_data": True,
                "abilities": {},
                "error_details": str(e)
            }
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return asdict(self.metrics)
        
    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self.metrics = ScrapingMetrics()
        self.logger.info("Performance metrics reset")
        
    async def cleanup_cache(self) -> int:
        """Cleanup expired cache entries"""
        if self.cache_manager:
            return await asyncio.to_thread(self.cache_manager.cleanup_expired)
        return 0
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information and statistics
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.cache_manager:
            return {"status": "disabled"}
            
        try:
            metadata = self.cache_manager._load_metadata()
            total_entries = len(metadata)
            
            # Calculate cache sizes
            total_size = 0
            for entry in metadata.values():
                total_size += entry.get('file_size', 0)
            
            return {
                "status": "enabled",
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "cache_directory": str(self.cache_manager.cache_dir),
            "ttl_hours": self.cache_manager.ttl.total_seconds() / 3600,
                "metrics": asdict(self.metrics)
            }
        except Exception as e:
            self.logger.warning(f"Failed to get cache info: {e}")
            return {"status": "error", "error": str(e)}

    def normalize_champion_name(self, name: str) -> str:
        """
        Enhanced champion name normalization with special character handling
        
        Args:
            name: Champion name to normalize
            
        Returns:
            Normalized champion name
        """
        if not name:
            return ""
        
        # Remove extra whitespace and convert to title case
        normalized = re.sub(r'\s+', ' ', name.strip()).title()
        
        # Handle special cases for champion names
        special_cases = {
            "Kaisa": "Kai'Sa",
            "Kai Sa": "Kai'Sa", 
            "Kha Zix": "Kha'Zix",
            "Khazix": "Kha'Zix",
            "Kogmaw": "Kog'Maw",
            "Kog Maw": "Kog'Maw",
            "Leblanc": "LeBlanc",
            "Le Blanc": "LeBlanc",
            "Dr Mundo": "Dr. Mundo",
            "Dr. Mundo": "Dr. Mundo",
            "Aurelion Sol": "Aurelion Sol",
            "Twisted Fate": "Twisted Fate",
            "Master Yi": "Master Yi",
            "Miss Fortune": "Miss Fortune",
            "Tahm Kench": "Tahm Kench",
            "Xin Zhao": "Xin Zhao",
            "Jarvan Iv": "Jarvan IV",
            "Jarvan 4": "Jarvan IV"
        }
        
        # Check for special cases
        for variant, correct in special_cases.items():
            if normalized.lower() == variant.lower():
                normalized = correct
                break
        
        self.logger.debug(f"Normalized champion name: {name} -> {normalized}")
        return normalized 